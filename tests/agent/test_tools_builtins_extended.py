"""Extended unit tests for agent/tools/builtins.py.

Covers missed lines (98 statements) not exercised by test_builtin_tools.py:
  - _run_cypher(): neo4j session mock, node/relationship serialization, LIMIT injection,
    COUNT/COLLECT bypass, exception propagation
  - _handle_kg_query(): strategy-1 pipeline success + execution error,
    strategy-2 direct cypher, strategy-3 stub
  - _handle_kg_schema(): real neo4j path (all labels, specific label, invalid label,
    non-identifier label, prop query failure)
  - _handle_cypher_execute(): danger-blocked + real neo4j success
  - _handle_vessel_search(): CypherBuilder real path, node with properties, plain row
  - _handle_document_search(): real RAG engine path
  - _handle_route_query(): real neo4j path with routes
  - _get_pipeline() / _get_rag_engine(): singleton caching + ImportError fallback
  - reset_tool_singletons()
  - _is_dangerous(): each dangerous pattern
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_record(data: dict[str, Any]) -> MagicMock:
    """Build a mock neo4j record that behaves like record[key]."""
    rec = MagicMock()
    rec.keys.return_value = list(data.keys())
    rec.__getitem__ = lambda self, k: data[k]
    return rec


def _make_driver_and_cfg(records: list[MagicMock] | None = None):
    """Build mock neo4j driver + config from a list of pre-built record mocks."""
    records = records or []
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.__iter__ = lambda s: iter(records)
    mock_session.run.return_value = mock_result
    mock_session.__enter__ = lambda s: mock_session
    mock_session.__exit__ = MagicMock(return_value=False)

    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    mock_cfg = MagicMock()
    mock_cfg.neo4j.database = "neo4j"

    return mock_driver, mock_cfg, mock_session


# ---------------------------------------------------------------------------
# _is_dangerous() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsDangerous:
    """Direct tests for the danger-detection regex patterns."""

    def _call(self, cypher: str):
        from agent.tools.builtins import _is_dangerous
        return _is_dangerous(cypher)

    def test_drop_is_dangerous(self):
        ok, reason = self._call("DROP INDEX ON :Vessel(name)")
        assert ok is True
        assert reason != ""

    def test_detach_delete_without_where_is_dangerous(self):
        ok, _ = self._call("MATCH (n:Vessel) DETACH DELETE n")
        assert ok is True

    def test_delete_without_where_is_dangerous(self):
        ok, _ = self._call("MATCH (n) DELETE n")
        assert ok is True

    def test_apoc_schema_is_dangerous(self):
        ok, _ = self._call("CALL apoc.schema.assert({},{})")
        assert ok is True

    def test_apoc_trigger_is_dangerous(self):
        ok, _ = self._call("CALL apoc.trigger.add('t', '', {})")
        assert ok is True

    def test_db_create_is_dangerous(self):
        ok, _ = self._call("CALL db.create()")
        assert ok is True

    def test_safe_match_not_dangerous(self):
        ok, _ = self._call("MATCH (n:Vessel) WHERE n.mmsi = $m RETURN n")
        assert ok is False

    def test_empty_query_not_dangerous(self):
        ok, _ = self._call("")
        assert ok is False


# ---------------------------------------------------------------------------
# _run_cypher() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunCypher:
    """Tests for _run_cypher() with mocked neo4j driver.

    _run_cypher() uses a local import:
        from core.kg.config import get_config, get_driver
    so we patch core.kg.config.get_driver / core.kg.config.get_config.
    """

    def test_run_cypher_simple_scalar_record(self):
        """Scalar (non-node/rel) values are returned as-is."""
        records = [_fake_record({"count": 42})]
        mock_driver, mock_cfg, _ = _make_driver_and_cfg(records)

        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            rows = _run_cypher("MATCH (n) RETURN count(n) AS count")

        assert rows == [{"count": 42}]

    def test_run_cypher_injects_limit_when_absent(self):
        """LIMIT is appended to a plain MATCH query."""
        mock_driver, mock_cfg, mock_session = _make_driver_and_cfg([])

        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            _run_cypher("MATCH (n:Vessel) RETURN n")

        called_query = mock_session.run.call_args[0][0]
        assert "LIMIT" in called_query.upper()

    def test_run_cypher_does_not_inject_limit_when_present(self):
        """LIMIT is NOT added when query already contains LIMIT."""
        mock_driver, mock_cfg, mock_session = _make_driver_and_cfg([])

        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            _run_cypher("MATCH (n) RETURN n LIMIT 5")

        called_query = mock_session.run.call_args[0][0]
        assert called_query.upper().count("LIMIT") == 1

    def test_run_cypher_does_not_inject_limit_for_count(self):
        """COUNT( in query bypasses LIMIT injection."""
        mock_driver, mock_cfg, mock_session = _make_driver_and_cfg([])

        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            _run_cypher("RETURN COUNT(n)")

        called_query = mock_session.run.call_args[0][0]
        assert "LIMIT" not in called_query.upper()

    def test_run_cypher_does_not_inject_limit_for_collect(self):
        """COLLECT( in query bypasses LIMIT injection."""
        mock_driver, mock_cfg, mock_session = _make_driver_and_cfg([])

        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            _run_cypher("RETURN COLLECT(n.name)")

        called_query = mock_session.run.call_args[0][0]
        assert "LIMIT" not in called_query.upper()

    def test_run_cypher_serializes_node_objects(self):
        """Neo4j Node objects (has element_id + labels, but NOT type) are serialized."""
        # spec limits available attributes so hasattr(node, 'type') → False
        # Neo4j Node is dict-like: dict(node) yields properties
        class FakeNode:
            element_id = "4:abc:1"
            labels = ["Vessel"]
            _props = {"mmsi": "440100001", "name": "TEST"}
            def __iter__(self):
                return iter(self._props)
            def __getitem__(self, k):
                return self._props[k]
            def keys(self):
                return self._props.keys()
        node_spec = FakeNode()

        rec = MagicMock()
        rec.keys.return_value = ["v"]
        rec.__getitem__ = lambda s, k: node_spec if k == "v" else None

        mock_driver, mock_cfg, mock_session = _make_driver_and_cfg()
        mock_result = MagicMock()
        mock_result.__iter__ = lambda s: iter([rec])
        mock_session.run.return_value = mock_result

        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            rows = _run_cypher("MATCH (v:Vessel) RETURN v")

        assert len(rows) == 1
        serialized = rows[0]["v"]
        assert serialized["id"] == "4:abc:1"
        assert serialized["labels"] == ["Vessel"]
        assert "properties" in serialized

    def test_run_cypher_serializes_relationship_objects(self):
        """Neo4j Relationship objects (has element_id + type) are serialized."""
        # spec gives element_id AND type, but NOT labels → relationship branch
        # Neo4j Relationship is dict-like: dict(rel) yields properties
        class FakeRel:
            element_id = "5:abc:99"
            type = "DOCKED_AT"
            _props = {"since": "2024-01-01"}
            def __iter__(self):
                return iter(self._props)
            def __getitem__(self, k):
                return self._props[k]
            def keys(self):
                return self._props.keys()
        rel_spec = FakeRel()

        rec = MagicMock()
        rec.keys.return_value = ["r"]
        rec.__getitem__ = lambda s, k: rel_spec if k == "r" else None

        mock_driver, mock_cfg, mock_session = _make_driver_and_cfg()
        mock_result = MagicMock()
        mock_result.__iter__ = lambda s: iter([rec])
        mock_session.run.return_value = mock_result

        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            rows = _run_cypher("MATCH ()-[r]->() RETURN r")

        assert len(rows) == 1
        serialized = rows[0]["r"]
        assert serialized["id"] == "5:abc:99"
        assert serialized["type"] == "DOCKED_AT"

    def test_run_cypher_raises_on_exception(self):
        """If session.run() raises, _run_cypher lets the exception propagate."""
        mock_session = MagicMock()
        mock_session.run.side_effect = RuntimeError("connection refused")
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_cfg = MagicMock()
        mock_cfg.neo4j.database = "neo4j"

        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            with pytest.raises(RuntimeError, match="connection refused"):
                _run_cypher("MATCH (n) RETURN n")

    def test_run_cypher_passes_parameters(self):
        """Parameters dict is forwarded to session.run() as second positional arg."""
        mock_driver, mock_cfg, mock_session = _make_driver_and_cfg([])

        params = {"name": "부산"}
        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            _run_cypher("MATCH (n) WHERE n.name = $name RETURN n LIMIT 1", params)

        assert mock_session.run.call_args[0][1] == params

    def test_run_cypher_max_results_truncates(self):
        """max_results slices the result list down to the requested size."""
        records = [_fake_record({"i": i}) for i in range(5)]
        mock_driver, mock_cfg, _ = _make_driver_and_cfg(records)

        with (
            patch("core.kg.config.get_driver", return_value=mock_driver),
            patch("core.kg.config.get_config", return_value=mock_cfg),
        ):
            from agent.tools.builtins import _run_cypher
            rows = _run_cypher("MATCH (n) RETURN n LIMIT 5", max_results=3)

        assert len(rows) == 3


# ---------------------------------------------------------------------------
# _get_pipeline() / _get_rag_engine() singleton tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSingletonGetters:
    """Tests for _get_pipeline() and _get_rag_engine() singleton factories."""

    def setup_method(self):
        from agent.tools.builtins import reset_tool_singletons
        reset_tool_singletons()

    def teardown_method(self):
        from agent.tools.builtins import reset_tool_singletons
        reset_tool_singletons()

    def test_get_pipeline_returns_none_on_exception(self):
        """If TextToCypherPipeline constructor raises, _get_pipeline returns None."""
        mock_module = MagicMock()
        mock_module.TextToCypherPipeline.side_effect = ImportError("not available")

        with patch.dict("sys.modules", {"core.kg.pipeline": mock_module}):
            import agent.tools.builtins as bmod
            bmod._pipeline_instance = None  # ensure fresh
            result = bmod._get_pipeline()

        assert result is None

    def test_get_pipeline_caches_instance(self):
        """Second call returns the same object without constructing a new one."""
        mock_pipeline = MagicMock()
        mock_module = MagicMock()
        mock_module.TextToCypherPipeline.return_value = mock_pipeline

        with patch.dict("sys.modules", {"core.kg.pipeline": mock_module}):
            import agent.tools.builtins as bmod
            bmod._pipeline_instance = None
            first = bmod._get_pipeline()
            second = bmod._get_pipeline()

        assert first is second
        assert mock_module.TextToCypherPipeline.call_count == 1

    def test_get_rag_engine_returns_none_on_exception(self):
        """If HybridRAGEngine constructor raises, _get_rag_engine returns None."""
        mock_module = MagicMock()
        mock_module.HybridRAGEngine.side_effect = ImportError("not available")

        with patch.dict("sys.modules", {"rag.engines.orchestrator": mock_module}):
            import agent.tools.builtins as bmod
            bmod._rag_engine_instance = None
            result = bmod._get_rag_engine()

        assert result is None

    def test_get_rag_engine_caches_instance(self):
        """Second call reuses the cached engine instance."""
        mock_engine = MagicMock()
        mock_module = MagicMock()
        mock_module.HybridRAGEngine.return_value = mock_engine

        with patch.dict("sys.modules", {"rag.engines.orchestrator": mock_module}):
            import agent.tools.builtins as bmod
            bmod._rag_engine_instance = None
            first = bmod._get_rag_engine()
            second = bmod._get_rag_engine()

        assert first is second
        assert mock_module.HybridRAGEngine.call_count == 1

    def test_reset_tool_singletons_clears_both(self):
        """After reset, both module-level singletons are set to None."""
        import agent.tools.builtins as bmod
        bmod._pipeline_instance = object()
        bmod._rag_engine_instance = object()
        bmod.reset_tool_singletons()
        assert bmod._pipeline_instance is None
        assert bmod._rag_engine_instance is None


# ---------------------------------------------------------------------------
# _handle_kg_query() tests — 3-strategy fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleKgQuery:
    """Tests for the 3-strategy fallback in _handle_kg_query()."""

    def setup_method(self):
        from agent.tools.builtins import reset_tool_singletons
        reset_tool_singletons()

    def teardown_method(self):
        from agent.tools.builtins import reset_tool_singletons
        reset_tool_singletons()

    def _make_pipeline_output(
        self,
        success: bool,
        query: str | None = None,
        error: str | None = None,
    ) -> MagicMock:
        output = MagicMock()
        output.success = success
        output.error = error
        if query is not None:
            output.generated_query = MagicMock()
            output.generated_query.query = query
            output.generated_query.parameters = {}
        else:
            output.generated_query = None
        return output

    def test_strategy1_pipeline_success_no_generated_query(self):
        """Pipeline succeeds but returns no generated_query → results stay empty."""
        output = self._make_pipeline_output(success=True, query=None)
        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = output

        with patch("agent.tools.builtins._get_pipeline", return_value=mock_pipeline):
            from agent.tools.builtins import _handle_kg_query
            json_str = _handle_kg_query("선박 검색", "ko")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["success"] is True
        assert data["results"] == []

    def test_strategy1_pipeline_success_with_cypher_execution(self):
        """Pipeline succeeds and generated_query runs → rows returned."""
        output = self._make_pipeline_output(success=True, query="MATCH (v:Vessel) RETURN v")
        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = output

        mock_rows = [{"v": {"id": "1", "labels": ["Vessel"], "properties": {"name": "TEST"}}}]

        with (
            patch("agent.tools.builtins._get_pipeline", return_value=mock_pipeline),
            patch("agent.tools.builtins._run_cypher", return_value=mock_rows),
        ):
            from agent.tools.builtins import _handle_kg_query
            json_str = _handle_kg_query("선박 목록", "ko")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["results"] == mock_rows

    def test_strategy1_pipeline_success_cypher_execution_error(self):
        """Pipeline succeeds but Cypher execution fails → execution_error set."""
        output = self._make_pipeline_output(success=True, query="MATCH (v) RETURN v")
        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = output

        with (
            patch("agent.tools.builtins._get_pipeline", return_value=mock_pipeline),
            patch("agent.tools.builtins._run_cypher", side_effect=RuntimeError("db down")),
        ):
            from agent.tools.builtins import _handle_kg_query
            json_str = _handle_kg_query("질의", "ko")

        data = json.loads(json_str)
        assert "execution_error" in data
        assert data["stub"] is False

    def test_strategy1_pipeline_failure_error_field_propagated(self):
        """Pipeline returns success=False with error → error field in result."""
        output = self._make_pipeline_output(success=False, query=None, error="parse_failed")
        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = output

        with patch("agent.tools.builtins._get_pipeline", return_value=mock_pipeline):
            from agent.tools.builtins import _handle_kg_query
            json_str = _handle_kg_query("bad query", "ko")

        data = json.loads(json_str)
        assert data["error"] == "parse_failed"
        assert data["stub"] is False

    def test_strategy2_direct_cypher_when_pipeline_returns_none(self):
        """When _get_pipeline returns None (ImportError path), strategy-2 fires."""
        mock_rows = [{"n": {"name": "부산항"}}]

        with (
            patch("agent.tools.builtins._get_pipeline", return_value=None),
            patch("agent.tools.builtins._run_cypher", return_value=mock_rows),
        ):
            from agent.tools.builtins import _handle_kg_query
            json_str = _handle_kg_query("부산항", "ko")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["results"] == mock_rows

    def test_strategy3_stub_when_all_backends_fail(self):
        """When both pipeline and Neo4j fail, returns stub=True fallback."""
        with (
            patch("agent.tools.builtins._get_pipeline", return_value=None),
            patch("agent.tools.builtins._run_cypher", side_effect=RuntimeError("no neo4j")),
        ):
            from agent.tools.builtins import _handle_kg_query
            json_str = _handle_kg_query("선박", "en")

        data = json.loads(json_str)
        assert data["stub"] is True
        assert data["language"] == "en"
        assert data["fallback_reason"] == "neo4j_unavailable"

    def test_strategy1_pipeline_exception_falls_to_strategy2(self):
        """If pipeline.process() raises (non-ImportError), strategy-2 is tried."""
        mock_pipeline = MagicMock()
        mock_pipeline.process.side_effect = ValueError("unexpected error")

        mock_rows = [{"n": {"name": "test"}}]
        with (
            patch("agent.tools.builtins._get_pipeline", return_value=mock_pipeline),
            patch("agent.tools.builtins._run_cypher", return_value=mock_rows),
        ):
            from agent.tools.builtins import _handle_kg_query
            json_str = _handle_kg_query("test query", "en")

        data = json.loads(json_str)
        assert data["stub"] is False

    def test_strategy1_language_field_preserved(self):
        """Language parameter is preserved in the result regardless of pipeline result."""
        output = self._make_pipeline_output(success=True, query=None)
        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = output

        with patch("agent.tools.builtins._get_pipeline", return_value=mock_pipeline):
            from agent.tools.builtins import _handle_kg_query
            json_str = _handle_kg_query("query", "en")

        data = json.loads(json_str)
        assert data["language"] == "en"


# ---------------------------------------------------------------------------
# _handle_kg_schema() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleKgSchema:
    """Tests for _handle_kg_schema() real and stub paths."""

    def _make_schema_side_effect(
        self,
        labels: list[str],
        rel_types: list[str],
        per_label_props: dict[str, list[str]] | None = None,
    ):
        """Return a callable for use as _run_cypher side_effect."""
        per_label_props = per_label_props or {}

        def side_effect(cypher: str, *args, **kwargs):
            if "db.labels" in cypher:
                return [{"labels": labels}]
            elif "db.relationshipTypes" in cypher:
                return [{"types": rel_types}]
            elif "collect(DISTINCT k)" in cypher:
                # Specific-label properties query
                for lbl, props in per_label_props.items():
                    if f"`{lbl}`" in cypher or lbl in cypher:
                        return [{"properties": props}]
                return [{"properties": []}]
            else:
                # per-label loop: MATCH (n:`LBL`) RETURN keys(n) AS props LIMIT 1
                for lbl, props in per_label_props.items():
                    if f"`{lbl}`" in cypher:
                        return [{"props": props}]
                return []

        return side_effect

    def test_schema_real_path_returns_all_labels_and_rel_types(self):
        """Real neo4j path: returns node_labels, rel_types, stub=False."""
        side_effect = self._make_schema_side_effect(
            labels=["Vessel", "Port"],
            rel_types=["DOCKED_AT", "SAILED_TO"],
            per_label_props={"Vessel": ["mmsi", "name"], "Port": ["portId", "name"]},
        )
        with patch("agent.tools.builtins._run_cypher", side_effect=side_effect):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema()

        data = json.loads(json_str)
        assert data["stub"] is False
        assert "Vessel" in data["node_labels"]
        assert "DOCKED_AT" in data["relationship_types"]

    def test_schema_specific_label_found(self):
        """Query with specific label that exists returns property list."""
        side_effect = self._make_schema_side_effect(
            labels=["Vessel", "Port"],
            rel_types=["DOCKED_AT"],
            per_label_props={"Vessel": ["mmsi", "name"]},
        )
        with patch("agent.tools.builtins._run_cypher", side_effect=side_effect):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema(label="Vessel")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["label"] == "Vessel"
        assert "mmsi" in data["properties"]

    def test_schema_specific_label_not_in_db_returns_error(self):
        """Requesting a label not returned by db.labels() gives error dict."""
        side_effect = self._make_schema_side_effect(
            labels=["Vessel"],
            rel_types=[],
        )
        with patch("agent.tools.builtins._run_cypher", side_effect=side_effect):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema(label="NonExistentLabel")

        data = json.loads(json_str)
        assert "error" in data
        assert "NonExistentLabel" in data["error"]
        assert data["stub"] is False

    def test_schema_label_with_invalid_identifier_format_returns_error(self):
        """Label that passes db.labels() but fails isidentifier() check."""
        side_effect = self._make_schema_side_effect(
            labels=["123-Invalid"],
            rel_types=[],
        )
        with patch("agent.tools.builtins._run_cypher", side_effect=side_effect):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema(label="123-Invalid")

        data = json.loads(json_str)
        assert "error" in data

    def test_schema_loop_skips_non_identifier_labels(self):
        """Labels failing isidentifier() are skipped in the properties-fetch loop."""
        side_effect = self._make_schema_side_effect(
            labels=["Vessel", "123BadLabel"],
            rel_types=[],
            per_label_props={"Vessel": ["name"]},
        )
        with patch("agent.tools.builtins._run_cypher", side_effect=side_effect):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema()

        data = json.loads(json_str)
        assert "123BadLabel" not in data.get("properties", {})
        assert data["stub"] is False

    def test_schema_prop_query_exception_gives_empty_list(self):
        """If the per-label property query raises, that label gets empty list."""
        call_num = [0]

        def mock_run(cypher: str, *args, **kwargs):
            call_num[0] += 1
            if "db.labels" in cypher:
                return [{"labels": ["Vessel"]}]
            elif "db.relationshipTypes" in cypher:
                return [{"types": []}]
            else:
                raise RuntimeError("props query failed")

        with patch("agent.tools.builtins._run_cypher", side_effect=mock_run):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema()

        data = json.loads(json_str)
        assert data["properties"].get("Vessel") == []

    def test_schema_stub_when_neo4j_unavailable(self):
        """When _run_cypher raises immediately, stub data with known labels returned."""
        with patch("agent.tools.builtins._run_cypher", side_effect=RuntimeError("no db")):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema()

        data = json.loads(json_str)
        assert data["stub"] is True
        assert "Vessel" in data["node_labels"]

    def test_schema_stub_specific_known_label(self):
        """Stub fallback with a label present in stub data returns properties."""
        with patch("agent.tools.builtins._run_cypher", side_effect=RuntimeError("no db")):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema(label="Vessel")

        data = json.loads(json_str)
        assert data["stub"] is True
        assert data["label"] == "Vessel"
        assert isinstance(data["properties"], list)

    def test_schema_stub_unknown_label_returns_error(self):
        """Stub fallback with label not in stub data returns error dict."""
        with patch("agent.tools.builtins._run_cypher", side_effect=RuntimeError("no db")):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema(label="UnknownXYZ")

        data = json.loads(json_str)
        assert "error" in data
        assert data["stub"] is True

    def test_schema_real_path_empty_labels_list(self):
        """When db.labels() returns empty list, node_labels and properties are empty."""
        def mock_run(cypher: str, *args, **kwargs):
            if "db.labels" in cypher:
                return []
            elif "db.relationshipTypes" in cypher:
                return []
            return []

        with patch("agent.tools.builtins._run_cypher", side_effect=mock_run):
            from agent.tools.builtins import _handle_kg_schema
            json_str = _handle_kg_schema()

        data = json.loads(json_str)
        assert data["node_labels"] == []
        assert data["relationship_types"] == []
        assert data["stub"] is False


# ---------------------------------------------------------------------------
# _handle_cypher_execute() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleCypherExecute:
    """Tests for _handle_cypher_execute() — danger blocking + real neo4j path."""

    def test_dangerous_query_is_blocked(self):
        """DROP query returns blocked=True without touching neo4j."""
        from agent.tools.builtins import _handle_cypher_execute
        json_str = _handle_cypher_execute("DROP INDEX ON :Vessel(name)")
        data = json.loads(json_str)
        assert data["blocked"] is True
        assert "error" in data

    def test_safe_query_uses_real_neo4j(self):
        """Safe MATCH query goes through _run_cypher and returns stub=False."""
        mock_rows = [{"n": {"id": "1", "labels": ["Vessel"], "properties": {}}}]
        with patch("agent.tools.builtins._run_cypher", return_value=mock_rows):
            from agent.tools.builtins import _handle_cypher_execute
            json_str = _handle_cypher_execute("MATCH (n:Vessel) RETURN n LIMIT 1")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["rows"] == mock_rows
        assert data["row_count"] == 1

    def test_cypher_execute_parameters_forwarded(self):
        """Parameters are forwarded to _run_cypher."""
        with patch("agent.tools.builtins._run_cypher", return_value=[]) as mock_rc:
            from agent.tools.builtins import _handle_cypher_execute
            _handle_cypher_execute(
                "MATCH (n) WHERE n.mmsi=$m RETURN n",
                {"m": "440"},
            )
        mock_rc.assert_called_once_with(
            "MATCH (n) WHERE n.mmsi=$m RETURN n", {"m": "440"}
        )

    def test_cypher_execute_stub_fallback_on_exception(self):
        """When _run_cypher raises, returns stub=True."""
        with patch("agent.tools.builtins._run_cypher", side_effect=RuntimeError("db error")):
            from agent.tools.builtins import _handle_cypher_execute
            json_str = _handle_cypher_execute("MATCH (n) RETURN n LIMIT 1")

        data = json.loads(json_str)
        assert data["stub"] is True
        assert data["fallback_reason"] == "neo4j_unavailable"

    def test_detach_delete_is_blocked(self):
        """DETACH DELETE query is blocked."""
        from agent.tools.builtins import _handle_cypher_execute
        json_str = _handle_cypher_execute("MATCH (n) DETACH DELETE n")
        data = json.loads(json_str)
        assert data["blocked"] is True


# ---------------------------------------------------------------------------
# _handle_vessel_search() — CypherBuilder real path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleVesselSearchRealPath:
    """Tests for _handle_vessel_search() CypherBuilder real neo4j path."""

    def _make_builder(self, cypher: str = "MATCH (v:Vessel) RETURN v", params: dict | None = None):
        """Create a chainable mock CypherBuilder that produces a known query."""
        builder = MagicMock()
        builder.match.return_value = builder
        builder.where.return_value = builder
        builder.return_.return_value = builder
        builder.limit.return_value = builder
        builder.build.return_value = (cypher, params or {})
        return builder

    def test_vessel_search_real_path_with_node_properties(self):
        """CypherBuilder path extracts properties from nested 'properties' key."""
        builder = self._make_builder()
        rows = [{"v": {"id": "1", "labels": ["Vessel"], "properties": {"name": "TEST", "mmsi": "440"}}}]

        with (
            patch("core.kg.cypher_builder.CypherBuilder", return_value=builder),
            patch("agent.tools.builtins._run_cypher", return_value=rows),
        ):
            from agent.tools.builtins import _handle_vessel_search
            json_str = _handle_vessel_search("TEST", "name")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["count"] == 1
        assert data["vessels"][0]["name"] == "TEST"

    def test_vessel_search_real_path_plain_row_no_properties_key(self):
        """Row without 'properties' key is returned as-is (plain dict)."""
        builder = self._make_builder()
        rows = [{"v": {"name": "PLAIN", "mmsi": "999"}}]

        with (
            patch("core.kg.cypher_builder.CypherBuilder", return_value=builder),
            patch("agent.tools.builtins._run_cypher", return_value=rows),
        ):
            from agent.tools.builtins import _handle_vessel_search
            json_str = _handle_vessel_search("PLAIN", "name")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["vessels"][0]["name"] == "PLAIN"

    def test_vessel_search_mmsi_search_type(self):
        """CypherBuilder where() is called with mmsi condition."""
        builder = self._make_builder()
        rows: list = []

        with (
            patch("core.kg.cypher_builder.CypherBuilder", return_value=builder),
            patch("agent.tools.builtins._run_cypher", return_value=rows),
        ):
            from agent.tools.builtins import _handle_vessel_search
            json_str = _handle_vessel_search("440100001", "mmsi")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["search_type"] == "mmsi"
        # Check where was called with mmsi condition
        where_calls = [str(c) for c in builder.where.call_args_list]
        assert any("mmsi" in c for c in where_calls)

    def test_vessel_search_imo_search_type(self):
        """CypherBuilder where() is called with imo condition."""
        builder = self._make_builder()
        rows: list = []

        with (
            patch("core.kg.cypher_builder.CypherBuilder", return_value=builder),
            patch("agent.tools.builtins._run_cypher", return_value=rows),
        ):
            from agent.tools.builtins import _handle_vessel_search
            json_str = _handle_vessel_search("IMO9876543", "imo")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["search_type"] == "imo"

    def test_vessel_search_invalid_search_type_defaults_to_name(self):
        """Invalid search_type is normalized to 'name' before execution."""
        with patch("agent.tools.builtins._run_cypher", side_effect=RuntimeError("no db")):
            from agent.tools.builtins import _handle_vessel_search
            json_str = _handle_vessel_search("BUSAN", "invalid_type")

        data = json.loads(json_str)
        assert data["search_type"] == "name"

    def test_vessel_search_stub_when_run_cypher_fails(self):
        """If _run_cypher raises after building query, falls back to stub."""
        builder = self._make_builder()

        with (
            patch("core.kg.cypher_builder.CypherBuilder", return_value=builder),
            patch("agent.tools.builtins._run_cypher", side_effect=RuntimeError("db down")),
        ):
            from agent.tools.builtins import _handle_vessel_search
            json_str = _handle_vessel_search("BUSAN", "name")

        data = json.loads(json_str)
        assert data["stub"] is True


# ---------------------------------------------------------------------------
# _handle_document_search() — real RAG engine path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleDocumentSearchRealPath:
    """Tests for _handle_document_search() with real RAG engine mocked."""

    def setup_method(self):
        from agent.tools.builtins import reset_tool_singletons
        reset_tool_singletons()

    def teardown_method(self):
        from agent.tools.builtins import reset_tool_singletons
        reset_tool_singletons()

    def test_document_search_real_engine_path(self):
        """Real engine path returns answer, documents, duration_ms, stub=False."""
        mock_chunk = MagicMock()
        mock_chunk.chunk_id = "chunk-001"
        mock_chunk.content = "SOLAS 규정에 따르면..."
        mock_chunk.metadata = {"source": "solas.pdf"}

        mock_rc = MagicMock()
        mock_rc.chunk = mock_chunk
        mock_rc.score = 0.92

        mock_rag_result = MagicMock()
        mock_rag_result.retrieved_chunks = [mock_rc]
        mock_rag_result.answer = "SOLAS 규정은..."
        mock_rag_result.duration_ms = 150.0

        mock_engine = MagicMock()
        mock_engine.query.return_value = mock_rag_result

        with patch("agent.tools.builtins._get_rag_engine", return_value=mock_engine):
            from agent.tools.builtins import _handle_document_search
            json_str = _handle_document_search("SOLAS 규정", top_k=3)

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["answer"] == "SOLAS 규정은..."
        assert len(data["documents"]) == 1
        assert data["documents"][0]["chunk_id"] == "chunk-001"
        assert data["documents"][0]["score"] == 0.92
        assert data["top_k"] == 3

    def test_document_search_engine_exception_falls_to_stub(self):
        """If engine.query() raises, falls back to stub."""
        mock_engine = MagicMock()
        mock_engine.query.side_effect = RuntimeError("rag engine error")

        with patch("agent.tools.builtins._get_rag_engine", return_value=mock_engine):
            from agent.tools.builtins import _handle_document_search
            json_str = _handle_document_search("query", top_k=5)

        data = json.loads(json_str)
        assert data["stub"] is True

    def test_document_search_none_engine_falls_to_stub(self):
        """If _get_rag_engine() returns None (ImportError path), stub returned."""
        with patch("agent.tools.builtins._get_rag_engine", return_value=None):
            from agent.tools.builtins import _handle_document_search
            json_str = _handle_document_search("query")

        data = json.loads(json_str)
        assert data["stub"] is True
        assert data["fallback_reason"] == "import_error"


# ---------------------------------------------------------------------------
# _handle_route_query() — real neo4j path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleRouteQueryRealPath:
    """Tests for _handle_route_query() real neo4j path."""

    def test_route_query_real_path_with_route_rows(self):
        """When neo4j returns rows with relationship, parses route properties."""
        mock_rows = [
            {
                "o": {"name": "부산항"},
                "r": {
                    "id": "rel-1",
                    "type": "SAILED_TO",
                    "properties": {"distance": 1500, "estimatedDays": 3},
                },
                "d": {"name": "도쿄항"},
            }
        ]
        with patch("agent.tools.builtins._run_cypher", return_value=mock_rows):
            from agent.tools.builtins import _handle_route_query
            json_str = _handle_route_query("부산", "도쿄")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["origin"] == "부산"
        assert data["destination"] == "도쿄"
        assert data["count"] == 1
        assert data["routes"][0]["distance"] == 1500
        assert data["routes"][0]["type"] == "SAILED_TO"

    def test_route_query_empty_rows_falls_to_stub(self):
        """When neo4j returns empty rows list, stub fallback fires."""
        with patch("agent.tools.builtins._run_cypher", return_value=[]):
            from agent.tools.builtins import _handle_route_query
            json_str = _handle_route_query("부산", "싱가포르")

        data = json.loads(json_str)
        assert data["stub"] is True

    def test_route_query_stub_routeid_format(self):
        """Stub routeId uses first 3 chars of origin/destination uppercased."""
        with patch("agent.tools.builtins._run_cypher", side_effect=RuntimeError("no db")):
            from agent.tools.builtins import _handle_route_query
            json_str = _handle_route_query("부산", "싱가포르")

        data = json.loads(json_str)
        assert data["stub"] is True
        route_id = data["routes"][0]["routeId"]
        assert route_id.startswith("ROUTE_")
        assert data["fallback_reason"] == "neo4j_unavailable"

    def test_route_query_row_without_relationship_properties(self):
        """Row where 'r' is not a dict with 'properties' key yields empty route_info."""
        mock_rows = [{"o": {}, "r": "not_a_dict", "d": {}}]
        with patch("agent.tools.builtins._run_cypher", return_value=mock_rows):
            from agent.tools.builtins import _handle_route_query
            json_str = _handle_route_query("A", "B")

        data = json.loads(json_str)
        assert data["stub"] is False
        assert data["routes"] == [{}]


# ---------------------------------------------------------------------------
# Registry integration — dispatch verification with mocked handlers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRegistryDispatch:
    """Verify create_builtin_registry() dispatches correctly to each handler."""

    def setup_method(self):
        from agent.tools.builtins import reset_tool_singletons
        reset_tool_singletons()

    def teardown_method(self):
        from agent.tools.builtins import reset_tool_singletons
        reset_tool_singletons()

    def test_registry_kg_query_dispatches_to_handler(self):
        """registry.execute('kg_query') calls _handle_kg_query."""
        with patch("agent.tools.builtins._handle_kg_query", return_value='{"ok": true}') as mock_h:
            from agent.tools.builtins import create_builtin_registry
            registry = create_builtin_registry()
            result = registry.execute("kg_query", {"query": "test"})

        mock_h.assert_called_once_with(query="test")
        assert result.success is True

    def test_registry_kg_schema_dispatches_to_handler(self):
        """registry.execute('kg_schema') calls _handle_kg_schema."""
        with patch("agent.tools.builtins._handle_kg_schema", return_value='{"stub": false}') as mock_h:
            from agent.tools.builtins import create_builtin_registry
            registry = create_builtin_registry()
            result = registry.execute("kg_schema", {})

        mock_h.assert_called_once_with()
        assert result.success is True

    def test_registry_cypher_execute_dispatches_to_handler(self):
        """registry.execute('cypher_execute') calls _handle_cypher_execute."""
        with patch(
            "agent.tools.builtins._handle_cypher_execute",
            return_value='{"stub": false}',
        ) as mock_h:
            from agent.tools.builtins import create_builtin_registry
            registry = create_builtin_registry()
            result = registry.execute("cypher_execute", {"cypher": "MATCH (n) RETURN n"})

        mock_h.assert_called_once_with(cypher="MATCH (n) RETURN n")
        assert result.success is True

    def test_registry_vessel_search_dispatches_to_handler(self):
        """registry.execute('vessel_search') calls _handle_vessel_search."""
        with patch(
            "agent.tools.builtins._handle_vessel_search",
            return_value='{"vessels": []}',
        ) as mock_h:
            from agent.tools.builtins import create_builtin_registry
            registry = create_builtin_registry()
            result = registry.execute("vessel_search", {"query": "BUSAN"})

        mock_h.assert_called_once_with(query="BUSAN")
        assert result.success is True

    def test_registry_document_search_dispatches_to_handler(self):
        """registry.execute('document_search') calls _handle_document_search."""
        with patch(
            "agent.tools.builtins._handle_document_search",
            return_value='{"documents": []}',
        ) as mock_h:
            from agent.tools.builtins import create_builtin_registry
            registry = create_builtin_registry()
            result = registry.execute("document_search", {"query": "SOLAS"})

        mock_h.assert_called_once_with(query="SOLAS")
        assert result.success is True

    def test_registry_port_info_dispatches_to_handler(self):
        """registry.execute('port_info') calls _handle_port_info."""
        with patch(
            "agent.tools.builtins._handle_port_info",
            return_value='{"portId": "KRPUS"}',
        ) as mock_h:
            from agent.tools.builtins import create_builtin_registry
            registry = create_builtin_registry()
            result = registry.execute("port_info", {"port_name": "부산"})

        mock_h.assert_called_once_with(port_name="부산")
        assert result.success is True

    def test_registry_route_query_dispatches_to_handler(self):
        """registry.execute('route_query') calls _handle_route_query."""
        with patch(
            "agent.tools.builtins._handle_route_query",
            return_value='{"routes": []}',
        ) as mock_h:
            from agent.tools.builtins import create_builtin_registry
            registry = create_builtin_registry()
            result = registry.execute("route_query", {"origin": "부산", "destination": "도쿄"})

        mock_h.assert_called_once_with(origin="부산", destination="도쿄")
        assert result.success is True
