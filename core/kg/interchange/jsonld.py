"""JSON-LD exporter for Knowledge Graph data.

Serializes KG nodes and edges to the JSON-LD 1.1 format, producing
@context/@graph documents compatible with standard linked-data tooling.

Example::

    exporter = JsonLDExporter()
    nodes = [
        {"id": "n1", "labels": ["Vessel"], "properties": {"name": "EVER ACE"}},
    ]
    result = exporter.export_nodes(nodes)
    print(result.data)  # JSON-LD string
"""

from __future__ import annotations

import json
import logging
from typing import Any

from kg.interchange.models import ExportConfig, ExportResult

logger = logging.getLogger(__name__)

# Canonical URN scheme used for KG resources.
_NODE_URN_PREFIX = "urn:kg:node:"
_EDGE_URN_PREFIX = "urn:kg:edge:"


class JsonLDExporter:
    """Exports KG nodes and edges to JSON-LD format.

    Produces a JSON-LD document with an @context block derived from
    ``ExportConfig.context_uri`` and an @graph array containing one
    entry per node/edge.

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
        """Export a list of nodes to a JSON-LD document.

        Args:
            nodes: List of node dicts. Each dict must contain:
                - ``id`` (str): Unique node identifier.
                - ``labels`` (list[str]): One or more node labels.
                - ``properties`` (dict): Arbitrary property key/value pairs.

        Returns:
            ExportResult with format ``"json-ld"``, serialized JSON-LD
            string in ``data``, and any per-node errors in ``errors``.
        """
        errors: list[str] = []
        graph: list[dict[str, Any]] = []

        filtered = self._apply_label_filter(nodes)
        if self.config.max_nodes is not None:
            filtered = filtered[: self.config.max_nodes]

        for node in filtered:
            try:
                graph.append(self._node_to_jsonld(node))
            except Exception as exc:  # noqa: BLE001
                msg = f"Node '{node.get('id', '?')}' skipped: {exc}"
                errors.append(msg)
                logger.warning(msg)

        document = self._build_document(graph)
        return ExportResult(
            format="json-ld",
            node_count=len(graph),
            edge_count=0,
            data=self._serialize(document),
            errors=errors,
        )

    def export_graph(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> ExportResult:
        """Export nodes and edges to a single JSON-LD document.

        Args:
            nodes: List of node dicts (same schema as ``export_nodes``).
            edges: List of edge dicts. Each dict must contain:
                - ``id`` (str): Unique edge identifier.
                - ``type`` (str): Relationship type label.
                - ``sourceId`` (str): ID of the source node.
                - ``targetId`` (str): ID of the target node.
                - ``properties`` (dict): Arbitrary property key/value pairs.

        Returns:
            ExportResult with both ``node_count`` and ``edge_count``
            populated. Errors from either nodes or edges are aggregated.
        """
        errors: list[str] = []
        graph: list[dict[str, Any]] = []

        filtered_nodes = self._apply_label_filter(nodes)
        if self.config.max_nodes is not None:
            filtered_nodes = filtered_nodes[: self.config.max_nodes]

        for node in filtered_nodes:
            try:
                graph.append(self._node_to_jsonld(node))
            except Exception as exc:  # noqa: BLE001
                msg = f"Node '{node.get('id', '?')}' skipped: {exc}"
                errors.append(msg)
                logger.warning(msg)

        node_ids = {n.get("id") for n in filtered_nodes}
        filtered_edges = self._apply_rel_filter(edges)

        for edge in filtered_edges:
            try:
                graph.append(self._edge_to_jsonld(edge))
            except Exception as exc:  # noqa: BLE001
                msg = f"Edge '{edge.get('id', '?')}' skipped: {exc}"
                errors.append(msg)
                logger.warning(msg)

        node_count = sum(1 for e in graph if "@type" in e and isinstance(e.get("@type"), list))
        edge_count = len(graph) - node_count

        document = self._build_document(graph)
        return ExportResult(
            format="json-ld",
            node_count=node_count,
            edge_count=edge_count,
            data=self._serialize(document),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _node_to_jsonld(self, node: dict[str, Any]) -> dict[str, Any]:
        """Convert a single node dict to a JSON-LD object.

        Args:
            node: Node dict with ``id``, ``labels``, and ``properties`` keys.

        Returns:
            JSON-LD dict with ``@id``, ``@type``, and flattened properties.
        """
        entry: dict[str, Any] = {
            "@id": f"{_NODE_URN_PREFIX}{node['id']}",
            "@type": node.get("labels", []),
        }
        if self.config.include_properties:
            entry.update(node.get("properties", {}))
        return entry

    def _edge_to_jsonld(self, edge: dict[str, Any]) -> dict[str, Any]:
        """Convert a single edge dict to a JSON-LD object.

        Args:
            edge: Edge dict with ``id``, ``type``, ``sourceId``,
                ``targetId``, and ``properties`` keys.

        Returns:
            JSON-LD dict representing the relationship.
        """
        entry: dict[str, Any] = {
            "@id": f"{_EDGE_URN_PREFIX}{edge['id']}",
            "@type": edge["type"],
            "source": edge["sourceId"],
            "target": edge["targetId"],
        }
        if self.config.include_properties:
            entry.update(edge.get("properties", {}))
        return entry

    def _build_document(self, graph: list[dict[str, Any]]) -> dict[str, Any]:
        """Wrap graph items in a JSON-LD envelope.

        Args:
            graph: List of JSON-LD node/edge objects.

        Returns:
            Top-level JSON-LD document dict with ``@context`` and ``@graph``.
        """
        return {
            "@context": self.config.context_uri,
            "@graph": graph,
        }

    def _serialize(self, document: dict[str, Any]) -> str:
        """Serialise a document dict to a JSON string.

        Args:
            document: JSON-LD document dict.

        Returns:
            JSON string, indented when ``config.pretty_print`` is True.
        """
        indent = 2 if self.config.pretty_print else None
        return json.dumps(document, ensure_ascii=False, indent=indent)

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
