"""CSV importer and exporter for Knowledge Graph data.

Provides flat-file interchange for KG nodes and edges using standard
CSV format. Suitable for spreadsheet tooling and bulk data pipelines.

Node CSV columns:  id, labels (semicolon-separated), <property columns...>
Edge CSV columns:  id, type, sourceId, targetId, <property columns...>

Example::

    exporter = CSVExporter()
    nodes = [{"id": "n1", "labels": ["Vessel"], "properties": {"name": "EVER ACE"}}]
    result = exporter.export_nodes(nodes)

    importer = CSVImporter()
    parsed = importer.parse_nodes(result.data)
    cypher_stmts = importer.generate_cypher(parsed)
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from kg.interchange.models import ExportConfig, ExportResult, ImportConfig

logger = logging.getLogger(__name__)

# Column names for built-in node/edge attributes.
_NODE_ID_COL = "id"
_NODE_LABELS_COL = "labels"
_EDGE_ID_COL = "id"
_EDGE_TYPE_COL = "type"
_EDGE_SOURCE_COL = "sourceId"
_EDGE_TARGET_COL = "targetId"

# Separator used when joining/splitting multi-value label strings.
_LABEL_SEP = ";"


class CSVExporter:
    """Exports KG nodes and edges to CSV flat-file format.

    Attributes:
        config: Export configuration controlling output behaviour.
    """

    def __init__(self, config: ExportConfig | None = None) -> None:
        """Initialise the exporter.

        Args:
            config: Optional export configuration. Defaults to
                ``ExportConfig()`` if not supplied.
        """
        self.config: ExportConfig = config or ExportConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export_nodes(self, nodes: list[dict[str, Any]]) -> ExportResult:
        """Export a list of nodes to CSV format.

        The output CSV has columns: ``id``, ``labels``, then one column
        per property found across all nodes. Labels are joined with ``";"``.
        Missing properties for a given node are written as empty strings.

        Args:
            nodes: List of node dicts. Each dict must contain:
                - ``id`` (str): Unique node identifier.
                - ``labels`` (list[str]): One or more node labels.
                - ``properties`` (dict): Arbitrary property key/value pairs.

        Returns:
            ExportResult with format ``"csv"``, the CSV string in ``data``,
            and any per-node errors in ``errors``.
        """
        errors: list[str] = []
        filtered = self._apply_label_filter(nodes)
        if self.config.max_nodes is not None:
            filtered = filtered[: self.config.max_nodes]

        # Collect all property column names in stable order.
        prop_cols: list[str] = []
        if self.config.include_properties:
            seen: set[str] = set()
            for node in filtered:
                for key in node.get("properties", {}).keys():
                    if key not in seen:
                        seen.add(key)
                        prop_cols.append(key)

        fieldnames = [_NODE_ID_COL, _NODE_LABELS_COL] + prop_cols

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        node_count = 0
        for node in filtered:
            try:
                row: dict[str, Any] = {
                    _NODE_ID_COL: node["id"],
                    _NODE_LABELS_COL: _LABEL_SEP.join(node.get("labels", [])),
                }
                if self.config.include_properties:
                    for col in prop_cols:
                        row[col] = node.get("properties", {}).get(col, "")
                writer.writerow(row)
                node_count += 1
            except Exception as exc:  # noqa: BLE001
                msg = f"Node '{node.get('id', '?')}' skipped: {exc}"
                errors.append(msg)
                logger.warning(msg)

        return ExportResult(
            format="csv",
            node_count=node_count,
            edge_count=0,
            data=buf.getvalue(),
            errors=errors,
        )

    def export_edges(self, edges: list[dict[str, Any]]) -> ExportResult:
        """Export a list of edges to CSV format.

        The output CSV has columns: ``id``, ``type``, ``sourceId``,
        ``targetId``, then one column per property found across all edges.
        Missing properties are written as empty strings.

        Args:
            edges: List of edge dicts. Each dict must contain:
                - ``id`` (str): Unique edge identifier.
                - ``type`` (str): Relationship type label.
                - ``sourceId`` (str): ID of the source node.
                - ``targetId`` (str): ID of the target node.
                - ``properties`` (dict): Arbitrary property key/value pairs.

        Returns:
            ExportResult with format ``"csv"``, the CSV string in ``data``,
            and any per-edge errors in ``errors``.
        """
        errors: list[str] = []
        filtered = self._apply_rel_filter(edges)

        prop_cols: list[str] = []
        if self.config.include_properties:
            seen: set[str] = set()
            for edge in filtered:
                for key in edge.get("properties", {}).keys():
                    if key not in seen:
                        seen.add(key)
                        prop_cols.append(key)

        fieldnames = [_EDGE_ID_COL, _EDGE_TYPE_COL, _EDGE_SOURCE_COL, _EDGE_TARGET_COL] + prop_cols

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        edge_count = 0
        for edge in filtered:
            try:
                row: dict[str, Any] = {
                    _EDGE_ID_COL: edge["id"],
                    _EDGE_TYPE_COL: edge.get("type", ""),
                    _EDGE_SOURCE_COL: edge["sourceId"],
                    _EDGE_TARGET_COL: edge["targetId"],
                }
                if self.config.include_properties:
                    for col in prop_cols:
                        row[col] = edge.get("properties", {}).get(col, "")
                writer.writerow(row)
                edge_count += 1
            except Exception as exc:  # noqa: BLE001
                msg = f"Edge '{edge.get('id', '?')}' skipped: {exc}"
                errors.append(msg)
                logger.warning(msg)

        return ExportResult(
            format="csv",
            node_count=0,
            edge_count=edge_count,
            data=buf.getvalue(),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_label_filter(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter nodes by configured label whitelist.

        Args:
            nodes: Full list of node dicts.

        Returns:
            Filtered list; all nodes returned when ``config.labels`` is None.
        """
        if self.config.labels is None:
            return nodes
        allowed = set(self.config.labels)
        return [n for n in nodes if allowed.intersection(n.get("labels", []))]

    def _apply_rel_filter(self, edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter edges by configured relationship type whitelist.

        Args:
            edges: Full list of edge dicts.

        Returns:
            Filtered list; all edges returned when ``config.relationship_types`` is None.
        """
        if self.config.relationship_types is None:
            return edges
        allowed = set(self.config.relationship_types)
        return [e for e in edges if e.get("type") in allowed]


class CSVImporter:
    """Imports KG nodes and edges from CSV flat-file format.

    Parses CSV data produced by ``CSVExporter`` (or compatible sources)
    back into standard node/edge dicts. Can also generate Cypher statements
    from parsed node data for direct Neo4j ingestion.

    Attributes:
        config: Import configuration controlling parsing behaviour.
    """

    def __init__(self, config: ImportConfig | None = None) -> None:
        """Initialise the importer.

        Args:
            config: Optional import configuration. Defaults to
                ``ImportConfig()`` if not supplied.
        """
        self.config: ImportConfig = config or ImportConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_nodes(self, csv_data: str) -> list[dict[str, Any]]:
        """Parse node CSV data into a list of node dicts.

        Expects columns: ``id`` (or ``config.id_column``),
        ``labels`` (or ``config.label_column``), plus optional property columns.
        The ``labels`` column value is split on ``";"`` to produce a list.
        All remaining columns beyond the two built-in ones are treated as
        node properties.

        Args:
            csv_data: CSV string as produced by ``CSVExporter.export_nodes``.

        Returns:
            List of node dicts with schema::

                {"id": str, "labels": list[str], "properties": dict}
        """
        id_col = self.config.id_column
        label_col = self.config.label_column
        reserved = {id_col, label_col}

        nodes: list[dict[str, Any]] = []
        reader = csv.DictReader(io.StringIO(csv_data))

        for row in reader:
            node_id = row.get(id_col, "").strip()
            raw_labels = row.get(label_col, "")
            labels = [lbl.strip() for lbl in raw_labels.split(_LABEL_SEP) if lbl.strip()]
            properties: dict[str, Any] = {
                k: v for k, v in row.items() if k not in reserved
            }
            nodes.append({"id": node_id, "labels": labels, "properties": properties})

        return nodes

    def parse_edges(self, csv_data: str) -> list[dict[str, Any]]:
        """Parse edge CSV data into a list of edge dicts.

        Expects columns: ``id``, ``type``, ``sourceId``, ``targetId``,
        plus optional property columns.

        Args:
            csv_data: CSV string as produced by ``CSVExporter.export_edges``.

        Returns:
            List of edge dicts with schema::

                {
                    "id": str,
                    "type": str,
                    "sourceId": str,
                    "targetId": str,
                    "properties": dict,
                }
        """
        reserved = {_EDGE_ID_COL, _EDGE_TYPE_COL, _EDGE_SOURCE_COL, _EDGE_TARGET_COL}
        edges: list[dict[str, Any]] = []
        reader = csv.DictReader(io.StringIO(csv_data))

        for row in reader:
            properties: dict[str, Any] = {k: v for k, v in row.items() if k not in reserved}
            edges.append(
                {
                    "id": row.get(_EDGE_ID_COL, "").strip(),
                    "type": row.get(_EDGE_TYPE_COL, "").strip(),
                    "sourceId": row.get(_EDGE_SOURCE_COL, "").strip(),
                    "targetId": row.get(_EDGE_TARGET_COL, "").strip(),
                    "properties": properties,
                }
            )

        return edges

    def generate_cypher(self, nodes: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
        """Generate Cypher CREATE/MERGE statements for a list of nodes.

        The strategy (CREATE vs MERGE) is determined by
        ``config.merge_strategy``. Each returned tuple contains the
        parameterised Cypher string and its parameter dict.

        For ``MERGE`` strategy the match key is the node ``id``. ``CREATE``
        strategy unconditionally inserts all properties.

        Args:
            nodes: List of node dicts as returned by ``parse_nodes``.

        Returns:
            List of ``(cypher, params)`` tuples, one per node.

        Example::

            importer = CSVImporter(ImportConfig(merge_strategy="MERGE"))
            stmts = importer.generate_cypher(parsed_nodes)
            for cypher, params in stmts:
                session.run(cypher, **params)
        """
        statements: list[tuple[str, dict[str, Any]]] = []
        strategy = self.config.merge_strategy.upper()

        for node in nodes:
            node_id = node["id"]
            labels = node.get("labels", [])
            properties = node.get("properties", {})

            label_str = ":" + ":".join(labels) if labels else ""
            # Merge all properties including id into the params dict.
            all_props: dict[str, Any] = {"_id": node_id, **properties}

            if strategy == "MERGE":
                cypher = (
                    f"MERGE (n{label_str} {{id: $_id}}) "
                    f"SET n += $props"
                )
                params: dict[str, Any] = {"_id": node_id, "props": properties}
            else:
                # Default: CREATE
                cypher = (
                    f"CREATE (n{label_str} {{id: $_id}}) "
                    f"SET n += $props"
                )
                params = {"_id": node_id, "props": properties}

            statements.append((cypher, params))

        return statements
