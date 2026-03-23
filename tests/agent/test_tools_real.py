"""Unit tests for real-backend-connected agent tools.

Covers:
    TC-TR01  kg_query stub fallback when imports fail
    TC-TR02  kg_schema stub fallback
    TC-TR03  vessel_search stub fallback
    TC-TR04  document_search stub fallback
    TC-TR05  cypher_execute blocks dangerous queries
    TC-TR06  all tools return valid JSON
    TC-TR07  cypher_execute allows safe queries
    TC-TR08  port_info stub fallback
    TC-TR09  route_query stub fallback
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.tools.builtins import (
    _handle_cypher_execute,
    _handle_document_search,
    _handle_kg_query,
    _handle_kg_schema,
    _handle_port_info,
    _handle_route_query,
    _handle_vessel_search,
    _is_dangerous,
    create_builtin_registry,
)


# ---------------------------------------------------------------------------
# TC-TR01: kg_query stub fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestKgQueryStubFallback:
    """TC-TR01: kg_query falls back to stub when backends are unavailable."""

    def test_tr01a_returns_stub_when_pipeline_import_fails(self) -> None:
        """TC-TR01-a: Returns stub data when TextToCypherPipeline import fails."""
        # The pipeline import will fail in test env (no Neo4j), so stub is expected
        result_str = _handle_kg_query("부산항에 정박한 선박")
        data = json.loads(result_str)
        assert "query" in data
        assert "stub" in data
        # Should have valid structure regardless of stub status
        assert isinstance(data.get("results", []), list)

    def test_tr01b_returns_valid_json_with_language(self) -> None:
        """TC-TR01-b: Returns valid JSON with language parameter."""
        result_str = _handle_kg_query("vessel search", language="en")
        data = json.loads(result_str)
        assert data.get("language") == "en"
        assert "query" in data

    def test_tr01c_stub_has_cypher_field(self) -> None:
        """TC-TR01-c: Stub result includes a cypher field."""
        result_str = _handle_kg_query("test query")
        data = json.loads(result_str)
        assert "cypher" in data


# ---------------------------------------------------------------------------
# TC-TR02: kg_schema stub fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestKgSchemaStubFallback:
    """TC-TR02: kg_schema falls back to stub when Neo4j is unavailable."""

    def test_tr02a_returns_stub_schema(self) -> None:
        """TC-TR02-a: Returns full schema with node_labels and relationship_types."""
        result_str = _handle_kg_schema()
        data = json.loads(result_str)
        assert "node_labels" in data
        assert "relationship_types" in data
        assert isinstance(data["node_labels"], list)
        assert len(data["node_labels"]) > 0

    def test_tr02b_returns_label_specific_schema(self) -> None:
        """TC-TR02-b: Returns properties for a specific label."""
        result_str = _handle_kg_schema(label="Vessel")
        data = json.loads(result_str)
        assert data.get("label") == "Vessel"
        assert "properties" in data

    def test_tr02c_returns_error_for_unknown_label(self) -> None:
        """TC-TR02-c: Returns error for an unknown label in stub mode."""
        result_str = _handle_kg_schema(label="NonexistentLabel")
        data = json.loads(result_str)
        assert "error" in data


# ---------------------------------------------------------------------------
# TC-TR03: vessel_search stub fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVesselSearchStubFallback:
    """TC-TR03: vessel_search falls back to stub when Neo4j is unavailable."""

    def test_tr03a_returns_stub_vessels_by_name(self) -> None:
        """TC-TR03-a: Returns stub vessels when searching by name."""
        result_str = _handle_vessel_search("BUSAN")
        data = json.loads(result_str)
        assert "vessels" in data
        assert data["search_type"] == "name"
        assert data["count"] > 0

    def test_tr03b_returns_empty_for_no_match(self) -> None:
        """TC-TR03-b: Returns empty list when no match found."""
        result_str = _handle_vessel_search("NONEXISTENT_VESSEL_XYZ_999")
        data = json.loads(result_str)
        assert data["count"] == 0
        assert data["vessels"] == []

    def test_tr03c_mmsi_search_type(self) -> None:
        """TC-TR03-c: MMSI search type is preserved in result."""
        result_str = _handle_vessel_search("440100001", search_type="mmsi")
        data = json.loads(result_str)
        assert data["search_type"] == "mmsi"

    def test_tr03d_invalid_search_type_defaults_to_name(self) -> None:
        """TC-TR03-d: Invalid search type defaults to name."""
        result_str = _handle_vessel_search("BUSAN", search_type="invalid")
        data = json.loads(result_str)
        assert data["search_type"] == "name"


# ---------------------------------------------------------------------------
# TC-TR04: document_search stub fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDocumentSearchStubFallback:
    """TC-TR04: document_search falls back to stub when RAG engine is unavailable."""

    def test_tr04a_returns_stub_documents(self) -> None:
        """TC-TR04-a: Returns stub result with documents list."""
        result_str = _handle_document_search("선박 충돌 사고")
        data = json.loads(result_str)
        assert "documents" in data
        assert "query" in data
        assert isinstance(data["documents"], list)

    def test_tr04b_top_k_preserved(self) -> None:
        """TC-TR04-b: top_k parameter is preserved in stub result."""
        result_str = _handle_document_search("test", top_k=10)
        data = json.loads(result_str)
        assert data.get("top_k") == 10


# ---------------------------------------------------------------------------
# TC-TR05: cypher_execute blocks dangerous queries
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCypherExecuteBlocksDangerous:
    """TC-TR05: cypher_execute blocks dangerous operations."""

    def test_tr05a_blocks_drop_query(self) -> None:
        """TC-TR05-a: Blocks DROP queries."""
        result_str = _handle_cypher_execute("DROP INDEX my_index")
        data = json.loads(result_str)
        assert data.get("blocked") is True
        assert "error" in data

    def test_tr05b_blocks_detach_delete(self) -> None:
        """TC-TR05-b: Blocks DETACH DELETE queries."""
        result_str = _handle_cypher_execute("MATCH (n) DETACH DELETE n")
        data = json.loads(result_str)
        assert data.get("blocked") is True

    def test_tr05c_blocks_apoc_schema(self) -> None:
        """TC-TR05-c: Blocks CALL apoc.schema queries."""
        result_str = _handle_cypher_execute("CALL apoc.schema.assert({})")
        data = json.loads(result_str)
        assert data.get("blocked") is True

    def test_tr05d_blocks_db_management(self) -> None:
        """TC-TR05-d: Blocks db.create/drop/shutdown calls."""
        result_str = _handle_cypher_execute("CALL db.create.index()")
        data = json.loads(result_str)
        assert data.get("blocked") is True

    def test_tr05e_allows_safe_read_query(self) -> None:
        """TC-TR05-e: Allows safe MATCH/RETURN queries (stub fallback)."""
        result_str = _handle_cypher_execute("MATCH (n) RETURN n LIMIT 1")
        data = json.loads(result_str)
        assert data.get("blocked") is not True
        assert "cypher" in data

    def test_tr05f_is_dangerous_function_direct(self) -> None:
        """TC-TR05-f: _is_dangerous correctly classifies queries."""
        assert _is_dangerous("DROP INDEX x")[0] is True
        assert _is_dangerous("MATCH (n) RETURN n")[0] is False
        assert _is_dangerous("CALL db.shutdown()")[0] is True


# ---------------------------------------------------------------------------
# TC-TR06: all tools return valid JSON
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAllToolsReturnValidJson:
    """TC-TR06: every tool handler returns parseable JSON."""

    def test_tr06a_kg_query_valid_json(self) -> None:
        result = json.loads(_handle_kg_query("test"))
        assert isinstance(result, dict)

    def test_tr06b_kg_schema_valid_json(self) -> None:
        result = json.loads(_handle_kg_schema())
        assert isinstance(result, dict)

    def test_tr06c_cypher_execute_valid_json(self) -> None:
        result = json.loads(_handle_cypher_execute("MATCH (n) RETURN n LIMIT 1"))
        assert isinstance(result, dict)

    def test_tr06d_vessel_search_valid_json(self) -> None:
        result = json.loads(_handle_vessel_search("test"))
        assert isinstance(result, dict)

    def test_tr06e_port_info_valid_json(self) -> None:
        result = json.loads(_handle_port_info("test"))
        assert isinstance(result, dict)

    def test_tr06f_route_query_valid_json(self) -> None:
        result = json.loads(_handle_route_query("부산", "인천"))
        assert isinstance(result, dict)

    def test_tr06g_document_search_valid_json(self) -> None:
        result = json.loads(_handle_document_search("test"))
        assert isinstance(result, dict)

    def test_tr06h_blocked_cypher_valid_json(self) -> None:
        """Blocked (dangerous) queries also return valid JSON."""
        result = json.loads(_handle_cypher_execute("DROP INDEX x"))
        assert isinstance(result, dict)

    def test_tr06i_all_via_registry(self) -> None:
        """Execute all tools via the registry and verify JSON output."""
        registry = create_builtin_registry()
        test_cases: list[tuple[str, dict[str, Any]]] = [
            ("kg_query", {"query": "test"}),
            ("kg_schema", {}),
            ("cypher_execute", {"cypher": "RETURN 1"}),
            ("vessel_search", {"query": "test"}),
            ("port_info", {"port_name": "test"}),
            ("route_query", {"origin": "A", "destination": "B"}),
            ("document_search", {"query": "test"}),
        ]
        for tool_name, inputs in test_cases:
            result = registry.execute(tool_name, inputs)
            assert result.success is True, f"{tool_name} failed: {result.error}"
            parsed = json.loads(result.output)
            assert isinstance(parsed, dict), f"{tool_name} did not return a dict"


# ---------------------------------------------------------------------------
# TC-TR07: cypher_execute allows safe queries
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCypherExecuteAllowsSafe:
    """TC-TR07: cypher_execute allows safe read queries."""

    def test_tr07a_match_return_query(self) -> None:
        """TC-TR07-a: Simple MATCH/RETURN query is allowed."""
        result_str = _handle_cypher_execute(
            "MATCH (n:Vessel) RETURN n.name LIMIT 5"
        )
        data = json.loads(result_str)
        assert data.get("blocked") is not True
        assert data["cypher"] == "MATCH (n:Vessel) RETURN n.name LIMIT 5"

    def test_tr07b_parameterized_query(self) -> None:
        """TC-TR07-b: Parameterized query preserves parameters."""
        result_str = _handle_cypher_execute(
            "MATCH (n) WHERE n.id = $id RETURN n",
            parameters={"id": 123},
        )
        data = json.loads(result_str)
        assert data.get("blocked") is not True


# ---------------------------------------------------------------------------
# TC-TR08: port_info stub fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPortInfoStubFallback:
    """TC-TR08: port_info falls back to stub when Neo4j is unavailable."""

    def test_tr08a_known_port_stub(self) -> None:
        """TC-TR08-a: Returns stub data for known port."""
        result_str = _handle_port_info("부산")
        data = json.loads(result_str)
        assert "portId" in data or "port_name" in data

    def test_tr08b_unknown_port_stub(self) -> None:
        """TC-TR08-b: Returns not-found for unknown port."""
        result_str = _handle_port_info("NONEXISTENT_PORT_ZZZ")
        data = json.loads(result_str)
        assert data.get("found") is False


# ---------------------------------------------------------------------------
# TC-TR09: route_query stub fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRouteQueryStubFallback:
    """TC-TR09: route_query falls back to stub when Neo4j is unavailable."""

    def test_tr09a_returns_stub_route(self) -> None:
        """TC-TR09-a: Returns stub route data."""
        result_str = _handle_route_query("부산", "인천")
        data = json.loads(result_str)
        assert data["origin"] == "부산"
        assert data["destination"] == "인천"
        assert "routes" in data
        assert len(data["routes"]) > 0
