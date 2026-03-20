"""Embedding utilities for the Maritime KG platform.

Provides:
- OllamaEmbedder: Thin wrapper around neo4j-graphrag OllamaEmbeddings
- generate_embeddings_batch: Batch generator for Document node embeddings
"""

from kg.embeddings.ollama_embedder import (
    EmbeddingResult,
    OllamaEmbedder,
    generate_embeddings_batch,
)

__all__ = [
    "OllamaEmbedder",
    "EmbeddingResult",
    "generate_embeddings_batch",
]
