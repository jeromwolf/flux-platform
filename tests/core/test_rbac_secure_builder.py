"""Unit tests for RBAC Secure Cypher Builder.

Tests for ``kg/rbac/secure_builder.py`` - SecureCypherBuilder and secure_query.
All tests are pure Python unit tests that do NOT require Neo4j.
"""

from __future__ import annotations

import pytest

from kg.rbac.secure_builder import SecureCypherBuilder, secure_query

# =============================================================================
# SecureCypherBuilder - 기본 동작 (CypherBuilder 호환)
# =============================================================================


@pytest.mark.unit
class TestSecureCypherBuilderBasic:
    """SecureCypherBuilder without access control acts like CypherBuilder."""

    def test_no_access_control_same_as_cypher_builder(self) -> None:
        """접근 제어 없이 일반 CypherBuilder와 동일하게 동작."""
        query, params = (
            SecureCypherBuilder()
            .match("(v:Vessel)")
            .where("v.vesselType = $type", {"type": "ContainerShip"})
            .return_("v")
            .build()
        )
        assert "MATCH (v:Vessel)" in query
        assert "RETURN v" in query
        assert "v.vesselType = $type" in query
        assert params == {"type": "ContainerShip"}
        # RBAC 파라미터가 없어야 함
        assert "__rbac_user_id" not in params

    def test_backward_compatibility_all_methods(self) -> None:
        """CypherBuilder의 모든 메서드를 SecureCypherBuilder에서 사용 가능."""
        query, params = (
            SecureCypherBuilder()
            .match("(v:Vessel)")
            .optional_match("(v)-[:DOCKED_AT]->(p:Port)")
            .where("v.mmsi IS NOT NULL")
            .return_("v, p")
            .order_by("name", "asc", "v")
            .skip(10)
            .limit(5)
            .build()
        )
        assert "MATCH (v:Vessel)" in query
        assert "OPTIONAL MATCH (v)-[:DOCKED_AT]->(p:Port)" in query
        assert "RETURN v, p" in query
        assert "ORDER BY" in query
        assert "SKIP 10" in query
        assert "LIMIT 5" in query

    def test_user_id_none_no_rbac(self) -> None:
        """user_id=None이면 with_access_control 마킹해도 RBAC 미적용."""
        query, params = (
            SecureCypherBuilder(user_id=None, access_level=2)
            .match("(v:Vessel)")
            .with_access_control("v", data_class_level=1)
            .return_("v")
            .build()
        )
        assert "__rbac_user_id" not in params
        assert "EXISTS" not in query


# =============================================================================
# SecureCypherBuilder - Admin 바이패스
# =============================================================================


@pytest.mark.unit
class TestSecureCypherBuilderAdmin:
    """Admin users (access_level >= 5) bypass all access control."""

    def test_admin_level_5_bypasses_rbac(self) -> None:
        """access_level=5인 admin은 RBAC WHERE 절이 추가되지 않음."""
        query, params = (
            SecureCypherBuilder(user_id="ADMIN-001", access_level=5)
            .match("(v:Vessel)")
            .with_access_control("v", data_class_level=3)
            .return_("v")
            .build()
        )
        assert "EXISTS" not in query
        assert "__rbac_user_id" not in params
        assert "__rbac_dc_level_v" not in params

    def test_admin_level_above_5_bypasses_rbac(self) -> None:
        """access_level > 5도 admin으로 처리."""
        query, params = (
            SecureCypherBuilder(user_id="SUPERADMIN", access_level=10)
            .match("(v:Vessel)")
            .with_access_control("v")
            .return_("v")
            .build()
        )
        assert "EXISTS" not in query
        assert "__rbac_user_id" not in params


# =============================================================================
# SecureCypherBuilder - 일반 사용자 RBAC 주입
# =============================================================================


@pytest.mark.unit
class TestSecureCypherBuilderRBAC:
    """Regular users get RBAC WHERE clauses injected."""

    def test_single_alias_adds_exists_subquery(self) -> None:
        """단일 alias에 대한 EXISTS 서브쿼리 주입."""
        query, params = (
            SecureCypherBuilder(user_id="USER-001", access_level=2)
            .match("(v:Vessel)")
            .with_access_control("v", data_class_level=2)
            .return_("v")
            .build()
        )
        assert "EXISTS" in query
        assert "$__rbac_user_id" in query
        assert "$__rbac_dc_level_v" in query
        assert params["__rbac_user_id"] == "USER-001"
        assert params["__rbac_dc_level_v"] == 2

    def test_multiple_aliases_add_multiple_checks(self) -> None:
        """다중 alias에 대해 각각 EXISTS 서브쿼리 주입."""
        query, params = (
            SecureCypherBuilder(user_id="USER-002", access_level=3)
            .match("(v:Vessel)")
            .match("(p:Port)")
            .with_access_control("v", data_class_level=2)
            .with_access_control("p", data_class_level=1)
            .return_("v, p")
            .build()
        )
        # 두 개의 EXISTS 서브쿼리
        assert query.count("EXISTS") == 2
        assert "$__rbac_dc_level_v" in query
        assert "$__rbac_dc_level_p" in query
        assert params["__rbac_dc_level_v"] == 2
        assert params["__rbac_dc_level_p"] == 1
        assert params["__rbac_user_id"] == "USER-002"

    def test_with_access_control_returns_self(self) -> None:
        """with_access_control()이 self를 반환하여 fluent chaining 가능."""
        builder = SecureCypherBuilder(user_id="USER-001", access_level=1)
        result = builder.with_access_control("v", data_class_level=1)
        assert result is builder

    def test_rbac_params_dont_collide_with_user_params(self) -> None:
        """RBAC 파라미터가 사용자 파라미터와 충돌하지 않음."""
        query, params = (
            SecureCypherBuilder(user_id="USER-001", access_level=2)
            .match("(v:Vessel)")
            .where("v.vesselType = $type", {"type": "ContainerShip"})
            .where("v.tonnage > $minTonnage", {"minTonnage": 5000})
            .with_access_control("v", data_class_level=2)
            .return_("v")
            .build()
        )
        # 사용자 파라미터 유지
        assert params["type"] == "ContainerShip"
        assert params["minTonnage"] == 5000
        # RBAC 파라미터 존재
        assert params["__rbac_user_id"] == "USER-001"
        assert params["__rbac_dc_level_v"] == 2
        # 총 파라미터 수 확인 (사용자 2개 + RBAC 2개)
        assert len(params) == 4

    def test_default_data_class_level_is_1(self) -> None:
        """data_class_level 기본값이 1(공개)."""
        query, params = (
            SecureCypherBuilder(user_id="USER-001", access_level=1)
            .match("(v:Vessel)")
            .with_access_control("v")
            .return_("v")
            .build()
        )
        assert params["__rbac_dc_level_v"] == 1


# =============================================================================
# SecureCypherBuilder - build_unrestricted
# =============================================================================


@pytest.mark.unit
class TestBuildUnrestricted:
    """build_unrestricted() always returns clean query without RBAC."""

    def test_build_unrestricted_ignores_access_control(self) -> None:
        """build_unrestricted()는 with_access_control 마킹을 무시."""
        builder = (
            SecureCypherBuilder(user_id="USER-001", access_level=2)
            .match("(v:Vessel)")
            .with_access_control("v", data_class_level=3)
            .return_("v")
        )
        query, params = builder.build_unrestricted()
        assert "EXISTS" not in query
        assert "__rbac_user_id" not in params
        assert "__rbac_dc_level_v" not in params


# =============================================================================
# secure_query 유틸리티 함수
# =============================================================================


@pytest.mark.unit
class TestSecureQuery:
    """Tests for the secure_query() utility function."""

    def test_admin_bypass_returns_unchanged(self) -> None:
        """Admin (level >= 5)은 쿼리 변경 없이 반환."""
        original_query = "MATCH (v:Vessel) RETURN v"
        original_params = {"foo": "bar"}

        query, params = secure_query(
            original_query,
            original_params,
            user_id="ADMIN-001",
            access_level=5,
        )
        assert query == original_query
        assert params == original_params

    def test_regular_user_adds_rbac_check(self) -> None:
        """일반 사용자에게 RBAC 체크 쿼리 추가."""
        original_query = "MATCH (v:Vessel) RETURN v"
        original_params = {"type": "Tanker"}

        query, params = secure_query(
            original_query,
            original_params,
            user_id="USER-001",
            access_level=2,
        )
        # RBAC MATCH가 추가됨
        assert "User {userId: $__rbac_user_id}" in query
        assert "HAS_ROLE" in query
        assert "CAN_ACCESS" in query
        assert "DataClass" in query
        # 원본 쿼리가 포함됨
        assert "MATCH (v:Vessel) RETURN v" in query
        # 파라미터 병합
        assert params["__rbac_user_id"] == "USER-001"
        assert params["type"] == "Tanker"

    def test_secure_query_preserves_original_params(self) -> None:
        """secure_query가 원본 params dict를 변경하지 않음."""
        original_params = {"type": "Tanker"}
        original_params_copy = original_params.copy()

        secure_query(
            "MATCH (v:Vessel) RETURN v",
            original_params,
            user_id="USER-001",
            access_level=2,
        )
        # 원본 dict가 변경되지 않았는지 확인
        assert original_params == original_params_copy
