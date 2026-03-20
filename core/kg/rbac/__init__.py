"""RBAC (Role-Based Access Control) module for the Maritime Knowledge Graph.

Provides graph-native access control where users, roles, and data classifications
are stored as nodes in Neo4j with relationship-based permission resolution.

Graph pattern::

    (:User)-[:HAS_ROLE]->(:Role)-[:CAN_ACCESS]->(:DataClass)

5 default role levels:
    1. 관리자 (Admin)        -> 전체 데이터
    2. 내부 연구원 (Internal) -> 시험데이터 + 설계데이터 + 공개데이터
    3. 외부 연구자 (External) -> 비보안 시험데이터 + 공개데이터
    4. 민간 개발자 (Developer) -> 공개 API 데이터만
    5. 일반 사용자 (Public)    -> 공개데이터만

Usage::

    from kg.rbac import RBACPolicy, AccessDecision

    policy = RBACPolicy(driver, database="neo4j")
    decision = policy.check_access("USER-001", "DC-RESTRICTED")
    if decision.allowed:
        print("Access granted")
    else:
        print(f"Access denied: {decision.reason}")
"""

from kg.rbac.models import (
    AccessDecision,
    AccessPermission,
    DataClassification,
    PermissionType,
    RBACRole,
    RBACUser,
    UserStatus,
)
from kg.rbac.policy import RBACPolicy
from kg.rbac.schema import get_rbac_schema_statements
from kg.rbac.secure_builder import SecureCypherBuilder, secure_query

__all__ = [
    # Models
    "RBACUser",
    "RBACRole",
    "DataClassification",
    "AccessPermission",
    "AccessDecision",
    "PermissionType",
    "UserStatus",
    # Policy engine
    "RBACPolicy",
    # Secure builder
    "SecureCypherBuilder",
    "secure_query",
    # Schema
    "get_rbac_schema_statements",
]
