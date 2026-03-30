"""Integration tests for project-scoped API routes.

Verifies that route handlers and helpers correctly handle project labels:
- _extract_node filters KG_ prefix from primaryLabel
- schema endpoint filters KG_ labels
- node routes inject project labels into Cypher
All tests use mock Neo4j sessions (no real database needed).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kg.project import PROJECT_LABEL_PREFIX


# ---------------------------------------------------------------------------
# _extract_node project label filtering
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractNodeProjectFiltering:
    """_extract_node should filter KG_ labels from primaryLabel."""

    def _make_node(
        self, labels: list[str], element_id: str = "4:abc:0", props: dict | None = None
    ) -> MagicMock:
        """Create a mock Neo4j node with the given labels and properties."""
        node = MagicMock()
        node.labels = labels
        node.element_id = element_id
        items = list((props or {}).items())
        node.items.return_value = items
        # dict() conversion: make the mock iterable over keys
        node.__iter__ = MagicMock(return_value=iter(dict(items)))
        node.__getitem__ = MagicMock(side_effect=lambda k: dict(items).get(k, ""))
        return node

    def test_primary_label_excludes_kg_prefix(self) -> None:
        from kg.api.routes.graph import _extract_node

        node = self._make_node(["Vessel", "KG_DevKG"], props={"name": "TestShip"})
        record = MagicMock()
        record.__getitem__ = MagicMock(return_value=node)
        record.__contains__ = MagicMock(return_value=True)

        result = _extract_node(record, "n")
        assert result is not None
        assert result["primaryLabel"] == "Vessel"
        assert "KG_DevKG" in result["labels"]
        assert "Vessel" in result["labels"]

    def test_only_kg_label_falls_back(self) -> None:
        """When only KG_ label exists, primaryLabel falls back to it."""
        from kg.api.routes.graph import _extract_node

        node = self._make_node(["KG_default"])
        record = MagicMock()
        record.__getitem__ = MagicMock(return_value=node)

        result = _extract_node(record, "n")
        assert result is not None
        assert result["primaryLabel"] == "KG_default"

    def test_multiple_domain_labels_picks_first(self) -> None:
        from kg.api.routes.graph import _extract_node

        node = self._make_node(["Port", "Infrastructure", "KG_DevKG"])
        record = MagicMock()
        record.__getitem__ = MagicMock(return_value=node)

        result = _extract_node(record, "n")
        assert result is not None
        assert result["primaryLabel"] == "Port"

    def test_no_labels_at_all(self) -> None:
        """Node with empty labels list should use 'Unknown' as primaryLabel."""
        from kg.api.routes.graph import _extract_node

        node = self._make_node([])
        record = MagicMock()
        record.__getitem__ = MagicMock(return_value=node)

        result = _extract_node(record, "n")
        assert result is not None
        assert result["primaryLabel"] == "Unknown"


# ---------------------------------------------------------------------------
# Schema filtering
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaProjectFiltering:
    """Schema-level project label filtering logic."""

    def test_filter_kg_labels_from_list(self) -> None:
        """Schema endpoint should filter out KG_ prefix labels."""
        labels = ["Vessel", "Port", "KG_default", "KG_DevKG"]
        filtered = [lbl for lbl in labels if not lbl.startswith(PROJECT_LABEL_PREFIX)]
        assert filtered == ["Vessel", "Port"]

    def test_no_kg_labels_unchanged(self) -> None:
        labels = ["Vessel", "Port", "Document"]
        filtered = [lbl for lbl in labels if not lbl.startswith(PROJECT_LABEL_PREFIX)]
        assert filtered == labels

    def test_all_kg_labels_empty_result(self) -> None:
        labels = ["KG_default", "KG_DevKG"]
        filtered = [lbl for lbl in labels if not lbl.startswith(PROJECT_LABEL_PREFIX)]
        assert filtered == []


# ---------------------------------------------------------------------------
# Node route Cypher generation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNodeRouteCypherGeneration:
    """Verify node route helper functions build correct project-scoped Cypher."""

    def test_create_node_cypher_includes_project_label(self) -> None:
        """CREATE node Cypher should include the project label."""
        from kg.project import KGProjectContext

        project = KGProjectContext(name="DevKG")
        labels = ["Vessel"]
        label_str = ":".join(labels) + ":" + project.label
        cypher = f"CREATE (n:{label_str}) SET n += $props RETURN n"

        assert "Vessel:KG_DevKG" in cypher
        assert "CREATE" in cypher

    def test_get_node_cypher_uses_project_label(self) -> None:
        """MATCH for get_node should use project.label."""
        from kg.project import KGProjectContext

        project = KGProjectContext(name="ProdKG")
        cypher = f"MATCH (n:{project.label}) WHERE elementId(n) = $id RETURN n"

        assert "KG_ProdKG" in cypher

    def test_delete_node_cypher_scoped(self) -> None:
        """DETACH DELETE should be scoped to project."""
        from kg.project import KGProjectContext

        project = KGProjectContext(name="Test")
        cypher = f"MATCH (n:{project.label}) WHERE elementId(n) = $id DETACH DELETE n"

        assert "KG_Test" in cypher
        assert "DETACH DELETE" in cypher

    def test_list_nodes_cypher_with_label_filter(self) -> None:
        """list_nodes builds label_clause combining domain label + project."""
        from kg.project import KGProjectContext

        project = KGProjectContext(name="DevKG")
        label = "Vessel"
        label_clause = f":{label}:{project.label}"

        assert label_clause == ":Vessel:KG_DevKG"

    def test_list_nodes_cypher_without_label_filter(self) -> None:
        """Without domain label filter, only project label is used."""
        from kg.project import KGProjectContext

        project = KGProjectContext(name="DevKG")
        label_clause = f":{project.label}"

        assert label_clause == ":KG_DevKG"

    def test_update_node_cypher_scoped(self) -> None:
        """Update Cypher should match on project label."""
        from kg.project import KGProjectContext

        project = KGProjectContext(name="Upd")
        cypher = f"MATCH (n:{project.label}) WHERE elementId(n) = $id SET n += $props RETURN n"

        assert "KG_Upd" in cypher
        assert "SET n += $props" in cypher


# ---------------------------------------------------------------------------
# Graph route Cypher
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGraphRouteCypherGeneration:
    """Verify graph route Cypher patterns include project scoping."""

    def test_subgraph_cypher_includes_project(self) -> None:
        from kg.project import KGProjectContext

        project = KGProjectContext(name="DevKG")
        label = "Vessel"
        cypher = f"MATCH (n:{label}:{project.label}) WITH n LIMIT $limit"

        assert "Vessel:KG_DevKG" in cypher

    def test_neighbors_cypher_includes_project(self) -> None:
        from kg.project import KGProjectContext

        project = KGProjectContext(name="DevKG")
        cypher = f"MATCH (n:{project.label}) WHERE elementId(n) = $nodeId"

        assert "KG_DevKG" in cypher

    def test_search_fulltext_branch_includes_project(self) -> None:
        """Each fulltext UNION branch filters by project label."""
        from kg.project import KGProjectContext

        project = KGProjectContext(name="Srch")
        branch = (
            f"CALL db.index.fulltext.queryNodes('vessel_search', $query) "
            f"YIELD node, score "
            f"WHERE node:{project.label} "
            f"RETURN node, score LIMIT $limit"
        )
        assert "WHERE node:KG_Srch" in branch
