"""Pydantic response models for the Maritime KG API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# Re-export standard response envelope models
from kg.api.models.responses import (
    PaginatedResponse,
    PaginationInfo,
    ResponseMeta,
    StandardResponse,
)


class NodeResponse(BaseModel):
    """A single graph node in the response."""

    id: str
    labels: list[str]
    primaryLabel: str
    group: str
    color: str
    properties: dict[str, Any] = Field(default_factory=dict)
    displayName: str


class EdgeResponse(BaseModel):
    """A single graph edge (relationship) in the response."""

    id: str
    type: str
    sourceId: str
    targetId: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    """Response containing graph nodes, edges, and metadata."""

    nodes: list[NodeResponse] = Field(default_factory=list)
    edges: list[EdgeResponse] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class SchemaLabelInfo(BaseModel):
    """Information about a single node label in the schema."""

    label: str
    group: str
    color: str
    count: int = 0


class SchemaResponse(BaseModel):
    """Response describing the graph schema (labels, relationships, groups)."""

    labels: list[SchemaLabelInfo] = Field(default_factory=list)
    relationshipTypes: list[str] = Field(default_factory=list)
    entityGroups: dict[str, Any] = Field(default_factory=dict)
    totalLabels: int = 0
    totalRelationshipTypes: int = 0


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    neo4j_connected: bool


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None  # noqa: UP045 - Pydantic requires Optional on Python 3.9


# ---------------------------------------------------------------------------
# NL Query models
# ---------------------------------------------------------------------------


class NLQueryRequest(BaseModel):
    """Request body for the natural language query endpoint."""

    text: str = Field(..., min_length=1, description="Korean natural language query")
    execute: bool = Field(default=True, description="Whether to execute the generated Cypher against Neo4j")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum number of result rows")


class NLQueryResponse(BaseModel):
    """Response from the natural language query endpoint."""

    input_text: str
    generated_cypher: Optional[str] = None  # noqa: UP045
    parameters: dict[str, Any] = Field(default_factory=dict)
    results: Optional[list[dict[str, Any]]] = None  # noqa: UP045
    confidence: float = 0.0
    parse_details: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None  # noqa: UP045


# ---------------------------------------------------------------------------
# Lineage models
# ---------------------------------------------------------------------------


class LineageNodeInfo(BaseModel):
    """A lineage node returned from lineage queries."""

    nodeId: str
    entityType: str
    entityId: str
    createdAt: Optional[str] = None  # noqa: UP045
    depth: Optional[int] = None  # noqa: UP045


class LineageEdgeInfo(BaseModel):
    """A lineage edge returned from lineage queries."""

    edgeId: Optional[str] = None  # noqa: UP045
    targetId: Optional[str] = None  # noqa: UP045
    eventType: Optional[str] = None  # noqa: UP045
    agent: Optional[str] = None  # noqa: UP045
    activity: Optional[str] = None  # noqa: UP045
    timestamp: Optional[str] = None  # noqa: UP045


class LineageResponse(BaseModel):
    """Full lineage graph response (nodes + edges)."""

    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class LineageNodesResponse(BaseModel):
    """Lineage ancestors/descendants response (nodes only)."""

    nodes: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class LineageTimelineResponse(BaseModel):
    """Lineage timeline response (ordered events)."""

    events: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Node CRUD models
# ---------------------------------------------------------------------------


class CreateNodeRequest(BaseModel):
    """Request body for creating a new node."""

    labels: list[str] = Field(..., min_length=1, description="One or more node labels (PascalCase)")
    properties: dict[str, Any] = Field(default_factory=dict, description="Initial node properties")


class UpdateNodeRequest(BaseModel):
    """Request body for updating node properties (merge semantics)."""

    properties: dict[str, Any] = Field(..., description="Properties to merge onto the node")


class NodeListResponse(BaseModel):
    """Paginated list of nodes."""

    nodes: list[NodeResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


# ---------------------------------------------------------------------------
# Relationship CRUD models
# ---------------------------------------------------------------------------


class CreateRelationshipRequest(BaseModel):
    """Request body for creating a new relationship."""

    sourceId: str = Field(..., description="Element ID of the source node")
    targetId: str = Field(..., description="Element ID of the target node")
    type: str = Field(  # noqa: A003
        ...,
        pattern=r"^[A-Z][A-Z_0-9]*$",
        description="Relationship type in SCREAMING_SNAKE_CASE",
    )
    properties: dict[str, Any] = Field(default_factory=dict)


class UpdateRelationshipRequest(BaseModel):
    """Request body for updating relationship properties (merge semantics)."""

    properties: dict[str, Any] = Field(..., description="Properties to merge onto the relationship")


class RelationshipDetailResponse(BaseModel):
    """Relationship together with its source and target nodes."""

    relationship: EdgeResponse
    sourceNode: NodeResponse
    targetNode: NodeResponse


class RelationshipListResponse(BaseModel):
    """Paginated list of relationships."""

    relationships: list[EdgeResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


# ---------------------------------------------------------------------------
# Cypher execution models
# ---------------------------------------------------------------------------


class CypherRequest(BaseModel):
    """Request body for raw Cypher query endpoints."""

    cypher: str = Field(..., min_length=1, description="Cypher query string")
    parameters: dict[str, Any] = Field(default_factory=dict)


class CypherResponse(BaseModel):
    """Response from the raw Cypher execution endpoint."""

    results: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    rowCount: int = 0
    executionTimeMs: float = 0.0


class CypherValidationResponse(BaseModel):
    """Response from the Cypher validation endpoint."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    queryType: str = "read"


class CypherExplainResponse(BaseModel):
    """Response from the Cypher explain endpoint."""

    plan: dict[str, Any] = Field(default_factory=dict)
    estimatedRows: int = 0


# ---------------------------------------------------------------------------
# Embedding search models
# ---------------------------------------------------------------------------


class EmbeddingSearchRequest(BaseModel):
    """Request body for vector similarity search."""

    label: str
    property: str = "embedding"
    queryVector: list[float]
    topK: int = Field(default=10, ge=1, le=100)


class HybridSearchRequest(BaseModel):
    """Request body for hybrid vector + full-text search."""

    label: str
    property: str = "embedding"
    queryVector: list[float]
    textQuery: str
    topK: int = Field(default=10, ge=1, le=100)


class CreateIndexRequest(BaseModel):
    """Request body for creating a Neo4j vector index."""

    label: str
    property: str = "embedding"
    dimensions: int = Field(default=768, ge=1)
    similarity: str = Field(default="cosine", pattern="^(cosine|euclidean|dot_product)$")


class EmbeddingSearchResponse(BaseModel):
    """Response from vector or hybrid search endpoints."""

    results: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Algorithm models
# ---------------------------------------------------------------------------


class AlgorithmRequest(BaseModel):
    """Base request body for graph algorithm endpoints."""

    label: str = "Vessel"
    relationshipType: str = "DOCKED_AT"


class PageRankRequest(AlgorithmRequest):
    """Request body for the PageRank endpoint."""

    iterations: int = Field(default=20, ge=1, le=100)
    dampingFactor: float = Field(default=0.85, ge=0.0, le=1.0)


class ShortestPathRequest(BaseModel):
    """Request body for the shortest-path (Dijkstra) endpoint."""

    sourceId: str
    targetId: str
    relationshipType: str = "ROUTE_TO"
    weightProperty: str = "distance"


class SimilarityRequest(AlgorithmRequest):
    """Request body for the node similarity endpoint."""

    topK: int = Field(default=10, ge=1, le=100)


class AlgorithmResponse(BaseModel):
    """Response from graph algorithm execution endpoints."""

    algorithm: str
    results: list[dict[str, Any]] = Field(default_factory=list)
    cypher: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
