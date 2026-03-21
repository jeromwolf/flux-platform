"""Unit tests for kg.interchange package.

Covers JsonLDExporter, GraphMLExporter, CSVExporter, CSVImporter,
ExportConfig, ImportConfig, and ExportResult. All tests run without
any external dependencies or running services.
"""

from __future__ import annotations

import csv
import io
import json

import pytest

from kg.interchange import (
    CSVExporter,
    CSVImporter,
    ExportConfig,
    ExportResult,
    GraphMLExporter,
    ImportConfig,
    JsonLDExporter,
)
from kg.interchange.models import ExportConfig, ExportResult, ImportConfig

# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

SAMPLE_NODES = [
    {"id": "v1", "labels": ["Vessel"], "properties": {"name": "Ever Given", "mmsi": "353136000"}},
    {"id": "p1", "labels": ["Port"], "properties": {"name": "Busan", "country": "KR"}},
]

SAMPLE_EDGES = [
    {
        "id": "e1",
        "type": "DOCKED_AT",
        "sourceId": "v1",
        "targetId": "p1",
        "properties": {"date": "2025-01-15"},
    },
]


# ===========================================================================
# ExportConfig
# ===========================================================================


@pytest.mark.unit
class TestExportConfig:
    """ExportConfig default values and frozen behaviour."""

    def test_defaults(self) -> None:
        cfg = ExportConfig()
        assert cfg.labels is None
        assert cfg.relationship_types is None
        assert cfg.pretty_print is True
        assert cfg.include_properties is True
        assert cfg.max_nodes is None

    def test_frozen(self) -> None:
        cfg = ExportConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.pretty_print = False  # type: ignore[misc]

    def test_custom_values(self) -> None:
        cfg = ExportConfig(labels=["Vessel"], pretty_print=False, max_nodes=100)
        assert cfg.labels == ["Vessel"]
        assert cfg.pretty_print is False
        assert cfg.max_nodes == 100


# ===========================================================================
# ExportResult
# ===========================================================================


@pytest.mark.unit
class TestExportResult:
    """ExportResult success property and error accumulation."""

    def test_success_when_no_errors(self) -> None:
        result = ExportResult(format="json-ld", node_count=2, edge_count=1, data="{}")
        assert result.success is True

    def test_failure_when_errors(self) -> None:
        result = ExportResult(
            format="json-ld",
            node_count=1,
            edge_count=0,
            data="{}",
            errors=["Node 'x' skipped: missing id"],
        )
        assert result.success is False

    def test_defaults(self) -> None:
        result = ExportResult(format="csv")
        assert result.node_count == 0
        assert result.edge_count == 0
        assert result.data == ""
        assert result.errors == []
        assert result.success is True

    def test_multiple_errors(self) -> None:
        result = ExportResult(format="graphml", errors=["err1", "err2"])
        assert result.success is False
        assert len(result.errors) == 2


# ===========================================================================
# JsonLDExporter
# ===========================================================================


@pytest.mark.unit
class TestJsonLDExporter:
    """JsonLDExporter correctness across nodes and graphs."""

    def test_export_nodes(self) -> None:
        exporter = JsonLDExporter()
        result = exporter.export_nodes(SAMPLE_NODES)
        assert result.format == "json-ld"
        assert result.node_count == 2
        assert result.success is True
        doc = json.loads(result.data)
        assert "@context" in doc
        assert "@graph" in doc
        graph = doc["@graph"]
        assert len(graph) == 2

    def test_export_graph_with_edges(self) -> None:
        exporter = JsonLDExporter()
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        assert result.format == "json-ld"
        # 2 nodes + 1 edge = 3 graph entries
        doc = json.loads(result.data)
        assert len(doc["@graph"]) == 3

    def test_empty_nodes(self) -> None:
        exporter = JsonLDExporter()
        result = exporter.export_nodes([])
        assert result.node_count == 0
        assert result.success is True
        doc = json.loads(result.data)
        assert doc["@graph"] == []

    def test_node_id_format(self) -> None:
        exporter = JsonLDExporter()
        result = exporter.export_nodes(SAMPLE_NODES)
        doc = json.loads(result.data)
        for entry in doc["@graph"]:
            assert entry["@id"].startswith("urn:kg:node:")

    def test_properties_included(self) -> None:
        exporter = JsonLDExporter()
        result = exporter.export_nodes(SAMPLE_NODES)
        doc = json.loads(result.data)
        vessel_entry = next(e for e in doc["@graph"] if "Ever Given" in e.get("name", ""))
        assert vessel_entry["name"] == "Ever Given"
        assert vessel_entry["mmsi"] == "353136000"

    def test_properties_excluded_when_config_disabled(self) -> None:
        exporter = JsonLDExporter(ExportConfig(include_properties=False))
        result = exporter.export_nodes(SAMPLE_NODES)
        doc = json.loads(result.data)
        for entry in doc["@graph"]:
            assert "name" not in entry

    def test_type_is_list_for_nodes(self) -> None:
        exporter = JsonLDExporter()
        result = exporter.export_nodes(SAMPLE_NODES)
        doc = json.loads(result.data)
        for entry in doc["@graph"]:
            assert isinstance(entry["@type"], list)

    def test_label_filter_applied(self) -> None:
        exporter = JsonLDExporter(ExportConfig(labels=["Vessel"]))
        result = exporter.export_nodes(SAMPLE_NODES)
        assert result.node_count == 1
        doc = json.loads(result.data)
        assert doc["@graph"][0]["@id"] == "urn:kg:node:v1"

    def test_max_nodes_applied(self) -> None:
        exporter = JsonLDExporter(ExportConfig(max_nodes=1))
        result = exporter.export_nodes(SAMPLE_NODES)
        assert result.node_count == 1

    def test_pretty_print_true(self) -> None:
        exporter = JsonLDExporter(ExportConfig(pretty_print=True))
        result = exporter.export_nodes(SAMPLE_NODES)
        assert "\n" in result.data

    def test_pretty_print_false(self) -> None:
        exporter = JsonLDExporter(ExportConfig(pretty_print=False))
        result = exporter.export_nodes(SAMPLE_NODES)
        assert "\n" not in result.data


# ===========================================================================
# GraphMLExporter
# ===========================================================================


@pytest.mark.unit
class TestGraphMLExporter:
    """GraphMLExporter correctness for nodes, edges, and properties."""

    def test_export_graph(self) -> None:
        exporter = GraphMLExporter()
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        assert result.format == "graphml"
        assert result.node_count == 2
        assert result.edge_count == 1
        assert result.success is True
        assert "<graphml" in result.data
        assert "<node" in result.data
        assert "<edge" in result.data

    def test_node_ids_present(self) -> None:
        exporter = GraphMLExporter()
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        assert 'id="v1"' in result.data
        assert 'id="p1"' in result.data

    def test_edge_source_target(self) -> None:
        exporter = GraphMLExporter()
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        assert 'source="v1"' in result.data
        assert 'target="p1"' in result.data

    def test_empty_graph(self) -> None:
        exporter = GraphMLExporter()
        result = exporter.export_graph([], [])
        assert result.node_count == 0
        assert result.edge_count == 0
        assert result.success is True
        assert "<graphml" in result.data

    def test_properties_as_data_elements(self) -> None:
        exporter = GraphMLExporter()
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        assert "<data" in result.data

    def test_xml_declaration_present(self) -> None:
        exporter = GraphMLExporter()
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        assert result.data.startswith("<?xml")

    def test_properties_excluded_when_config_disabled(self) -> None:
        exporter = GraphMLExporter(ExportConfig(include_properties=False))
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        # With include_properties=False, no np_ keys should appear
        assert "np_name" not in result.data

    def test_label_filter(self) -> None:
        exporter = GraphMLExporter(ExportConfig(labels=["Vessel"]))
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        assert result.node_count == 1

    def test_rel_filter(self) -> None:
        exporter = GraphMLExporter(ExportConfig(relationship_types=["NONE_EXISTING"]))
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        assert result.edge_count == 0

    def test_edge_type_in_data(self) -> None:
        exporter = GraphMLExporter()
        result = exporter.export_graph(SAMPLE_NODES, SAMPLE_EDGES)
        assert "DOCKED_AT" in result.data


# ===========================================================================
# CSVExporter
# ===========================================================================


@pytest.mark.unit
class TestCSVExporter:
    """CSVExporter output structure and column conventions."""

    def test_export_nodes(self) -> None:
        exporter = CSVExporter()
        result = exporter.export_nodes(SAMPLE_NODES)
        assert result.format == "csv"
        assert result.node_count == 2
        assert result.success is True
        reader = csv.DictReader(io.StringIO(result.data))
        rows = list(reader)
        assert len(rows) == 2
        ids = {r["id"] for r in rows}
        assert ids == {"v1", "p1"}

    def test_export_edges(self) -> None:
        exporter = CSVExporter()
        result = exporter.export_edges(SAMPLE_EDGES)
        assert result.format == "csv"
        assert result.edge_count == 1
        reader = csv.DictReader(io.StringIO(result.data))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["type"] == "DOCKED_AT"
        assert rows[0]["sourceId"] == "v1"
        assert rows[0]["targetId"] == "p1"

    def test_labels_semicolon_joined(self) -> None:
        nodes = [{"id": "n1", "labels": ["Vessel", "Entity"], "properties": {}}]
        exporter = CSVExporter()
        result = exporter.export_nodes(nodes)
        reader = csv.DictReader(io.StringIO(result.data))
        rows = list(reader)
        assert rows[0]["labels"] == "Vessel;Entity"

    def test_node_headers_include_properties(self) -> None:
        exporter = CSVExporter()
        result = exporter.export_nodes(SAMPLE_NODES)
        reader = csv.DictReader(io.StringIO(result.data))
        assert "name" in (reader.fieldnames or [])

    def test_edge_headers(self) -> None:
        exporter = CSVExporter()
        result = exporter.export_edges(SAMPLE_EDGES)
        reader = csv.DictReader(io.StringIO(result.data))
        for col in ("id", "type", "sourceId", "targetId"):
            assert col in (reader.fieldnames or [])

    def test_empty_nodes(self) -> None:
        exporter = CSVExporter()
        result = exporter.export_nodes([])
        assert result.node_count == 0
        assert result.success is True

    def test_missing_property_written_as_empty(self) -> None:
        nodes = [
            {"id": "n1", "labels": ["A"], "properties": {"x": "1"}},
            {"id": "n2", "labels": ["A"], "properties": {}},
        ]
        exporter = CSVExporter()
        result = exporter.export_nodes(nodes)
        reader = csv.DictReader(io.StringIO(result.data))
        rows = list(reader)
        n2_row = next(r for r in rows if r["id"] == "n2")
        assert n2_row["x"] == ""


# ===========================================================================
# CSVImporter
# ===========================================================================


@pytest.mark.unit
class TestCSVImporter:
    """CSVImporter parse and Cypher generation logic."""

    def test_parse_nodes(self) -> None:
        exporter = CSVExporter()
        csv_data = exporter.export_nodes(SAMPLE_NODES).data
        importer = CSVImporter()
        parsed = importer.parse_nodes(csv_data)
        assert len(parsed) == 2
        ids = {n["id"] for n in parsed}
        assert ids == {"v1", "p1"}

    def test_parse_nodes_roundtrip_labels(self) -> None:
        exporter = CSVExporter()
        csv_data = exporter.export_nodes(SAMPLE_NODES).data
        importer = CSVImporter()
        parsed = importer.parse_nodes(csv_data)
        vessel = next(n for n in parsed if n["id"] == "v1")
        assert "Vessel" in vessel["labels"]

    def test_parse_edges(self) -> None:
        exporter = CSVExporter()
        csv_data = exporter.export_edges(SAMPLE_EDGES).data
        importer = CSVImporter()
        parsed = importer.parse_edges(csv_data)
        assert len(parsed) == 1
        edge = parsed[0]
        assert edge["id"] == "e1"
        assert edge["type"] == "DOCKED_AT"
        assert edge["sourceId"] == "v1"
        assert edge["targetId"] == "p1"

    def test_generate_cypher_create(self) -> None:
        exporter = CSVExporter()
        csv_data = exporter.export_nodes(SAMPLE_NODES).data
        importer = CSVImporter(ImportConfig(merge_strategy="CREATE"))
        parsed = importer.parse_nodes(csv_data)
        stmts = importer.generate_cypher(parsed)
        assert len(stmts) == 2
        for cypher, params in stmts:
            assert "CREATE" in cypher
            assert "_id" in params

    def test_generate_cypher_merge(self) -> None:
        exporter = CSVExporter()
        csv_data = exporter.export_nodes(SAMPLE_NODES).data
        importer = CSVImporter(ImportConfig(merge_strategy="MERGE"))
        parsed = importer.parse_nodes(csv_data)
        stmts = importer.generate_cypher(parsed)
        assert len(stmts) == 2
        for cypher, params in stmts:
            assert "MERGE" in cypher

    def test_labels_split(self) -> None:
        csv_text = "id,labels,name\nn1,Vessel;Entity,Ship A\n"
        importer = CSVImporter()
        parsed = importer.parse_nodes(csv_text)
        assert parsed[0]["labels"] == ["Vessel", "Entity"]

    def test_generate_cypher_params_have_props(self) -> None:
        exporter = CSVExporter()
        csv_data = exporter.export_nodes(SAMPLE_NODES).data
        importer = CSVImporter()
        parsed = importer.parse_nodes(csv_data)
        stmts = importer.generate_cypher(parsed)
        for _cypher, params in stmts:
            assert "props" in params

    def test_parse_edges_properties(self) -> None:
        exporter = CSVExporter()
        csv_data = exporter.export_edges(SAMPLE_EDGES).data
        importer = CSVImporter()
        parsed = importer.parse_edges(csv_data)
        edge = parsed[0]
        assert "date" in edge["properties"]
        assert edge["properties"]["date"] == "2025-01-15"

    def test_parse_nodes_empty_csv(self) -> None:
        csv_text = "id,labels\n"
        importer = CSVImporter()
        parsed = importer.parse_nodes(csv_text)
        assert parsed == []

    def test_import_config_defaults(self) -> None:
        cfg = ImportConfig()
        assert cfg.merge_strategy == "CREATE"
        assert cfg.batch_size == 500
        assert cfg.label_column == "labels"
        assert cfg.id_column == "id"
