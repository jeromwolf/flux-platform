"""KG Visualizer API Server -- Lightweight HTTP backend for the KG visualization tool.

Provides REST endpoints for exploring the Maritime Knowledge Graph
via Neo4j. Uses only Python stdlib (http.server) -- no Flask required.

Endpoints:
    GET /api/subgraph?label=Vessel&limit=50  -- Get nodes by label with relationships
    GET /api/neighbors?nodeId=xxx             -- Expand neighbors of a node
    GET /api/search?q=부산                     -- Search nodes by name
    GET /api/schema                           -- Get available labels and relationship types

Usage::
    PYTHONPATH=. python poc/kg_visualizer_api.py
    # Serves HTML at http://localhost:8765/
    # API at http://localhost:8765/api/...
"""

from __future__ import annotations

import atexit
import json
import os
import traceback
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from kg.config import get_config, get_driver

# ---------------------------------------------------------------------------
# Entity group -> color mapping (matches the HTML frontend)
# ---------------------------------------------------------------------------

ENTITY_GROUPS: dict[str, list[str]] = {
    "PhysicalEntity": [
        "Vessel",
        "CargoShip",
        "Tanker",
        "FishingVessel",
        "PassengerShip",
        "NavalVessel",
        "AutonomousVessel",
        "Port",
        "TradePort",
        "CoastalPort",
        "FishingPort",
        "PortFacility",
        "Berth",
        "Anchorage",
        "Terminal",
        "Waterway",
        "TSS",
        "Channel",
        "Cargo",
        "DangerousGoods",
        "BulkCargo",
        "ContainerCargo",
        "Sensor",
        "AISTransceiver",
        "Radar",
        "CCTVCamera",
        "WeatherStation",
    ],
    "SpatialEntity": [
        "SeaArea",
        "EEZ",
        "TerritorialSea",
        "CoastalRegion",
        "GeoPoint",
    ],
    "TemporalEntity": [
        "Voyage",
        "PortCall",
        "TrackSegment",
        "Incident",
        "Collision",
        "Grounding",
        "Pollution",
        "Distress",
        "IllegalFishing",
        "WeatherCondition",
        "Activity",
        "Loading",
        "Unloading",
        "Bunkering",
        "Anchoring",
        "Loitering",
    ],
    "InformationEntity": [
        "Regulation",
        "COLREG",
        "SOLAS",
        "MARPOL",
        "IMDGCode",
        "Document",
        "AccidentReport",
        "InspectionReport",
        "NavigationalWarning",
        "CargoManifest",
        "DataSource",
        "APIEndpoint",
        "StreamSource",
        "FileSource",
        "Service",
        "QueryService",
        "AnalysisService",
        "AlertService",
        "PredictionService",
    ],
    "Observation": [
        "SARObservation",
        "OpticalObservation",
        "CCTVObservation",
        "AISObservation",
        "RadarObservation",
        "WeatherObservation",
    ],
    "Agent": [
        "Organization",
        "GovernmentAgency",
        "ShippingCompany",
        "ResearchInstitute",
        "ClassificationSociety",
        "Person",
        "CrewMember",
        "Inspector",
    ],
    "PlatformResource": [
        "Workflow",
        "WorkflowNode",
        "WorkflowExecution",
        "AIModel",
        "DataPipeline",
        "AIAgent",
        "MCPTool",
        "MCPResource",
    ],
    "MultimodalData": [
        "AISData",
        "SatelliteImage",
        "RadarImage",
        "SensorReading",
        "MaritimeChart",
        "VideoClip",
    ],
    "MultimodalRepresentation": [
        "VisualEmbedding",
        "TrajectoryEmbedding",
        "TextEmbedding",
        "FusedEmbedding",
    ],
    "KRISO": [
        "Experiment",
        "TestFacility",
        "TowingTank",
        "OceanEngineeringBasin",
        "IceTank",
        "DeepOceanBasin",
        "WaveEnergyTestSite",
        "HyperbaricChamber",
        "CavitationTunnel",
        "LargeCavitationTunnel",
        "MediumCavitationTunnel",
        "HighSpeedCavitationTunnel",
        "BridgeSimulator",
        "ExperimentalDataset",
        "TestCondition",
        "ModelShip",
        "Measurement",
        "Resistance",
        "Propulsion",
        "Maneuvering",
        "Seakeeping",
        "IcePerformance",
        "StructuralResponse",
    ],
    "RBAC": [
        "User",
        "Role",
        "DataClass",
        "Permission",
    ],
}

GROUP_COLORS: dict[str, str] = {
    "PhysicalEntity": "#4A90D9",
    "SpatialEntity": "#50C878",
    "TemporalEntity": "#E67E22",
    "InformationEntity": "#9B59B6",
    "Observation": "#E74C3C",
    "Agent": "#F39C12",
    "PlatformResource": "#1ABC9C",
    "MultimodalData": "#3498DB",
    "MultimodalRepresentation": "#5DADE2",
    "KRISO": "#FF6B35",
    "RBAC": "#95A5A6",
}

# Build reverse mapping: label -> group
_LABEL_TO_GROUP: dict[str, str] = {}
for _group, _labels in ENTITY_GROUPS.items():
    for _label in _labels:
        _LABEL_TO_GROUP[_label] = _group


def get_group_for_label(label: str) -> str:
    """Return the entity group name for a given Neo4j label."""
    return _LABEL_TO_GROUP.get(label, "Unknown")


def get_color_for_label(label: str) -> str:
    """Return the hex color for a given Neo4j label."""
    group = get_group_for_label(label)
    return GROUP_COLORS.get(group, "#888888")


# ---------------------------------------------------------------------------
# Neo4j query helpers
# ---------------------------------------------------------------------------

# Module-level driver (initialized lazily)
_driver = None


def _get_driver():
    """Get or create a shared Neo4j driver instance."""
    global _driver
    if _driver is None:
        _driver = get_driver()
    return _driver


def _close_driver():
    """Close the shared driver if open."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


# Register cleanup handler
atexit.register(_close_driver)


def _run_query(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a Cypher query and return list of record dicts."""
    driver = _get_driver()
    with driver.session(database=get_config().neo4j.database) as session:
        result = session.run(cypher, params or {})
        return [record.data() for record in result]


def _node_to_dict(node: dict[str, Any]) -> dict[str, Any]:
    """Convert a Neo4j node record to a serializable dict for the frontend.

    Args:
        node: A dict typically containing 'n' (the node) from the query.
              We accept both raw node objects and pre-extracted dicts.

    Returns:
        Dict with id, labels, properties, group, color.
    """
    # Handle cases where node is already a simple dict
    if "id" in node and "labels" in node:
        return node

    return node


def _serialize_value(val: Any) -> Any:
    """Serialize Neo4j values to JSON-compatible types."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, list):
        return [_serialize_value(v) for v in val]
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    # neo4j spatial / temporal types
    if hasattr(val, "x") and hasattr(val, "y"):
        # Point type
        return {"lat": val.y, "lon": val.x}
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _extract_node(record: Any, key: str) -> dict[str, Any] | None:
    """Extract a node from a record into a serializable dict."""
    node = record.get(key) if isinstance(record, dict) else None
    if node is None:
        return None

    # Neo4j node object
    if hasattr(node, "element_id") and hasattr(node, "labels"):
        props = {k: _serialize_value(v) for k, v in dict(node).items()}
        labels = list(node.labels)
        primary_label = labels[0] if labels else "Unknown"
        return {
            "id": node.element_id,
            "labels": labels,
            "primaryLabel": primary_label,
            "group": get_group_for_label(primary_label),
            "color": get_color_for_label(primary_label),
            "properties": props,
            "displayName": props.get("name", props.get("title", primary_label)),
        }
    return None


def _extract_relationship(record: Any, key: str) -> dict[str, Any] | None:
    """Extract a relationship from a record into a serializable dict."""
    rel = record.get(key) if isinstance(record, dict) else None
    if rel is None:
        return None

    if hasattr(rel, "type") and hasattr(rel, "start_node"):
        props = {k: _serialize_value(v) for k, v in dict(rel).items()}
        return {
            "id": rel.element_id,
            "type": rel.type,
            "sourceId": rel.start_node.element_id,
            "targetId": rel.end_node.element_id,
            "properties": props,
        }
    return None


# ---------------------------------------------------------------------------
# API endpoint handlers
# ---------------------------------------------------------------------------


def api_subgraph(params: dict[str, list[str]]) -> dict[str, Any]:
    """GET /api/subgraph?label=Vessel&limit=50

    Fetch nodes of a given label along with their relationships.
    """
    label = params.get("label", ["Vessel"])[0]
    limit = min(int(params.get("limit", ["50"])[0]), 200)

    # Validate label to prevent injection
    if not label.isalnum():
        return {"error": "Invalid label", "nodes": [], "edges": []}

    cypher = f"""
    MATCH (n:{label})
    WITH n LIMIT $limit
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    """

    driver = _get_driver()
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    with driver.session(database=get_config().neo4j.database) as session:
        result = session.run(cypher, {"limit": limit})
        for record in result:
            # Process source node
            n = _extract_node(record, "n")
            if n:
                nodes[n["id"]] = n

            # Process related node
            m = _extract_node(record, "m")
            if m:
                nodes[m["id"]] = m

            # Process relationship
            r = _extract_relationship(record, "r")
            if r:
                edges[r["id"]] = r

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "meta": {
            "label": label,
            "limit": limit,
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
        },
    }


def api_neighbors(params: dict[str, list[str]]) -> dict[str, Any]:
    """GET /api/neighbors?nodeId=xxx&depth=1

    Expand neighbors of a specific node.
    """
    node_id = params.get("nodeId", [""])[0]

    if not node_id:
        return {"error": "nodeId is required", "nodes": [], "edges": []}

    cypher = """
    MATCH (n)
    WHERE elementId(n) = $nodeId
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    """

    driver = _get_driver()
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    with driver.session(database=get_config().neo4j.database) as session:
        result = session.run(cypher, {"nodeId": node_id})
        for record in result:
            n = _extract_node(record, "n")
            if n:
                nodes[n["id"]] = n

            m = _extract_node(record, "m")
            if m:
                nodes[m["id"]] = m

            r = _extract_relationship(record, "r")
            if r:
                edges[r["id"]] = r

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "meta": {
            "centerNodeId": node_id,
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
        },
    }


def api_search(params: dict[str, list[str]]) -> dict[str, Any]:
    """GET /api/search?q=부산&limit=30

    Search nodes by name/title using CONTAINS.
    """
    query = params.get("q", [""])[0]
    limit = min(int(params.get("limit", ["30"])[0]), 100)

    if not query or len(query) < 1:
        return {"error": "Search query (q) is required", "nodes": [], "edges": []}

    cypher = """
    MATCH (n)
    WHERE n.name CONTAINS $query
       OR n.title CONTAINS $query
       OR n.nameEn CONTAINS $query
       OR n.description CONTAINS $query
    WITH n LIMIT $limit
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    """

    driver = _get_driver()
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    with driver.session(database=get_config().neo4j.database) as session:
        result = session.run(cypher, {"query": query, "limit": limit})
        for record in result:
            n = _extract_node(record, "n")
            if n:
                nodes[n["id"]] = n

            m = _extract_node(record, "m")
            if m:
                nodes[m["id"]] = m

            r = _extract_relationship(record, "r")
            if r:
                edges[r["id"]] = r

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "meta": {
            "query": query,
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
        },
    }


def api_schema(params: dict[str, list[str]]) -> dict[str, Any]:
    """GET /api/schema

    Get available labels, relationship types, and entity group info.
    """
    driver = _get_driver()
    with driver.session(database=get_config().neo4j.database) as session:
        # Get node labels with counts
        labels_result = session.run("CALL db.labels() YIELD label RETURN label ORDER BY label")
        labels = []
        for record in labels_result:
            lbl = record["label"]
            labels.append(
                {
                    "label": lbl,
                    "group": get_group_for_label(lbl),
                    "color": get_color_for_label(lbl),
                }
            )

        # Get relationship types
        rel_result = session.run(
            "CALL db.relationshipTypes() YIELD relationshipType "
            "RETURN relationshipType ORDER BY relationshipType"
        )
        rel_types = [record["relationshipType"] for record in rel_result]

        # Get node counts per label
        _count_result = session.run(
            "CALL db.labels() YIELD label "
            "CALL { WITH label "
            "  CALL db.stats.retrieve('GRAPH COUNTS') YIELD data "
            "  RETURN 0 AS cnt "
            "} "
            "RETURN label, cnt"
        )
        # Fallback: count per label individually
        label_counts: dict[str, int] = {}
        for lbl_info in labels:
            lbl = lbl_info["label"]
            try:
                cnt_result = session.run(f"MATCH (n:{lbl}) RETURN count(n) AS cnt")
                cnt_record = cnt_result.single()
                label_counts[lbl] = cnt_record["cnt"] if cnt_record else 0
            except Exception:
                label_counts[lbl] = 0

    # Add counts to labels
    for lbl_info in labels:
        lbl_info["count"] = label_counts.get(lbl_info["label"], 0)

    return {
        "labels": labels,
        "relationshipTypes": rel_types,
        "entityGroups": {
            group: {
                "color": color,
                "labels": ENTITY_GROUPS.get(group, []),
            }
            for group, color in GROUP_COLORS.items()
        },
        "totalLabels": len(labels),
        "totalRelationshipTypes": len(rel_types),
    }


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

# Mapping of API routes to handler functions
API_ROUTES: dict[str, Any] = {
    "/api/subgraph": api_subgraph,
    "/api/neighbors": api_neighbors,
    "/api/search": api_search,
    "/api/schema": api_schema,
}


class KGVisualizerHandler(SimpleHTTPRequestHandler):
    """HTTP request handler that serves both static files and API endpoints."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Serve files from the poc/ directory
        self.poc_dir = str(Path(__file__).resolve().parent)
        super().__init__(*args, directory=self.poc_dir, **kwargs)

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Serve the visualizer HTML at root
        if path == "/" or path == "":
            self.path = "/kg_visualizer.html"
            return super().do_GET()

        # API endpoints
        if path in API_ROUTES:
            self._handle_api(path, parsed.query)
            return

        # Fall through to static file serving
        return super().do_GET()

    def _handle_api(self, path: str, query_string: str) -> None:
        """Dispatch to the appropriate API handler."""
        params = parse_qs(query_string)
        handler_fn = API_ROUTES[path]

        try:
            result = handler_fn(params)
            self._send_json(200, result)
        except Exception as exc:
            traceback.print_exc()
            self._send_json(
                500,
                {
                    "error": str(exc),
                    "type": type(exc).__name__,
                },
            )

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        """Send a JSON response."""
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Override to add prefix."""
        print(f"[KG-API] {args[0]} {args[1]} {args[2]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the KG Visualizer API server."""
    host = os.getenv("KG_VIS_HOST", "0.0.0.0")  # noqa: S104
    port = int(os.getenv("KG_VIS_PORT", "8765"))

    server = HTTPServer((host, port), KGVisualizerHandler)

    print("=" * 60)
    print("  Maritime KG Visualizer API Server")
    print("=" * 60)
    print(f"  Server:  http://localhost:{port}/")
    print(f"  API:     http://localhost:{port}/api/schema")
    print(f"  Neo4j:   {os.getenv('NEO4J_URI', 'bolt://localhost:7687')}")
    print(f"  DB:      {get_config().neo4j.database}")
    print("=" * 60)
    print()
    print("  Endpoints:")
    print("    GET /api/subgraph?label=Vessel&limit=50")
    print("    GET /api/neighbors?nodeId=xxx")
    print("    GET /api/search?q=부산")
    print("    GET /api/schema")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Shutting down]")
        server.shutdown()


if __name__ == "__main__":
    main()
