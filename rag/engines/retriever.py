"""Simple in-memory retriever for Y1 RAG pipeline."""
from __future__ import annotations

import math

from rag.documents.models import DocumentChunk
from rag.engines.models import RAGConfig, RetrievalMode, RetrievedChunk


class SimpleRetriever:
    """Simple in-memory retriever using cosine similarity.

    Y1 implementation: stores chunks in memory with embeddings and retrieves
    by cosine similarity.  Y2+ will replace the in-memory store with a
    dedicated vector database (Milvus / Weaviate).

    All computation uses pure Python stdlib — no numpy, no external packages.

    Example::

        retriever = SimpleRetriever()
        retriever.add_chunks(embedded_chunks)
        results = retriever.retrieve(query_vector, top_k=5)
    """

    def __init__(self, config: RAGConfig | None = None) -> None:
        self._config: RAGConfig = config or RAGConfig()
        self._chunks: list[DocumentChunk] = []

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Add embedded chunks to the retriever index.

        Only chunks that already carry an embedding vector are accepted.

        Args:
            chunks: Chunks to index, typically produced by ``TextChunker``
                    and then enriched with embeddings by an
                    ``EmbeddingProvider``.

        Returns:
            Number of chunks actually added (those with embeddings).
        """
        added = 0
        for chunk in chunks:
            if chunk.has_embedding:
                self._chunks.append(chunk)
                added += 1
        return added

    def clear(self) -> None:
        """Remove all indexed chunks."""
        self._chunks.clear()

    @property
    def chunk_count(self) -> int:
        """Number of chunks currently held in the index."""
        return len(self._chunks)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query_embedding: tuple[float, ...],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve the most similar chunks by cosine similarity.

        Args:
            query_embedding: Dense query vector produced by an
                ``EmbeddingProvider``.
            top_k: Override ``RAGConfig.top_k`` for this call.

        Returns:
            Up to *top_k* ``RetrievedChunk`` objects sorted by descending
            score, filtered to scores >= ``similarity_threshold``.
        """
        k = top_k if top_k is not None else self._config.top_k
        threshold = self._config.similarity_threshold

        scored: list[tuple[float, DocumentChunk]] = []
        for chunk in self._chunks:
            if not chunk.has_embedding:
                continue
            score = self.cosine_similarity(query_embedding, chunk.embedding)
            if score >= threshold:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            RetrievedChunk(chunk=chunk, score=score, retrieval_mode=RetrievalMode.SEMANTIC)
            for score, chunk in scored[:k]
        ]

    def keyword_search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Simple keyword-based search using term-frequency scoring.

        Scores each chunk by the number of query terms it contains,
        normalised by the chunk length (TF-like measure).  The result is
        bounded to [0, 1] by capping at 1.0.

        Args:
            query: Raw query string; split on whitespace into search terms.
            top_k: Override ``RAGConfig.top_k`` for this call.

        Returns:
            Up to *top_k* ``RetrievedChunk`` objects sorted by descending
            score (zero-score chunks are excluded).
        """
        k = top_k if top_k is not None else self._config.top_k
        terms = [t.lower() for t in query.split() if t.strip()]
        if not terms:
            return []

        scored: list[tuple[float, DocumentChunk]] = []
        for chunk in self._chunks:
            chunk_lower = chunk.content.lower()
            chunk_words = chunk_lower.split()
            total_words = max(len(chunk_words), 1)

            # Count how many times any query term appears
            hit_count = sum(chunk_lower.count(term) for term in terms)
            if hit_count == 0:
                continue

            # Normalise: hits per word, scaled by query coverage
            tf_score = hit_count / total_words
            # Blend with query coverage (fraction of terms found at all)
            terms_found = sum(1 for term in terms if term in chunk_lower)
            coverage = terms_found / len(terms)
            score = min(tf_score * 10 * coverage, 1.0)  # scale to ~[0,1]
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            RetrievedChunk(chunk=chunk, score=score, retrieval_mode=RetrievalMode.KEYWORD)
            for score, chunk in scored[:k]
        ]

    # ------------------------------------------------------------------
    # Static utilities
    # ------------------------------------------------------------------

    @staticmethod
    def cosine_similarity(
        a: tuple[float, ...],
        b: tuple[float, ...],
    ) -> float:
        """Calculate cosine similarity between two vectors.

        Pure Python implementation using ``math.sqrt`` and built-in ``sum``.
        Returns 0.0 when either vector has zero magnitude or the vectors
        have different dimensions.

        Args:
            a: First vector as a tuple of floats.
            b: Second vector as a tuple of floats.

        Returns:
            Cosine similarity in [-1, 1].  Typically [0, 1] for embedding
            vectors produced by language models.
        """
        if len(a) != len(b) or not a:
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))

        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0

        return dot / (mag_a * mag_b)
