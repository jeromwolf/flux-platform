"""RBAC Policy Engine for the Maritime Knowledge Graph.

Implements graph-based access control by traversing the permission graph::

    (:User)-[:HAS_ROLE]->(:Role)-[:CAN_ACCESS]->(:DataClass)

The policy engine queries Neo4j to resolve user roles, check data-class
access, filter query results, and augment Cypher queries with access
control WHERE clauses.

Usage::

    from neo4j import GraphDatabase
    from kg.rbac import RBACPolicy

    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "pw"))
    policy = RBACPolicy(driver, database="neo4j")

    decision = policy.check_access("USER-001", "DC-RESTRICTED")
    if decision.allowed:
        # proceed with data access
        ...
"""

from __future__ import annotations

import logging
import re
from typing import Any

from kg.rbac.models import (
    AccessDecision,
    AccessPermission,
    DataClassification,
    RBACRole,
    RBACUser,
)

logger = logging.getLogger(__name__)


class RBACPolicy:
    """Graph-native RBAC policy engine.

    Resolves access decisions by traversing the Neo4j permission graph.
    All methods use read transactions for safety.

    Args:
        driver: Neo4j driver instance.
        database: Neo4j database name. Defaults to ``"neo4j"``.
    """

    def __init__(self, driver: Any, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    # =====================================================================
    # Core Access Check
    # =====================================================================

    def check_access(
        self,
        user_id: str,
        data_class_id: str,
    ) -> AccessDecision:
        """Check whether a user can access a specific data classification.

        Traverses the graph pattern::

            (:User {userId})-[:HAS_ROLE]->(:Role)-[:CAN_ACCESS]->(:DataClass {classId})

        Args:
            user_id: The user's unique identifier.
            data_class_id: The target data classification identifier.

        Returns:
            AccessDecision with allowed/denied status and reason.
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (u:User {userId: $userId})
                OPTIONAL MATCH (u)-[:HAS_ROLE]->(r:Role)-[:CAN_ACCESS]->(dc:DataClass {classId: $classId})
                OPTIONAL MATCH (target:DataClass {classId: $classId})
                RETURN
                    u.userId AS userId,
                    u.status AS userStatus,
                    target.level AS requiredLevel,
                    target.name AS targetName,
                    collect(DISTINCT r.roleId) AS matchedRoles,
                    collect(DISTINCT r.name) AS matchedRoleNames
                """,
                userId=user_id,
                classId=data_class_id,
            )
            record = result.single()

        # User not found
        if record is None or record["userId"] is None:
            return AccessDecision.deny(
                reason=f"사용자를 찾을 수 없습니다: {user_id}",
                user_id=user_id,
                data_class_id=data_class_id,
            )

        # User is not active
        user_status = record["userStatus"]
        if user_status != "ACTIVE":
            return AccessDecision.deny(
                reason=f"사용자 계정이 비활성 상태입니다 (status={user_status})",
                user_id=user_id,
                data_class_id=data_class_id,
            )

        # Target data class not found
        required_level = record["requiredLevel"]
        if required_level is None:
            return AccessDecision.deny(
                reason=f"데이터 등급을 찾을 수 없습니다: {data_class_id}",
                user_id=user_id,
                data_class_id=data_class_id,
            )

        # Check if any role grants access
        matched_roles: list[str] = record["matchedRoles"]
        matched_role_names: list[str] = record["matchedRoleNames"]

        if matched_roles and matched_roles[0] is not None:
            role_display = ", ".join(
                f"{rid} ({rname})"
                for rid, rname in zip(matched_roles, matched_role_names)
                if rid is not None
            )
            return AccessDecision.allow(
                reason=f"역할 [{role_display}]을 통해 '{record['targetName']}' 데이터에 접근 허용",
                user_id=user_id,
                data_class_id=data_class_id,
                matched_role=matched_roles[0],
                required_level=required_level,
            )

        # No matching role -> denied
        return AccessDecision.deny(
            reason=(
                f"'{record['targetName']}' (Level {required_level}) "
                f"데이터에 접근할 수 있는 역할이 없습니다"
            ),
            user_id=user_id,
            data_class_id=data_class_id,
            required_level=required_level,
        )

    # =====================================================================
    # User Information Retrieval
    # =====================================================================

    def get_user(self, user_id: str) -> RBACUser | None:
        """Load a user with all roles and data-class access from the graph.

        Args:
            user_id: The user's unique identifier.

        Returns:
            Fully populated RBACUser or None if not found.
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (u:User {userId: $userId})
                OPTIONAL MATCH (u)-[:HAS_ROLE]->(r:Role)
                OPTIONAL MATCH (r)-[:CAN_ACCESS]->(dc:DataClass)
                RETURN
                    u {.*} AS user,
                    collect(DISTINCT r {.*}) AS roles,
                    collect(DISTINCT {roleId: r.roleId, dc: dc {.*}}) AS roleDataClasses
                """,
                userId=user_id,
            )
            record = result.single()

        if record is None or record["user"] is None:
            return None

        user = RBACUser.from_neo4j(record["user"])

        # Build role -> data class mapping
        role_dc_map: dict[str, list[DataClassification]] = {}
        for item in record["roleDataClasses"]:
            rid = item.get("roleId")
            dc_data = item.get("dc")
            if rid is not None and dc_data is not None and dc_data.get("classId") is not None:
                if rid not in role_dc_map:
                    role_dc_map[rid] = []
                role_dc_map[rid].append(DataClassification.from_neo4j(dc_data))

        # Build roles
        for role_data in record["roles"]:
            if role_data is not None and role_data.get("roleId") is not None:
                role = RBACRole.from_neo4j(role_data)
                role.accessible_data_classes = role_dc_map.get(role.role_id, [])
                user.roles.append(role)

        return user

    def get_user_permissions(self, user_id: str) -> list[AccessPermission]:
        """Get all permissions granted to a user through their roles.

        Traverses::

            (:User)-[:HAS_ROLE]->(:Role)-[:GRANTS]->(:Permission)

        Args:
            user_id: The user's unique identifier.

        Returns:
            List of AccessPermission objects.
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (u:User {userId: $userId})-[:HAS_ROLE]->(r:Role)-[:GRANTS]->(p:Permission)
                RETURN DISTINCT p {.*} AS permission
                """,
                userId=user_id,
            )
            records = list(result)

        permissions: list[AccessPermission] = []
        for record in records:
            perm_data = record["permission"]
            if perm_data is not None and perm_data.get("permissionId") is not None:
                permissions.append(AccessPermission.from_neo4j(perm_data))

        return permissions

    def get_accessible_data_classes(self, user_id: str) -> list[DataClassification]:
        """Get all data classifications accessible to a user.

        Traverses::

            (:User)-[:HAS_ROLE]->(:Role)-[:CAN_ACCESS]->(:DataClass)

        Args:
            user_id: The user's unique identifier.

        Returns:
            List of DataClassification objects, sorted by level ascending.
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (u:User {userId: $userId})-[:HAS_ROLE]->(r:Role)-[:CAN_ACCESS]->(dc:DataClass)
                RETURN DISTINCT dc {.*} AS dataClass
                ORDER BY dc.level ASC
                """,
                userId=user_id,
            )
            records = list(result)

        data_classes: list[DataClassification] = []
        for record in records:
            dc_data = record["dataClass"]
            if dc_data is not None and dc_data.get("classId") is not None:
                data_classes.append(DataClassification.from_neo4j(dc_data))

        return data_classes

    # =====================================================================
    # Query Result Filtering
    # =====================================================================

    def filter_query_results(
        self,
        user_id: str,
        results: list[dict[str, Any]],
        data_class_key: str = "dataClassLevel",
    ) -> list[dict[str, Any]]:
        """Filter query results based on the user's access level.

        Each result record is expected to contain a numeric data classification
        level at the specified key. Records with a level exceeding the user's
        maximum accessible level are removed.

        Args:
            user_id: The user's unique identifier.
            results: List of result dictionaries from a Cypher query.
            data_class_key: Key in each result dict holding the data
                classification level. Defaults to ``"dataClassLevel"``.

        Returns:
            Filtered list containing only accessible results.
        """
        if not results:
            return results

        accessible = self.get_accessible_data_classes(user_id)
        if not accessible:
            logger.warning(
                "User %s has no accessible data classes; filtering all results",
                user_id,
            )
            return []

        max_level = max(dc.level for dc in accessible)

        filtered: list[dict[str, Any]] = []
        for record in results:
            record_level = record.get(data_class_key)
            if record_level is None:
                # 데이터 등급 정보가 없는 결과는 공개(Level 1)로 간주
                filtered.append(record)
            elif isinstance(record_level, (int, float)) and record_level <= max_level:
                filtered.append(record)
            else:
                logger.debug(
                    "Filtered out record for user %s: required level %s > max level %s",
                    user_id,
                    record_level,
                    max_level,
                )

        return filtered

    # =====================================================================
    # Cypher Query Augmentation
    # =====================================================================

    def augment_cypher_with_access(
        self,
        user_id: str,
        cypher: str,
        node_alias: str = "n",
    ) -> tuple[str, dict[str, Any]]:
        """Augment a Cypher query with access control WHERE clauses.

        Adds a subquery pattern that checks the target node's data classification
        against the user's accessible levels. This works for nodes that have a
        ``CLASSIFIED_AS`` relationship to a ``DataClass`` node.

        The augmented query adds::

            AND (
                NOT exists((n)-[:CLASSIFIED_AS]->(:DataClass))
                OR (n)-[:CLASSIFIED_AS]->(dc:DataClass)
                   WHERE dc.level <= $__rbac_max_level
            )

        For admin users, the original query is returned unchanged.

        Args:
            user_id: The user's unique identifier.
            cypher: Original Cypher query string.
            node_alias: Alias of the node to apply access control to.
                Defaults to ``"n"``.

        Returns:
            Tuple of (augmented_cypher, parameters).
        """
        params: dict[str, Any] = {}

        # Resolve user's max access level
        accessible = self.get_accessible_data_classes(user_id)
        if not accessible:
            # 접근 가능한 데이터 등급 없음 -> 모든 데이터 차단
            # 불가능한 조건 추가
            access_clause = f"AND 1 = 0 /* RBAC: no access for {user_id} */"
            return _inject_where_clause(cypher, access_clause), params

        max_level = max(dc.level for dc in accessible)

        # Admin users (level 5) get unrestricted access
        if max_level >= 5:
            return cypher, params

        # 분류되지 않은 노드는 공개(허용), 분류된 노드는 레벨 체크
        access_clause = (
            f"AND ("
            f"NOT EXISTS(({node_alias})-[:CLASSIFIED_AS]->(:DataClass)) "
            f"OR EXISTS(({node_alias})-[:CLASSIFIED_AS]->(dc__rbac:DataClass) "
            f"WHERE dc__rbac.level <= $__rbac_max_level)"
            f")"
        )
        params["__rbac_max_level"] = max_level

        return _inject_where_clause(cypher, access_clause), params

    # =====================================================================
    # Role Management Helpers
    # =====================================================================

    def assign_role(self, user_id: str, role_id: str) -> bool:
        """Assign a role to a user.

        Creates a ``(:User)-[:HAS_ROLE]->(:Role)`` relationship.

        Args:
            user_id: The user's unique identifier.
            role_id: The role identifier to assign.

        Returns:
            True if the relationship was created, False if user or role not found.
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (u:User {userId: $userId})
                MATCH (r:Role {roleId: $roleId})
                MERGE (u)-[rel:HAS_ROLE]->(r)
                ON CREATE SET rel.assignedAt = datetime()
                RETURN u.userId AS uid, r.roleId AS rid
                """,
                userId=user_id,
                roleId=role_id,
            )
            record = result.single()

        if record is None:
            logger.warning(
                "Failed to assign role %s to user %s: user or role not found",
                role_id,
                user_id,
            )
            return False

        logger.info("Assigned role %s to user %s", role_id, user_id)
        return True

    def revoke_role(self, user_id: str, role_id: str) -> bool:
        """Revoke a role from a user.

        Removes the ``(:User)-[:HAS_ROLE]->(:Role)`` relationship.

        Args:
            user_id: The user's unique identifier.
            role_id: The role identifier to revoke.

        Returns:
            True if the relationship was removed, False if it did not exist.
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (u:User {userId: $userId})-[rel:HAS_ROLE]->(r:Role {roleId: $roleId})
                DELETE rel
                RETURN count(rel) AS deleted
                """,
                userId=user_id,
                roleId=role_id,
            )
            record = result.single()

        deleted = record["deleted"] if record else 0
        if deleted > 0:
            logger.info("Revoked role %s from user %s", role_id, user_id)
            return True
        else:
            logger.warning(
                "No role %s found on user %s to revoke",
                role_id,
                user_id,
            )
            return False

    # =====================================================================
    # Listing
    # =====================================================================

    def list_roles(self) -> list[RBACRole]:
        """List all defined roles.

        Returns:
            List of RBACRole objects sorted by level ascending.
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (r:Role)
                OPTIONAL MATCH (r)-[:CAN_ACCESS]->(dc:DataClass)
                RETURN r {.*} AS role, collect(dc {.*}) AS dataClasses
                ORDER BY r.level ASC
                """,
            )
            records = list(result)

        roles: list[RBACRole] = []
        for record in records:
            role_data = record["role"]
            if role_data is not None and role_data.get("roleId") is not None:
                role = RBACRole.from_neo4j(role_data)
                for dc_data in record["dataClasses"]:
                    if dc_data is not None and dc_data.get("classId") is not None:
                        role.accessible_data_classes.append(DataClassification.from_neo4j(dc_data))
                roles.append(role)

        return roles

    def list_data_classes(self) -> list[DataClassification]:
        """List all defined data classifications.

        Returns:
            List of DataClassification objects sorted by level ascending.
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (dc:DataClass)
                RETURN dc {.*} AS dataClass
                ORDER BY dc.level ASC
                """,
            )
            records = list(result)

        return [
            DataClassification.from_neo4j(r["dataClass"])
            for r in records
            if r["dataClass"] is not None and r["dataClass"].get("classId") is not None
        ]


# =========================================================================
# Internal Helpers
# =========================================================================


def _inject_where_clause(cypher: str, clause: str) -> str:
    """Inject an additional AND clause into a Cypher query.

    Strategy:
        1. If the query contains a WHERE keyword, append the clause after
           the last WHERE block (before RETURN/WITH/ORDER/LIMIT/SKIP).
        2. If no WHERE exists, insert ``WHERE TRUE {clause}`` before
           the first RETURN/WITH.

    This is a best-effort heuristic for simple queries. Complex queries
    with subqueries or UNION may require manual augmentation.

    Args:
        cypher: Original Cypher query string.
        clause: The AND clause to inject (should start with "AND").

    Returns:
        Augmented Cypher query string.
    """
    # 대소문자 무시 패턴 매칭을 위한 키워드
    terminal_keywords = r"(?:RETURN|WITH|ORDER\s+BY|LIMIT|SKIP|UNION|CALL)"

    # WHERE가 이미 존재하는 경우
    where_pattern = re.compile(
        r"(WHERE\s+.+?)(\s+" + terminal_keywords + r")",
        re.IGNORECASE | re.DOTALL,
    )
    match = where_pattern.search(cypher)
    if match:
        insert_pos = match.end(1)
        return cypher[:insert_pos] + "\n  " + clause + cypher[insert_pos:]

    # WHERE가 없는 경우 -> RETURN/WITH 앞에 WHERE TRUE 추가
    terminal_pattern = re.compile(
        r"(\s+)(" + terminal_keywords + r")",
        re.IGNORECASE,
    )
    match = terminal_pattern.search(cypher)
    if match:
        insert_pos = match.start()
        return cypher[:insert_pos] + "\nWHERE TRUE " + clause + cypher[insert_pos:]

    # 매칭 실패 시 쿼리 끝에 추가
    return cypher + "\nWHERE TRUE " + clause
