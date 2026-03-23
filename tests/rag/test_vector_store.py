"""Unit tests for rag.engines.vector_store."""
from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rag.engines.vector_store import (
    ChromaVectorStore,
    InMemoryVectorStore,
    VectorSearchResult,
    VectorStore,
    VectorStoreConfig,
    _cosine_similarity,
    create_vector_store,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding(values: list[float]) -> tuple[float, ...]:
    return tuple(values)


def _unit_vec(n: int, pos: int) -> tuple[float, ...]:
    """Return a unit vector with 1.0 at *pos* and 0.0 elsewhere."""
    v = [0.0] * n
    v[pos] = 1.0
    return tuple(v)


# ---------------------------------------------------------------------------
# TestInMemoryVectorStore
# ---------------------------------------------------------------------------


class TestInMemoryVectorStore:
    """Tests for the pure-Python in-memory vector store."""

    def test_add_and_count(self) -> None:
        store = InMemoryVectorStore()
        assert store.count() == 0
        store.add(
            ids=["a", "b"],
            embeddings=[_unit_vec(3, 0), _unit_vec(3, 1)],
            documents=["doc a", "doc b"],
        )
        assert store.count() == 2

    @pytest.mark.unit
    def test_query_returns_sorted_by_score(self) -> None:
        store = InMemoryVectorStore()
        # Three orthogonal unit vectors
        store.add(
            ids=["x", "y", "z"],
            embeddings=[_unit_vec(3, 0), _unit_vec(3, 1), _unit_vec(3, 2)],
            documents=["doc x", "doc y", "doc z"],
        )
        # Query closest to z-axis
        results = store.query(_unit_vec(3, 2), top_k=3)
        assert len(results) == 3
        assert results[0].id == "z"
        assert results[0].score == pytest.approx(1.0)
        # Scores should be descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.unit
    def test_query_empty_store_returns_empty(self) -> None:
        store = InMemoryVectorStore()
        results = store.query(_unit_vec(3, 0), top_k=5)
        assert results == []

    @pytest.mark.unit
    def test_delete_removes_items(self) -> None:
        store = InMemoryVectorStore()
        store.add(
            ids=["a", "b", "c"],
            embeddings=[_unit_vec(2, 0), _unit_vec(2, 1), _unit_vec(2, 0)],
            documents=["a", "b", "c"],
        )
        store.delete(["a", "c"])
        assert store.count() == 1
        results = store.query(_unit_vec(2, 0), top_k=10)
        ids = [r.id for r in results]
        assert "a" not in ids
        assert "c" not in ids
        assert "b" in ids

    @pytest.mark.unit
    def test_clear_empties_store(self) -> None:
        store = InMemoryVectorStore()
        store.add(
            ids=["a", "b"],
            embeddings=[_unit_vec(2, 0), _unit_vec(2, 1)],
            documents=["a", "b"],
        )
        store.clear()
        assert store.count() == 0
        assert store.query(_unit_vec(2, 0)) == []

    @pytest.mark.unit
    def test_query_top_k_limits_results(self) -> None:
        store = InMemoryVectorStore()
        n = 10
        store.add(
            ids=[str(i) for i in range(n)],
            embeddings=[_unit_vec(n, i) for i in range(n)],
            documents=[f"doc {i}" for i in range(n)],
        )
        results = store.query(_unit_vec(n, 0), top_k=3)
        assert len(results) == 3

    @pytest.mark.unit
    def test_add_upserts_existing_id(self) -> None:
        store = InMemoryVectorStore()
        store.add(ids=["a"], embeddings=[_unit_vec(2, 0)], documents=["original"])
        store.add(ids=["a"], embeddings=[_unit_vec(2, 0)], documents=["updated"])
        assert store.count() == 1
        results = store.query(_unit_vec(2, 0), top_k=1)
        assert results[0].document == "updated"

    @pytest.mark.unit
    def test_metadata_stored_and_returned(self) -> None:
        store = InMemoryVectorStore()
        store.add(
            ids=["m"],
            embeddings=[_unit_vec(2, 0)],
            documents=["meta doc"],
            metadatas=[{"source": "test", "page": 1}],
        )
        results = store.query(_unit_vec(2, 0), top_k=1)
        assert results[0].metadata == {"source": "test", "page": 1}

    @pytest.mark.unit
    def test_where_filter_excludes_non_matching(self) -> None:
        store = InMemoryVectorStore()
        store.add(
            ids=["a", "b"],
            embeddings=[_unit_vec(2, 0), _unit_vec(2, 0)],
            documents=["a", "b"],
            metadatas=[{"tag": "ship"}, {"tag": "port"}],
        )
        results = store.query(_unit_vec(2, 0), top_k=10, where={"tag": "ship"})
        assert len(results) == 1
        assert results[0].id == "a"

    @pytest.mark.unit
    def test_delete_missing_id_is_silent(self) -> None:
        store = InMemoryVectorStore()
        store.delete(["nonexistent"])  # must not raise
        assert store.count() == 0


# ---------------------------------------------------------------------------
# TestChromaVectorStore
# ---------------------------------------------------------------------------


class TestChromaVectorStore:
    """Tests for the ChromaDB-backed vector store."""

    @pytest.mark.unit
    def test_fallback_to_memory_when_chromadb_not_installed(self) -> None:
        """ImportError during chromadb import must activate in-memory fallback."""
        with patch.dict(sys.modules, {"chromadb": None}):
            store = ChromaVectorStore()
        assert store._is_fallback
        assert isinstance(store._fallback, InMemoryVectorStore)

    @pytest.mark.unit
    def test_fallback_delegates_add_and_query(self) -> None:
        """After fallback, add/query/count should work via InMemoryVectorStore."""
        with patch.dict(sys.modules, {"chromadb": None}):
            store = ChromaVectorStore()
        store.add(
            ids=["f1"],
            embeddings=[_unit_vec(3, 0)],
            documents=["fallback doc"],
        )
        assert store.count() == 1
        results = store.query(_unit_vec(3, 0), top_k=1)
        assert len(results) == 1
        assert results[0].id == "f1"

    @pytest.mark.unit
    def test_fallback_clear(self) -> None:
        with patch.dict(sys.modules, {"chromadb": None}):
            store = ChromaVectorStore()
        store.add(ids=["x"], embeddings=[_unit_vec(2, 0)], documents=["x"])
        store.clear()
        assert store.count() == 0

    @pytest.mark.unit
    def test_fallback_delete(self) -> None:
        with patch.dict(sys.modules, {"chromadb": None}):
            store = ChromaVectorStore()
        store.add(ids=["x", "y"], embeddings=[_unit_vec(2, 0), _unit_vec(2, 1)], documents=["x", "y"])
        store.delete(["x"])
        assert store.count() == 1

    @pytest.mark.unit
    def test_chromadb_add_and_query(self) -> None:
        """Mock chromadb and verify the correct calls are forwarded."""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "distances": [[0.1, 0.4]],
            "documents": [["doc one", "doc two"]],
            "metadatas": [[{"src": "a"}, {"src": "b"}]],
        }
        mock_collection.count.return_value = 2

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            store = ChromaVectorStore(VectorStoreConfig(backend="chromadb"))

        assert not store._is_fallback

        embs = [_unit_vec(3, 0), _unit_vec(3, 1)]
        store.add(
            ids=["id1", "id2"],
            embeddings=embs,
            documents=["doc one", "doc two"],
        )
        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args
        assert call_kwargs.kwargs["ids"] == ["id1", "id2"]

        results = store.query(_unit_vec(3, 0), top_k=2)
        assert len(results) == 2
        # cosine distance 0.1 -> score 0.9
        assert results[0].score == pytest.approx(0.9)
        assert results[0].document == "doc one"
        assert results[1].score == pytest.approx(0.6)

    @pytest.mark.unit
    def test_chromadb_count(self) -> None:
        mock_collection = MagicMock()
        mock_collection.count.return_value = 42

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            store = ChromaVectorStore()

        assert store.count() == 42

    @pytest.mark.unit
    def test_chromadb_clear_recreates_collection(self) -> None:
        mock_collection = MagicMock()
        mock_collection.name = "imsp_documents"
        mock_collection.metadata = {"hnsw:space": "cosine"}

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            store = ChromaVectorStore()

        store.clear()
        mock_client.delete_collection.assert_called_once_with("imsp_documents")
        # get_or_create_collection called twice: once at init, once after clear
        assert mock_client.get_or_create_collection.call_count == 2

    @pytest.mark.unit
    def test_chromadb_delete_forwards_ids(self) -> None:
        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            store = ChromaVectorStore()

        store.delete(["id1", "id2"])
        mock_collection.delete.assert_called_once_with(ids=["id1", "id2"])

    @pytest.mark.unit
    def test_chromadb_where_filter_forwarded(self) -> None:
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
            "documents": [[]],
            "metadatas": [[]],
        }
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            store = ChromaVectorStore()

        store.query(_unit_vec(3, 0), top_k=5, where={"tag": "ship"})
        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["where"] == {"tag": "ship"}


# ---------------------------------------------------------------------------
# TestVectorStoreFactory
# ---------------------------------------------------------------------------


class TestVectorStoreFactory:
    """Tests for the create_vector_store factory function."""

    @pytest.mark.unit
    def test_create_memory_store(self) -> None:
        store = create_vector_store(VectorStoreConfig(backend="memory"))
        assert isinstance(store, InMemoryVectorStore)

    @pytest.mark.unit
    def test_create_memory_store_default(self) -> None:
        store = create_vector_store()
        assert isinstance(store, InMemoryVectorStore)

    @pytest.mark.unit
    def test_create_chromadb_store_falls_back(self) -> None:
        """When chromadb is not installed, factory still returns a usable store."""
        with patch.dict(sys.modules, {"chromadb": None}):
            store = create_vector_store(VectorStoreConfig(backend="chromadb"))
        assert isinstance(store, ChromaVectorStore)
        # Must be in fallback mode
        assert store._is_fallback  # type: ignore[union-attr]
        # But still functional
        store.add(ids=["test"], embeddings=[_unit_vec(2, 0)], documents=["t"])  # type: ignore[union-attr]
        assert store.count() == 1  # type: ignore[union-attr]

    @pytest.mark.unit
    def test_config_defaults(self) -> None:
        cfg = VectorStoreConfig()
        assert cfg.backend == "memory"
        assert cfg.collection_name == "imsp_documents"
        assert cfg.persist_directory == ".chromadb"
        assert cfg.distance_metric == "cosine"

    @pytest.mark.unit
    def test_config_is_frozen(self) -> None:
        cfg = VectorStoreConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.backend = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestVectorStoreProtocol
# ---------------------------------------------------------------------------


class TestVectorStoreProtocol:
    """Protocol compliance and utility function tests."""

    @pytest.mark.unit
    def test_in_memory_implements_protocol(self) -> None:
        store = InMemoryVectorStore()
        assert isinstance(store, VectorStore)

    @pytest.mark.unit
    def test_chroma_implements_protocol(self) -> None:
        with patch.dict(sys.modules, {"chromadb": None}):
            store = ChromaVectorStore()
        assert isinstance(store, VectorStore)

    @pytest.mark.unit
    def test_cosine_similarity_identical(self) -> None:
        v = (1.0, 2.0, 3.0)
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_cosine_similarity_orthogonal(self) -> None:
        a = (1.0, 0.0, 0.0)
        b = (0.0, 1.0, 0.0)
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_cosine_similarity_opposite(self) -> None:
        a = (1.0, 0.0)
        b = (-1.0, 0.0)
        assert _cosine_similarity(a, b) == pytest.approx(-1.0)

    @pytest.mark.unit
    def test_cosine_similarity_zero_vector(self) -> None:
        a = (0.0, 0.0, 0.0)
        b = (1.0, 2.0, 3.0)
        assert _cosine_similarity(a, b) == 0.0

    @pytest.mark.unit
    def test_cosine_similarity_mismatched_lengths(self) -> None:
        a = (1.0, 2.0)
        b = (1.0, 2.0, 3.0)
        assert _cosine_similarity(a, b) == 0.0

    @pytest.mark.unit
    def test_cosine_similarity_empty_vectors(self) -> None:
        assert _cosine_similarity((), ()) == 0.0

    @pytest.mark.unit
    def test_vector_search_result_is_frozen(self) -> None:
        r = VectorSearchResult(id="x", score=0.5, document="text")
        with pytest.raises((AttributeError, TypeError)):
            r.score = 0.9  # type: ignore[misc]

    @pytest.mark.unit
    def test_vector_search_result_default_metadata(self) -> None:
        r = VectorSearchResult(id="x", score=0.5, document="d")
        assert r.metadata == {}
