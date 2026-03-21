"""Unit tests for RBAC models and policy utilities.

These tests do NOT require Neo4j - they are pure Python unit tests
verifying the data model serialization/deserialization logic and
utility functions.
"""

from datetime import datetime, timezone

import pytest

from kg.rbac.models import (
    AccessDecision,
    AccessPermission,
    DataClassification,
    PermissionType,
    RBACRole,
    RBACUser,
    UserStatus,
)
from kg.rbac.policy import _inject_where_clause

# =============================================================================
# TestDataClassification
# =============================================================================


@pytest.mark.unit
class TestDataClassification:
    """Tests for DataClassification model."""

    def test_to_neo4j_properties_returns_camelcase_keys(self):
        """to_neo4j_properties() returns correct camelCase keys."""
        dc = DataClassification(
            class_id="DC-PUBLIC",
            name="공개",
            description="Public data",
            level=1,
        )
        props = dc.to_neo4j_properties()

        assert props == {
            "classId": "DC-PUBLIC",
            "name": "공개",
            "description": "Public data",
            "level": 1,
        }

    def test_from_neo4j_roundtrip(self):
        """from_neo4j() roundtrip serialization/deserialization."""
        original = DataClassification(
            class_id="DC-SECRET",
            name="기밀",
            description="Secret data",
            level=4,
        )
        props = original.to_neo4j_properties()
        restored = DataClassification.from_neo4j(props)

        assert restored.class_id == original.class_id
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.level == original.level

    def test_from_neo4j_with_missing_optional_fields(self):
        """from_neo4j() with missing optional fields defaults correctly."""
        record = {
            "classId": "DC-MINIMAL",
            "name": "최소",
            # description and level missing
        }
        dc = DataClassification.from_neo4j(record)

        assert dc.class_id == "DC-MINIMAL"
        assert dc.name == "최소"
        assert dc.description == ""  # default
        assert dc.level == 1  # default


# =============================================================================
# TestAccessPermission
# =============================================================================


@pytest.mark.unit
class TestAccessPermission:
    """Tests for AccessPermission model."""

    def test_to_neo4j_properties_serialization(self):
        """to_neo4j_properties() serializes correctly."""
        perm = AccessPermission(
            permission_id="PERM-001",
            permission_type=PermissionType.READ,
            resource="vessel:*",
            description="Read all vessels",
        )
        props = perm.to_neo4j_properties()

        assert props == {
            "permissionId": "PERM-001",
            "type": "READ",
            "resource": "vessel:*",
            "description": "Read all vessels",
        }

    def test_from_neo4j_roundtrip(self):
        """from_neo4j() roundtrip serialization/deserialization."""
        original = AccessPermission(
            permission_id="PERM-WRITE",
            permission_type=PermissionType.WRITE,
            resource="port:*",
            description="Write ports",
        )
        props = original.to_neo4j_properties()
        restored = AccessPermission.from_neo4j(props)

        assert restored.permission_id == original.permission_id
        assert restored.permission_type == original.permission_type
        assert restored.resource == original.resource
        assert restored.description == original.description

    def test_from_neo4j_enum_conversion(self):
        """from_neo4j() converts PermissionType enum correctly."""
        record = {
            "permissionId": "PERM-ADMIN",
            "type": "ADMIN",  # string value
            "resource": "*",
            "description": "Admin access",
        }
        perm = AccessPermission.from_neo4j(record)

        assert perm.permission_type == PermissionType.ADMIN
        assert isinstance(perm.permission_type, PermissionType)


# =============================================================================
# TestRBACRole
# =============================================================================


@pytest.mark.unit
class TestRBACRole:
    """Tests for RBACRole model."""

    def test_to_neo4j_properties_serialization(self):
        """to_neo4j_properties() serializes correctly."""
        role = RBACRole(
            role_id="ROLE-VIEWER",
            name="뷰어",
            description="Read-only access",
            level=2,
        )
        props = role.to_neo4j_properties()

        assert props == {
            "roleId": "ROLE-VIEWER",
            "name": "뷰어",
            "description": "Read-only access",
            "level": 2,
        }

    def test_from_neo4j_roundtrip(self):
        """from_neo4j() roundtrip serialization/deserialization."""
        original = RBACRole(
            role_id="ROLE-EDITOR",
            name="편집자",
            description="Can edit content",
            level=3,
        )
        props = original.to_neo4j_properties()
        restored = RBACRole.from_neo4j(props)

        assert restored.role_id == original.role_id
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.level == original.level

    def test_can_access_level_returns_true_when_matching(self):
        """can_access_level() returns True when role has matching data class."""
        dc1 = DataClassification("DC-PUBLIC", "공개", level=1)
        dc2 = DataClassification("DC-INTERNAL", "내부", level=2)
        role = RBACRole(
            role_id="ROLE-TEST",
            name="테스터",
            accessible_data_classes=[dc1, dc2],
        )

        assert role.can_access_level(1)  # dc1
        assert role.can_access_level(2)  # dc2

    def test_can_access_level_returns_false_when_level_too_high(self):
        """can_access_level() returns False when level too high."""
        dc = DataClassification("DC-PUBLIC", "공개", level=1)
        role = RBACRole(
            role_id="ROLE-LOW",
            name="낮은권한",
            accessible_data_classes=[dc],
        )

        assert not role.can_access_level(2)
        assert not role.can_access_level(5)

    def test_can_access_level_returns_false_when_no_data_classes(self):
        """can_access_level() returns False when no accessible data classes."""
        role = RBACRole(
            role_id="ROLE-EMPTY",
            name="비어있음",
            accessible_data_classes=[],
        )

        assert not role.can_access_level(1)


# =============================================================================
# TestRBACUser
# =============================================================================


@pytest.mark.unit
class TestRBACUser:
    """Tests for RBACUser model."""

    def test_to_neo4j_properties_serialization(self):
        """to_neo4j_properties() serializes correctly."""
        user = RBACUser(
            user_id="USER-001",
            name="홍길동",
            email="hong@example.com",
            organization="ACME Corp",
            status=UserStatus.ACTIVE,
        )
        props = user.to_neo4j_properties()

        assert props == {
            "userId": "USER-001",
            "name": "홍길동",
            "email": "hong@example.com",
            "organization": "ACME Corp",
            "status": "ACTIVE",
        }

    def test_to_neo4j_properties_with_created_at_iso_format(self):
        """to_neo4j_properties() serializes created_at to ISO format."""
        dt = datetime(2026, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        user = RBACUser(
            user_id="USER-002",
            name="김철수",
            created_at=dt,
        )
        props = user.to_neo4j_properties()

        assert "createdAt" in props
        assert props["createdAt"] == "2026-01-15T10:30:45+00:00"

    def test_to_neo4j_properties_without_created_at(self):
        """to_neo4j_properties() omits createdAt when None."""
        user = RBACUser(
            user_id="USER-003",
            name="이영희",
            created_at=None,
        )
        props = user.to_neo4j_properties()

        assert "createdAt" not in props

    def test_from_neo4j_roundtrip_with_all_fields(self):
        """from_neo4j() roundtrip with all fields."""
        original = RBACUser(
            user_id="USER-004",
            name="박민수",
            email="park@example.com",
            organization="TestOrg",
            status=UserStatus.ACTIVE,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        props = original.to_neo4j_properties()
        restored = RBACUser.from_neo4j(props)

        assert restored.user_id == original.user_id
        assert restored.name == original.name
        assert restored.email == original.email
        assert restored.organization == original.organization
        assert restored.status == original.status
        assert restored.created_at == original.created_at

    def test_from_neo4j_status_string_conversion(self):
        """from_neo4j() converts status string to UserStatus enum."""
        record = {
            "userId": "USER-005",
            "name": "최지훈",
            "status": "SUSPENDED",  # string value
        }
        user = RBACUser.from_neo4j(record)

        assert user.status == UserStatus.SUSPENDED
        assert isinstance(user.status, UserStatus)

    def test_from_neo4j_with_iso_datetime_string(self):
        """from_neo4j() parses ISO datetime string."""
        record = {
            "userId": "USER-006",
            "name": "정수진",
            "createdAt": "2026-02-09T12:00:00+00:00",
        }
        user = RBACUser.from_neo4j(record)

        assert user.created_at is not None
        assert user.created_at.year == 2026
        assert user.created_at.month == 2
        assert user.created_at.day == 9

    def test_max_access_level_with_roles_and_data_classes(self):
        """max_access_level property returns highest level across roles."""
        dc1 = DataClassification("DC-PUBLIC", "공개", level=1)
        dc2 = DataClassification("DC-SECRET", "기밀", level=4)
        dc3 = DataClassification("DC-INTERNAL", "내부", level=2)

        role1 = RBACRole("ROLE-1", "역할1", accessible_data_classes=[dc1, dc2])
        role2 = RBACRole("ROLE-2", "역할2", accessible_data_classes=[dc3])

        user = RBACUser(
            user_id="USER-007",
            name="강대리",
            roles=[role1, role2],
        )

        assert user.max_access_level == 4

    def test_max_access_level_with_no_roles_returns_zero(self):
        """max_access_level property returns 0 when no roles."""
        user = RBACUser(user_id="USER-008", name="신입", roles=[])

        assert user.max_access_level == 0

    def test_is_admin_property_true_for_role_admin(self):
        """is_admin property returns True for ROLE-ADMIN."""
        admin_role = RBACRole(role_id="ROLE-ADMIN", name="관리자")
        user = RBACUser(
            user_id="USER-009",
            name="관리자",
            roles=[admin_role],
        )

        assert user.is_admin

    def test_is_admin_property_false_for_other_roles(self):
        """is_admin property returns False for other roles."""
        viewer_role = RBACRole(role_id="ROLE-VIEWER", name="뷰어")
        user = RBACUser(
            user_id="USER-010",
            name="일반사용자",
            roles=[viewer_role],
        )

        assert not user.is_admin

    def test_has_role_method(self):
        """has_role() method checks for specific role."""
        role1 = RBACRole(role_id="ROLE-EDITOR", name="편집자")
        role2 = RBACRole(role_id="ROLE-VIEWER", name="뷰어")
        user = RBACUser(
            user_id="USER-011",
            name="테스터",
            roles=[role1, role2],
        )

        assert user.has_role("ROLE-EDITOR")
        assert user.has_role("ROLE-VIEWER")
        assert not user.has_role("ROLE-ADMIN")


# =============================================================================
# TestAccessDecision
# =============================================================================


@pytest.mark.unit
class TestAccessDecision:
    """Tests for AccessDecision factory methods."""

    def test_deny_factory_method(self):
        """deny() factory creates denial decision correctly."""
        decision = AccessDecision.deny(
            reason="Access denied",
            user_id="USER-001",
            data_class_id="DC-SECRET",
            required_level=4,
            user_max_level=2,
        )

        assert not decision.allowed
        assert decision.reason == "Access denied"
        assert decision.user_id == "USER-001"
        assert decision.data_class_id == "DC-SECRET"
        assert decision.matched_role is None
        assert decision.required_level == 4
        assert decision.user_max_level == 2

    def test_allow_factory_method(self):
        """allow() factory creates approval decision correctly."""
        decision = AccessDecision.allow(
            reason="Access granted",
            user_id="USER-002",
            data_class_id="DC-PUBLIC",
            matched_role="ROLE-VIEWER",
            required_level=1,
            user_max_level=3,
        )

        assert decision.allowed
        assert decision.reason == "Access granted"
        assert decision.user_id == "USER-002"
        assert decision.data_class_id == "DC-PUBLIC"
        assert decision.matched_role == "ROLE-VIEWER"
        assert decision.required_level == 1
        assert decision.user_max_level == 3


# =============================================================================
# TestEnums
# =============================================================================


@pytest.mark.unit
class TestEnums:
    """Tests for enum types."""

    def test_permission_type_values(self):
        """PermissionType enum has correct values."""
        assert PermissionType.READ.value == "READ"
        assert PermissionType.WRITE.value == "WRITE"
        assert PermissionType.ADMIN.value == "ADMIN"

    def test_user_status_values(self):
        """UserStatus enum has correct values."""
        assert UserStatus.ACTIVE.value == "ACTIVE"
        assert UserStatus.INACTIVE.value == "INACTIVE"
        assert UserStatus.SUSPENDED.value == "SUSPENDED"
        assert UserStatus.PENDING.value == "PENDING"


# =============================================================================
# TestInjectWhereClause
# =============================================================================


@pytest.mark.unit
class TestInjectWhereClause:
    """Tests for _inject_where_clause utility function."""

    def test_inject_into_query_with_existing_where_clause(self):
        """Inject into query WITH existing WHERE clause."""
        query = "MATCH (n:Node) WHERE n.type = 'test' RETURN n"
        clause = "AND n.level <= 3"
        result = _inject_where_clause(query, clause)

        assert "WHERE n.type = 'test'" in result
        assert "AND n.level <= 3" in result
        # Should inject before RETURN
        assert result.index("AND n.level") < result.index("RETURN")

    def test_inject_into_query_without_where_clause(self):
        """Inject into query WITHOUT WHERE clause (before RETURN)."""
        query = "MATCH (n:Node) RETURN n"
        clause = "AND n.visible = true"
        result = _inject_where_clause(query, clause)

        assert "WHERE TRUE" in result
        assert "AND n.visible = true" in result
        # Should inject before RETURN
        assert result.index("WHERE") < result.index("RETURN")

    def test_inject_into_query_with_order_by(self):
        """Inject into query with ORDER BY."""
        query = "MATCH (n:Node) WHERE n.status = 'active' ORDER BY n.name"
        clause = "AND n.level >= 1"
        result = _inject_where_clause(query, clause)

        assert "WHERE n.status = 'active'" in result
        assert "AND n.level >= 1" in result
        # Should inject before ORDER BY
        assert result.index("AND n.level") < result.index("ORDER BY")

    def test_inject_into_query_with_no_terminal_keyword(self):
        """Inject into query with no terminal keyword (fallback)."""
        query = "MATCH (n:Node)"
        clause = "AND n.exists = true"
        result = _inject_where_clause(query, clause)

        assert "WHERE TRUE" in result
        assert "AND n.exists = true" in result
        # Should append at the end
        assert result.endswith("AND n.exists = true")


# =============================================================================
# TestRBACPolicy (with Mocking)
# =============================================================================


def _create_mock_driver_with_session(mock_session):
    """Helper to create a mock driver with proper context manager support."""
    from unittest.mock import MagicMock, Mock

    mock_driver = Mock()
    mock_session_context = MagicMock()
    mock_session_context.__enter__.return_value = mock_session
    mock_session_context.__exit__.return_value = None
    mock_driver.session.return_value = mock_session_context
    return mock_driver


@pytest.mark.unit
class TestRBACPolicy:
    """Tests for RBACPolicy class using mocked Neo4j sessions."""

    def test_init_stores_driver_and_database(self):
        """RBACPolicy initialization stores driver and database."""
        from unittest.mock import Mock

        from kg.rbac.policy import RBACPolicy

        mock_driver = Mock()
        policy = RBACPolicy(mock_driver, database="test_db")

        assert policy._driver is mock_driver
        assert policy._database == "test_db"

    def test_check_access_user_not_found(self):
        """check_access() denies when user not found."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        decision = policy.check_access("USER-NONEXISTENT", "DC-PUBLIC")

        assert not decision.allowed
        assert "사용자를 찾을 수 없습니다" in decision.reason
        assert decision.user_id == "USER-NONEXISTENT"

    def test_check_access_user_inactive(self):
        """check_access() denies when user is not active."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_record = {
            "userId": "USER-001",
            "userStatus": "SUSPENDED",
            "requiredLevel": 1,
            "targetName": "공개",
            "matchedRoles": [],
            "matchedRoleNames": [],
        }
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        decision = policy.check_access("USER-001", "DC-PUBLIC")

        assert not decision.allowed
        assert "비활성 상태" in decision.reason
        assert "SUSPENDED" in decision.reason

    def test_check_access_data_class_not_found(self):
        """check_access() denies when data class not found."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_record = {
            "userId": "USER-001",
            "userStatus": "ACTIVE",
            "requiredLevel": None,  # Data class not found
            "targetName": None,
            "matchedRoles": [],
            "matchedRoleNames": [],
        }
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        decision = policy.check_access("USER-001", "DC-NONEXISTENT")

        assert not decision.allowed
        assert "데이터 등급을 찾을 수 없습니다" in decision.reason

    def test_check_access_no_matching_role(self):
        """check_access() denies when no matching role found."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_record = {
            "userId": "USER-001",
            "userStatus": "ACTIVE",
            "requiredLevel": 3,
            "targetName": "내부자료",
            "matchedRoles": [None],  # No role matches
            "matchedRoleNames": [None],
        }
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        decision = policy.check_access("USER-001", "DC-INTERNAL")

        assert not decision.allowed
        assert "접근할 수 있는 역할이 없습니다" in decision.reason
        assert decision.required_level == 3

    def test_check_access_allowed_with_matching_role(self):
        """check_access() allows when user has matching role."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_record = {
            "userId": "USER-001",
            "userStatus": "ACTIVE",
            "requiredLevel": 2,
            "targetName": "내부",
            "matchedRoles": ["ROLE-INTERNAL", "ROLE-VIEWER"],
            "matchedRoleNames": ["내부직원", "뷰어"],
        }
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        decision = policy.check_access("USER-001", "DC-INTERNAL")

        assert decision.allowed
        assert "접근 허용" in decision.reason
        assert decision.matched_role == "ROLE-INTERNAL"
        assert decision.required_level == 2

    def test_get_user_returns_none_when_not_found(self):
        """get_user() returns None when user not found."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        user = policy.get_user("USER-NONEXISTENT")

        assert user is None

    def test_get_user_returns_user_with_roles_and_data_classes(self):
        """get_user() returns fully populated user."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_record = {
            "user": {
                "userId": "USER-001",
                "name": "홍길동",
                "email": "hong@example.com",
                "organization": "ACME",
                "status": "ACTIVE",
            },
            "roles": [
                {
                    "roleId": "ROLE-VIEWER",
                    "name": "뷰어",
                    "description": "Read only",
                    "level": 1,
                },
            ],
            "roleDataClasses": [
                {
                    "roleId": "ROLE-VIEWER",
                    "dc": {
                        "classId": "DC-PUBLIC",
                        "name": "공개",
                        "description": "Public data",
                        "level": 1,
                    },
                },
            ],
        }
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        user = policy.get_user("USER-001")

        assert user is not None
        assert user.user_id == "USER-001"
        assert user.name == "홍길동"
        assert len(user.roles) == 1
        assert user.roles[0].role_id == "ROLE-VIEWER"
        assert len(user.roles[0].accessible_data_classes) == 1
        assert user.roles[0].accessible_data_classes[0].class_id == "DC-PUBLIC"

    def test_get_user_permissions_returns_list(self):
        """get_user_permissions() returns list of permissions."""
        from unittest.mock import MagicMock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = [
            {
                "permission": {
                    "permissionId": "PERM-READ",
                    "type": "READ",
                    "resource": "*",
                    "description": "Read access",
                }
            },
            {
                "permission": {
                    "permissionId": "PERM-WRITE",
                    "type": "WRITE",
                    "resource": "vessel:*",
                    "description": "Write vessels",
                }
            },
        ]
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        permissions = policy.get_user_permissions("USER-001")

        assert len(permissions) == 2
        assert permissions[0].permission_id == "PERM-READ"
        assert permissions[1].permission_id == "PERM-WRITE"

    def test_get_accessible_data_classes_returns_sorted_list(self):
        """get_accessible_data_classes() returns sorted list."""
        from unittest.mock import MagicMock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = [
            {"dataClass": {"classId": "DC-PUBLIC", "name": "공개", "level": 1}},
            {"dataClass": {"classId": "DC-INTERNAL", "name": "내부", "level": 2}},
        ]
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        data_classes = policy.get_accessible_data_classes("USER-001")

        assert len(data_classes) == 2
        assert data_classes[0].class_id == "DC-PUBLIC"
        assert data_classes[1].class_id == "DC-INTERNAL"

    def test_filter_query_results_empty_list(self):
        """filter_query_results() handles empty results."""
        from unittest.mock import Mock

        from kg.rbac.policy import RBACPolicy

        mock_driver = Mock()
        policy = RBACPolicy(mock_driver)

        filtered = policy.filter_query_results("USER-001", [])
        assert filtered == []

    def test_filter_query_results_no_accessible_classes(self):
        """filter_query_results() filters all when user has no access."""
        from unittest.mock import Mock, patch

        from kg.rbac.policy import RBACPolicy

        mock_driver = Mock()
        policy = RBACPolicy(mock_driver)

        with patch.object(policy, "get_accessible_data_classes", return_value=[]):
            results = [
                {"name": "Item1", "dataClassLevel": 1},
                {"name": "Item2", "dataClassLevel": 2},
            ]
            filtered = policy.filter_query_results("USER-001", results)
            assert filtered == []

    def test_filter_query_results_filters_by_level(self):
        """filter_query_results() filters results by access level."""
        from unittest.mock import Mock, patch

        from kg.rbac.policy import RBACPolicy

        mock_driver = Mock()
        policy = RBACPolicy(mock_driver)

        dc1 = DataClassification("DC-PUBLIC", "공개", level=1)
        dc2 = DataClassification("DC-INTERNAL", "내부", level=2)

        with patch.object(policy, "get_accessible_data_classes", return_value=[dc1, dc2]):
            results = [
                {"name": "Item1", "dataClassLevel": 1},
                {"name": "Item2", "dataClassLevel": 2},
                {"name": "Item3", "dataClassLevel": 3},  # Should be filtered
                {"name": "Item4", "dataClassLevel": None},  # Public, allowed
            ]
            filtered = policy.filter_query_results("USER-001", results)

            assert len(filtered) == 3
            assert filtered[0]["name"] == "Item1"
            assert filtered[1]["name"] == "Item2"
            assert filtered[2]["name"] == "Item4"

    def test_augment_cypher_with_access_no_accessible_classes(self):
        """augment_cypher_with_access() blocks access when no classes."""
        from unittest.mock import Mock, patch

        from kg.rbac.policy import RBACPolicy

        mock_driver = Mock()
        policy = RBACPolicy(mock_driver)

        with patch.object(policy, "get_accessible_data_classes", return_value=[]):
            query = "MATCH (n:Node) RETURN n"
            augmented, params = policy.augment_cypher_with_access("USER-001", query)

            assert "AND 1 = 0" in augmented
            assert "no access" in augmented

    def test_augment_cypher_with_access_admin_level(self):
        """augment_cypher_with_access() skips filtering for admin."""
        from unittest.mock import Mock, patch

        from kg.rbac.policy import RBACPolicy

        mock_driver = Mock()
        policy = RBACPolicy(mock_driver)

        dc_admin = DataClassification("DC-ADMIN", "관리자", level=5)

        with patch.object(policy, "get_accessible_data_classes", return_value=[dc_admin]):
            query = "MATCH (n:Node) RETURN n"
            augmented, params = policy.augment_cypher_with_access("USER-001", query)

            # Should return original query unchanged
            assert augmented == query
            assert params == {}

    def test_augment_cypher_with_access_adds_rbac_clause(self):
        """augment_cypher_with_access() adds RBAC filter clause."""
        from unittest.mock import Mock, patch

        from kg.rbac.policy import RBACPolicy

        mock_driver = Mock()
        policy = RBACPolicy(mock_driver)

        dc = DataClassification("DC-INTERNAL", "내부", level=2)

        with patch.object(policy, "get_accessible_data_classes", return_value=[dc]):
            query = "MATCH (n:Node) RETURN n"
            augmented, params = policy.augment_cypher_with_access("USER-001", query, node_alias="n")

            assert "NOT EXISTS((n)-[:CLASSIFIED_AS]->(:DataClass))" in augmented
            assert "dc__rbac.level <= $__rbac_max_level" in augmented
            assert params["__rbac_max_level"] == 2

    def test_assign_role_success(self):
        """assign_role() returns True on success."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_result.single.return_value = {"uid": "USER-001", "rid": "ROLE-VIEWER"}
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        success = policy.assign_role("USER-001", "ROLE-VIEWER")

        assert success is True

    def test_assign_role_failure(self):
        """assign_role() returns False when user or role not found."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        success = policy.assign_role("USER-NONEXISTENT", "ROLE-VIEWER")

        assert success is False

    def test_revoke_role_success(self):
        """revoke_role() returns True when relationship removed."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_result.single.return_value = {"deleted": 1}
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        success = policy.revoke_role("USER-001", "ROLE-VIEWER")

        assert success is True

    def test_revoke_role_failure(self):
        """revoke_role() returns False when relationship not found."""
        from unittest.mock import MagicMock, Mock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = Mock()
        mock_result.single.return_value = {"deleted": 0}
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        success = policy.revoke_role("USER-001", "ROLE-VIEWER")

        assert success is False

    def test_list_roles_returns_sorted_list(self):
        """list_roles() returns sorted list of roles."""
        from unittest.mock import MagicMock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = [
            {
                "role": {
                    "roleId": "ROLE-VIEWER",
                    "name": "뷰어",
                    "description": "Read only",
                    "level": 1,
                },
                "dataClasses": [
                    {"classId": "DC-PUBLIC", "name": "공개", "level": 1},
                ],
            },
            {
                "role": {
                    "roleId": "ROLE-EDITOR",
                    "name": "편집자",
                    "description": "Read/write",
                    "level": 2,
                },
                "dataClasses": [],
            },
        ]
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        roles = policy.list_roles()

        assert len(roles) == 2
        assert roles[0].role_id == "ROLE-VIEWER"
        assert len(roles[0].accessible_data_classes) == 1
        assert roles[1].role_id == "ROLE-EDITOR"
        assert len(roles[1].accessible_data_classes) == 0

    def test_list_data_classes_returns_sorted_list(self):
        """list_data_classes() returns sorted list of data classes."""
        from unittest.mock import MagicMock

        from kg.rbac.policy import RBACPolicy

        mock_session = MagicMock()
        mock_result = [
            {"dataClass": {"classId": "DC-PUBLIC", "name": "공개", "level": 1}},
            {"dataClass": {"classId": "DC-INTERNAL", "name": "내부", "level": 2}},
        ]
        mock_session.run.return_value = mock_result
        mock_driver = _create_mock_driver_with_session(mock_session)

        policy = RBACPolicy(mock_driver)
        data_classes = policy.list_data_classes()

        assert len(data_classes) == 2
        assert data_classes[0].class_id == "DC-PUBLIC"
        assert data_classes[1].class_id == "DC-INTERNAL"


# =============================================================================
# TestRBACSchema
# =============================================================================


@pytest.mark.unit
class TestRBACSchema:
    """Tests for RBAC schema module."""

    def test_parse_cypher_file_extracts_statements(self):
        """_parse_cypher_file() extracts statements from file."""
        import tempfile
        from pathlib import Path

        from kg.utils.cypher_parser import parse_cypher_file as _parse_cypher_file

        content = """
        // Comment line
        CREATE CONSTRAINT user_id_unique IF NOT EXISTS
        FOR (u:User) REQUIRE u.userId IS UNIQUE;

        CREATE INDEX role_level IF NOT EXISTS
        FOR (r:Role) ON (r.level);
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".cypher", delete=False) as f:
            f.write(content)
            f.flush()
            temp_path = Path(f.name)

        try:
            statements = _parse_cypher_file(temp_path)
            assert len(statements) == 2
            assert "User" in statements[0]
            assert "Role" in statements[1]
        finally:
            temp_path.unlink()

    def test_filter_rbac_statements_keeps_only_rbac_labels(self):
        """_filter_rbac_statements() keeps only RBAC-related statements."""
        from kg.rbac.schema import _filter_rbac_statements

        statements = [
            "CREATE CONSTRAINT FOR (u:User) REQUIRE u.userId IS UNIQUE",
            "CREATE CONSTRAINT FOR (v:Vessel) REQUIRE v.vesselId IS UNIQUE",
            "CREATE INDEX FOR (r:Role) ON (r.level)",
            "CREATE INDEX FOR (p:Port) ON (p.portId)",
            "CREATE CONSTRAINT FOR (dc:DataClass) REQUIRE dc.classId IS UNIQUE",
            "CREATE INDEX FOR (perm:Permission) ON (perm.permissionId)",
        ]

        filtered = _filter_rbac_statements(statements)

        assert len(filtered) == 4
        assert any("User" in stmt for stmt in filtered)
        assert any("Role" in stmt for stmt in filtered)
        assert any("DataClass" in stmt for stmt in filtered)
        assert any("Permission" in stmt for stmt in filtered)
        assert not any("Vessel" in stmt for stmt in filtered)
        assert not any("Port" in stmt for stmt in filtered)

    def test_get_rbac_schema_statements_returns_combined_list(self):
        """get_rbac_schema_statements() returns combined constraints + indexes."""
        from kg.rbac.schema import get_rbac_schema_statements

        statements = get_rbac_schema_statements()

        # Should return at least some statements
        assert len(statements) > 0

        # Should contain RBAC labels
        combined_text = " ".join(statements)
        assert "User" in combined_text or "Role" in combined_text or "DataClass" in combined_text

    def test_get_rbac_schema_statements_returns_list_type(self):
        """get_rbac_schema_statements() returns a list."""
        from kg.rbac.schema import get_rbac_schema_statements

        statements = get_rbac_schema_statements()
        assert isinstance(statements, list)
        assert all(isinstance(stmt, str) for stmt in statements)
