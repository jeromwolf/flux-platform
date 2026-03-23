"""Reranking module for RAG retrieval results.

Provides a Protocol-based reranker abstraction with multiple implementations:
- ScoreBoostReranker: Simple score multiplication (existing behavior)
- CrossEncoderReranker: Sentence-transformers cross-encoder (when available)
- APIReranker: HTTP-based reranking via external service
- FlashRankReranker: FlashRank library (lightweight, no GPU required)

Every reranker MUST work without its optional dependency by falling back
to ScoreBoostReranker. This guarantees the RAG pipeline never breaks
due to a missing pip package.

Usage::

    from rag.engines.reranker import create_reranker, RerankerConfig

    config = RerankerConfig(backend="cross_encoder")
    reranker = create_reranker(config)
    reranked = reranker.rerank("What is COLREG?", chunks, top_k=5)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class Reranker(Protocol):
    """Protocol for reranking retrieved chunks.

    All concrete implementations must satisfy this interface so the
    ``HybridRAGEngine`` can swap rerankers at construction time.
    """

    def rerank(self, query: str, chunks: list, top_k: int = 10) -> list:
        """Rerank chunks by relevance to query.

        Args:
            query: The user's search query.
            chunks: List of ``RetrievedChunk`` objects from retrieval stage.
            top_k: Maximum number of chunks to return after reranking.

        Returns:
            Reranked list of ``RetrievedChunk`` objects, sorted by
            descending relevance score, trimmed to *top_k*.
        """
        ...


@dataclass(frozen=True)
class RerankerConfig:
    """Configuration for reranker selection and tuning.

    Attributes:
        backend: Which reranker to instantiate.
            ``"score_boost"`` (default), ``"cross_encoder"``,
            ``"flash_rank"``, or ``"api"``.
        model_name: Model identifier for cross-encoder or flash-rank backends.
        api_url: Endpoint URL for the API reranker backend.
        score_boost: Multiplication factor for the score-boost reranker.
        batch_size: Batch size for cross-encoder inference.
    """

    backend: str = "score_boost"
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    api_url: str = ""
    score_boost: float = 1.1
    batch_size: int = 32


# ---------------------------------------------------------------------------
# ScoreBoostReranker (default / fallback)
# ---------------------------------------------------------------------------


@dataclass
class ScoreBoostReranker:
    """Simple reranker that boosts scores by a fixed factor.

    This is the default and fallback reranker.  It requires no external
    dependencies and is used when optional libraries are unavailable.

    The boost is *diminishing*: the top-ranked chunk receives the full
    ``boost_factor``, while lower-ranked chunks receive progressively
    less boost.  All scores are clamped to [0, 1].
    """

    boost_factor: float = 1.1

    def rerank(self, query: str, chunks: list, top_k: int = 10) -> list:
        """Rerank by multiplying scores with a diminishing positional boost."""
        if not chunks:
            return []

        from rag.engines.models import RetrievedChunk

        # Sort by original score descending, then apply diminishing boost
        sorted_chunks = sorted(chunks, key=lambda c: c.score, reverse=True)
        n = max(len(sorted_chunks), 1)
        reranked = []
        for i, chunk in enumerate(sorted_chunks[:top_k]):
            # Diminishing: top result gets full boost, linearly fading
            position_factor = 1.0 - (i / n) * 0.5
            new_score = min(chunk.score * self.boost_factor * position_factor, 1.0)
            reranked.append(
                RetrievedChunk(
                    chunk=chunk.chunk,
                    score=new_score,
                    retrieval_mode=chunk.retrieval_mode,
                )
            )

        return sorted(reranked, key=lambda c: c.score, reverse=True)


# ---------------------------------------------------------------------------
# CrossEncoderReranker
# ---------------------------------------------------------------------------


@dataclass
class CrossEncoderReranker:
    """Cross-encoder reranker using sentence-transformers.

    Computes a direct relevance score for each (query, document) pair
    using a cross-encoder model.  This is slower than bi-encoder
    retrieval but significantly more accurate for reranking.

    Falls back to ``ScoreBoostReranker`` if ``sentence-transformers``
    is not installed or the model fails to load.
    """

    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    batch_size: int = 32
    _model: object = field(default=None, init=False, repr=False)
    _fallback: ScoreBoostReranker = field(
        default_factory=ScoreBoostReranker, init=False
    )

    def _load_model(self) -> bool:
        """Lazy-load the cross-encoder model.

        Returns:
            True if model is ready, False if fallback is required.
        """
        if self._model is not None:
            return True
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            logger.info("Loaded cross-encoder model: %s", self.model_name)
            return True
        except ImportError:
            logger.warning(
                "sentence-transformers not installed, "
                "falling back to ScoreBoostReranker"
            )
            return False
        except Exception as e:
            logger.warning("Failed to load cross-encoder model: %s", e)
            return False

    def rerank(self, query: str, chunks: list, top_k: int = 10) -> list:
        """Rerank using cross-encoder similarity scores.

        Scores are normalised to [0, 1] via min-max scaling across the
        batch.  On any failure the method transparently falls back to
        ``ScoreBoostReranker``.
        """
        if not chunks:
            return []

        if not self._load_model():
            return self._fallback.rerank(query, chunks, top_k)

        from rag.engines.models import RetrievedChunk

        # Prepare query-document pairs
        pairs = [(query, c.chunk.content) for c in chunks]

        try:
            scores = self._model.predict(pairs, batch_size=self.batch_size)

            # Min-max normalise to [0, 1]
            min_score = float(min(scores)) if len(scores) > 0 else 0.0
            max_score = float(max(scores)) if len(scores) > 0 else 1.0
            score_range = max_score - min_score
            if score_range == 0:
                score_range = 1.0

            reranked = []
            for chunk, score in zip(chunks, scores):
                normalized = (float(score) - min_score) / score_range
                reranked.append(
                    RetrievedChunk(
                        chunk=chunk.chunk,
                        score=normalized,
                        retrieval_mode=chunk.retrieval_mode,
                    )
                )

            reranked.sort(key=lambda c: c.score, reverse=True)
            return reranked[:top_k]
        except Exception as e:
            logger.warning(
                "Cross-encoder reranking failed: %s, using fallback", e
            )
            return self._fallback.rerank(query, chunks, top_k)


# ---------------------------------------------------------------------------
# FlashRankReranker
# ---------------------------------------------------------------------------


@dataclass
class FlashRankReranker:
    """Lightweight reranker using FlashRank (no GPU required).

    FlashRank provides efficient ONNX-based reranking models that run
    on CPU.  Falls back to ``ScoreBoostReranker`` if the ``flashrank``
    package is not installed.
    """

    model_name: str = "ms-marco-MiniLM-L-12-v2"
    _ranker: object = field(default=None, init=False, repr=False)
    _fallback: ScoreBoostReranker = field(
        default_factory=ScoreBoostReranker, init=False
    )

    def _load_ranker(self) -> bool:
        """Lazy-load the FlashRank model.

        Returns:
            True if ranker is ready, False if fallback is required.
        """
        if self._ranker is not None:
            return True
        try:
            from flashrank import Ranker

            self._ranker = Ranker(model_name=self.model_name)
            logger.info("Loaded FlashRank model: %s", self.model_name)
            return True
        except ImportError:
            logger.warning(
                "flashrank not installed, falling back to ScoreBoostReranker"
            )
            return False
        except Exception as e:
            logger.warning("Failed to load FlashRank: %s", e)
            return False

    def rerank(self, query: str, chunks: list, top_k: int = 10) -> list:
        """Rerank using FlashRank ONNX models.

        On any failure the method transparently falls back to
        ``ScoreBoostReranker``.
        """
        if not chunks:
            return []

        if not self._load_ranker():
            return self._fallback.rerank(query, chunks, top_k)

        from rag.engines.models import RetrievedChunk

        try:
            from flashrank import RerankRequest

            passages = [
                {"id": str(i), "text": c.chunk.content}
                for i, c in enumerate(chunks)
            ]
            request = RerankRequest(query=query, passages=passages)
            results = self._ranker.rerank(request)

            # Map results back to original chunks
            id_to_chunk = {str(i): c for i, c in enumerate(chunks)}
            reranked = []
            for r in results[:top_k]:
                original = id_to_chunk.get(r["id"])
                if original:
                    reranked.append(
                        RetrievedChunk(
                            chunk=original.chunk,
                            score=float(r.get("score", 0.0)),
                            retrieval_mode=original.retrieval_mode,
                        )
                    )
            return reranked
        except Exception as e:
            logger.warning("FlashRank reranking failed: %s, using fallback", e)
            return self._fallback.rerank(query, chunks, top_k)


# ---------------------------------------------------------------------------
# APIReranker
# ---------------------------------------------------------------------------


@dataclass
class APIReranker:
    """HTTP-based reranker for external reranking services.

    Supports Cohere-compatible reranking APIs (``/rerank`` endpoint).
    Falls back to ``ScoreBoostReranker`` on connection failure or when
    no ``api_url`` is configured.

    Environment variable ``RERANKER_API_KEY`` is read at construction
    time via the ``create_reranker`` factory.
    """

    api_url: str = ""
    api_key: str = ""
    model: str = "rerank-multilingual-v3.0"
    _fallback: ScoreBoostReranker = field(
        default_factory=ScoreBoostReranker, init=False
    )

    def rerank(self, query: str, chunks: list, top_k: int = 10) -> list:
        """Rerank via HTTP POST to an external service.

        On any failure (timeout, bad response, missing URL) the method
        transparently falls back to ``ScoreBoostReranker``.
        """
        if not chunks or not self.api_url:
            return (
                self._fallback.rerank(query, chunks, top_k) if chunks else []
            )

        from rag.engines.models import RetrievedChunk
        import json
        from urllib.request import Request, urlopen

        try:
            documents = [c.chunk.content for c in chunks]
            payload = json.dumps(
                {
                    "model": self.model,
                    "query": query,
                    "documents": documents,
                    "top_n": top_k,
                }
            ).encode()

            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            req = Request(
                self.api_url,
                data=payload,
                headers=headers,
                method="POST",
            )
            resp = urlopen(req, timeout=10)
            data = json.loads(resp.read())

            results = data.get("results", [])
            reranked = []
            for r in results:
                idx = r.get("index", 0)
                if 0 <= idx < len(chunks):
                    reranked.append(
                        RetrievedChunk(
                            chunk=chunks[idx].chunk,
                            score=float(r.get("relevance_score", 0.0)),
                            retrieval_mode=chunks[idx].retrieval_mode,
                        )
                    )
            return reranked[:top_k]
        except Exception as e:
            logger.warning("API reranking failed: %s", e)
            return self._fallback.rerank(query, chunks, top_k)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_reranker(config: RerankerConfig | None = None) -> Reranker:
    """Factory to create a reranker based on configuration.

    Args:
        config: Reranker configuration. Defaults to
            ``RerankerConfig()`` (score-boost backend).

    Returns:
        A ``Reranker``-conformant instance.

    Examples::

        # Default (no optional deps needed)
        reranker = create_reranker()

        # Cross-encoder (needs sentence-transformers; falls back if absent)
        reranker = create_reranker(RerankerConfig(backend="cross_encoder"))

        # External API
        reranker = create_reranker(RerankerConfig(
            backend="api",
            api_url="https://api.cohere.com/v1/rerank",
        ))
    """
    if config is None:
        config = RerankerConfig()

    if config.backend == "cross_encoder":
        return CrossEncoderReranker(
            model_name=config.model_name,
            batch_size=config.batch_size,
        )
    elif config.backend == "flash_rank":
        return FlashRankReranker(model_name=config.model_name)
    elif config.backend == "api":
        import os

        return APIReranker(
            api_url=config.api_url,
            api_key=os.environ.get("RERANKER_API_KEY", ""),
        )
    else:
        return ScoreBoostReranker(boost_factor=config.score_boost)
