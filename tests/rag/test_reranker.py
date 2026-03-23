"""Unit tests for the reranker module.

Covers:
    TC-RR01: ScoreBoostReranker
    TC-RR02: CrossEncoderReranker (fallback behaviour)
    TC-RR03: FlashRankReranker (fallback behaviour)
    TC-RR04: APIReranker (fallback behaviour)
    TC-RR05: create_reranker factory
    TC-RR06: Reranker Protocol compliance
    TC-RR07: HybridRAGEngine orchestrator integration

All tests are marked @pytest.mark.unit and require no external dependencies.
PYTHONPATH: .
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rag.documents.models import DocumentChunk
from rag.engines.models import RAGConfig, RetrievalMode, RetrievedChunk
from rag.engines.reranker import (
    APIReranker,
    CrossEncoderReranker,
    FlashRankReranker,
    Reranker,
    RerankerConfig,
    ScoreBoostReranker,
    create_reranker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_id: str,
    content: str,
    score: float = 0.5,
    mode: RetrievalMode = RetrievalMode.HYBRID,
) -> RetrievedChunk:
    """Build a RetrievedChunk for testing."""
    chunk = DocumentChunk(
        chunk_id=chunk_id,
        doc_id="d1",
        content=content,
        chunk_index=0,
        embedding=(0.1, 0.2, 0.3),
    )
    return RetrievedChunk(chunk=chunk, score=score, retrieval_mode=mode)


def _sample_chunks() -> list[RetrievedChunk]:
    """Return a small set of diverse chunks for reranking tests."""
    return [
        _make_chunk("c1", "COLREG maritime vessel navigation rules", 0.9),
        _make_chunk("c2", "Weather forecast for the Pacific ocean region", 0.7),
        _make_chunk("c3", "Port operations and container handling at Busan", 0.5),
        _make_chunk("c4", "Vessel speed regulations in Korean coastal waters", 0.3),
    ]


# ---------------------------------------------------------------------------
# TC-RR01: ScoreBoostReranker
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestScoreBoostReranker:
    """TC-RR01: ScoreBoostReranker basic functionality."""

    def test_score_boost_basic_rerank(self) -> None:
        """TC-RR01a: Reranked chunks are sorted by score descending."""
        reranker = ScoreBoostReranker(boost_factor=1.1)
        chunks = _sample_chunks()
        result = reranker.rerank("maritime navigation", chunks, top_k=10)

        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)

    def test_score_boost_empty_chunks(self) -> None:
        """TC-RR01b: Empty input returns empty output."""
        reranker = ScoreBoostReranker()
        result = reranker.rerank("any query", [], top_k=10)
        assert result == []

    def test_score_boost_top_k_limit(self) -> None:
        """TC-RR01c: Output is limited to top_k elements."""
        reranker = ScoreBoostReranker()
        chunks = _sample_chunks()
        result = reranker.rerank("query", chunks, top_k=2)
        assert len(result) <= 2

    def test_score_boost_scores_bounded_zero_one(self) -> None:
        """TC-RR01d: All boosted scores are within [0, 1]."""
        reranker = ScoreBoostReranker(boost_factor=2.0)
        chunks = [
            _make_chunk("c1", "high score chunk", 0.99),
            _make_chunk("c2", "medium score chunk", 0.5),
            _make_chunk("c3", "low score chunk", 0.01),
        ]
        result = reranker.rerank("query", chunks, top_k=10)
        for rc in result:
            assert 0.0 <= rc.score <= 1.0, f"Score {rc.score} is out of [0, 1]"

    def test_score_boost_preserves_retrieval_mode(self) -> None:
        """TC-RR01e: Retrieval mode is preserved through reranking."""
        reranker = ScoreBoostReranker()
        chunks = [
            _make_chunk("c1", "semantic result", 0.8, mode=RetrievalMode.SEMANTIC),
            _make_chunk("c2", "keyword result", 0.6, mode=RetrievalMode.KEYWORD),
        ]
        result = reranker.rerank("query", chunks, top_k=10)
        modes = {rc.chunk.chunk_id: rc.retrieval_mode for rc in result}
        assert modes["c1"] == RetrievalMode.SEMANTIC
        assert modes["c2"] == RetrievalMode.KEYWORD


# ---------------------------------------------------------------------------
# TC-RR02: CrossEncoderReranker
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCrossEncoderReranker:
    """TC-RR02: CrossEncoderReranker with fallback and mock model."""

    def test_cross_encoder_fallback_when_not_installed(self) -> None:
        """TC-RR02a: Falls back to ScoreBoostReranker when sentence-transformers is unavailable."""
        reranker = CrossEncoderReranker(model_name="cross-encoder/test")
        chunks = _sample_chunks()

        # Force ImportError by patching the import
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            # Reset model state so _load_model tries again
            object.__setattr__(reranker, "_model", None)
            result = reranker.rerank("maritime navigation", chunks, top_k=10)

        # Should still get results (from fallback)
        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)

    def test_cross_encoder_with_mock_model(self) -> None:
        """TC-RR02b: With a mock CrossEncoder model, reranking uses model predictions."""
        reranker = CrossEncoderReranker(model_name="cross-encoder/test")

        # Create a mock model
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.1, 0.5, 0.3]
        object.__setattr__(reranker, "_model", mock_model)

        chunks = _sample_chunks()
        result = reranker.rerank("maritime navigation", chunks, top_k=10)

        assert len(result) == 4
        # Scores should be normalized and sorted descending
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)
        # Top result should be the one with highest prediction (0.9 -> normalized 1.0)
        assert result[0].chunk.chunk_id == "c1"

    def test_cross_encoder_normalizes_scores(self) -> None:
        """TC-RR02c: Cross-encoder normalizes scores to [0, 1] range."""
        reranker = CrossEncoderReranker()

        mock_model = MagicMock()
        # Negative scores from cross-encoder (common for ms-marco models)
        mock_model.predict.return_value = [-5.0, -2.0, 3.0]
        object.__setattr__(reranker, "_model", mock_model)

        chunks = _sample_chunks()[:3]
        result = reranker.rerank("query", chunks, top_k=10)

        for rc in result:
            assert 0.0 <= rc.score <= 1.0, (
                f"Score {rc.score} not normalized to [0, 1]"
            )


# ---------------------------------------------------------------------------
# TC-RR03: FlashRankReranker
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFlashRankReranker:
    """TC-RR03: FlashRankReranker with fallback and mock ranker."""

    def test_flash_rank_fallback_when_not_installed(self) -> None:
        """TC-RR03a: Falls back to ScoreBoostReranker when flashrank is unavailable."""
        reranker = FlashRankReranker(model_name="test-model")
        chunks = _sample_chunks()

        with patch.dict("sys.modules", {"flashrank": None}):
            object.__setattr__(reranker, "_ranker", None)
            result = reranker.rerank("maritime navigation", chunks, top_k=10)

        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)

    def test_flash_rank_with_mock_ranker(self) -> None:
        """TC-RR03b: With a mock FlashRank ranker, reranking works correctly."""
        reranker = FlashRankReranker(model_name="test-model")

        # Mock the ranker
        mock_ranker = MagicMock()
        mock_ranker.rerank.return_value = [
            {"id": "0", "score": 0.95},
            {"id": "2", "score": 0.80},
            {"id": "1", "score": 0.60},
            {"id": "3", "score": 0.40},
        ]
        object.__setattr__(reranker, "_ranker", mock_ranker)

        # Mock the RerankRequest import
        mock_flashrank = MagicMock()
        mock_rerank_request_cls = MagicMock()
        mock_flashrank.RerankRequest = mock_rerank_request_cls

        chunks = _sample_chunks()
        with patch.dict("sys.modules", {"flashrank": mock_flashrank}):
            result = reranker.rerank("maritime navigation", chunks, top_k=10)

        assert len(result) == 4
        # First result should be c1 (id="0") with score 0.95
        assert result[0].chunk.chunk_id == "c1"
        assert result[0].score == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# TC-RR04: APIReranker
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAPIReranker:
    """TC-RR04: APIReranker with fallback and mock responses."""

    def test_api_reranker_fallback_when_no_url(self) -> None:
        """TC-RR04a: Falls back to ScoreBoostReranker when api_url is empty."""
        reranker = APIReranker(api_url="", api_key="")
        chunks = _sample_chunks()
        result = reranker.rerank("maritime navigation", chunks, top_k=10)

        # Should use ScoreBoostReranker fallback
        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)

    def test_api_reranker_with_mock_response(self) -> None:
        """TC-RR04b: With a mock HTTP response, reranking uses API results."""
        reranker = APIReranker(
            api_url="http://localhost:8000/rerank",
            api_key="test-key",
            model="test-model",
        )

        mock_response_data = json.dumps({
            "results": [
                {"index": 2, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.85},
                {"index": 3, "relevance_score": 0.70},
                {"index": 1, "relevance_score": 0.50},
            ]
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = mock_response_data

        chunks = _sample_chunks()
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = reranker.rerank("maritime navigation", chunks, top_k=10)

        assert len(result) == 4
        # First result should be c3 (index=2) with score 0.95
        assert result[0].chunk.chunk_id == "c3"
        assert result[0].score == pytest.approx(0.95)

    def test_api_reranker_handles_timeout(self) -> None:
        """TC-RR04c: Falls back gracefully when API call times out."""
        reranker = APIReranker(
            api_url="http://localhost:9999/rerank",
            api_key="test-key",
        )
        chunks = _sample_chunks()

        with patch(
            "urllib.request.urlopen",
            side_effect=TimeoutError("Connection timed out"),
        ):
            result = reranker.rerank("maritime navigation", chunks, top_k=10)

        # Should fall back to ScoreBoostReranker
        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# TC-RR05: create_reranker factory
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateReranker:
    """TC-RR05: create_reranker factory function."""

    def test_create_default_reranker_is_score_boost(self) -> None:
        """TC-RR05a: Default config creates a ScoreBoostReranker."""
        reranker = create_reranker()
        assert isinstance(reranker, ScoreBoostReranker)

    def test_create_cross_encoder_reranker(self) -> None:
        """TC-RR05b: backend='cross_encoder' creates a CrossEncoderReranker."""
        config = RerankerConfig(backend="cross_encoder")
        reranker = create_reranker(config)
        assert isinstance(reranker, CrossEncoderReranker)

    def test_create_flash_rank_reranker(self) -> None:
        """TC-RR05c: backend='flash_rank' creates a FlashRankReranker."""
        config = RerankerConfig(backend="flash_rank")
        reranker = create_reranker(config)
        assert isinstance(reranker, FlashRankReranker)

    def test_create_api_reranker(self) -> None:
        """TC-RR05d: backend='api' creates an APIReranker."""
        config = RerankerConfig(backend="api", api_url="http://example.com/rerank")
        reranker = create_reranker(config)
        assert isinstance(reranker, APIReranker)

    def test_create_with_custom_score_boost(self) -> None:
        """TC-RR05e: Custom score_boost value is applied to ScoreBoostReranker."""
        config = RerankerConfig(backend="score_boost", score_boost=1.5)
        reranker = create_reranker(config)
        assert isinstance(reranker, ScoreBoostReranker)
        assert reranker.boost_factor == 1.5


# ---------------------------------------------------------------------------
# TC-RR06: Protocol compliance
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRerankerProtocol:
    """TC-RR06: All rerankers implement the Reranker protocol."""

    def test_all_rerankers_implement_protocol(self) -> None:
        """TC-RR06a: All four reranker classes are instances of the Reranker Protocol."""
        rerankers = [
            ScoreBoostReranker(),
            CrossEncoderReranker(),
            FlashRankReranker(),
            APIReranker(),
        ]
        for reranker in rerankers:
            assert isinstance(reranker, Reranker), (
                f"{type(reranker).__name__} does not implement Reranker protocol"
            )

    def test_reranker_config_is_frozen(self) -> None:
        """TC-RR06b: RerankerConfig is a frozen dataclass."""
        config = RerankerConfig()
        with pytest.raises(AttributeError):
            config.backend = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-RR07: HybridRAGEngine integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOrchestratorIntegration:
    """TC-RR07: HybridRAGEngine integration with reranker module."""

    def test_orchestrator_uses_custom_reranker(self) -> None:
        """TC-RR07a: HybridRAGEngine accepts and uses a custom reranker."""
        from rag.engines.orchestrator import HybridRAGEngine

        mock_reranker = MagicMock(spec=Reranker)
        mock_reranker.rerank.return_value = []

        config = RAGConfig(
            mode=RetrievalMode.KEYWORD,
            top_k=3,
            similarity_threshold=0.0,
            rerank=True,
        )
        engine = HybridRAGEngine(config=config, reranker=mock_reranker)

        # Add some chunks so the retriever returns results
        chunks = [
            DocumentChunk(
                chunk_id=f"c{i}",
                doc_id="d1",
                content=f"maritime content {i}",
                chunk_index=i,
                embedding=(0.1, 0.2, 0.3),
            )
            for i in range(3)
        ]
        engine.retriever.add_chunks(chunks)

        engine.query("maritime content", query_embedding=None)

        # The custom reranker should have been called
        mock_reranker.rerank.assert_called_once()

    def test_orchestrator_default_reranker(self) -> None:
        """TC-RR07b: HybridRAGEngine defaults to ScoreBoostReranker when none provided."""
        from rag.engines.orchestrator import HybridRAGEngine

        engine = HybridRAGEngine()
        assert isinstance(engine._reranker, ScoreBoostReranker)

    def test_orchestrator_creates_from_config_backend(self) -> None:
        """TC-RR07c: HybridRAGEngine creates reranker from config.reranker_backend."""
        from rag.engines.orchestrator import HybridRAGEngine

        config = RAGConfig(reranker_backend="cross_encoder")
        engine = HybridRAGEngine(config=config)
        assert isinstance(engine._reranker, CrossEncoderReranker)

    def test_orchestrator_rerank_disabled_skips_reranking(self) -> None:
        """TC-RR07d: When config.rerank=False, reranker is not invoked."""
        from rag.engines.orchestrator import HybridRAGEngine

        mock_reranker = MagicMock(spec=Reranker)

        config = RAGConfig(
            mode=RetrievalMode.KEYWORD,
            top_k=3,
            similarity_threshold=0.0,
            rerank=False,  # Disabled
        )
        engine = HybridRAGEngine(config=config, reranker=mock_reranker)

        chunks = [
            DocumentChunk(
                chunk_id=f"c{i}",
                doc_id="d1",
                content=f"maritime content {i}",
                chunk_index=i,
                embedding=(0.1, 0.2, 0.3),
            )
            for i in range(3)
        ]
        engine.retriever.add_chunks(chunks)

        engine.query("maritime content", query_embedding=None)

        # Reranker should NOT have been called
        mock_reranker.rerank.assert_not_called()
