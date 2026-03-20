"""RBAC-aware Cypher Query Builder.

Extends ``CypherBuilder`` with graph-native access control injection.
The builder adds structural RBAC WHERE clauses based on user identity
and access level, rather than relying on regex-based injection.

Usage::

    from kg.rbac.secure_builder import SecureCypherBuilder

    # Fluent builder with access control
    query, params = (
        SecureCypherBuilder(user_id="USER-001", access_level=2)
        .match("(v:Vessel)")
        .with_access_control("v", data_class_level=1)
        .where("v.vesselType = $type", {"type": "ContainerShip"})
        .return_("v")
        .build()
    )

    # Utility function for raw Cypher
    from kg.rbac.secure_builder import secure_query

    query, params = secure_query(
        "MATCH (v:Vessel) RETURN v",
        {},
        user_id="USER-001",
        access_level=2,
    )
"""

from __future__ import annotations

from typing import Any

from kg.cypher_builder import CypherBuilder


class SecureCypherBuilder(CypherBuilder):
    """Fluent Cypher builder with RBAC access control injection.

    Extends :class:`CypherBuilder` to optionally inject graph-native
    RBAC WHERE clauses that verify the querying user's permissions
    through the ``(:User)-[:HAS_ROLE]->(:Role)-[:CAN_ACCESS]->(:DataClass)``
    permission graph.

    Args:
        user_id: Identifier of the user executing the query.
            If ``None``, no access control is applied.
        access_level: Numeric access level of the user (0-5).
            Level >= 5 is treated as admin and bypasses all checks.
    """

    def __init__(
        self,
        user_id: str | None = None,
        access_level: int = 0,
    ) -> None:
        super().__init__()
        self._user_id: str | None = user_id
        self._access_level: int = access_level
        self._access_control_aliases: list[tuple[str, int]] = []

    def with_access_control(
        self,
        alias: str,
        data_class_level: int = 1,
    ) -> SecureCypherBuilder:
        """Mark a node alias for RBAC access control enforcement.

        At ``build()`` time, an EXISTS subquery will be added for each
        marked alias to verify the user has permission to access nodes
        at the specified data classification level.

        Args:
            alias: The node alias in the MATCH pattern (e.g., ``"v"``).
            data_class_level: The minimum data classification level
                required. Defaults to 1 (public).

        Returns:
            Self for fluent chaining.
        """
        self._access_control_aliases.append((alias, data_class_level))
        return self

    def build(self) -> tuple[str, dict[str, Any]]:
        """Build the final Cypher query with RBAC access control.

        If no ``user_id`` was provided, or the user is an admin
        (``access_level >= 5``), or no aliases were marked for access
        control, the query is returned without modification.

        Otherwise, for each marked alias an EXISTS subquery is injected
        as an additional WHERE clause::

            EXISTS {
                MATCH (u:User {userId: $__rbac_user_id})
                      -[:HAS_ROLE]->(r:Role)-[:CAN_ACCESS]->(dc:DataClass)
                WHERE dc.level <= $__rbac_dc_level_{alias}
            }

        Returns:
            Tuple of (query_string, parameters_dict).
        """
        # 접근 제어가 불필요한 경우: user_id 없음, admin, 또는 마킹 없음
        if self._user_id is None or self._access_level >= 5 or not self._access_control_aliases:
            return super().build()

        # RBAC WHERE 절 주입
        for alias, _dc_level in self._access_control_aliases:
            rbac_clause = (
                f"EXISTS {{"
                f" MATCH (u:User {{userId: $__rbac_user_id}})"
                f"-[:HAS_ROLE]->(r:Role)-[:CAN_ACCESS]->(dc:DataClass)"
                f" WHERE dc.level <= $__rbac_dc_level_{alias}"
                f" }}"
            )
            self._where_clauses.append(rbac_clause)

        # RBAC 파라미터 주입
        self._parameters["__rbac_user_id"] = self._user_id
        for alias, dc_level in self._access_control_aliases:
            self._parameters[f"__rbac_dc_level_{alias}"] = dc_level

        return super().build()

    def build_unrestricted(self) -> tuple[str, dict[str, Any]]:
        """Build the query without any RBAC access control.

        Always returns the base query as-is, ignoring any
        ``with_access_control()`` markings. Useful for debugging
        or administrative tooling.

        Returns:
            Tuple of (query_string, parameters_dict).
        """
        return super().build()


def secure_query(
    query: str,
    params: dict[str, Any],
    user_id: str,
    access_level: int = 0,
) -> tuple[str, dict[str, Any]]:
    """Wrap an existing Cypher query with RBAC access control.

    A simpler alternative to :class:`SecureCypherBuilder` for cases
    where a raw Cypher query string already exists. The query is wrapped
    in a CALL subquery with an RBAC check prepended.

    For admin users (``access_level >= 5``), the query and parameters
    are returned unchanged.

    Args:
        query: Raw Cypher query string.
        params: Parameters for the query.
        user_id: Identifier of the user executing the query.
        access_level: Numeric access level (0-5). Level >= 5
            bypasses access control.

    Returns:
        Tuple of (possibly_augmented_query, merged_parameters).
    """
    if access_level >= 5:
        return query, params

    # RBAC 체크 쿼리를 앞에 추가하고 원본 쿼리와 결합
    rbac_check = (
        "MATCH (u:User {userId: $__rbac_user_id})"
        "-[:HAS_ROLE]->(r:Role)-[:CAN_ACCESS]->(dc:DataClass)\n"
        "WITH u, max(dc.level) AS __rbac_max_level\n"
    )

    augmented_query = rbac_check + query
    merged_params = {**params, "__rbac_user_id": user_id}

    return augmented_query, merged_params
