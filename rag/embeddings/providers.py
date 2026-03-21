"""Embedding provider implementations.

Y1: Stub/random providers for testing.
Y2: Ollama, OpenAI embedding integrations.
"""
from __future__ import annotations

import hashlib
import logging
import math
from typing import Optional

from rag.embeddings.models import EmbeddingConfig, EmbeddingResult

logger = logging.getLogger(__name__)


class StubEmbeddingProvider:
    """Deterministic stub embedding provider for testing.

    Generates reproducible pseudo-random vectors based on text content
    hash. Does NOT use actual ML models.
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None) -> None:
        self._config = config or EmbeddingConfig(dimension=64)

    @property
    def dimension(self) -> int:
        return self._config.dimension

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        """Generate deterministic embeddings from text hashes."""
        vectors = tuple(self._hash_to_vector(t) for t in texts)
        return EmbeddingResult(
            vectors=vectors,
            model=f"stub-{self._config.dimension}d",
            dimension=self._config.dimension,
            token_count=sum(len(t.split()) for t in texts),
        )

    def embed_query(self, query: str) -> tuple[float, ...]:
        """Generate a deterministic query embedding."""
        return self._hash_to_vector(query)

    def _hash_to_vector(self, text: str) -> tuple[float, ...]:
        """Convert text to a deterministic pseudo-random unit vector."""
        # Use SHA-256 to generate deterministic bytes
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        dim = self._config.dimension

        # Generate values from hex pairs
        raw = []
        for i in range(dim):
            # Cycle through hash chars
            idx = (i * 2) % len(h)
            val = int(h[idx : idx + 2], 16) / 255.0  # 0.0 to 1.0
            raw.append(val - 0.5)  # Center around 0

        # L2 normalize if configured
        if self._config.normalize:
            magnitude = math.sqrt(sum(x * x for x in raw))
            if magnitude > 0:
                raw = [x / magnitude for x in raw]

        return tuple(raw)


class OllamaEmbeddingProvider:
    """Ollama embedding provider stub.

    Y1: Returns stub embeddings. Y2: Uses actual Ollama API.
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None) -> None:
        self._config = config or EmbeddingConfig(
            model_name="nomic-embed-text", dimension=768
        )
        self._stub = StubEmbeddingProvider(self._config)

    @property
    def dimension(self) -> int:
        return self._config.dimension

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        try:
            from langchain_ollama import OllamaEmbeddings
        except ImportError:
            logger.debug("langchain-ollama not installed, using stub embeddings")
            return self._stub.embed_texts(texts)

        # Y2: actual Ollama embedding
        try:
            embedder = OllamaEmbeddings(model=self._config.model_name)
            vectors = embedder.embed_documents(texts)
            return EmbeddingResult(
                vectors=tuple(tuple(v) for v in vectors),
                model=self._config.model_name,
                dimension=len(vectors[0]) if vectors else self._config.dimension,
                token_count=sum(len(t.split()) for t in texts),
            )
        except Exception as exc:
            logger.warning(
                "Ollama embedding failed, falling back to stub: %s", exc
            )
            return self._stub.embed_texts(texts)

    def embed_query(self, query: str) -> tuple[float, ...]:
        result = self.embed_texts([query])
        return result.vectors[0] if result.vectors else ()


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider stub.

    Y1: Returns stub embeddings. Y2: Uses actual OpenAI API.
    """

    def __init__(
        self,
        config: Optional[EmbeddingConfig] = None,
        api_key: str = "",
    ) -> None:
        self._config = config or EmbeddingConfig(
            model_name="text-embedding-3-small", dimension=1536
        )
        self._api_key = api_key
        self._stub = StubEmbeddingProvider(self._config)

    @property
    def dimension(self) -> int:
        return self._config.dimension

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not self._api_key:
            return self._stub.embed_texts(texts)
        # Y2: actual OpenAI API call
        return self._stub.embed_texts(texts)

    def embed_query(self, query: str) -> tuple[float, ...]:
        result = self.embed_texts([query])
        return result.vectors[0] if result.vectors else ()
