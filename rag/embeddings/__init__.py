"""Embedding generation and vector operations."""
from rag.embeddings.models import EmbeddingConfig, EmbeddingResult
from rag.embeddings.protocol import EmbeddingProvider
from rag.embeddings.providers import (
    StubEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
)

__all__ = [
    "EmbeddingConfig",
    "EmbeddingProvider",
    "EmbeddingResult",
    "StubEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "OpenAIEmbeddingProvider",
]
