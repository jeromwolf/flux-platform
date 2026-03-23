"""Unit tests for embedding provider implementations.

Covers:
    TC-EP01: OllamaEmbeddingProvider with mock HTTP response
    TC-EP02: OllamaEmbeddingProvider fallback on connection error
    TC-EP03: embed_batch (embed_texts with multiple texts)
    TC-EP04: OpenAIEmbeddingProvider with mock response

All tests are @pytest.mark.unit.
No real HTTP calls are made; urllib is fully mocked.
PYTHONPATH: .
"""
from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from rag.embeddings.models import EmbeddingConfig, EmbeddingResult
from rag.embeddings.providers import (
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
    StubEmbeddingProvider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_urllib_response(body: dict) -> MagicMock:
    """Return a mock urllib response context manager yielding *body* as JSON."""
    raw = json.dumps(body).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = raw
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# TC-EP01: OllamaEmbeddingProvider with mock HTTP response
# ---------------------------------------------------------------------------


class TestOllamaEmbeddingProviderSuccess:
    """TC-EP01: OllamaEmbeddingProvider returns real embeddings via HTTP."""

    @pytest.mark.unit
    def test_embed_texts_single_returns_embedding_result(self) -> None:
        """TC-EP01-a: embed_texts(['hello']) returns EmbeddingResult with 1 vector."""
        fake_vector = [0.1, 0.2, 0.3, 0.4]
        mock_resp = _make_urllib_response({"embedding": fake_vector})

        with patch("urllib.request.urlopen", return_value=mock_resp):
            provider = OllamaEmbeddingProvider()
            result = provider.embed_texts(["hello"])

        assert isinstance(result, EmbeddingResult)
        assert len(result.vectors) == 1
        assert result.vectors[0] == tuple(fake_vector)

    @pytest.mark.unit
    def test_embed_texts_model_name_in_result(self) -> None:
        """TC-EP01-b: result.model matches the configured model name."""
        fake_vector = [0.1] * 768
        mock_resp = _make_urllib_response({"embedding": fake_vector})

        config = EmbeddingConfig(model_name="nomic-embed-text", dimension=768)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            provider = OllamaEmbeddingProvider(config=config)
            result = provider.embed_texts(["test"])

        assert result.model == "nomic-embed-text"

    @pytest.mark.unit
    def test_embed_query_returns_tuple_of_floats(self) -> None:
        """TC-EP01-c: embed_query returns a plain tuple of floats."""
        fake_vector = [0.5, 0.6, 0.7]
        mock_resp = _make_urllib_response({"embedding": fake_vector})

        with patch("urllib.request.urlopen", return_value=mock_resp):
            provider = OllamaEmbeddingProvider()
            vec = provider.embed_query("maritime route")

        assert isinstance(vec, tuple)
        assert len(vec) == 3
        assert all(isinstance(v, float) for v in vec)

    @pytest.mark.unit
    def test_embed_empty_list_returns_empty_result(self) -> None:
        """TC-EP01-d: embed_texts([]) returns EmbeddingResult with no vectors."""
        provider = OllamaEmbeddingProvider()
        result = provider.embed_texts([])
        assert isinstance(result, EmbeddingResult)
        assert len(result.vectors) == 0


# ---------------------------------------------------------------------------
# TC-EP02: OllamaEmbeddingProvider fallback on connection error
# ---------------------------------------------------------------------------


class TestOllamaEmbeddingProviderFallback:
    """TC-EP02: OllamaEmbeddingProvider falls back to stub on errors."""

    @pytest.mark.unit
    def test_fallback_on_url_error(self) -> None:
        """TC-EP02-a: URLError causes fallback to StubEmbeddingProvider."""
        import urllib.error

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            provider = OllamaEmbeddingProvider()
            result = provider.embed_texts(["hello"])

        # Stub uses dimension from config (768)
        assert isinstance(result, EmbeddingResult)
        assert len(result.vectors) == 1
        assert result.vectors[0] != ()  # stub produces non-empty vectors

    @pytest.mark.unit
    def test_fallback_on_os_error(self) -> None:
        """TC-EP02-b: OSError (connection refused) causes fallback to stub."""
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            provider = OllamaEmbeddingProvider()
            result = provider.embed_texts(["test"])

        assert isinstance(result, EmbeddingResult)
        assert len(result.vectors) == 1

    @pytest.mark.unit
    def test_fallback_uses_stub_vectors_not_real(self) -> None:
        """TC-EP02-c: Fallback result comes from stub (non-Ollama model name)."""
        import urllib.error

        config = EmbeddingConfig(model_name="nomic-embed-text", dimension=64)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            provider = OllamaEmbeddingProvider(config=config)
            result = provider.embed_texts(["test"])

        # Stub model name contains "stub"
        assert "stub" in result.model.lower()


# ---------------------------------------------------------------------------
# TC-EP03: embed_batch (multiple texts)
# ---------------------------------------------------------------------------


class TestOllamaEmbedBatch:
    """TC-EP03: embed_texts with a batch of texts."""

    @pytest.mark.unit
    def test_embed_batch_returns_one_vector_per_text(self) -> None:
        """TC-EP03-a: embed_texts(['a','b','c']) returns 3 vectors."""
        fake_vector = [0.1, 0.2, 0.3]
        mock_resp = _make_urllib_response({"embedding": fake_vector})

        texts = ["ship", "port", "maritime"]
        with patch("urllib.request.urlopen", return_value=mock_resp):
            provider = OllamaEmbeddingProvider()
            result = provider.embed_texts(texts)

        assert len(result.vectors) == len(texts)

    @pytest.mark.unit
    def test_embed_batch_token_count_equals_word_count(self) -> None:
        """TC-EP03-b: token_count is the total word count across all texts."""
        fake_vector = [0.1, 0.2]
        mock_resp = _make_urllib_response({"embedding": fake_vector})

        texts = ["hello world", "foo bar baz"]  # 2 + 3 = 5 words
        with patch("urllib.request.urlopen", return_value=mock_resp):
            provider = OllamaEmbeddingProvider()
            result = provider.embed_texts(texts)

        assert result.token_count == 5


# ---------------------------------------------------------------------------
# TC-EP04: OpenAIEmbeddingProvider with mock response
# ---------------------------------------------------------------------------


class TestOpenAIEmbeddingProvider:
    """TC-EP04: OpenAIEmbeddingProvider."""

    @pytest.mark.unit
    def test_embed_texts_without_api_key_uses_stub(self) -> None:
        """TC-EP04-a: No API key → stub embeddings without any HTTP call."""
        import urllib.error

        # Ensure env var is absent during this test
        with patch.dict("os.environ", {}, clear=True):
            provider = OpenAIEmbeddingProvider(api_key="")
            result = provider.embed_texts(["hello"])

        assert isinstance(result, EmbeddingResult)
        assert len(result.vectors) == 1
        assert "stub" in result.model.lower()

    @pytest.mark.unit
    def test_embed_texts_with_api_key_calls_openai(self) -> None:
        """TC-EP04-b: With API key, provider calls OpenAI and returns real vectors."""
        fake_vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        openai_response = {
            "data": [
                {"index": 0, "embedding": fake_vectors[0]},
                {"index": 1, "embedding": fake_vectors[1]},
            ],
            "usage": {"total_tokens": 10},
        }
        mock_resp = _make_urllib_response(openai_response)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            provider = OpenAIEmbeddingProvider(api_key="sk-test-key")
            result = provider.embed_texts(["text one", "text two"])

        assert len(result.vectors) == 2
        assert result.vectors[0] == tuple(fake_vectors[0])
        assert result.vectors[1] == tuple(fake_vectors[1])
        assert result.token_count == 10

    @pytest.mark.unit
    def test_embed_texts_fallback_on_api_error(self) -> None:
        """TC-EP04-c: API error → fall back to stub without raising."""
        import urllib.error

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            provider = OpenAIEmbeddingProvider(api_key="sk-test-key")
            result = provider.embed_texts(["hello"])

        assert isinstance(result, EmbeddingResult)
        assert len(result.vectors) == 1
        assert "stub" in result.model.lower()

    @pytest.mark.unit
    def test_embed_query_returns_tuple(self) -> None:
        """TC-EP04-d: embed_query returns a plain tuple (falls back to stub when no key)."""
        with patch.dict("os.environ", {}, clear=True):
            provider = OpenAIEmbeddingProvider(api_key="")
            vec = provider.embed_query("test query")

        assert isinstance(vec, tuple)
        assert len(vec) > 0

    @pytest.mark.unit
    def test_embed_empty_list_with_api_key_returns_empty(self) -> None:
        """TC-EP04-e: embed_texts([]) returns empty EmbeddingResult even with key."""
        provider = OpenAIEmbeddingProvider(api_key="sk-test-key")
        result = provider.embed_texts([])
        assert len(result.vectors) == 0
