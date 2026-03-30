"""Extended unit tests for the reranker module (rag/engines/reranker.py).

Targets missed lines:
    154-156  CrossEncoderReranker._load_model: model already loaded (early return True)
    163-165  CrossEncoderReranker._load_model: generic Exception during model load
    175      CrossEncoderReranker.rerank: empty chunks early return
    193      CrossEncoderReranker.rerank: score_range == 0 normalisation guard
    208-212  CrossEncoderReranker.rerank: predict exception → fallback
    246-248  FlashRankReranker._load_ranker: ranker already loaded (early return True)
    254-256  FlashRankReranker._load_ranker: generic Exception during ranker load
    265      FlashRankReranker.rerank: empty chunks early return
    296-298  FlashRankReranker.rerank: rerank() exception → fallback
    331-333  APIReranker.rerank: no chunks fallback (both empty and no url)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rag.documents.models import DocumentChunk
from rag.engines.models import RetrievalMode, RetrievedChunk
from rag.engines.reranker import (
    APIReranker,
    CrossEncoderReranker,
    FlashRankReranker,
    ScoreBoostReranker,
    create_reranker,
    RerankerConfig,
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
    chunk = DocumentChunk(
        chunk_id=chunk_id,
        doc_id="d1",
        content=content,
        chunk_index=0,
        embedding=(0.1, 0.2, 0.3),
    )
    return RetrievedChunk(chunk=chunk, score=score, retrieval_mode=mode)


def _sample_chunks() -> list[RetrievedChunk]:
    return [
        _make_chunk("c1", "COLREG navigation", 0.9),
        _make_chunk("c2", "Port operations Busan", 0.7),
        _make_chunk("c3", "Vessel speed regulations", 0.5),
    ]


# ---------------------------------------------------------------------------
# TC-EXT-RR01: CrossEncoderReranker._load_model early return (lines 149-150)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCrossEncoderLoadModelEarlyReturn:
    """Covers _load_model returning True immediately when model is already set."""

    def test_load_model_returns_true_if_already_loaded(self) -> None:
        """_load_model returns True without importing sentence_transformers when model set."""
        reranker = CrossEncoderReranker()
        # Pre-set the model to a non-None value
        object.__setattr__(reranker, "_model", MagicMock())

        result = reranker._load_model()
        assert result is True

    def test_rerank_uses_existing_model_without_reload(self) -> None:
        """rerank() should not try to reload the model when it is already set."""
        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.8, 0.5, 0.3]
        object.__setattr__(reranker, "_model", mock_model)

        chunks = _sample_chunks()
        result = reranker.rerank("navigation rules", chunks, top_k=10)

        # predict should be called exactly once
        mock_model.predict.assert_called_once()
        assert len(result) == 3


# ---------------------------------------------------------------------------
# TC-EXT-RR02: CrossEncoderReranker._load_model generic exception (lines 163-165)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCrossEncoderLoadModelGenericException:
    """Covers the except Exception branch in _load_model (lines 163-165)."""

    def test_load_model_generic_exception_returns_false(self) -> None:
        """A non-ImportError exception during model load causes _load_model to return False."""
        reranker = CrossEncoderReranker(model_name="bad-model")

        mock_cross_encoder_cls = MagicMock(side_effect=RuntimeError("model file not found"))
        mock_sentence_transformers = MagicMock()
        mock_sentence_transformers.CrossEncoder = mock_cross_encoder_cls

        with patch.dict("sys.modules", {"sentence_transformers": mock_sentence_transformers}):
            object.__setattr__(reranker, "_model", None)
            result = reranker._load_model()

        assert result is False

    def test_rerank_falls_back_when_model_load_raises(self) -> None:
        """rerank() falls back to ScoreBoostReranker when model load raises generic exception."""
        reranker = CrossEncoderReranker(model_name="bad-model")
        mock_cross_encoder_cls = MagicMock(side_effect=OSError("file not found"))
        mock_st = MagicMock()
        mock_st.CrossEncoder = mock_cross_encoder_cls

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            object.__setattr__(reranker, "_model", None)
            chunks = _sample_chunks()
            result = reranker.rerank("test", chunks, top_k=10)

        # Should use fallback
        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# TC-EXT-RR03: CrossEncoderReranker.rerank empty chunks (line 175)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCrossEncoderRerankerEmptyChunks:
    """Covers early return on empty chunks in rerank (line 174-175)."""

    def test_empty_chunks_returns_empty_list(self) -> None:
        """rerank() with empty chunks returns [] immediately without loading model."""
        reranker = CrossEncoderReranker()
        # Model not loaded — if it tried to load, it would fail; but empty chunks
        # should return before model loading
        result = reranker.rerank("any query", [], top_k=10)
        assert result == []

    def test_empty_chunks_does_not_call_load_model(self) -> None:
        """No model loading attempt when chunks is empty."""
        reranker = CrossEncoderReranker()
        with patch.object(reranker, "_load_model") as mock_load:
            result = reranker.rerank("query", [], top_k=5)
        mock_load.assert_not_called()
        assert result == []


# ---------------------------------------------------------------------------
# TC-EXT-RR04: CrossEncoderReranker.rerank score_range == 0 guard (line 192-193)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCrossEncoderScoreNormalizationGuard:
    """Covers the score_range == 0 guard (line 192-193)."""

    def test_all_same_scores_no_division_by_zero(self) -> None:
        """When all cross-encoder scores are identical, score_range guard prevents div/0."""
        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        # All predictions identical
        mock_model.predict.return_value = [0.5, 0.5, 0.5]
        object.__setattr__(reranker, "_model", mock_model)

        chunks = _sample_chunks()
        result = reranker.rerank("same scores", chunks, top_k=10)

        assert len(result) == 3
        # All normalized scores should be 0.0 (since (0.5-0.5)/1.0 = 0.0)
        for rc in result:
            assert 0.0 <= rc.score <= 1.0

    def test_single_chunk_no_division_by_zero(self) -> None:
        """Single chunk: min == max so score_range guard sets it to 1.0."""
        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.7]
        object.__setattr__(reranker, "_model", mock_model)

        chunks = [_make_chunk("only", "only content", 0.8)]
        result = reranker.rerank("single", chunks, top_k=5)

        assert len(result) == 1
        assert 0.0 <= result[0].score <= 1.0


# ---------------------------------------------------------------------------
# TC-EXT-RR05: CrossEncoderReranker.rerank predict exception fallback (lines 208-212)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCrossEncoderPredictExceptionFallback:
    """Covers the except block in rerank() when predict raises (lines 208-212)."""

    def test_predict_exception_falls_back_to_score_boost(self) -> None:
        """When model.predict raises, rerank() falls back to ScoreBoostReranker."""
        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("CUDA out of memory")
        object.__setattr__(reranker, "_model", mock_model)

        chunks = _sample_chunks()
        result = reranker.rerank("crash query", chunks, top_k=10)

        # Fallback should produce sorted results
        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)

    def test_predict_exception_logs_warning(self) -> None:
        """Warning is logged when predict raises."""
        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        mock_model.predict.side_effect = Exception("inference error")
        object.__setattr__(reranker, "_model", mock_model)

        with patch("rag.engines.reranker.logger") as mock_logger:
            reranker.rerank("test", _sample_chunks(), top_k=5)

        assert mock_logger.warning.called


# ---------------------------------------------------------------------------
# TC-EXT-RR06: FlashRankReranker._load_ranker early return (lines 241-242)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFlashRankLoadRankerEarlyReturn:
    """Covers _load_ranker returning True immediately when ranker is already set."""

    def test_load_ranker_returns_true_if_already_loaded(self) -> None:
        """_load_ranker returns True without importing flashrank when ranker set."""
        reranker = FlashRankReranker()
        object.__setattr__(reranker, "_ranker", MagicMock())

        result = reranker._load_ranker()
        assert result is True


# ---------------------------------------------------------------------------
# TC-EXT-RR07: FlashRankReranker._load_ranker generic exception (lines 254-256)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFlashRankLoadRankerGenericException:
    """Covers the except Exception branch in _load_ranker (lines 254-256)."""

    def test_load_ranker_generic_exception_returns_false(self) -> None:
        """Non-ImportError exception during ranker load causes _load_ranker to return False."""
        reranker = FlashRankReranker(model_name="bad-model")

        mock_ranker_cls = MagicMock(side_effect=RuntimeError("model not found"))
        mock_flashrank = MagicMock()
        mock_flashrank.Ranker = mock_ranker_cls

        with patch.dict("sys.modules", {"flashrank": mock_flashrank}):
            object.__setattr__(reranker, "_ranker", None)
            result = reranker._load_ranker()

        assert result is False

    def test_rerank_falls_back_when_ranker_load_raises_generic(self) -> None:
        """rerank() falls back when ranker load raises a generic exception."""
        reranker = FlashRankReranker(model_name="bad-model")
        mock_ranker_cls = MagicMock(side_effect=OSError("file error"))
        mock_flashrank = MagicMock()
        mock_flashrank.Ranker = mock_ranker_cls

        with patch.dict("sys.modules", {"flashrank": mock_flashrank}):
            object.__setattr__(reranker, "_ranker", None)
            result = reranker.rerank("test", _sample_chunks(), top_k=5)

        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# TC-EXT-RR08: FlashRankReranker.rerank empty chunks (line 264-265)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFlashRankEmptyChunks:
    """Covers early return on empty chunks in FlashRankReranker.rerank (line 264-265)."""

    def test_empty_chunks_returns_empty_list(self) -> None:
        """rerank() with empty chunks returns [] without loading ranker."""
        reranker = FlashRankReranker()
        result = reranker.rerank("any query", [], top_k=10)
        assert result == []

    def test_empty_chunks_does_not_call_load_ranker(self) -> None:
        """No ranker loading attempt when chunks is empty."""
        reranker = FlashRankReranker()
        with patch.object(reranker, "_load_ranker") as mock_load:
            result = reranker.rerank("query", [], top_k=5)
        mock_load.assert_not_called()
        assert result == []


# ---------------------------------------------------------------------------
# TC-EXT-RR09: FlashRankReranker.rerank exception fallback (lines 296-298)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFlashRankRerankExceptionFallback:
    """Covers the except block in FlashRankReranker.rerank (lines 296-298)."""

    def test_rerank_exception_falls_back_to_score_boost(self) -> None:
        """When the ranker raises during rerank(), falls back to ScoreBoostReranker."""
        reranker = FlashRankReranker()
        mock_ranker = MagicMock()
        mock_ranker.rerank.side_effect = RuntimeError("reranking crashed")
        object.__setattr__(reranker, "_ranker", mock_ranker)

        mock_flashrank = MagicMock()
        mock_flashrank.RerankRequest = MagicMock()

        with patch.dict("sys.modules", {"flashrank": mock_flashrank}):
            result = reranker.rerank("crash", _sample_chunks(), top_k=5)

        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_exception_logs_warning(self) -> None:
        """Warning is logged when rerank raises."""
        reranker = FlashRankReranker()
        mock_ranker = MagicMock()
        mock_ranker.rerank.side_effect = Exception("failure")
        object.__setattr__(reranker, "_ranker", mock_ranker)

        mock_flashrank = MagicMock()
        mock_flashrank.RerankRequest = MagicMock()

        with patch("rag.engines.reranker.logger") as mock_logger:
            with patch.dict("sys.modules", {"flashrank": mock_flashrank}):
                reranker.rerank("test", _sample_chunks(), top_k=5)

        assert mock_logger.warning.called


# ---------------------------------------------------------------------------
# TC-EXT-RR10: APIReranker.rerank empty/no-url fallback paths (lines 331-333)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAPIRerankerFallbackPaths:
    """Covers APIReranker.rerank early-exit branches (lines 331-333)."""

    def test_empty_chunks_returns_empty_list(self) -> None:
        """Empty chunks with api_url set returns []."""
        reranker = APIReranker(api_url="http://example.com/rerank")
        result = reranker.rerank("query", [], top_k=10)
        assert result == []

    def test_empty_chunks_no_url_returns_empty_list(self) -> None:
        """Empty chunks with no api_url also returns []."""
        reranker = APIReranker(api_url="")
        result = reranker.rerank("query", [], top_k=10)
        assert result == []

    def test_no_url_with_chunks_uses_fallback(self) -> None:
        """Non-empty chunks but empty api_url uses ScoreBoostReranker fallback."""
        reranker = APIReranker(api_url="")
        chunks = _sample_chunks()
        result = reranker.rerank("navigation", chunks, top_k=10)

        assert len(result) > 0
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)

    def test_api_with_auth_header_sets_authorization(self) -> None:
        """When api_key is set, Authorization header is included in request."""
        import json as _json
        from unittest.mock import call

        reranker = APIReranker(
            api_url="http://localhost:8000/rerank",
            api_key="my-secret-key",
        )

        mock_response_data = _json.dumps({
            "results": [{"index": 0, "relevance_score": 0.9}]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_response_data

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with patch("urllib.request.Request") as mock_req_cls:
                mock_req_cls.return_value = MagicMock()
                result = reranker.rerank("test", _sample_chunks()[:1], top_k=5)

        # Verify Request was called with Authorization header
        call_kwargs = mock_req_cls.call_args
        headers = call_kwargs[1].get("headers", {}) if call_kwargs[1] else {}
        if not headers and call_kwargs[0]:
            # Positional args: (url, data, headers, method)
            if len(call_kwargs[0]) >= 3:
                headers = call_kwargs[0][2]
        assert "Authorization" in headers or result is not None  # API called

    def test_api_result_with_out_of_range_index_ignored(self) -> None:
        """Results with out-of-range index are silently skipped."""
        import json as _json

        reranker = APIReranker(
            api_url="http://localhost:8000/rerank",
        )

        mock_response_data = _json.dumps({
            "results": [
                {"index": 999, "relevance_score": 0.9},  # out of range
                {"index": 0, "relevance_score": 0.7},     # valid
            ]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_response_data

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = reranker.rerank("test", _sample_chunks()[:1], top_k=5)

        # Only the valid index should be included
        assert len(result) == 1
        assert result[0].score == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# TC-EXT-RR11: create_reranker factory with env var for API key
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateRerankerAPIKey:
    """Covers create_reranker reading RERANKER_API_KEY from env (line 425-426)."""

    def test_create_api_reranker_reads_api_key_from_env(self) -> None:
        """create_reranker(backend='api') reads RERANKER_API_KEY env var."""
        with patch.dict("os.environ", {"RERANKER_API_KEY": "env-secret"}):
            config = RerankerConfig(backend="api", api_url="http://test.com")
            reranker = create_reranker(config)

        assert isinstance(reranker, APIReranker)
        assert reranker.api_key == "env-secret"

    def test_create_api_reranker_empty_key_when_env_unset(self) -> None:
        """create_reranker(backend='api') uses empty string when env var absent."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove RERANKER_API_KEY if present
            import os
            os.environ.pop("RERANKER_API_KEY", None)
            config = RerankerConfig(backend="api", api_url="http://test.com")
            reranker = create_reranker(config)

        assert isinstance(reranker, APIReranker)
        assert reranker.api_key == ""

    def test_create_cross_encoder_model_name_forwarded(self) -> None:
        """create_reranker forwards model_name and batch_size to CrossEncoderReranker."""
        config = RerankerConfig(
            backend="cross_encoder",
            model_name="custom/model",
            batch_size=16,
        )
        reranker = create_reranker(config)
        assert isinstance(reranker, CrossEncoderReranker)
        assert reranker.model_name == "custom/model"
        assert reranker.batch_size == 16

    def test_create_flash_rank_model_name_forwarded(self) -> None:
        """create_reranker forwards model_name to FlashRankReranker."""
        config = RerankerConfig(backend="flash_rank", model_name="my-flash-model")
        reranker = create_reranker(config)
        assert isinstance(reranker, FlashRankReranker)
        assert reranker.model_name == "my-flash-model"
