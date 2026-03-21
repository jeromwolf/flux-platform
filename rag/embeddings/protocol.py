"""Structural protocol for embedding providers."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from rag.embeddings.models import EmbeddingResult


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Interface that every embedding backend must satisfy.

    Concrete implementations can wrap Ollama, OpenAI, a local sentence-
    transformer, or any other vector model as long as they fulfil this
    contract.
    """

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        """Encode a batch of texts into dense vectors.

        Args:
            texts: Non-empty list of strings to embed.

        Returns:
            ``EmbeddingResult`` containing one vector per input string.
        """
        ...

    def embed_query(self, query: str) -> tuple[float, ...]:
        """Encode a single query string into a dense vector.

        Args:
            query: User query or search string.

        Returns:
            Flat tuple of floats representing the query vector.
        """
        ...

    @property
    def dimension(self) -> int:
        """Dimensionality of the vectors produced by this provider."""
        ...
