"""Pre-built Cypher queries for lineage persistence and retrieval.

All queries use parameterized format (``$paramName``) and follow the
project convention of camelCase property names for Neo4j.

These queries are designed to work with the lineage node labels:

- ``(:LineageNode)`` - Tracks provenance of data entities.
- ``(:DataSnapshot)`` - Point-in-time property captures.
- Relationship types: ``DERIVED_FROM``, ``TRANSFORMED_BY``, ``HAS_SNAPSHOT``.

Usage::

    from kg.lineage.queries import MERGE_LINEAGE_NODE, GET_ANCESTORS
    from kg.config import get_driver, get_config

    driver = get_driver()
    cfg = get_config()
    with driver.session(database=cfg.neo4j.database) as session:
        session.run(MERGE_LINEAGE_NODE, nodeId="...", entityType="Vessel", ...)
"""

from __future__ import annotations

# =========================================================================
# Write Queries
# =========================================================================

MERGE_LINEAGE_NODE: str = """
MERGE (ln:LineageNode {nodeId: $nodeId})
ON CREATE SET
    ln.entityType = $entityType,
    ln.entityId = $entityId,
    ln.createdAt = datetime($createdAt),
    ln.metadata = $metadata
ON MATCH SET
    ln.updatedAt = datetime()
RETURN ln
""".strip()

MERGE_LINEAGE_EDGE: str = """
MATCH (source:LineageNode {nodeId: $sourceId})
MATCH (target:LineageNode {nodeId: $targetId})
CREATE (source)-[r:DERIVED_FROM {
    edgeId: $edgeId,
    eventType: $eventType,
    timestamp: datetime($timestamp),
    agent: $agent,
    activity: $activity,
    metadata: $metadata
}]->(target)
RETURN r
""".strip()

MERGE_SNAPSHOT: str = """
MATCH (ln:LineageNode {entityId: $entityId, entityType: $entityType})
CREATE (snap:DataSnapshot {
    snapshotId: $snapshotId,
    entityType: $entityType,
    entityId: $entityId,
    properties: $properties,
    capturedAt: datetime($capturedAt),
    capturedBy: $capturedBy
})
CREATE (ln)-[:HAS_SNAPSHOT]->(snap)
RETURN snap
""".strip()

# =========================================================================
# Read Queries
# =========================================================================

GET_ANCESTORS: str = """
MATCH (start:LineageNode {entityId: $entityId, entityType: $entityType})
MATCH path = (ancestor:LineageNode)-[:DERIVED_FROM*1..]->(start)
RETURN DISTINCT ancestor.nodeId AS nodeId,
       ancestor.entityType AS entityType,
       ancestor.entityId AS entityId,
       ancestor.createdAt AS createdAt,
       length(path) AS depth
ORDER BY depth ASC
""".strip()

GET_DESCENDANTS: str = """
MATCH (start:LineageNode {entityId: $entityId, entityType: $entityType})
MATCH path = (start)-[:DERIVED_FROM*1..]->(descendant:LineageNode)
RETURN DISTINCT descendant.nodeId AS nodeId,
       descendant.entityType AS entityType,
       descendant.entityId AS entityId,
       descendant.createdAt AS createdAt,
       length(path) AS depth
ORDER BY depth ASC
""".strip()

GET_FULL_LINEAGE: str = """
MATCH (start:LineageNode {entityId: $entityId, entityType: $entityType})
OPTIONAL MATCH ancestorPath = (ancestor:LineageNode)-[:DERIVED_FROM*1..]->(start)
OPTIONAL MATCH descendantPath = (start)-[:DERIVED_FROM*1..]->(descendant:LineageNode)
WITH start,
     collect(DISTINCT ancestor) AS ancestors,
     collect(DISTINCT descendant) AS descendants
WITH start, ancestors, descendants,
     ancestors + descendants + [start] AS allNodes
UNWIND allNodes AS node
WITH DISTINCT node
OPTIONAL MATCH (node)-[r:DERIVED_FROM]->(target:LineageNode)
RETURN node.nodeId AS nodeId,
       node.entityType AS entityType,
       node.entityId AS entityId,
       node.createdAt AS createdAt,
       collect({
           edgeId: r.edgeId,
           targetId: target.nodeId,
           eventType: r.eventType,
           agent: r.agent,
           activity: r.activity,
           timestamp: r.timestamp
       }) AS edges
""".strip()

GET_LINEAGE_TIMELINE: str = """
MATCH (ln:LineageNode {entityId: $entityId, entityType: $entityType})
MATCH (ln)-[r:DERIVED_FROM]-(related:LineageNode)
RETURN r.edgeId AS edgeId,
       r.eventType AS eventType,
       r.agent AS agent,
       r.activity AS activity,
       r.timestamp AS timestamp,
       related.entityId AS relatedEntityId,
       related.entityType AS relatedEntityType
ORDER BY r.timestamp ASC
""".strip()
