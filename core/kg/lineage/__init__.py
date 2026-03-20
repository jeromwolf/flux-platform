"""Data lineage tracking module for the Maritime Knowledge Graph.

Implements W3C PROV-O inspired provenance tracking with configurable
recording policies that integrate with the RBAC DataClassification system.

Core components:

- **models**: Domain models (LineageNode, LineageEdge, LineageGraph, DataSnapshot)
- **policy**: Recording policy engine (LineagePolicy, RecordingLevel)
- **recorder**: High-level recording API (LineageRecorder)
- **queries**: Pre-built Cypher queries for Neo4j persistence

Usage::

    from kg.lineage import LineageRecorder, LineageEventType

    recorder = LineageRecorder()
    recorder.record_event(
        entity_type="Vessel",
        entity_id="VES-001",
        event_type=LineageEventType.CREATION,
        agent="ETL-Pipeline-1",
        activity="Imported from AIS feed",
    )
    graph = recorder.get_graph()
"""

from kg.lineage.models import (
    DataSnapshot,
    LineageEdge,
    LineageEventType,
    LineageGraph,
    LineageNode,
    ProvenanceRole,
)
from kg.lineage.policy import LineagePolicy, RecordingLevel
from kg.lineage.recorder import LineageRecorder

__all__ = [
    # Models
    "LineageNode",
    "LineageEdge",
    "LineageGraph",
    "LineageEventType",
    "ProvenanceRole",
    "DataSnapshot",
    # Policy
    "LineagePolicy",
    "RecordingLevel",
    # Recorder
    "LineageRecorder",
]
