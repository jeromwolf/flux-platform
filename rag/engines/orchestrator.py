"""Hybrid RAG orchestrator combining multiple retrieval strategies.

Supports semantic (vector), keyword (TF), and hybrid (reciprocal rank fusion)
retrieval modes with optional re-ranking.

Usage::

    orchestrator = HybridRAGEngine(retriever=my_retriever)
    result = orchestrator.query("What is COLREG?", query_embedding=vec)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from rag.documents.models import DocumentChunk
from rag.engines.models import RAGConfig, RAGResult, RetrievalMode, RetrievedChunk
from rag.engines.retriever import SimpleRetriever

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankerConfig:
    """Configuration for the re-ranking stage."""

    enabled: bool = False
    top_k: int = 3  # Final top-k after re-ranking
    strategy: str = "score_boost"  # "score_boost", "cross_encoder" (Y2)


class HybridRAGEngine:
    """Hybrid RAG engine combining semantic + keyword retrieval.

    Retrieval strategies:
    - SEMANTIC: Vector cosine similarity only
    - KEYWORD: Term frequency search only
    - HYBRID: Reciprocal rank fusion of both strategies

    Optional re-ranking stage refines the final results.
    """

    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        retriever: Optional[SimpleRetriever] = None,
        reranker_config: Optional[RerankerConfig] = None,
        llm: Any = None,  # Optional LLM for answer generation
    ) -> None:
        self._config = config or RAGConfig()
        self._retriever = retriever or SimpleRetriever(self._config)
        self._reranker = reranker_config or RerankerConfig()
        self._llm = llm

    @property
    def config(self) -> RAGConfig:
        return self._config

    @property
    def retriever(self) -> SimpleRetriever:
        return self._retriever

    def query(
        self,
        query_text: str,
        query_embedding: Optional[tuple[float, ...]] = None,
        top_k: Optional[int] = None,
    ) -> RAGResult:
        """Execute a RAG query.

        Args:
            query_text: The user's question.
            query_embedding: Dense vector for semantic search (required for SEMANTIC/HYBRID).
            top_k: Override config top_k.

        Returns:
            RAGResult with retrieved chunks and optional answer.
        """
        start = time.monotonic()
        k = top_k or self._config.top_k

        # 1. Retrieve based on mode
        if self._config.mode == RetrievalMode.SEMANTIC:
            if query_embedding is None:
                return self._empty_result(
                    query_text, start, "query_embedding required for SEMANTIC mode"
                )
            chunks = self._retriever.retrieve(query_embedding, top_k=k * 2)  # over-fetch for re-ranking

        elif self._config.mode == RetrievalMode.KEYWORD:
            chunks = self._retriever.keyword_search(query_text, top_k=k * 2)

        else:  # HYBRID
            chunks = self._hybrid_retrieve(query_text, query_embedding, k)

        # 2. Optional re-ranking
        if self._reranker.enabled and len(chunks) > 0:
            chunks = self._rerank(chunks, query_text)

        # 3. Truncate to final top_k
        final_chunks = chunks[:k]

        # 4. Generate answer (if LLM available)
        answer = self._generate_answer(query_text, final_chunks)

        duration = (time.monotonic() - start) * 1000
        return RAGResult(
            answer=answer,
            retrieved_chunks=tuple(final_chunks),
            query=query_text,
            duration_ms=round(duration, 2),
        )

    def _hybrid_retrieve(
        self,
        query_text: str,
        query_embedding: Optional[tuple[float, ...]],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Combine semantic + keyword results using reciprocal rank fusion."""
        fetch_k = top_k * 3  # over-fetch both sides

        semantic_results: list[RetrievedChunk] = []
        if query_embedding is not None:
            semantic_results = self._retriever.retrieve(query_embedding, top_k=fetch_k)

        keyword_results = self._retriever.keyword_search(query_text, top_k=fetch_k)

        # Reciprocal Rank Fusion (RRF)
        return self._reciprocal_rank_fusion(semantic_results, keyword_results, top_k=top_k * 2)

    @staticmethod
    def _reciprocal_rank_fusion(
        *result_lists: list[RetrievedChunk],
        k: int = 60,
        top_k: int = 10,
    ) -> list[RetrievedChunk]:
        """Combine multiple ranked lists using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank + 1)) across all lists.
        Higher k gives more weight to lower-ranked results.
        """
        # Score by chunk_id
        scores: dict[str, float] = {}
        chunk_map: dict[str, RetrievedChunk] = {}

        for result_list in result_lists:
            for rank, rc in enumerate(result_list):
                cid = rc.chunk.chunk_id
                rrf_score = 1.0 / (k + rank + 1)
                scores[cid] = scores.get(cid, 0.0) + rrf_score
                # Keep the highest-scored version
                if cid not in chunk_map or rc.score > chunk_map[cid].score:
                    chunk_map[cid] = rc

        # Sort by RRF score
        sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

        return [
            RetrievedChunk(
                chunk=chunk_map[cid].chunk,
                score=round(scores[cid], 6),
                retrieval_mode=RetrievalMode.HYBRID,
            )
            for cid in sorted_ids[:top_k]
        ]

    def _rerank(self, chunks: list[RetrievedChunk], query: str) -> list[RetrievedChunk]:
        """Re-rank retrieved chunks.

        Y1: Simple score_boost based on query term overlap.
        Y2: Cross-encoder re-ranking.
        """
        if self._reranker.strategy == "score_boost":
            return self._score_boost_rerank(chunks, query)
        return chunks  # Unknown strategy = passthrough

    @staticmethod
    def _score_boost_rerank(chunks: list[RetrievedChunk], query: str) -> list[RetrievedChunk]:
        """Boost scores based on query term presence in chunk content."""
        terms = [t.lower() for t in query.split() if len(t) > 2]
        if not terms:
            return chunks

        boosted: list[RetrievedChunk] = []
        for rc in chunks:
            content_lower = rc.chunk.content.lower()
            matches = sum(1 for t in terms if t in content_lower)
            boost = 1.0 + (matches / len(terms)) * 0.3  # up to 30% boost
            new_score = min(rc.score * boost, 1.0)
            boosted.append(
                RetrievedChunk(
                    chunk=rc.chunk,
                    score=round(new_score, 6),
                    retrieval_mode=rc.retrieval_mode,
                )
            )

        boosted.sort(key=lambda x: x.score, reverse=True)
        return boosted

    def _generate_answer(self, query: str, chunks: list[RetrievedChunk]) -> str:
        """Generate answer using LLM if available, otherwise return context summary."""
        if not chunks:
            return "No relevant information found."

        if self._llm is not None:
            context = "\n\n".join(rc.chunk.content for rc in chunks)
            prompt = (
                f"Based on the following context, answer the question.\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {query}\n\n"
                f"Answer:"
            )
            try:
                response = self._llm.generate(prompt)
                return response.text
            except Exception as exc:
                logger.warning("LLM answer generation failed: %s", exc)

        # Fallback: return top chunk content as answer
        return chunks[0].chunk.content

    def _empty_result(self, query: str, start_time: float, error: str = "") -> RAGResult:
        """Return empty result with timing."""
        duration = (time.monotonic() - start_time) * 1000
        logger.warning("RAG query returned empty: %s", error)
        return RAGResult(
            answer=error or "No results",
            retrieved_chunks=(),
            query=query,
            duration_ms=round(duration, 2),
        )
