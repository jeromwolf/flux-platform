"""RBAC data models for the Maritime Knowledge Graph platform.

Defines the core data structures used by the access control system.
All models follow the ontology definitions in ``kg/ontology/maritime_ontology.py``
and use camelCase property names consistent with the Neo4j schema.

Node labels:
    - ``User``  (userId, name, email, organization, status, createdAt)
    - ``Role``  (roleId, name, description, level)
    - ``DataClass`` (classId, name, description, level)
    - ``Permission`` (permissionId, type, resource, description)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# =========================================================================
# Enums
# =========================================================================


class PermissionType(str, Enum):
    """Types of access permissions."""

    READ = "READ"
    WRITE = "WRITE"
    ADMIN = "ADMIN"


class UserStatus(str, Enum):
    """Lifecycle states for a platform user account."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING = "PENDING"


# =========================================================================
# Data Classes
# =========================================================================


@dataclass
class DataClassification:
    """Data classification level controlling access to resources.

    Maps to the Neo4j ``(:DataClass)`` node.

    Attributes:
        class_id: Unique identifier (e.g. "DC-PUBLIC").
        name: Korean display name (e.g. "공개").
        description: Human-readable description.
        level: Numeric level (1 = PUBLIC ... 5 = TOP_SECRET).
    """

    class_id: str
    name: str
    description: str = ""
    level: int = 1

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Serialize to Neo4j property map (camelCase keys)."""
        return {
            "classId": self.class_id,
            "name": self.name,
            "description": self.description,
            "level": self.level,
        }

    @classmethod
    def from_neo4j(cls, record: dict[str, Any]) -> DataClassification:
        """Deserialize from a Neo4j record."""
        return cls(
            class_id=record["classId"],
            name=record["name"],
            description=record.get("description", ""),
            level=record.get("level", 1),
        )


@dataclass
class AccessPermission:
    """A specific permission that can be granted to a role.

    Maps to the Neo4j ``(:Permission)`` node.

    Attributes:
        permission_id: Unique identifier (e.g. "PERM-READ-PUBLIC").
        permission_type: READ, WRITE, or ADMIN.
        resource: The resource or scope this permission applies to.
        description: Human-readable description.
    """

    permission_id: str
    permission_type: PermissionType
    resource: str = "*"
    description: str = ""

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Serialize to Neo4j property map."""
        return {
            "permissionId": self.permission_id,
            "type": self.permission_type.value,
            "resource": self.resource,
            "description": self.description,
        }

    @classmethod
    def from_neo4j(cls, record: dict[str, Any]) -> AccessPermission:
        """Deserialize from a Neo4j record."""
        return cls(
            permission_id=record["permissionId"],
            permission_type=PermissionType(record["type"]),
            resource=record.get("resource", "*"),
            description=record.get("description", ""),
        )


@dataclass
class RBACRole:
    """Access control role assigned to users.

    Maps to the Neo4j ``(:Role)`` node.

    Attributes:
        role_id: Unique identifier (e.g. "ROLE-ADMIN").
        name: Korean display name (e.g. "관리자").
        description: Human-readable description.
        level: Numeric privilege level (1 = lowest, 5 = highest).
        accessible_data_classes: Data classification levels this role can access.
        permissions: Specific permissions granted to this role.
    """

    role_id: str
    name: str
    description: str = ""
    level: int = 1
    accessible_data_classes: list[DataClassification] = field(default_factory=list)
    permissions: list[AccessPermission] = field(default_factory=list)

    def can_access_level(self, data_class_level: int) -> bool:
        """Check if this role can access a given data classification level.

        Args:
            data_class_level: The numeric level of the data classification.

        Returns:
            True if any of the role's accessible data classes has a level
            greater than or equal to the requested level.
        """
        return any(dc.level >= data_class_level for dc in self.accessible_data_classes)

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Serialize to Neo4j property map."""
        return {
            "roleId": self.role_id,
            "name": self.name,
            "description": self.description,
            "level": self.level,
        }

    @classmethod
    def from_neo4j(cls, record: dict[str, Any]) -> RBACRole:
        """Deserialize from a Neo4j record (without nested data classes)."""
        return cls(
            role_id=record["roleId"],
            name=record["name"],
            description=record.get("description", ""),
            level=record.get("level", 1),
        )


@dataclass
class RBACUser:
    """Platform user account with role-based access.

    Maps to the Neo4j ``(:User)`` node.

    Attributes:
        user_id: Unique identifier (e.g. "USER-001").
        name: Display name.
        email: Email address.
        organization: Organization name or ID.
        status: Account lifecycle status.
        created_at: Account creation timestamp.
        roles: Assigned roles (populated from graph traversal).
    """

    user_id: str
    name: str
    email: str = ""
    organization: str = ""
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime | None = None
    roles: list[RBACRole] = field(default_factory=list)

    @property
    def max_access_level(self) -> int:
        """Return the highest data-class level accessible through any role."""
        if not self.roles:
            return 0
        max_level = 0
        for role in self.roles:
            for dc in role.accessible_data_classes:
                if dc.level > max_level:
                    max_level = dc.level
        return max_level

    @property
    def is_admin(self) -> bool:
        """Check if the user has the admin role."""
        return any(r.role_id == "ROLE-ADMIN" for r in self.roles)

    def has_role(self, role_id: str) -> bool:
        """Check if the user has a specific role.

        Args:
            role_id: Role identifier to check.
        """
        return any(r.role_id == role_id for r in self.roles)

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Serialize to Neo4j property map."""
        props: dict[str, Any] = {
            "userId": self.user_id,
            "name": self.name,
            "email": self.email,
            "organization": self.organization,
            "status": self.status.value,
        }
        if self.created_at is not None:
            props["createdAt"] = self.created_at.isoformat()
        return props

    @classmethod
    def from_neo4j(cls, record: dict[str, Any]) -> RBACUser:
        """Deserialize from a Neo4j record (without nested roles)."""
        created_at = record.get("createdAt")
        if created_at is not None and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            user_id=record["userId"],
            name=record["name"],
            email=record.get("email", ""),
            organization=record.get("organization", ""),
            status=UserStatus(record.get("status", "ACTIVE")),
            created_at=created_at,
        )


@dataclass
class AccessDecision:
    """Result of an access control check.

    Attributes:
        allowed: Whether access is permitted.
        reason: Human-readable explanation of the decision.
        user_id: The user who requested access.
        data_class_id: The data classification that was checked.
        matched_role: The role that granted access (if allowed).
        required_level: The data classification level required.
        user_max_level: The user's maximum accessible level.
    """

    allowed: bool
    reason: str
    user_id: str = ""
    data_class_id: str = ""
    matched_role: str | None = None
    required_level: int = 0
    user_max_level: int = 0

    @staticmethod
    def deny(
        reason: str,
        user_id: str = "",
        data_class_id: str = "",
        required_level: int = 0,
        user_max_level: int = 0,
    ) -> AccessDecision:
        """Factory for a denial decision."""
        return AccessDecision(
            allowed=False,
            reason=reason,
            user_id=user_id,
            data_class_id=data_class_id,
            required_level=required_level,
            user_max_level=user_max_level,
        )

    @staticmethod
    def allow(
        reason: str,
        user_id: str = "",
        data_class_id: str = "",
        matched_role: str | None = None,
        required_level: int = 0,
        user_max_level: int = 0,
    ) -> AccessDecision:
        """Factory for an approval decision."""
        return AccessDecision(
            allowed=True,
            reason=reason,
            user_id=user_id,
            data_class_id=data_class_id,
            matched_role=matched_role,
            required_level=required_level,
            user_max_level=user_max_level,
        )
