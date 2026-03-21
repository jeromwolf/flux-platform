"""GraphML exporter for Knowledge Graph data.

Serializes KG nodes and edges to the GraphML XML format, which is
supported by Gephi, yEd, NetworkX, and most graph analysis tools.

GraphML specification: http://graphml.graphdrawing.org/

Example::

    exporter = GraphMLExporter()
    nodes = [{"id": "n1", "labels": ["Vessel"], "properties": {"name": "EVER ACE"}}]
    edges = [{"id": "e1", "type": "DOCKED_AT", "sourceId": "n1", "targetId": "n2",
              "properties": {}}]
    result = exporter.export_graph(nodes, edges)
    print(result.data)  # GraphML XML string
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

from kg.interchange.models import ExportConfig, ExportResult

logger = logging.getLogger(__name__)

# GraphML XML namespace.
_GRAPHML_NS = "http://graphml.graphstruct.org/xmlns"
# Reserved key IDs for built-in attributes.
_KEY_LABELS = "d_labels"
_KEY_EDGE_TYPE = "d_type"


class GraphMLExporter:
    """Exports KG nodes and edges to GraphML XML format.

    Uses Python's standard ``xml.etree.ElementTree`` to construct a
    well-formed GraphML document with proper ``<key>`` declarations and
    ``<data>`` elements per node/edge.

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

    def export_graph(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> ExportResult:
        """Export nodes and edges to a GraphML XML document.

        Args:
            nodes: List of node dicts. Each dict must contain:
                - ``id`` (str): Unique node identifier.
                - ``labels`` (list[str]): One or more node labels.
                - ``properties`` (dict): Arbitrary property key/value pairs.
            edges: List of edge dicts. Each dict must contain:
                - ``id`` (str): Unique edge identifier.
                - ``type`` (str): Relationship type label.
                - ``sourceId`` (str): ID of the source node.
                - ``targetId`` (str): ID of the target node.
                - ``properties`` (dict): Arbitrary property key/value pairs.

        Returns:
            ExportResult with format ``"graphml"``, the serialized XML in
            ``data``, node/edge counts, and any errors encountered.
        """
        errors: list[str] = []

        filtered_nodes = self._apply_label_filter(nodes)
        if self.config.max_nodes is not None:
            filtered_nodes = filtered_nodes[: self.config.max_nodes]
        filtered_edges = self._apply_rel_filter(edges)

        # Root element with namespace.
        root = ET.Element("graphml", xmlns=_GRAPHML_NS)

        # Register <key> declarations for all known property names.
        self._register_keys(root, filtered_nodes, filtered_edges)

        # <graph> container.
        graph_elem = ET.SubElement(root, "graph", id="G", edgedefault="directed")

        # Emit nodes.
        node_count = 0
        for node in filtered_nodes:
            try:
                self._write_node(graph_elem, node)
                node_count += 1
            except Exception as exc:  # noqa: BLE001
                msg = f"Node '{node.get('id', '?')}' skipped: {exc}"
                errors.append(msg)
                logger.warning(msg)

        # Emit edges.
        edge_count = 0
        for edge in filtered_edges:
            try:
                self._write_edge(graph_elem, edge)
                edge_count += 1
            except Exception as exc:  # noqa: BLE001
                msg = f"Edge '{edge.get('id', '?')}' skipped: {exc}"
                errors.append(msg)
                logger.warning(msg)

        if self.config.pretty_print:
            self._indent_xml(root)

        xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

        return ExportResult(
            format="graphml",
            node_count=node_count,
            edge_count=edge_count,
            data=xml_str,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _register_keys(
        self,
        root: ET.Element,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> None:
        """Auto-detect property names and create GraphML ``<key>`` elements.

        Scans all node/edge dicts to collect unique property names, then
        inserts ``<key>`` declarations before the ``<graph>`` element.
        The ``labels`` attribute on nodes and ``type`` on edges always
        receive dedicated keys.

        Args:
            root: The root ``<graphml>`` element to insert keys into.
            nodes: Node dicts to scan for property names.
            edges: Edge dicts to scan for property names.
        """
        # Fixed keys for built-in attributes.
        ET.SubElement(
            root, "key", id=_KEY_LABELS, **{"for": "node", "attr.name": "labels", "attr.type": "string"}
        )
        ET.SubElement(
            root, "key", id=_KEY_EDGE_TYPE, **{"for": "edge", "attr.name": "type", "attr.type": "string"}
        )

        if not self.config.include_properties:
            return

        # Collect unique node property names.
        node_props: set[str] = set()
        for node in nodes:
            node_props.update(node.get("properties", {}).keys())

        for prop in sorted(node_props):
            key_id = f"np_{prop}"
            ET.SubElement(
                root,
                "key",
                id=key_id,
                **{"for": "node", "attr.name": prop, "attr.type": "string"},
            )

        # Collect unique edge property names.
        edge_props: set[str] = set()
        for edge in edges:
            edge_props.update(edge.get("properties", {}).keys())

        for prop in sorted(edge_props):
            key_id = f"ep_{prop}"
            ET.SubElement(
                root,
                "key",
                id=key_id,
                **{"for": "edge", "attr.name": prop, "attr.type": "string"},
            )

    def _write_node(self, graph_elem: ET.Element, node: dict[str, Any]) -> None:
        """Append a ``<node>`` element to the graph container.

        Args:
            graph_elem: The ``<graph>`` element to append to.
            node: Node dict with ``id``, ``labels``, and ``properties``.
        """
        node_elem = ET.SubElement(graph_elem, "node", id=str(node["id"]))

        # Labels as semicolon-separated string.
        labels_str = ";".join(node.get("labels", []))
        data_labels = ET.SubElement(node_elem, "data", key=_KEY_LABELS)
        data_labels.text = labels_str

        if self.config.include_properties:
            for prop, value in node.get("properties", {}).items():
                data_elem = ET.SubElement(node_elem, "data", key=f"np_{prop}")
                data_elem.text = str(value) if value is not None else ""

    def _write_edge(self, graph_elem: ET.Element, edge: dict[str, Any]) -> None:
        """Append an ``<edge>`` element to the graph container.

        Args:
            graph_elem: The ``<graph>`` element to append to.
            edge: Edge dict with ``id``, ``type``, ``sourceId``, ``targetId``,
                and ``properties``.
        """
        edge_elem = ET.SubElement(
            graph_elem,
            "edge",
            id=str(edge["id"]),
            source=str(edge["sourceId"]),
            target=str(edge["targetId"]),
        )

        data_type = ET.SubElement(edge_elem, "data", key=_KEY_EDGE_TYPE)
        data_type.text = edge.get("type", "")

        if self.config.include_properties:
            for prop, value in edge.get("properties", {}).items():
                data_elem = ET.SubElement(edge_elem, "data", key=f"ep_{prop}")
                data_elem.text = str(value) if value is not None else ""

    def _indent_xml(self, elem: ET.Element, level: int = 0) -> None:
        """Add whitespace indentation to an XML element tree in-place.

        Args:
            elem: The XML element to indent.
            level: Current indentation depth (spaces = level * 2).
        """
        indent = "\n" + "  " * level
        child_indent = "\n" + "  " * (level + 1)

        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = child_indent
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            # Last child tail should revert to parent level.
            if not child.tail or not child.tail.strip():  # type: ignore[possibly-undefined]
                child.tail = indent  # type: ignore[possibly-undefined]
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent

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
