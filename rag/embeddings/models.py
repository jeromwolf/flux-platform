"""Embedding configuration and result models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmbeddingConfig:
    """Configuration for an embedding provider.

    Attributes:
        model_name: Identifier of the embedding model to use.
        dimension: Expected output vector dimensionality.
        batch_size: Number of texts to embed in a single request.
        normalize: Whether to L2-normalise the output vectors.
    """

    model_name: str = "nomic-embed-text"
    dimension: int = 768
    batch_size: int = 32
    normalize: bool = True


@dataclass(frozen=True)
class EmbeddingResult:
    """Result returned by an embedding provider after encoding a batch.

    Attributes:
        vectors: Tuple of dense float vectors, one per input text.
        model: Model identifier used to produce the embeddings.
        dimension: Vector dimensionality.
        token_count: Total number of tokens consumed (0 if unknown).
        duration_ms: Wall-clock time for the embedding call in milliseconds.
    """

    vectors: tuple[tuple[float, ...], ...]
    model: str
    dimension: int
    token_count: int = 0
    duration_ms: float = 0.0
