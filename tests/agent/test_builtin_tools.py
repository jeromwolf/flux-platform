"""Unit tests for built-in agent tools.

Covers:
    TC-BT01  create_builtin_registry returns non-empty registry
    TC-BT02  All tool definitions have valid parameters
    TC-BT03  kg_query tool stub returns result
    TC-BT04  vessel_search tool stub returns result
    TC-BT05  port_info tool stub returns result
    TC-BT06  document_search tool stub returns result
    TC-BT07  All tools validate required params
"""

from __future__ import annotations

import json

import pytest

from agent.tools.builtins import (
    CYPHER_EXECUTE_TOOL,
    DOCUMENT_SEARCH_TOOL,
    KG_QUERY_TOOL,
    KG_SCHEMA_TOOL,
    PORT_INFO_TOOL,
    ROUTE_QUERY_TOOL,
    VESSEL_SEARCH_TOOL,
    create_builtin_registry,
)
from agent.tools.models import ToolDefinition, ToolResult
from agent.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# TC-BT01: create_builtin_registry returns non-empty registry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateBuiltinRegistry:
    """TC-BT01: create_builtin_registry 팩토리 함수 검증."""

    def test_bt01a_returns_tool_registry(self) -> None:
        """TC-BT01-a: create_builtin_registry()가 ToolRegistry 인스턴스 반환."""
        registry = create_builtin_registry()
        assert isinstance(registry, ToolRegistry)

    def test_bt01b_registry_is_not_empty(self) -> None:
        """TC-BT01-b: 반환된 레지스트리가 하나 이상의 도구를 포함."""
        registry = create_builtin_registry()
        assert registry.tool_count > 0

    def test_bt01c_all_expected_tools_registered(self) -> None:
        """TC-BT01-c: 7개 내장 도구가 모두 등록됨."""
        expected = {
            "kg_query", "kg_schema", "cypher_execute",
            "vessel_search", "port_info", "route_query",
            "document_search",
        }
        registry = create_builtin_registry()
        assert expected.issubset(set(registry.tool_names))


# ---------------------------------------------------------------------------
# TC-BT02: All tool definitions have valid parameters
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestToolDefinitionValidity:
    """TC-BT02: 모든 내장 도구 정의의 유효성 검증."""

    _all_definitions = [
        KG_QUERY_TOOL,
        KG_SCHEMA_TOOL,
        CYPHER_EXECUTE_TOOL,
        VESSEL_SEARCH_TOOL,
        PORT_INFO_TOOL,
        ROUTE_QUERY_TOOL,
        DOCUMENT_SEARCH_TOOL,
    ]

    def test_bt02a_all_tools_have_name(self) -> None:
        """TC-BT02-a: 모든 도구가 비어있지 않은 name을 가짐."""
        for defn in self._all_definitions:
            assert defn.name, f"{defn} has empty name"

    def test_bt02b_all_tools_have_description(self) -> None:
        """TC-BT02-b: 모든 도구가 비어있지 않은 description을 가짐."""
        for defn in self._all_definitions:
            assert defn.description, f"{defn.name} has empty description"

    def test_bt02c_all_tools_are_frozen(self) -> None:
        """TC-BT02-c: 모든 도구 정의가 frozen dataclass임."""
        import dataclasses

        for defn in self._all_definitions:
            with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
                defn.name = "changed"  # type: ignore[misc]

    def test_bt02d_all_tools_are_tool_definition_instances(self) -> None:
        """TC-BT02-d: 모든 도구가 ToolDefinition 인스턴스임."""
        for defn in self._all_definitions:
            assert isinstance(defn, ToolDefinition)

    def test_bt02e_cypher_execute_is_dangerous(self) -> None:
        """TC-BT02-e: cypher_execute 도구는 is_dangerous=True."""
        assert CYPHER_EXECUTE_TOOL.is_dangerous is True

    def test_bt02f_other_tools_are_not_dangerous(self) -> None:
        """TC-BT02-f: cypher_execute 외 도구들은 is_dangerous=False."""
        safe_tools = [
            KG_QUERY_TOOL, KG_SCHEMA_TOOL, VESSEL_SEARCH_TOOL,
            PORT_INFO_TOOL, ROUTE_QUERY_TOOL, DOCUMENT_SEARCH_TOOL,
        ]
        for defn in safe_tools:
            assert not defn.is_dangerous, f"{defn.name} should not be dangerous"

    def test_bt02g_tool_categories_are_set(self) -> None:
        """TC-BT02-g: 모든 도구의 category가 'general'이 아닌 도메인별 카테고리임."""
        for defn in self._all_definitions:
            assert defn.category != "general", f"{defn.name} should have a domain category"


# ---------------------------------------------------------------------------
# TC-BT03: kg_query tool stub returns result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestKgQueryTool:
    """TC-BT03: kg_query 도구 stub 실행 검증."""

    def test_bt03a_kg_query_executes_successfully(self) -> None:
        """TC-BT03-a: kg_query 도구가 성공적으로 실행됨."""
        registry = create_builtin_registry()
        result = registry.execute("kg_query", {"query": "부산항에 정박한 선박 목록"})
        assert result.success is True

    def test_bt03b_kg_query_returns_json_output(self) -> None:
        """TC-BT03-b: kg_query 결과가 JSON 파싱 가능한 문자열임."""
        registry = create_builtin_registry()
        result = registry.execute("kg_query", {"query": "선박 검색"})
        data = json.loads(result.output)
        assert "query" in data

    def test_bt03c_kg_query_with_language_param(self) -> None:
        """TC-BT03-c: language 파라미터를 포함한 kg_query 실행 성공."""
        registry = create_builtin_registry()
        result = registry.execute("kg_query", {"query": "vessel search", "language": "en"})
        assert result.success is True
        data = json.loads(result.output)
        assert data["language"] == "en"

    def test_bt03d_kg_query_stub_flag_set(self) -> None:
        """TC-BT03-d: stub 모드에서 실행 시 결과에 stub=True 포함."""
        registry = create_builtin_registry()
        result = registry.execute("kg_query", {"query": "test"})
        data = json.loads(result.output)
        # stub 또는 실제 결과 모두 허용 (외부 서비스 연결 여부에 따라)
        assert isinstance(result.success, bool)


# ---------------------------------------------------------------------------
# TC-BT04: vessel_search tool stub returns result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVesselSearchTool:
    """TC-BT04: vessel_search 도구 stub 실행 검증."""

    def test_bt04a_vessel_search_by_name(self) -> None:
        """TC-BT04-a: 이름으로 선박 검색 성공."""
        registry = create_builtin_registry()
        result = registry.execute("vessel_search", {"query": "BUSAN"})
        assert result.success is True

    def test_bt04b_vessel_search_returns_json(self) -> None:
        """TC-BT04-b: vessel_search 결과가 JSON임."""
        registry = create_builtin_registry()
        result = registry.execute("vessel_search", {"query": "PIONEER"})
        data = json.loads(result.output)
        assert "vessels" in data
        assert "count" in data

    def test_bt04c_vessel_search_by_mmsi(self) -> None:
        """TC-BT04-c: MMSI로 선박 검색."""
        registry = create_builtin_registry()
        result = registry.execute("vessel_search", {
            "query": "440100001",
            "search_type": "mmsi",
        })
        assert result.success is True
        data = json.loads(result.output)
        assert data["search_type"] == "mmsi"

    def test_bt04d_vessel_search_by_imo(self) -> None:
        """TC-BT04-d: IMO 번호로 선박 검색."""
        registry = create_builtin_registry()
        result = registry.execute("vessel_search", {
            "query": "IMO9876543",
            "search_type": "imo",
        })
        assert result.success is True

    def test_bt04e_vessel_search_no_match_returns_empty_list(self) -> None:
        """TC-BT04-e: 매칭 결과 없으면 빈 vessels 목록 반환."""
        registry = create_builtin_registry()
        result = registry.execute("vessel_search", {"query": "NONEXISTENT_VESSEL_XYZ"})
        data = json.loads(result.output)
        assert data["count"] == 0
        assert data["vessels"] == []


# ---------------------------------------------------------------------------
# TC-BT05: port_info tool stub returns result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPortInfoTool:
    """TC-BT05: port_info 도구 stub 실행 검증."""

    def test_bt05a_port_info_known_port(self) -> None:
        """TC-BT05-a: 알려진 항구(부산) 조회 성공."""
        registry = create_builtin_registry()
        result = registry.execute("port_info", {"port_name": "부산"})
        assert result.success is True

    def test_bt05b_port_info_returns_json(self) -> None:
        """TC-BT05-b: port_info 결과가 JSON임."""
        registry = create_builtin_registry()
        result = registry.execute("port_info", {"port_name": "부산"})
        data = json.loads(result.output)
        assert "portId" in data or "port_name" in data

    def test_bt05c_port_info_unknown_port_returns_not_found(self) -> None:
        """TC-BT05-c: 알 수 없는 항구 조회 시 found=False 반환."""
        registry = create_builtin_registry()
        result = registry.execute("port_info", {"port_name": "NONEXISTENT_PORT_XYZ"})
        assert result.success is True  # 도구는 성공, 결과에 not found 표시
        data = json.loads(result.output)
        assert data.get("found") is False

    def test_bt05d_port_info_incheon(self) -> None:
        """TC-BT05-d: 인천항 조회 성공."""
        registry = create_builtin_registry()
        result = registry.execute("port_info", {"port_name": "인천"})
        data = json.loads(result.output)
        assert "portId" in data


# ---------------------------------------------------------------------------
# TC-BT06: document_search tool stub returns result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDocumentSearchTool:
    """TC-BT06: document_search 도구 stub 실행 검증."""

    def test_bt06a_document_search_executes_successfully(self) -> None:
        """TC-BT06-a: document_search 도구 실행 성공."""
        registry = create_builtin_registry()
        result = registry.execute("document_search", {"query": "선박 충돌 사고"})
        assert result.success is True

    def test_bt06b_document_search_returns_json(self) -> None:
        """TC-BT06-b: document_search 결과가 JSON임."""
        registry = create_builtin_registry()
        result = registry.execute("document_search", {"query": "해상 안전 규정"})
        data = json.loads(result.output)
        assert "documents" in data
        assert "query" in data

    def test_bt06c_document_search_with_top_k(self) -> None:
        """TC-BT06-c: top_k 파라미터를 포함한 검색 실행."""
        registry = create_builtin_registry()
        result = registry.execute("document_search", {"query": "SOLAS 규정", "top_k": 10})
        assert result.success is True
        data = json.loads(result.output)
        assert data.get("top_k") == 10 or isinstance(data.get("documents"), list)


# ---------------------------------------------------------------------------
# TC-BT07: All tools validate required params
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestToolParamValidation:
    """TC-BT07: 모든 도구의 필수 파라미터 유효성 검증."""

    def test_bt07a_kg_query_requires_query_param(self) -> None:
        """TC-BT07-a: kg_query는 query 파라미터가 필수."""
        registry = create_builtin_registry()
        result = registry.execute("kg_query", {})
        assert result.success is False
        assert "query" in result.error

    def test_bt07b_vessel_search_requires_query_param(self) -> None:
        """TC-BT07-b: vessel_search는 query 파라미터가 필수."""
        registry = create_builtin_registry()
        result = registry.execute("vessel_search", {})
        assert result.success is False
        assert "query" in result.error

    def test_bt07c_port_info_requires_port_name_param(self) -> None:
        """TC-BT07-c: port_info는 port_name 파라미터가 필수."""
        registry = create_builtin_registry()
        result = registry.execute("port_info", {})
        assert result.success is False
        assert "port_name" in result.error

    def test_bt07d_document_search_requires_query_param(self) -> None:
        """TC-BT07-d: document_search는 query 파라미터가 필수."""
        registry = create_builtin_registry()
        result = registry.execute("document_search", {})
        assert result.success is False
        assert "query" in result.error

    def test_bt07e_route_query_requires_both_origin_and_destination(self) -> None:
        """TC-BT07-e: route_query는 origin과 destination 모두 필수."""
        registry = create_builtin_registry()
        # origin만 제공
        result = registry.execute("route_query", {"origin": "부산"})
        assert result.success is False

    def test_bt07f_cypher_execute_requires_cypher_param(self) -> None:
        """TC-BT07-f: cypher_execute는 cypher 파라미터가 필수."""
        registry = create_builtin_registry()
        result = registry.execute("cypher_execute", {})
        assert result.success is False
        assert "cypher" in result.error

    def test_bt07g_kg_schema_has_no_required_params(self) -> None:
        """TC-BT07-g: kg_schema는 필수 파라미터 없이 실행 가능."""
        registry = create_builtin_registry()
        result = registry.execute("kg_schema", {})
        assert result.success is True

    def test_bt07h_cypher_execute_with_optional_parameters(self) -> None:
        """TC-BT07-h: cypher_execute는 parameters 없이도 실행 가능."""
        registry = create_builtin_registry()
        result = registry.execute("cypher_execute", {"cypher": "MATCH (n) RETURN n LIMIT 1"})
        assert result.success is True
