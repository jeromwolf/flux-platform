"""Load RBAC seed data into Neo4j.

Creates default roles, data classifications, role-to-dataclass access
mappings, and sample users for the Maritime Knowledge Graph platform.

Uses MERGE for idempotent execution -- safe to run multiple times.

Usage::

    python -m kg.rbac.load_rbac_data
"""

from __future__ import annotations

import sys
from typing import Any

from kg.config import get_config, get_driver
from kg.rbac.schema import get_rbac_schema_statements

# =========================================================================
# Seed Data
# =========================================================================

# 5 default roles with access level mappings
ROLES: list[dict[str, Any]] = [
    {
        "roleId": "ROLE-ADMIN",
        "name": "관리자",
        "description": "시스템 관리자 - 전체 데이터 접근 권한",
        "level": 5,
        "access_levels": [1, 2, 3, 4, 5],
    },
    {
        "roleId": "ROLE-RESEARCHER-INT",
        "name": "내부 연구원",
        "description": "KRISO 내부 연구원 - 시험데이터, 설계데이터, 공개데이터 접근",
        "level": 4,
        "access_levels": [1, 2, 3],
    },
    {
        "roleId": "ROLE-RESEARCHER-EXT",
        "name": "외부 연구자",
        "description": "외부 연구기관 연구자 - 비보안 시험데이터, 공개데이터 접근",
        "level": 3,
        "access_levels": [1, 2],
    },
    {
        "roleId": "ROLE-DEVELOPER",
        "name": "민간 개발자",
        "description": "민간 개발자 - 공개 API 데이터만 접근",
        "level": 2,
        "access_levels": [1],
    },
    {
        "roleId": "ROLE-PUBLIC",
        "name": "일반 사용자",
        "description": "일반 공개 사용자 - 공개데이터만 접근",
        "level": 1,
        "access_levels": [1],
    },
]

# 5 data classification levels
DATA_CLASSES: list[dict[str, Any]] = [
    {
        "classId": "DC-PUBLIC",
        "name": "공개",
        "description": "일반 공개 데이터 - 누구나 접근 가능",
        "level": 1,
    },
    {
        "classId": "DC-INTERNAL",
        "name": "내부",
        "description": "기관 내부 데이터 - 승인된 연구자 이상 접근",
        "level": 2,
    },
    {
        "classId": "DC-RESTRICTED",
        "name": "제한",
        "description": "제한 데이터 - 내부 연구원 이상 접근",
        "level": 3,
    },
    {
        "classId": "DC-CONFIDENTIAL",
        "name": "기밀",
        "description": "보안 시험 데이터 - 관리자만 접근",
        "level": 4,
    },
    {
        "classId": "DC-TOP-SECRET",
        "name": "극비",
        "description": "국방/안보 관련 데이터 - 관리자만 접근",
        "level": 5,
    },
]

# Sample users for testing
SAMPLE_USERS: list[dict[str, Any]] = [
    {
        "userId": "USER-ADMIN-001",
        "name": "시스템관리자",
        "email": "admin@kriso.re.kr",
        "organization": "KRISO",
        "status": "ACTIVE",
        "roleId": "ROLE-ADMIN",
    },
    {
        "userId": "USER-RESEARCHER-001",
        "name": "김해양",
        "email": "kimhaeyang@kriso.re.kr",
        "organization": "KRISO",
        "status": "ACTIVE",
        "roleId": "ROLE-RESEARCHER-INT",
    },
    {
        "userId": "USER-RESEARCHER-002",
        "name": "이선박",
        "email": "leeseonbak@snu.ac.kr",
        "organization": "서울대학교",
        "status": "ACTIVE",
        "roleId": "ROLE-RESEARCHER-EXT",
    },
    {
        "userId": "USER-DEV-001",
        "name": "박개발",
        "email": "parkdev@maritime-tech.co.kr",
        "organization": "해양테크",
        "status": "ACTIVE",
        "roleId": "ROLE-DEVELOPER",
    },
    {
        "userId": "USER-PUBLIC-001",
        "name": "최시민",
        "email": "choism@gmail.com",
        "organization": "",
        "status": "ACTIVE",
        "roleId": "ROLE-PUBLIC",
    },
]

# Default permissions
PERMISSIONS: list[dict[str, Any]] = [
    {
        "permissionId": "PERM-READ",
        "type": "READ",
        "resource": "*",
        "description": "읽기 권한 - 접근 가능한 데이터 조회",
    },
    {
        "permissionId": "PERM-WRITE",
        "type": "WRITE",
        "resource": "*",
        "description": "쓰기 권한 - 데이터 생성 및 수정",
    },
    {
        "permissionId": "PERM-ADMIN",
        "type": "ADMIN",
        "resource": "*",
        "description": "관리 권한 - 사용자/역할 관리",
    },
]

# Role -> Permission mappings
ROLE_PERMISSIONS: list[dict[str, str]] = [
    # 관리자: 모든 권한
    {"roleId": "ROLE-ADMIN", "permissionId": "PERM-READ"},
    {"roleId": "ROLE-ADMIN", "permissionId": "PERM-WRITE"},
    {"roleId": "ROLE-ADMIN", "permissionId": "PERM-ADMIN"},
    # 내부 연구원: 읽기 + 쓰기
    {"roleId": "ROLE-RESEARCHER-INT", "permissionId": "PERM-READ"},
    {"roleId": "ROLE-RESEARCHER-INT", "permissionId": "PERM-WRITE"},
    # 외부 연구자: 읽기만
    {"roleId": "ROLE-RESEARCHER-EXT", "permissionId": "PERM-READ"},
    # 민간 개발자: 읽기만
    {"roleId": "ROLE-DEVELOPER", "permissionId": "PERM-READ"},
    # 일반 사용자: 읽기만
    {"roleId": "ROLE-PUBLIC", "permissionId": "PERM-READ"},
]


# =========================================================================
# Helper
# =========================================================================


def _section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# =========================================================================
# Schema Setup
# =========================================================================


def _apply_schema(session: Any) -> None:
    """Apply RBAC constraints and indexes."""
    _section("RBAC Schema (Constraints & Indexes)")
    statements = get_rbac_schema_statements()
    ok = 0
    err = 0
    for stmt in statements:
        short = stmt[:80].replace("\n", " ")
        try:
            session.run(stmt)
            print(f"  [OK]  {short}")
            ok += 1
        except Exception as exc:
            # 이미 존재하는 constraint/index는 무시
            if "already exists" in str(exc).lower():
                print(f"  [SKIP] {short} (already exists)")
                ok += 1
            else:
                print(f"  [ERR]  {short}")
                print(f"         {exc}")
                err += 1
    print(f"  -> Schema: {ok} applied, {err} errors")


# =========================================================================
# Data Loading Functions
# =========================================================================


def _create_data_classes(tx: Any) -> None:
    """Create DataClass nodes."""
    _section("Data Classifications (5)")
    query = """
    UNWIND $classes AS c
    MERGE (dc:DataClass {classId: c.classId})
      ON CREATE SET
        dc.name        = c.name,
        dc.description = c.description,
        dc.level       = c.level,
        dc.createdAt   = datetime()
      ON MATCH SET
        dc.name        = c.name,
        dc.description = c.description,
        dc.level       = c.level,
        dc.updatedAt   = datetime()
    RETURN count(dc) AS cnt
    """
    result = tx.run(query, classes=DATA_CLASSES)
    cnt = result.single()["cnt"]
    print(f"  -> Merged {cnt} data classifications")


def _create_roles(tx: Any) -> None:
    """Create Role nodes."""
    _section("Roles (5)")
    # Role 노드 생성 (access_levels 제외)
    role_data = [
        {
            "roleId": r["roleId"],
            "name": r["name"],
            "description": r["description"],
            "level": r["level"],
        }
        for r in ROLES
    ]

    query = """
    UNWIND $roles AS r
    MERGE (role:Role {roleId: r.roleId})
      ON CREATE SET
        role.name        = r.name,
        role.description = r.description,
        role.level       = r.level,
        role.createdAt   = datetime()
      ON MATCH SET
        role.name        = r.name,
        role.description = r.description,
        role.level       = r.level,
        role.updatedAt   = datetime()
    RETURN count(role) AS cnt
    """
    result = tx.run(query, roles=role_data)
    cnt = result.single()["cnt"]
    print(f"  -> Merged {cnt} roles")


def _create_role_access_mappings(tx: Any) -> None:
    """Create Role -> DataClass CAN_ACCESS relationships."""
    _section("Role -> DataClass Access Mappings")

    # DataClass level -> classId mapping
    level_to_class_id = {dc["level"]: dc["classId"] for dc in DATA_CLASSES}

    count = 0
    for role in ROLES:
        for access_level in role["access_levels"]:
            class_id = level_to_class_id.get(access_level)
            if class_id is None:
                continue
            tx.run(
                """
                MATCH (r:Role {roleId: $roleId})
                MATCH (dc:DataClass {classId: $classId})
                MERGE (r)-[rel:CAN_ACCESS]->(dc)
                ON CREATE SET rel.accessLevel = $accessLevel
                ON MATCH SET rel.accessLevel = $accessLevel
                """,
                roleId=role["roleId"],
                classId=class_id,
                accessLevel="FULL",
            )
            count += 1

    print(f"  -> Created {count} role -> data-class access mappings")


def _create_permissions(tx: Any) -> None:
    """Create Permission nodes and Role -> Permission GRANTS relationships."""
    _section("Permissions (3) & Role Grants")

    # Permission 노드 생성
    query = """
    UNWIND $perms AS p
    MERGE (perm:Permission {permissionId: p.permissionId})
      ON CREATE SET
        perm.type        = p.type,
        perm.resource    = p.resource,
        perm.description = p.description,
        perm.createdAt   = datetime()
      ON MATCH SET
        perm.type        = p.type,
        perm.resource    = p.resource,
        perm.description = p.description,
        perm.updatedAt   = datetime()
    RETURN count(perm) AS cnt
    """
    result = tx.run(query, perms=PERMISSIONS)
    cnt = result.single()["cnt"]
    print(f"  -> Merged {cnt} permissions")

    # Role -> Permission GRANTS 관계 생성
    grant_count = 0
    for rp in ROLE_PERMISSIONS:
        tx.run(
            """
            MATCH (r:Role {roleId: $roleId})
            MATCH (p:Permission {permissionId: $permissionId})
            MERGE (r)-[:GRANTS]->(p)
            """,
            roleId=rp["roleId"],
            permissionId=rp["permissionId"],
        )
        grant_count += 1

    print(f"  -> Created {grant_count} role -> permission grants")


def _create_sample_users(tx: Any) -> None:
    """Create sample User nodes with role assignments."""
    _section("Sample Users (5)")

    # User 노드 생성
    user_data = [
        {
            "userId": u["userId"],
            "name": u["name"],
            "email": u["email"],
            "organization": u["organization"],
            "status": u["status"],
        }
        for u in SAMPLE_USERS
    ]

    query = """
    UNWIND $users AS u
    MERGE (user:User {userId: u.userId})
      ON CREATE SET
        user.name         = u.name,
        user.email        = u.email,
        user.organization = u.organization,
        user.status       = u.status,
        user.createdAt    = datetime()
      ON MATCH SET
        user.name         = u.name,
        user.email        = u.email,
        user.organization = u.organization,
        user.status       = u.status,
        user.updatedAt    = datetime()
    RETURN count(user) AS cnt
    """
    result = tx.run(query, users=user_data)
    cnt = result.single()["cnt"]
    print(f"  -> Merged {cnt} users")

    # User -> Role HAS_ROLE 관계 생성
    for u in SAMPLE_USERS:
        tx.run(
            """
            MATCH (user:User {userId: $userId})
            MATCH (role:Role {roleId: $roleId})
            MERGE (user)-[rel:HAS_ROLE]->(role)
            ON CREATE SET rel.assignedAt = datetime()
            """,
            userId=u["userId"],
            roleId=u["roleId"],
        )

    print("  -> Created user -> role assignments")

    # User -> Organization BELONGS_TO 관계 (organization이 있는 경우)
    for u in SAMPLE_USERS:
        if u["organization"]:
            tx.run(
                """
                MATCH (user:User {userId: $userId})
                OPTIONAL MATCH (org:Organization)
                  WHERE org.name = $orgName OR org.nameEn = $orgName
                WITH user, org
                WHERE org IS NOT NULL
                MERGE (user)-[:BELONGS_TO]->(org)
                """,
                userId=u["userId"],
                orgName=u["organization"],
            )

    print("  -> Created user -> organization links (where org exists)")


# =========================================================================
# Verification
# =========================================================================


def _verify(session: Any) -> None:
    """Verify RBAC data was loaded correctly."""
    from kg.utils.verification import verify_rbac

    verify_rbac(session)


# =========================================================================
# Main
# =========================================================================


def load_rbac_data() -> None:
    """Connect to Neo4j and load all RBAC seed data.

    Performs the following steps:
        1. Apply RBAC schema (constraints + indexes)
        2. Create DataClass nodes
        3. Create Role nodes
        4. Create Role -> DataClass access mappings
        5. Create Permission nodes and Role -> Permission grants
        6. Create sample User nodes with role assignments
        7. Verify loaded data
    """
    print("=" * 60)
    print("  Maritime KG - RBAC Seed Data Loader")
    print("=" * 60)

    driver = get_driver()
    try:
        with driver.session(database=get_config().neo4j.database) as session:
            # 1. Schema
            _apply_schema(session)

            # 2-6. Data (in transaction)
            session.execute_write(_create_data_classes)
            session.execute_write(_create_roles)
            session.execute_write(_create_role_access_mappings)
            session.execute_write(_create_permissions)
            session.execute_write(_create_sample_users)

            # 7. Verify (read-only)
            _verify(session)

    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    load_rbac_data()
