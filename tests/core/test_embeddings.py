"""Unit tests for kg.embeddings module.

All tests mock external dependencies (Ollama, Neo4j) and run without
any running services.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
class TestOllamaEmbedderConstruction:
    """Test OllamaEmbedder initialization and defaults."""

    def test_default_model(self) -> None:
        from kg.embeddings.ollama_embedder import DEFAULT_MODEL, OllamaEmbedder

        e = OllamaEmbedder()
        assert e.model == DEFAULT_MODEL

    def test_default_base_url(self) -> None:
        from kg.embeddings.ollama_embedder import DEFAULT_OLLAMA_BASE_URL, OllamaEmbedder

        e = OllamaEmbedder()
        assert e.base_url == DEFAULT_OLLAMA_BASE_URL

    def test_custom_model(self) -> None:
        from kg.embeddings.ollama_embedder import OllamaEmbedder

        e = OllamaEmbedder(model="bge-m3", base_url="http://custom:11434")
        assert e.model == "bge-m3"
        assert e.base_url == "http://custom:11434"

    def test_dimension_property(self) -> None:
        from kg.embeddings.ollama_embedder import NOMIC_EMBED_TEXT_DIM, OllamaEmbedder

        e = OllamaEmbedder()
        assert e.dimension == NOMIC_EMBED_TEXT_DIM
        assert e.dimension == 768

    def test_lazy_init_embedder_is_none(self) -> None:
        from kg.embeddings.ollama_embedder import OllamaEmbedder

        e = OllamaEmbedder()
        assert e._embedder is None


@pytest.mark.unit
class TestOllamaEmbedderEmbedQuery:
    """Test embed_query with mocked backend."""

    def test_embed_query_returns_vector(self) -> None:
        from kg.embeddings.ollama_embedder import NOMIC_EMBED_TEXT_DIM, OllamaEmbedder

        fake_vector = [0.1] * NOMIC_EMBED_TEXT_DIM
        e = OllamaEmbedder()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = fake_vector
        e._embedder = mock_embedder

        result = e.embed_query("선박 저항 성능")
        assert result == fake_vector
        assert len(result) == NOMIC_EMBED_TEXT_DIM

    def test_embed_query_delegates_to_backend(self) -> None:
        from kg.embeddings.ollama_embedder import NOMIC_EMBED_TEXT_DIM, OllamaEmbedder

        fake_vector = [0.5] * NOMIC_EMBED_TEXT_DIM
        e = OllamaEmbedder()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = fake_vector
        e._embedder = mock_embedder

        e.embed_query("test text")
        mock_embedder.embed_query.assert_called_once_with("test text")

    def test_embed_query_dimension_mismatch_raises(self) -> None:
        from kg.embeddings.ollama_embedder import OllamaEmbedder

        e = OllamaEmbedder()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1, 0.2, 0.3]
        e._embedder = mock_embedder

        with pytest.raises(ValueError, match="Expected 768-dim"):
            e.embed_query("test")

    def test_embed_query_empty_vector_raises(self) -> None:
        from kg.embeddings.ollama_embedder import OllamaEmbedder

        e = OllamaEmbedder()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = []
        e._embedder = mock_embedder

        with pytest.raises(ValueError, match="Expected 768-dim"):
            e.embed_query("test")

    def test_get_neo4j_graphrag_embedder(self) -> None:
        from kg.embeddings.ollama_embedder import OllamaEmbedder

        e = OllamaEmbedder()
        mock_embedder = MagicMock()
        e._embedder = mock_embedder

        result = e.get_neo4j_graphrag_embedder()
        assert result is mock_embedder


@pytest.mark.unit
class TestEmbeddingResult:
    """Test EmbeddingResult dataclass."""

    def test_defaults(self) -> None:
        from kg.embeddings.ollama_embedder import EmbeddingResult

        r = EmbeddingResult()
        assert r.total_processed == 0
        assert r.total_success == 0
        assert r.total_skipped == 0
        assert r.total_failed == 0
        assert r.errors == []

    def test_custom_values(self) -> None:
        from kg.embeddings.ollama_embedder import EmbeddingResult

        r = EmbeddingResult(
            total_processed=10,
            total_success=8,
            total_skipped=1,
            total_failed=1,
            errors=[("DOC-001", "timeout")],
        )
        assert r.total_processed == 10
        assert r.total_success == 8
        assert len(r.errors) == 1
        assert r.errors[0] == ("DOC-001", "timeout")

    def test_errors_list_independent(self) -> None:
        """Each instance should have its own errors list."""
        from kg.embeddings.ollama_embedder import EmbeddingResult

        r1 = EmbeddingResult()
        r2 = EmbeddingResult()
        r1.errors.append(("DOC-001", "err"))
        assert len(r2.errors) == 0


@pytest.mark.unit
class TestGenerateEmbeddingsBatch:
    """Test batch embedding generation with mocked Neo4j driver."""

    def _make_mock_driver(self, records: list[dict]) -> MagicMock:
        """Create a mock Neo4j driver that returns given records."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value.data.return_value = records
        return mock_driver

    def test_empty_documents(self) -> None:
        from kg.embeddings.ollama_embedder import OllamaEmbedder, generate_embeddings_batch

        mock_driver = self._make_mock_driver([])
        embedder = OllamaEmbedder()
        embedder._embedder = MagicMock()

        result = generate_embeddings_batch(
            driver=mock_driver, database="neo4j", embedder=embedder
        )
        assert result.total_processed == 0
        assert result.total_success == 0

    def test_successful_batch(self) -> None:
        from kg.embeddings.ollama_embedder import (
            NOMIC_EMBED_TEXT_DIM,
            OllamaEmbedder,
            generate_embeddings_batch,
        )

        records = [
            {"docId": "DOC-001", "title": "선박 저항 성능 연구", "content": "본 논문에서는 컨테이너선의 저항 특성을 분석한다."},
            {"docId": "DOC-002", "title": "빙해 환경 안전 연구", "content": "극지 항로에서의 선박 운항 안전성을 평가한다."},
        ]
        mock_driver = self._make_mock_driver(records)
        embedder = OllamaEmbedder()
        mock_backend = MagicMock()
        mock_backend.embed_query.return_value = [0.1] * NOMIC_EMBED_TEXT_DIM
        embedder._embedder = mock_backend

        result = generate_embeddings_batch(
            driver=mock_driver, database="neo4j", embedder=embedder
        )
        assert result.total_processed == 2
        assert result.total_success == 2
        assert result.total_failed == 0

    def test_skip_short_text(self) -> None:
        from kg.embeddings.ollama_embedder import OllamaEmbedder, generate_embeddings_batch

        records = [
            {"docId": "DOC-001", "title": "T1", "content": None},  # Too short
            {"docId": "DOC-002", "title": "충분히 긴 제목의 논문입니다", "content": "충분한 내용이 있는 문서"},
        ]
        mock_driver = self._make_mock_driver(records)
        embedder = OllamaEmbedder()
        mock_backend = MagicMock()
        mock_backend.embed_query.return_value = [0.1] * 768
        embedder._embedder = mock_backend

        result = generate_embeddings_batch(
            driver=mock_driver, database="neo4j", embedder=embedder,
            min_text_length=20,
        )
        assert result.total_skipped == 1
        assert result.total_success == 1

    def test_embedding_failure_records_error(self) -> None:
        from kg.embeddings.ollama_embedder import OllamaEmbedder, generate_embeddings_batch

        records = [
            {"docId": "DOC-001", "title": "충분히 긴 제목의 테스트 논문", "content": "충분한 내용"},
        ]
        mock_driver = self._make_mock_driver(records)
        embedder = OllamaEmbedder()
        mock_backend = MagicMock()
        mock_backend.embed_query.side_effect = ConnectionError("Ollama not running")
        embedder._embedder = mock_backend

        result = generate_embeddings_batch(
            driver=mock_driver, database="neo4j", embedder=embedder
        )
        assert result.total_failed == 1
        assert len(result.errors) == 1
        assert result.errors[0][0] == "DOC-001"
        assert "Ollama not running" in result.errors[0][1]

    def test_batch_size_respected(self) -> None:
        from kg.embeddings.ollama_embedder import (
            NOMIC_EMBED_TEXT_DIM,
            OllamaEmbedder,
            generate_embeddings_batch,
        )

        records = [
            {"docId": f"DOC-{i:03d}", "title": f"논문 제목 {i}번 - 충분히 긴 제목", "content": f"본문 내용 {i}번"}
            for i in range(5)
        ]
        mock_driver = self._make_mock_driver(records)
        embedder = OllamaEmbedder()
        mock_backend = MagicMock()
        mock_backend.embed_query.return_value = [0.1] * NOMIC_EMBED_TEXT_DIM
        embedder._embedder = mock_backend

        result = generate_embeddings_batch(
            driver=mock_driver, database="neo4j", embedder=embedder,
            batch_size=2,
        )
        assert result.total_success == 5

    def test_custom_text_fields(self) -> None:
        from kg.embeddings.ollama_embedder import (
            NOMIC_EMBED_TEXT_DIM,
            OllamaEmbedder,
            generate_embeddings_batch,
        )

        records = [
            {"docId": "DOC-001", "summary": "선박 저항 관련 연구 요약본 문서입니다"},
        ]
        mock_driver = self._make_mock_driver(records)
        embedder = OllamaEmbedder()
        mock_backend = MagicMock()
        mock_backend.embed_query.return_value = [0.1] * NOMIC_EMBED_TEXT_DIM
        embedder._embedder = mock_backend

        result = generate_embeddings_batch(
            driver=mock_driver, database="neo4j", embedder=embedder,
            text_fields=("summary",),
        )
        assert result.total_success == 1


@pytest.mark.unit
class TestModuleExports:
    """Test that kg.embeddings exports the correct symbols."""

    def test_exports_ollama_embedder(self) -> None:
        from kg.embeddings import OllamaEmbedder
        assert OllamaEmbedder is not None

    def test_exports_embedding_result(self) -> None:
        from kg.embeddings import EmbeddingResult
        assert EmbeddingResult is not None

    def test_exports_generate_batch(self) -> None:
        from kg.embeddings import generate_embeddings_batch
        assert callable(generate_embeddings_batch)
