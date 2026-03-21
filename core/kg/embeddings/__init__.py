"""Embedding utilities for the Maritime KG platform."""

from kg.embeddings.manager import EmbeddingManager
from kg.embeddings.models import HybridSearchResult, IndexMetadata, VectorIndexConfig
from kg.embeddings.ollama_embedder import (
    EmbeddingResult,
    OllamaEmbedder,
    generate_embeddings_batch,
)

__all__ = [
    "EmbeddingManager",
    "EmbeddingResult",
    "HybridSearchResult",
    "IndexMetadata",
    "OllamaEmbedder",
    "VectorIndexConfig",
    "generate_embeddings_batch",
]
