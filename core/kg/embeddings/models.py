"""Frozen dataclass models for the embedding subsystem.

Defines configuration and result types used by EmbeddingManager when
creating Neo4j vector indexes and running hybrid search queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VectorIndexConfig:
    """Configuration for a Neo4j vector index.

    Attributes:
        name: Unique index name used in Neo4j DDL and query calls.
        label: Neo4j node label the index is created on (e.g., "Document").
        property_name: Node property that holds the embedding vector
            (e.g., "textEmbedding").
        dimensions: Number of dimensions of the embedding vectors. Must match
            the model used to generate them. Defaults to 768 (nomic-embed-text).
        similarity_function: Distance metric — "cosine" or "euclidean".
            Defaults to "cosine".
    """

    name: str
    label: str
    property_name: str
    dimensions: int = 768
    similarity_function: str = "cosine"


@dataclass(frozen=True)
class IndexMetadata:
    """Runtime metadata tracking the state of a vector index.

    Attributes:
        config: The VectorIndexConfig this metadata describes.
        node_count: Number of indexed nodes (updated after build). Defaults to 0.
        created_at: ISO 8601 timestamp of when the index was registered.
        status: Lifecycle state — "pending", "building", "ready", "error".
    """

    config: VectorIndexConfig
    node_count: int = 0
    created_at: str = ""
    status: str = "pending"


@dataclass(frozen=True)
class HybridSearchResult:
    """A single result from a hybrid (vector + full-text) search.

    Attributes:
        node_id: Identifier of the matched Neo4j node.
        score: Combined relevance score after fusion (e.g., RRF).
        vector_score: Raw score from the vector index query. Defaults to 0.0.
        text_score: Raw score from the full-text index query. Defaults to 0.0.
        properties: Additional node properties returned alongside the score.
    """

    node_id: str
    score: float
    vector_score: float = 0.0
    text_score: float = 0.0
    properties: dict[str, Any] = field(default_factory=dict)
