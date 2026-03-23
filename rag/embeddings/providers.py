"""Embedding provider implementations.

Y1: Stub/deterministic providers for testing.
Real providers: Ollama (HTTP API), OpenAI (REST API).
All external dependencies are optional; providers fall back to stub on failure.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import urllib.error
import urllib.request
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
    """Ollama embedding provider using the HTTP API directly.

    Calls the Ollama ``/api/embeddings`` endpoint for each text.
    Falls back to ``StubEmbeddingProvider`` when the Ollama server is
    unreachable or returns an error.

    Environment variables:
        OLLAMA_BASE_URL: Base URL of the Ollama server
                         (default ``http://localhost:11434``).

    Example::

        provider = OllamaEmbeddingProvider()
        result = provider.embed_texts(["hello world"])
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None) -> None:
        self._config = config or EmbeddingConfig(
            model_name="nomic-embed-text", dimension=768
        )
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self._model = self._config.model_name
        self._stub = StubEmbeddingProvider(self._config)

    @property
    def dimension(self) -> int:
        return self._config.dimension

    def _embed_single(self, text: str) -> tuple[float, ...]:
        """Call Ollama /api/embeddings for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as a tuple of floats.

        Raises:
            RuntimeError: When the HTTP request or JSON parsing fails.
        """
        url = f"{self._base_url}/api/embeddings"
        payload = json.dumps({"model": self._model, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        vector = body.get("embedding")
        if not vector:
            raise RuntimeError(f"Ollama returned no embedding: {body}")
        return tuple(float(v) for v in vector)

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        """Embed a list of texts via Ollama.

        Processes each text individually (Ollama does not natively support
        batch embedding in the Y1 API).  Falls back to stub on any error.

        Args:
            texts: List of text strings to embed.

        Returns:
            EmbeddingResult with one vector per input text.
        """
        if not texts:
            return EmbeddingResult(
                vectors=(),
                model=self._model,
                dimension=self._config.dimension,
                token_count=0,
            )

        vectors: list[tuple[float, ...]] = []
        try:
            for text in texts:
                vec = self._embed_single(text)
                vectors.append(vec)
            return EmbeddingResult(
                vectors=tuple(vectors),
                model=self._model,
                dimension=len(vectors[0]) if vectors else self._config.dimension,
                token_count=sum(len(t.split()) for t in texts),
            )
        except (urllib.error.URLError, OSError) as exc:
            logger.warning("Ollama server unreachable, falling back to stub: %s", exc)
            return self._stub.embed_texts(texts)
        except Exception as exc:
            logger.warning("Ollama embedding failed, falling back to stub: %s", exc)
            return self._stub.embed_texts(texts)

    def embed_query(self, query: str) -> tuple[float, ...]:
        """Embed a single query string.

        Args:
            query: Query text.

        Returns:
            Embedding vector as a tuple of floats.
        """
        result = self.embed_texts([query])
        return result.vectors[0] if result.vectors else ()


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider using the REST API.

    Calls the OpenAI ``/v1/embeddings`` endpoint.
    Falls back to ``StubEmbeddingProvider`` when no API key is provided or
    the API call fails.

    Environment variables:
        OPENAI_API_KEY: OpenAI API key (overridden by the ``api_key`` arg).

    Example::

        provider = OpenAIEmbeddingProvider(api_key="sk-...")
        result = provider.embed_texts(["hello world"])
    """

    _OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"

    def __init__(
        self,
        config: Optional[EmbeddingConfig] = None,
        api_key: str = "",
    ) -> None:
        self._config = config or EmbeddingConfig(
            model_name="text-embedding-3-small", dimension=1536
        )
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._stub = StubEmbeddingProvider(self._config)

    @property
    def dimension(self) -> int:
        return self._config.dimension

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        """Embed a list of texts via the OpenAI API.

        Falls back to stub when no API key is configured or the request fails.

        Args:
            texts: List of text strings to embed.

        Returns:
            EmbeddingResult with one vector per input text.
        """
        if not self._api_key:
            logger.debug("No OpenAI API key configured; using stub embeddings")
            return self._stub.embed_texts(texts)

        if not texts:
            return EmbeddingResult(
                vectors=(),
                model=self._config.model_name,
                dimension=self._config.dimension,
                token_count=0,
            )

        try:
            payload = json.dumps({
                "model": self._config.model_name,
                "input": texts,
            }).encode("utf-8")
            req = urllib.request.Request(
                self._OPENAI_EMBEDDINGS_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            items = sorted(body["data"], key=lambda x: x["index"])
            vectors = tuple(tuple(float(v) for v in item["embedding"]) for item in items)
            total_tokens = body.get("usage", {}).get("total_tokens", 0)

            return EmbeddingResult(
                vectors=vectors,
                model=self._config.model_name,
                dimension=len(vectors[0]) if vectors else self._config.dimension,
                token_count=total_tokens,
            )
        except (urllib.error.URLError, OSError) as exc:
            logger.warning("OpenAI API unreachable, falling back to stub: %s", exc)
            return self._stub.embed_texts(texts)
        except Exception as exc:
            logger.warning("OpenAI embedding failed, falling back to stub: %s", exc)
            return self._stub.embed_texts(texts)

    def embed_query(self, query: str) -> tuple[float, ...]:
        """Embed a single query string.

        Args:
            query: Query text.

        Returns:
            Embedding vector as a tuple of floats.
        """
        result = self.embed_texts([query])
        return result.vectors[0] if result.vectors else ()
