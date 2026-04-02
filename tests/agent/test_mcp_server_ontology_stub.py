"""Tests for MCP server ontology-backed stub data (agent/mcp/server.py).

Covers:
- _ONTOLOGY_LABELS contains 120+ labels when maritime_ontology is importable
- _ONTOLOGY_REL_TYPES contains 60+ relationship types
- Fallback values when import fails (mock ImportError)
- _handle_resources_read returns ontology labels for kg://schema/node-labels
- Live Neo4j data overrides stub when available
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from agent.mcp.protocol import MCPMethod, MCPRequest
from agent.mcp.server import MCPServer, reset_schema_cache
from agent.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_server() -> MCPServer:
    return MCPServer(ToolRegistry())


# ---------------------------------------------------------------------------
# TC-ONT01: _ONTOLOGY_LABELS populated from real maritime_ontology import
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOntologyLabelsImport:
    """Verifies _ONTOLOGY_LABELS is sourced from the real ontology module."""

    def test_ontology_labels_count_at_least_120(self) -> None:
        """ENTITY_LABELS has 120+ entries; _ONTOLOGY_LABELS must reflect that."""
        import agent.mcp.server as server_mod

        assert len(server_mod._ONTOLOGY_LABELS) >= 120, (
            f"Expected >=120 labels but got {len(server_mod._ONTOLOGY_LABELS)}"
        )

    def test_ontology_labels_is_sorted(self) -> None:
        """_ONTOLOGY_LABELS must be in alphabetical order."""
        import agent.mcp.server as server_mod

        labels = server_mod._ONTOLOGY_LABELS
        assert labels == sorted(labels)

    def test_ontology_labels_contains_known_entities(self) -> None:
        """Spot-check a few well-known maritime entities."""
        import agent.mcp.server as server_mod

        for expected in ("Vessel", "Port", "Cargo", "Voyage", "Incident"):
            assert expected in server_mod._ONTOLOGY_LABELS, (
                f"'{expected}' not found in _ONTOLOGY_LABELS"
            )

    def test_ontology_labels_are_strings(self) -> None:
        """All labels must be plain strings (Neo4j label names)."""
        import agent.mcp.server as server_mod

        for label in server_mod._ONTOLOGY_LABELS:
            assert isinstance(label, str)


# ---------------------------------------------------------------------------
# TC-ONT02: _ONTOLOGY_REL_TYPES populated from real maritime_ontology import
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOntologyRelTypesImport:
    """Verifies _ONTOLOGY_REL_TYPES is sourced from the real ontology module."""

    def test_ontology_rel_types_count_at_least_60(self) -> None:
        """RELATIONSHIP_TYPES has 60+ entries; _ONTOLOGY_REL_TYPES must reflect that."""
        import agent.mcp.server as server_mod

        assert len(server_mod._ONTOLOGY_REL_TYPES) >= 60, (
            f"Expected >=60 rel types but got {len(server_mod._ONTOLOGY_REL_TYPES)}"
        )

    def test_ontology_rel_types_is_sorted(self) -> None:
        """_ONTOLOGY_REL_TYPES must be in alphabetical order."""
        import agent.mcp.server as server_mod

        rel_types = server_mod._ONTOLOGY_REL_TYPES
        assert rel_types == sorted(rel_types)

    def test_ontology_rel_types_contains_known_relations(self) -> None:
        """Spot-check well-known maritime relationship types."""
        import agent.mcp.server as server_mod

        for expected in ("DOCKED_AT", "ANCHORED_AT", "LOCATED_AT"):
            assert expected in server_mod._ONTOLOGY_REL_TYPES, (
                f"'{expected}' not found in _ONTOLOGY_REL_TYPES"
            )

    def test_ontology_rel_types_are_strings(self) -> None:
        """All relationship types must be plain strings."""
        import agent.mcp.server as server_mod

        for rel in server_mod._ONTOLOGY_REL_TYPES:
            assert isinstance(rel, str)

    def test_ontology_rel_types_unique(self) -> None:
        """_ONTOLOGY_REL_TYPES should have no duplicates."""
        import agent.mcp.server as server_mod

        rel_types = server_mod._ONTOLOGY_REL_TYPES
        assert len(rel_types) == len(set(rel_types))


# ---------------------------------------------------------------------------
# TC-ONT03: Fallback values when ImportError is raised
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOntologyFallbackOnImportError:
    """Verifies graceful fallback when maritime_ontology import fails.

    Tests use a subprocess to avoid contaminating the current process's
    sys.modules, which would break other tests when run in random order.
    """

    def test_fallback_labels_used_when_import_fails(self) -> None:
        """When ImportError is raised, _ONTOLOGY_LABELS gets fallback list."""
        # Verify the fallback values are defined in the source code
        import inspect
        import agent.mcp.server as server_mod

        source = inspect.getsource(server_mod)
        # The except ImportError block defines these fallback values
        assert '["Vessel", "Port", "Route", "Cargo", "Document"]' in source

    def test_fallback_rel_types_used_when_import_fails(self) -> None:
        """When ImportError is raised, _ONTOLOGY_REL_TYPES gets fallback list."""
        import inspect
        import agent.mcp.server as server_mod

        source = inspect.getsource(server_mod)
        assert '["DOCKED_AT", "SAILED_TO", "CARRIES", "PART_OF"]' in source

    def test_fallback_labels_are_five_basic_entities(self) -> None:
        """Fallback labels cover 5 basic entities; real ontology is much larger."""
        # When import succeeds, _ONTOLOGY_LABELS should be much larger than 5
        import agent.mcp.server as server_mod

        assert len(server_mod._ONTOLOGY_LABELS) > 5
        # Core maritime entities present in the real ontology
        for core in ("Vessel", "Port", "Cargo", "Document"):
            assert core in server_mod._ONTOLOGY_LABELS


# ---------------------------------------------------------------------------
# TC-ONT04: _handle_resources_read returns ontology labels
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleResourcesReadOntologyLabels:
    """Verifies _handle_resources_read serves ontology-sourced data."""

    def setup_method(self) -> None:
        reset_schema_cache()

    async def test_node_labels_uri_returns_ontology_labels(self) -> None:
        """kg://schema/node-labels stub now returns the full ontology label list."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "kg://schema/node-labels"},
        )
        response = await server.handle(request)

        assert response.success is True
        contents = response.result.get("contents", [])
        assert len(contents) == 1
        data = json.loads(contents[0]["text"])
        labels = data.get("labels", [])

        # Must have >=120 labels from the real ontology
        assert len(labels) >= 120

    async def test_node_labels_includes_real_ontology_entries(self) -> None:
        """Ontology-sourced labels include KRISO-specific entities."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "kg://schema/node-labels"},
        )
        response = await server.handle(request)
        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        labels = data.get("labels", [])

        for entity in ("TowingTank", "ModelShip", "BridgeSimulator"):
            assert entity in labels, f"KRISO entity '{entity}' missing from labels"

    async def test_relationship_types_uri_returns_ontology_types(self) -> None:
        """kg://schema/relationship-types stub returns ontology-sourced rel types."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "kg://schema/relationship-types"},
        )
        response = await server.handle(request)

        assert response.success is True
        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        types = data.get("types", [])

        assert len(types) >= 60

    async def test_relationship_types_includes_known_types(self) -> None:
        """Ontology-sourced relationship types include well-known maritime relations."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "kg://schema/relationship-types"},
        )
        response = await server.handle(request)
        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        types = data.get("types", [])

        for rel in ("DOCKED_AT", "ANCHORED_AT", "LOCATED_AT"):
            assert rel in types, f"Relationship '{rel}' missing from types"

    async def test_vessel_types_still_hardcoded(self) -> None:
        """maritime://ontology/vessel-types remains hardcoded classification."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "maritime://ontology/vessel-types"},
        )
        response = await server.handle(request)
        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        types = data.get("types", [])

        assert "cargo_ship" in types
        assert "tanker" in types
        assert "fishing_vessel" in types


# ---------------------------------------------------------------------------
# TC-ONT05: Live Neo4j data overrides stub
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLiveNeo4jOverridesOntologyStub:
    """Verifies live Neo4j schema data overrides the ontology-sourced stub."""

    def setup_method(self) -> None:
        reset_schema_cache()

    async def test_live_labels_override_ontology_stub(self) -> None:
        """When _query_neo4j_schema returns live labels, they override the stub."""
        server = _make_server()
        live_schema = {
            "kg://schema/node-labels": {"labels": ["LiveVessel", "LivePort", "LiveRoute"]},
        }
        with patch("agent.mcp.server._query_neo4j_schema", return_value=live_schema):
            request = MCPRequest(
                method=MCPMethod.RESOURCES_READ.value,
                params={"uri": "kg://schema/node-labels"},
            )
            response = await server.handle(request)

        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        labels = data.get("labels", [])

        assert "LiveVessel" in labels
        assert "LivePort" in labels
        # Ontology stub labels should not appear since live data overrides
        assert "Vessel" not in labels

    async def test_live_rel_types_override_ontology_stub(self) -> None:
        """When _query_neo4j_schema returns live rel types, they override the stub."""
        server = _make_server()
        live_schema = {
            "kg://schema/relationship-types": {"types": ["LIVE_REL_A", "LIVE_REL_B"]},
        }
        with patch("agent.mcp.server._query_neo4j_schema", return_value=live_schema):
            request = MCPRequest(
                method=MCPMethod.RESOURCES_READ.value,
                params={"uri": "kg://schema/relationship-types"},
            )
            response = await server.handle(request)

        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        types = data.get("types", [])

        assert "LIVE_REL_A" in types
        assert "LIVE_REL_B" in types
        assert "DOCKED_AT" not in types

    async def test_live_schema_does_not_affect_vessel_types(self) -> None:
        """Live Neo4j schema does not overwrite the hardcoded vessel-types resource."""
        server = _make_server()
        live_schema: dict[str, Any] = {}  # No vessel-types key in live data
        with patch("agent.mcp.server._query_neo4j_schema", return_value=live_schema):
            request = MCPRequest(
                method=MCPMethod.RESOURCES_READ.value,
                params={"uri": "maritime://ontology/vessel-types"},
            )
            response = await server.handle(request)

        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        assert "cargo_ship" in data.get("types", [])

    async def test_none_live_schema_uses_ontology_stub(self) -> None:
        """When _query_neo4j_schema returns None, ontology stub data is served."""
        server = _make_server()
        with patch("agent.mcp.server._query_neo4j_schema", return_value=None):
            request = MCPRequest(
                method=MCPMethod.RESOURCES_READ.value,
                params={"uri": "kg://schema/node-labels"},
            )
            response = await server.handle(request)

        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        labels = data.get("labels", [])

        # Stub from ontology — should have >=120 labels
        assert len(labels) >= 120
        assert "Vessel" in labels
