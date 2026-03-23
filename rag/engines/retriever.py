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
        """BM25 keyword-based search.

        Ranks chunks using the Okapi BM25 formula, which normalises term
        frequency by document length and applies an inverse document frequency
        weight so rare query terms score higher.

        BM25 parameters:
            k1 = 1.5  — term-frequency saturation
            b  = 0.75 — document-length normalisation factor

        Formula per chunk for each query term *t*::

            IDF(t) * tf(t, d) * (k1 + 1)
            ─────────────────────────────────────────────────────────────────
            tf(t, d) + k1 * (1 − b + b * doc_len / avg_doc_len)

        where ``IDF(t) = log((N − n(t) + 0.5) / (n(t) + 0.5) + 1)`` and
        ``N`` is the total number of indexed chunks, ``n(t)`` is the number
        of chunks containing term *t*.

        The final per-chunk score is the sum of BM25 contributions across
        all query terms, then normalised to [0, 1] by dividing by the
        maximum score in the result set (or 1.0 when all scores are zero).

        Args:
            query: Raw query string; split on whitespace into search terms.
            top_k: Override ``RAGConfig.top_k`` for this call.

        Returns:
            Up to *top_k* ``RetrievedChunk`` objects sorted by descending
            BM25 score (zero-score chunks are excluded).
        """
        k = top_k if top_k is not None else self._config.top_k
        terms = [t.lower() for t in query.split() if t.strip()]
        if not terms:
            return []

        if not self._chunks:
            return []

        # Pre-tokenise every chunk once
        tokenised: list[list[str]] = [c.content.lower().split() for c in self._chunks]
        doc_lengths = [len(words) for words in tokenised]
        n_docs = len(self._chunks)
        avg_dl = sum(doc_lengths) / max(n_docs, 1)

        # BM25 hyper-parameters
        k1: float = 1.5
        b: float = 0.75

        # Document frequency per query term (number of docs containing the term)
        doc_freq: dict[str, int] = {}
        for term in set(terms):
            doc_freq[term] = sum(1 for words in tokenised if term in words)

        raw_scores: list[float] = []
        for idx, words in enumerate(tokenised):
            dl = doc_lengths[idx]
            score = 0.0
            word_count: dict[str, int] = {}
            for w in words:
                word_count[w] = word_count.get(w, 0) + 1

            for term in terms:
                tf = word_count.get(term, 0)
                if tf == 0:
                    continue
                n_t = doc_freq.get(term, 0)
                # IDF with smoothing
                idf = math.log((n_docs - n_t + 0.5) / (n_t + 0.5) + 1.0)
                # BM25 TF component
                tf_component = tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / max(avg_dl, 1)))
                score += idf * tf_component

            raw_scores.append(score)

        # Normalise to [0, 1]
        max_score = max(raw_scores) if raw_scores else 0.0
        normaliser = max_score if max_score > 0.0 else 1.0

        scored: list[tuple[float, DocumentChunk]] = []
        for idx, chunk in enumerate(self._chunks):
            norm_score = raw_scores[idx] / normaliser
            if norm_score > 0.0:
                scored.append((norm_score, chunk))

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
