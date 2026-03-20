"""Pydantic response models for the Maritime KG API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


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
