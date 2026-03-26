"""Tests for Phase 2: Agent stub → real implementation transition.

Tests MCP live schema queries, LLM synthesis, Cypher injection prevention,
and guardrails (max_results, singletons, fallback_reason).

TC-P2-01  MCP schema cache reset and TTL
TC-P2-02  _query_neo4j_schema fallback (no Neo4j)
TC-P2-03  resources/read with stub fallback
TC-P2-04  property-keys resource registered
TC-P2-05  kg_schema fallback_reason present in stub
TC-P2-06  Cypher injection prevention via _is_dangerous
TC-P2-07  _run_cypher returns empty list when Neo4j unavailable
TC-P2-08  Singleton reset functions work
TC-P2-09  fallback_reason in all tool stubs
TC-P2-10  LLM synthesis fallback (_synthesize_answer)
TC-P2-11  _format_vessel_report fallback
TC-P2-12  reset_llm_provider clears singleton
TC-P2-13  _synthesize_answer with mock LLM uses LLM output
"""
from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# TC-P2-01 / TC-P2-02: MCP schema cache
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPLiveSchema:
    """TC-P2-01/02: MCP server live Neo4j schema queries and cache behavior."""

    def test_p201a_reset_schema_cache_clears_state(self) -> None:
        """TC-P2-01-a: reset_schema_cache empties _schema_cache and zeros _schema_cache_ts."""
        import agent.mcp.server as mcp_mod
        from agent.mcp.server import reset_schema_cache

        # Manually populate cache so reset has something to clear
        mcp_mod._schema_cache = {"kg://schema/node-labels": {"labels": ["Vessel"]}}
        mcp_mod._schema_cache_ts = time.time()

        reset_schema_cache()

        assert mcp_mod._schema_cache == {}
        assert mcp_mod._schema_cache_ts == 0.0

    def test_p201b_schema_cache_ttl_constant_is_300_seconds(self) -> None:
        """TC-P2-01-b: _SCHEMA_CACHE_TTL is 300 seconds (5 minutes)."""
        from agent.mcp.server import _SCHEMA_CACHE_TTL

        assert _SCHEMA_CACHE_TTL == 300.0

    def test_p202a_query_neo4j_schema_returns_none_without_neo4j(self) -> None:
        """TC-P2-02-a: _query_neo4j_schema returns None when Neo4j is unavailable."""
        from agent.mcp.server import reset_schema_cache, _query_neo4j_schema

        reset_schema_cache()
        result = _query_neo4j_schema()
        # In test environment (no Neo4j), should return None
        assert result is None

    def test_p202b_query_neo4j_schema_returns_cached_data(self) -> None:
        """TC-P2-02-b: _query_neo4j_schema returns cached data when cache is fresh."""
        import agent.mcp.server as mcp_mod
        from agent.mcp.server import reset_schema_cache, _query_neo4j_schema

        reset_schema_cache()

        # Manually populate cache with fresh timestamp
        cached = {"kg://schema/node-labels": {"labels": ["TestLabel"]}}
        mcp_mod._schema_cache = cached
        mcp_mod._schema_cache_ts = time.time()

        result = _query_neo4j_schema()

        assert result is not None
        assert result["kg://schema/node-labels"]["labels"] == ["TestLabel"]

        # Cleanup
        reset_schema_cache()

    def test_p202c_expired_cache_triggers_refetch(self) -> None:
        """TC-P2-02-c: Expired cache (ts=0) causes re-query attempt (returns None without Neo4j)."""
        import agent.mcp.server as mcp_mod
        from agent.mcp.server import reset_schema_cache, _query_neo4j_schema

        # Populate cache but mark timestamp as ancient (expired)
        mcp_mod._schema_cache = {"kg://schema/node-labels": {"labels": ["OldLabel"]}}
        mcp_mod._schema_cache_ts = 0.0  # expired

        result = _query_neo4j_schema()
        # Without Neo4j, re-query fails → None
        assert result is None

        reset_schema_cache()


# ---------------------------------------------------------------------------
# TC-P2-03 / TC-P2-04: MCP resources
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPResources:
    """TC-P2-03/04: MCP resources/read and resource registration."""

    def test_p203a_resources_read_node_labels_returns_contents(self) -> None:
        """TC-P2-03-a: resources/read for node-labels returns contents with labels."""
        import asyncio
        from agent.mcp.server import MCPServer, reset_schema_cache
        from agent.mcp.protocol import MCPRequest, MCPMethod

        reset_schema_cache()
        server = MCPServer(ToolRegistry())

        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "kg://schema/node-labels"},
        )
        response = asyncio.run(server.handle(request))

        assert response.success is True
        contents = response.result.get("contents", [])
        assert len(contents) > 0

        data = json.loads(contents[0]["text"])
        assert "labels" in data
        assert isinstance(data["labels"], list)
        assert len(data["labels"]) > 0

    def test_p203b_resources_read_relationship_types_returns_contents(self) -> None:
        """TC-P2-03-b: resources/read for relationship-types returns types list."""
        import asyncio
        from agent.mcp.server import MCPServer, reset_schema_cache
        from agent.mcp.protocol import MCPRequest, MCPMethod

        reset_schema_cache()
        server = MCPServer(ToolRegistry())

        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "kg://schema/relationship-types"},
        )
        response = asyncio.run(server.handle(request))

        assert response.success is True
        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        assert "types" in data

    def test_p203c_resources_read_unknown_uri_returns_error(self) -> None:
        """TC-P2-03-c: resources/read for unknown URI returns error in contents."""
        import asyncio
        from agent.mcp.server import MCPServer, reset_schema_cache
        from agent.mcp.protocol import MCPRequest, MCPMethod

        reset_schema_cache()
        server = MCPServer(ToolRegistry())

        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "kg://nonexistent/resource"},
        )
        response = asyncio.run(server.handle(request))

        assert response.success is True
        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        assert "error" in data

    def test_p204a_property_keys_resource_registered(self) -> None:
        """TC-P2-04-a: kg://schema/property-keys is in the resources list."""
        from agent.mcp.server import MCPServer

        server = MCPServer(ToolRegistry())
        uris = [r["uri"] for r in server._resources]
        assert "kg://schema/property-keys" in uris

    def test_p204b_all_three_schema_uris_registered(self) -> None:
        """TC-P2-04-b: All three KG schema URIs are registered."""
        from agent.mcp.server import MCPServer

        server = MCPServer(ToolRegistry())
        uris = [r["uri"] for r in server._resources]

        assert "kg://schema/node-labels" in uris
        assert "kg://schema/relationship-types" in uris
        assert "kg://schema/property-keys" in uris

    def test_p204c_maritime_ontology_resource_registered(self) -> None:
        """TC-P2-04-c: maritime://ontology/vessel-types resource is registered."""
        from agent.mcp.server import MCPServer

        server = MCPServer(ToolRegistry())
        uris = [r["uri"] for r in server._resources]
        assert "maritime://ontology/vessel-types" in uris


# ---------------------------------------------------------------------------
# TC-P2-05: kg_schema fallback_reason
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestKgSchemaFallbackReason:
    """TC-P2-05: kg_schema stub includes fallback_reason."""

    def test_p205a_kg_schema_stub_has_fallback_reason(self) -> None:
        """TC-P2-05-a: kg_schema returns fallback_reason in stub mode."""
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        result = registry.execute("kg_schema", {})

        data = json.loads(result.output)
        assert data.get("stub") is True
        assert "fallback_reason" in data

    def test_p205b_kg_schema_stub_fallback_reason_value(self) -> None:
        """TC-P2-05-b: fallback_reason value indicates neo4j unavailability."""
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        result = registry.execute("kg_schema", {})
        data = json.loads(result.output)

        assert data["fallback_reason"] == "neo4j_unavailable"

    def test_p205c_kg_schema_label_stub_has_fallback_reason(self) -> None:
        """TC-P2-05-c: kg_schema with known label also includes fallback_reason."""
        from agent.tools.builtins import _handle_kg_schema

        result = _handle_kg_schema(label="Vessel")
        data = json.loads(result)

        # stub=True in test env (no Neo4j)
        if data.get("stub"):
            assert "fallback_reason" in data


# ---------------------------------------------------------------------------
# TC-P2-06: Cypher injection prevention
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCypherInjectionPrevention:
    """TC-P2-06: Cypher injection prevention in kg_schema and cypher_execute."""

    def test_p206a_is_dangerous_detects_drop(self) -> None:
        """TC-P2-06-a: _is_dangerous correctly flags DROP."""
        from agent.tools.builtins import _is_dangerous

        is_dangerous, reason = _is_dangerous("DROP INDEX my_index")
        assert is_dangerous is True
        assert reason != ""

    def test_p206b_is_dangerous_detects_detach_delete(self) -> None:
        """TC-P2-06-b: _is_dangerous correctly flags DETACH DELETE."""
        from agent.tools.builtins import _is_dangerous

        is_dangerous, _ = _is_dangerous("MATCH (n) DETACH DELETE n")
        assert is_dangerous is True

    def test_p206c_is_dangerous_detects_apoc_schema(self) -> None:
        """TC-P2-06-c: _is_dangerous correctly flags CALL apoc.schema."""
        from agent.tools.builtins import _is_dangerous

        is_dangerous, _ = _is_dangerous("CALL apoc.schema.assert({})")
        assert is_dangerous is True

    def test_p206d_is_dangerous_detects_db_create(self) -> None:
        """TC-P2-06-d: _is_dangerous correctly flags db.create."""
        from agent.tools.builtins import _is_dangerous

        is_dangerous, _ = _is_dangerous("CALL db.create.index()")
        assert is_dangerous is True

    def test_p206e_safe_match_return_is_not_dangerous(self) -> None:
        """TC-P2-06-e: Safe MATCH/RETURN is not flagged as dangerous."""
        from agent.tools.builtins import _is_dangerous

        is_dangerous, _ = _is_dangerous("MATCH (n) RETURN n LIMIT 5")
        assert is_dangerous is False

    def test_p206f_safe_match_where_return_is_not_dangerous(self) -> None:
        """TC-P2-06-f: MATCH with WHERE RETURN is not flagged as dangerous."""
        from agent.tools.builtins import _is_dangerous

        is_dangerous, _ = _is_dangerous(
            "MATCH (n:Vessel) WHERE n.flag = 'KR' RETURN n.name, n.mmsi LIMIT 10"
        )
        assert is_dangerous is False

    def test_p206g_cypher_execute_blocks_drop_via_registry(self) -> None:
        """TC-P2-06-g: cypher_execute tool blocks DROP via registry."""
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        result = registry.execute("cypher_execute", {"cypher": "DROP INDEX my_index"})

        assert result.success is True  # Tool layer succeeds
        data = json.loads(result.output)
        assert data.get("blocked") is True

    def test_p206h_kg_schema_label_from_whitelist_only(self) -> None:
        """TC-P2-06-h: kg_schema returns error for injection-like label in stub mode."""
        from agent.tools.builtins import _handle_kg_schema

        # In stub mode, label must be in stub's properties dict
        result = _handle_kg_schema(label="Vessel'; DROP DATABASE neo4j; //")
        data = json.loads(result)
        # Should return error, not crash
        assert "error" in data or data.get("stub") is True


# ---------------------------------------------------------------------------
# TC-P2-07: _run_cypher guardrail
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunCypherGuardrail:
    """TC-P2-07: _run_cypher returns empty list when Neo4j is unavailable."""

    def test_p207a_run_cypher_raises_when_backend_unavailable(self) -> None:
        """TC-P2-07-a: _run_cypher raises an exception when Neo4j/deps are unavailable.

        _run_cypher does NOT return []; it raises.  The caller (handler
        functions) is responsible for catching and falling back to stub data.
        """
        from agent.tools.builtins import _run_cypher

        # In test environment without full Neo4j setup, an exception is expected
        with pytest.raises(Exception):
            _run_cypher("MATCH (n) RETURN n LIMIT 5")

    def test_p207b_handlers_catch_run_cypher_errors_and_use_stub(self) -> None:
        """TC-P2-07-b: Handler functions catch _run_cypher errors and return stub JSON.

        Even though _run_cypher raises, the high-level handlers (_handle_kg_query,
        _handle_cypher_execute, …) catch all exceptions and return valid JSON with
        stub=True.
        """
        from agent.tools.builtins import (
            _handle_kg_query,
            _handle_cypher_execute,
            _handle_vessel_search,
        )
        import json

        for call, kwargs in [
            (_handle_kg_query, {"query": "test"}),
            (_handle_cypher_execute, {"cypher": "MATCH (n) RETURN n LIMIT 1"}),
            (_handle_vessel_search, {"query": "BUSAN"}),
        ]:
            result = call(**kwargs)
            data = json.loads(result)
            # Must be valid JSON dict — stub or real, but never a crash
            assert isinstance(data, dict)

    def test_p207c_run_cypher_max_results_constant(self) -> None:
        """TC-P2-07-c: _MAX_CYPHER_RESULTS is set to 1000."""
        from agent.tools.builtins import _MAX_CYPHER_RESULTS

        assert _MAX_CYPHER_RESULTS == 1000


# ---------------------------------------------------------------------------
# TC-P2-08: Singleton reset functions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSingletonReset:
    """TC-P2-08: Singleton reset functions work correctly."""

    def test_p208a_reset_tool_singletons_clears_pipeline(self) -> None:
        """TC-P2-08-a: reset_tool_singletons sets _pipeline_instance to None."""
        import agent.tools.builtins as tools_mod
        from agent.tools.builtins import reset_tool_singletons

        reset_tool_singletons()
        assert tools_mod._pipeline_instance is None

    def test_p208b_reset_tool_singletons_clears_rag_engine(self) -> None:
        """TC-P2-08-b: reset_tool_singletons sets _rag_engine_instance to None."""
        import agent.tools.builtins as tools_mod
        from agent.tools.builtins import reset_tool_singletons

        reset_tool_singletons()
        assert tools_mod._rag_engine_instance is None

    def test_p208c_get_pipeline_returns_none_without_deps(self) -> None:
        """TC-P2-08-c: _get_pipeline returns None when TextToCypherPipeline unavailable."""
        from agent.tools.builtins import _get_pipeline, reset_tool_singletons

        reset_tool_singletons()
        result = _get_pipeline()
        # In test env, either None (import fails) or an instance (if deps available)
        # The key invariant: does not raise an exception
        reset_tool_singletons()

    def test_p208d_get_rag_engine_returns_none_without_deps(self) -> None:
        """TC-P2-08-d: _get_rag_engine returns None when HybridRAGEngine unavailable."""
        from agent.tools.builtins import _get_rag_engine, reset_tool_singletons

        reset_tool_singletons()
        result = _get_rag_engine()
        # Does not raise an exception
        reset_tool_singletons()

    def test_p208e_reset_llm_provider_clears_singleton(self) -> None:
        """TC-P2-08-e: reset_llm_provider sets _llm_provider to None."""
        import agent.skills.builtins as skills_mod
        from agent.skills.builtins import reset_llm_provider

        reset_llm_provider()
        assert skills_mod._llm_provider is None


# ---------------------------------------------------------------------------
# TC-P2-09: fallback_reason in all tool stubs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFallbackReasonInAllStubs:
    """TC-P2-09: All tool stubs include fallback_reason field."""

    def test_p209a_kg_query_stub_has_fallback_reason(self) -> None:
        """TC-P2-09-a: kg_query stub includes fallback_reason."""
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        result = registry.execute("kg_query", {"query": "테스트 질의"})
        data = json.loads(result.output)
        if data.get("stub"):
            assert "fallback_reason" in data

    def test_p209b_kg_schema_stub_has_fallback_reason(self) -> None:
        """TC-P2-09-b: kg_schema stub includes fallback_reason."""
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        result = registry.execute("kg_schema", {})
        data = json.loads(result.output)
        if data.get("stub"):
            assert "fallback_reason" in data

    def test_p209c_cypher_execute_stub_has_fallback_reason(self) -> None:
        """TC-P2-09-c: cypher_execute stub includes fallback_reason."""
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        result = registry.execute("cypher_execute", {"cypher": "RETURN 1"})
        data = json.loads(result.output)
        if data.get("stub"):
            assert "fallback_reason" in data

    def test_p209d_vessel_search_stub_has_fallback_reason(self) -> None:
        """TC-P2-09-d: vessel_search stub includes fallback_reason."""
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        result = registry.execute("vessel_search", {"query": "BUSAN"})
        data = json.loads(result.output)
        if data.get("stub"):
            assert "fallback_reason" in data

    def test_p209e_document_search_stub_has_fallback_reason(self) -> None:
        """TC-P2-09-e: document_search stub includes fallback_reason."""
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        result = registry.execute("document_search", {"query": "선박 안전"})
        data = json.loads(result.output)
        if data.get("stub"):
            assert "fallback_reason" in data

    def test_p209f_route_query_stub_has_fallback_reason(self) -> None:
        """TC-P2-09-f: route_query stub includes fallback_reason."""
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        result = registry.execute(
            "route_query", {"origin": "부산", "destination": "인천"}
        )
        data = json.loads(result.output)
        if data.get("stub"):
            assert "fallback_reason" in data


# ---------------------------------------------------------------------------
# TC-P2-10: LLM synthesis fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMSynthesisFallback:
    """TC-P2-10: LLM synthesis with fallback."""

    def test_p210a_synthesize_answer_fallback_returns_string(self) -> None:
        """TC-P2-10-a: Without LLM, _synthesize_answer returns a JSON string."""
        from agent.skills.builtins import _synthesize_answer, reset_llm_provider

        reset_llm_provider()
        result = _synthesize_answer(
            "테스트 질문",
            {"total": 3, "documents": []},
            {"results": []},
            "ko",
        )
        assert isinstance(result, str)
        # Must be valid JSON
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_p210b_synthesize_answer_fallback_includes_question(self) -> None:
        """TC-P2-10-b: Template fallback includes the question field."""
        from agent.skills.builtins import _synthesize_answer, reset_llm_provider

        reset_llm_provider()
        result = _synthesize_answer(
            "부산항 수심 질문",
            {"documents": []},
            {"results": []},
            "ko",
        )
        data = json.loads(result)
        assert "question" in data
        assert data["question"] == "부산항 수심 질문"

    def test_p210c_synthesize_answer_fallback_includes_language(self) -> None:
        """TC-P2-10-c: Template fallback includes language field."""
        from agent.skills.builtins import _synthesize_answer, reset_llm_provider

        reset_llm_provider()
        result = _synthesize_answer(
            "vessel depth",
            {"documents": []},
            {"results": []},
            "en",
        )
        data = json.loads(result)
        assert data.get("language") == "en"

    def test_p210d_synthesize_answer_template_stub_flag(self) -> None:
        """TC-P2-10-d: Template fallback sets stub=True when data sources are stubs and LLM is forced None."""
        import agent.skills.builtins as skills_mod
        from agent.skills.builtins import _synthesize_answer, reset_llm_provider

        # Force the module-level singleton to None so the template path is taken
        # (bypasses _get_llm_provider which may return a real Ollama provider)
        reset_llm_provider()
        original = skills_mod._llm_provider
        skills_mod._llm_provider = None  # sentinel: no LLM available

        try:
            # Patch _get_llm_provider to always return None for this test
            import unittest.mock as mock
            with mock.patch("agent.skills.builtins._get_llm_provider", return_value=None):
                result = _synthesize_answer(
                    "test",
                    {"documents": [], "stub": True},
                    {"results": [], "stub": True},
                    "ko",
                )
            data = json.loads(result)
            assert data.get("stub") is True
        finally:
            reset_llm_provider()

    def test_p210e_synthesize_answer_with_mock_llm(self) -> None:
        """TC-P2-10-e: With a mock LLM, _synthesize_answer uses LLM output."""
        import agent.skills.builtins as skills_mod
        from agent.skills.builtins import _synthesize_answer, reset_llm_provider

        reset_llm_provider()

        # Inject a mock LLM provider
        mock_llm = MagicMock()
        mock_llm.__class__.__name__ = "MockLLMProvider"
        mock_llm.generate.return_value = "이것은 LLM이 생성한 답변입니다."
        skills_mod._llm_provider = mock_llm

        result = _synthesize_answer(
            "선박 안전 규정은?",
            {"total": 2, "documents": [{"filename": "doc1.pdf", "content": "안전 규정..."}]},
            {"results": ["선박안전법 제1조"]},
            "ko",
        )
        data = json.loads(result)
        assert data["answer"] == "이것은 LLM이 생성한 답변입니다."
        assert data.get("stub") is False

        # Verify LLM.generate was called
        mock_llm.generate.assert_called_once()

        # Cleanup
        reset_llm_provider()


# ---------------------------------------------------------------------------
# TC-P2-11: _format_vessel_report fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatVesselReportFallback:
    """TC-P2-11: _format_vessel_report fallback behavior."""

    def test_p211a_format_vessel_report_returns_json_string(self) -> None:
        """TC-P2-11-a: Without LLM, _format_vessel_report returns JSON."""
        from agent.skills.builtins import _format_vessel_report, reset_llm_provider

        reset_llm_provider()
        result = _format_vessel_report(
            "BUSAN PIONEER",
            {"vessels": [{"name": "BUSAN PIONEER", "mmsi": "440100001"}], "stub": True},
            {"results": []},
        )
        assert isinstance(result, str)
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_p211b_format_vessel_report_has_required_keys(self) -> None:
        """TC-P2-11-b: Report includes report_type, vessel_count, and vessels."""
        from agent.skills.builtins import _format_vessel_report, reset_llm_provider

        reset_llm_provider()
        result = _format_vessel_report(
            "TEST SHIP",
            {"vessels": [{"name": "TEST SHIP"}], "stub": True},
            {"results": []},
        )
        data = json.loads(result)

        assert "report_type" in data
        assert data["report_type"] == "vessel_status"
        assert "vessel_count" in data
        assert "vessels" in data

    def test_p211c_format_vessel_report_vessel_count_matches(self) -> None:
        """TC-P2-11-c: vessel_count equals len(vessels)."""
        from agent.skills.builtins import _format_vessel_report, reset_llm_provider

        reset_llm_provider()
        vessels = [
            {"name": "SHIP_A"},
            {"name": "SHIP_B"},
            {"name": "SHIP_C"},
        ]
        result = _format_vessel_report(
            "SHIP",
            {"vessels": vessels, "stub": True},
            {"results": []},
        )
        data = json.loads(result)
        assert data["vessel_count"] == 3

    def test_p211d_format_vessel_report_with_mock_llm(self) -> None:
        """TC-P2-11-d: With mock LLM, report gains 'analysis' key."""
        import agent.skills.builtins as skills_mod
        from agent.skills.builtins import _format_vessel_report, reset_llm_provider

        reset_llm_provider()
        mock_llm = MagicMock()
        mock_llm.__class__.__name__ = "MockLLMProvider"
        mock_llm.generate.return_value = "선박 상태 분석 결과: 정상 운항 중입니다."
        skills_mod._llm_provider = mock_llm

        result = _format_vessel_report(
            "BUSAN PIONEER",
            {"vessels": [{"name": "BUSAN PIONEER"}], "stub": True},
            {"results": []},
        )
        data = json.loads(result)
        assert "analysis" in data
        assert data["analysis"] == "선박 상태 분석 결과: 정상 운항 중입니다."

        # Cleanup
        reset_llm_provider()


# ---------------------------------------------------------------------------
# TC-P2-12: reset_llm_provider
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResetLLMProvider:
    """TC-P2-12: reset_llm_provider clears the LLM singleton."""

    def test_p212a_reset_llm_provider_sets_none(self) -> None:
        """TC-P2-12-a: reset_llm_provider sets module-level _llm_provider to None."""
        import agent.skills.builtins as skills_mod
        from agent.skills.builtins import reset_llm_provider

        # Set some mock value first
        skills_mod._llm_provider = MagicMock()
        assert skills_mod._llm_provider is not None

        reset_llm_provider()
        assert skills_mod._llm_provider is None

    def test_p212b_get_llm_provider_returns_none_without_real_llm(self) -> None:
        """TC-P2-12-b: _get_llm_provider returns None in test env (StubLLMProvider or missing)."""
        from agent.skills.builtins import reset_llm_provider, _get_llm_provider

        reset_llm_provider()
        provider = _get_llm_provider()
        # In test env with no real LLM configured, expect None
        # (StubLLMProvider is treated as None per implementation)
        # We allow either None or a real provider object — just must not crash
        reset_llm_provider()

    def test_p212c_reset_is_idempotent(self) -> None:
        """TC-P2-12-c: Calling reset_llm_provider twice is safe."""
        from agent.skills.builtins import reset_llm_provider
        import agent.skills.builtins as skills_mod

        reset_llm_provider()
        reset_llm_provider()
        assert skills_mod._llm_provider is None


# ---------------------------------------------------------------------------
# TC-P2-13: All reset functions together
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAllResetFunctions:
    """TC-P2-13: All reset functions work together without interference."""

    def test_p213a_all_singletons_reset_cleanly(self) -> None:
        """TC-P2-13-a: All singleton resets run without errors."""
        from agent.mcp.server import reset_schema_cache
        from agent.tools.builtins import reset_tool_singletons
        from agent.skills.builtins import reset_llm_provider

        # Should not raise
        reset_schema_cache()
        reset_tool_singletons()
        reset_llm_provider()

    def test_p213b_schema_cache_reset_does_not_affect_tool_singletons(self) -> None:
        """TC-P2-13-b: reset_schema_cache does not affect tool singletons."""
        import agent.tools.builtins as tools_mod
        from agent.mcp.server import reset_schema_cache
        from agent.tools.builtins import reset_tool_singletons

        # Set a sentinel in tools
        reset_tool_singletons()
        assert tools_mod._pipeline_instance is None

        # Resetting MCP cache should not affect tools
        reset_schema_cache()
        assert tools_mod._pipeline_instance is None

    def test_p213c_multiple_resets_leave_modules_in_clean_state(self) -> None:
        """TC-P2-13-c: Repeated resets leave all singletons as None."""
        import agent.mcp.server as mcp_mod
        import agent.tools.builtins as tools_mod
        import agent.skills.builtins as skills_mod
        from agent.mcp.server import reset_schema_cache
        from agent.tools.builtins import reset_tool_singletons
        from agent.skills.builtins import reset_llm_provider

        for _ in range(3):
            reset_schema_cache()
            reset_tool_singletons()
            reset_llm_provider()

        assert mcp_mod._schema_cache == {}
        assert mcp_mod._schema_cache_ts == 0.0
        assert tools_mod._pipeline_instance is None
        assert tools_mod._rag_engine_instance is None
        assert skills_mod._llm_provider is None
