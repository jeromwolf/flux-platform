"""RAG engine configuration and result models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from rag.documents.models import DocumentChunk


class RetrievalMode(str, Enum):
    """Strategy used to retrieve relevant chunks."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class RAGConfig:
    """Configuration for the RAG retrieval pipeline.

    Attributes:
        mode: Retrieval strategy (semantic, keyword, or hybrid).
        top_k: Maximum number of chunks to return per query.
        similarity_threshold: Minimum cosine similarity score to include a chunk.
        rerank: Whether to apply a re-ranker after retrieval.
        reranker_backend: Which reranker backend to use.
            ``"score_boost"`` (default), ``"cross_encoder"``,
            ``"flash_rank"``, or ``"api"``.
        include_metadata: Whether to propagate chunk metadata to the result.
    """

    mode: RetrievalMode = RetrievalMode.HYBRID
    top_k: int = 5
    similarity_threshold: float = 0.7
    rerank: bool = False
    reranker_backend: str = "score_boost"
    include_metadata: bool = True


@dataclass(frozen=True)
class RetrievedChunk:
    """A document chunk paired with its retrieval score.

    Attributes:
        chunk: The underlying ``DocumentChunk``.
        score: Relevance score in [0, 1] (higher is more relevant).
        retrieval_mode: The strategy that produced this result.
    """

    chunk: DocumentChunk
    score: float
    retrieval_mode: RetrievalMode


@dataclass(frozen=True)
class RAGResult:
    """Final result of a RAG query.

    Attributes:
        answer: Generated or extracted answer text.
        retrieved_chunks: Ordered tuple of chunks used to produce the answer.
        query: The original user query string.
        duration_ms: Total pipeline wall-clock time in milliseconds.
    """

    answer: str
    retrieved_chunks: tuple[RetrievedChunk, ...]
    query: str
    duration_ms: float = 0.0

    @property
    def chunk_count(self) -> int:
        """Number of chunks included in this result."""
        return len(self.retrieved_chunks)

    @property
    def avg_score(self) -> float:
        """Average relevance score across retrieved chunks.

        Returns 0.0 when no chunks are present.
        """
        if not self.retrieved_chunks:
            return 0.0
        return sum(rc.score for rc in self.retrieved_chunks) / len(self.retrieved_chunks)
