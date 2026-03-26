"""Unit tests for rag.engines.qdrant_store."""
from __future__ import annotations

import os
import sys
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rag.engines.qdrant_store import (
    QdrantConfig,
    QdrantPool,
    QdrantVectorStore,
    _deterministic_uuid,
    _normalize_score,
)
from rag.engines.vector_store import (
    InMemoryVectorStore,
    VectorSearchResult,
    VectorStore,
    VectorStoreConfig,
    create_vector_store,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_vec(n: int, pos: int) -> tuple[float, ...]:
    """Return a unit vector with 1.0 at *pos* and 0.0 elsewhere."""
    v = [0.0] * n
    v[pos] = 1.0
    return tuple(v)


def _make_scored_point(
    point_id: str,
    score: float,
    payload: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock ScoredPoint as returned by Qdrant ``query_points``."""
    pt = MagicMock()
    pt.id = point_id
    pt.score = score
    pt.payload = dict(payload) if payload else {}
    return pt


def _build_mock_qdrant_env() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build mock modules for ``qdrant_client`` and ``qdrant_client.models``.

    Returns ``(mock_qdrant_module, mock_client_instance, mock_models_module)``.
    The mock_qdrant_module should be patched into ``sys.modules["qdrant_client"]``
    and mock_models_module into ``sys.modules["qdrant_client.models"]``.
    """
    mock_models = MagicMock()
    mock_models.Distance.COSINE = "Cosine"
    mock_models.Distance.EUCLID = "Euclid"
    mock_models.Distance.DOT = "Dot"

    mock_client = MagicMock()
    # get_collection succeeds by default (collection already exists)
    mock_client.get_collection.return_value = MagicMock()

    mock_qdrant = MagicMock()
    mock_qdrant.QdrantClient.return_value = mock_client
    mock_qdrant.models = mock_models

    return mock_qdrant, mock_client, mock_models


# ---------------------------------------------------------------------------
# TestQdrantConfig
# ---------------------------------------------------------------------------


class TestQdrantConfig:
    """Tests for the frozen QdrantConfig dataclass."""

    @pytest.mark.unit
    def test_defaults(self) -> None:
        cfg = QdrantConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 6333
        assert cfg.collection_name == "imsp_documents"
        assert cfg.distance == "cosine"
        assert cfg.dimension == 768

    @pytest.mark.unit
    def test_is_frozen(self) -> None:
        cfg = QdrantConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.host = "other"  # type: ignore[misc]

    @pytest.mark.unit
    def test_from_env(self) -> None:
        env = {
            "QDRANT_HOST": "qdrant-server",
            "QDRANT_PORT": "7333",
            "QDRANT_COLLECTION": "test_col",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = QdrantConfig.from_env()
        assert cfg.host == "qdrant-server"
        assert cfg.port == 7333
        assert cfg.collection_name == "test_col"

    @pytest.mark.unit
    def test_from_env_defaults(self) -> None:
        """from_env falls back to defaults when env vars are absent."""
        env_keys = [
            "QDRANT_HOST", "QDRANT_PORT", "QDRANT_COLLECTION",
            "QDRANT_GRPC_PORT", "QDRANT_API_KEY",
        ]
        clean = {k: v for k, v in os.environ.items() if k not in env_keys}
        with patch.dict(os.environ, clean, clear=True):
            cfg = QdrantConfig.from_env()
        assert cfg.host == "localhost"
        assert cfg.port == 6333

    @pytest.mark.unit
    def test_custom_values(self) -> None:
        cfg = QdrantConfig(host="remote", port=9999, dimension=512, distance="dot")
        assert cfg.host == "remote"
        assert cfg.port == 9999
        assert cfg.dimension == 512
        assert cfg.distance == "dot"

    @pytest.mark.unit
    def test_extra_fields(self) -> None:
        """Verify additional fields introduced in the expanded config."""
        cfg = QdrantConfig(grpc_port=7777, api_key="secret", prefer_grpc=False, timeout=60.0)
        assert cfg.grpc_port == 7777
        assert cfg.api_key == "secret"
        assert cfg.prefer_grpc is False
        assert cfg.timeout == 60.0


# ---------------------------------------------------------------------------
# TestQdrantPool
# ---------------------------------------------------------------------------


class TestQdrantPool:
    """Tests for the singleton QdrantPool."""

    def setup_method(self) -> None:
        QdrantPool.reset()

    def teardown_method(self) -> None:
        QdrantPool.reset()

    @pytest.mark.unit
    def test_singleton_pattern(self) -> None:
        """get_instance returns the same object on repeated calls."""
        mock_qdrant, _, _ = _build_mock_qdrant_env()
        with patch.dict(sys.modules, {"qdrant_client": mock_qdrant}):
            cfg = QdrantConfig()
            p1 = QdrantPool.get_instance(cfg)
            p2 = QdrantPool.get_instance(cfg)
            assert p1 is p2

    @pytest.mark.unit
    def test_get_instance_requires_config_on_first_call(self) -> None:
        """get_instance raises ValueError when called with None the first time."""
        with pytest.raises(ValueError, match="requires config"):
            QdrantPool.get_instance(None)

    @pytest.mark.unit
    def test_reset_clears_instance(self) -> None:
        mock_qdrant, _, _ = _build_mock_qdrant_env()
        with patch.dict(sys.modules, {"qdrant_client": mock_qdrant}):
            QdrantPool.get_instance(QdrantConfig())
            assert QdrantPool._instance is not None
            QdrantPool.reset()
            assert QdrantPool._instance is None

    @pytest.mark.unit
    def test_close_clears_client(self) -> None:
        pool = QdrantPool(QdrantConfig())
        mock_client = MagicMock()
        pool._client = mock_client
        pool.close()
        assert pool._client is None
        mock_client.close.assert_called_once()

    @pytest.mark.unit
    def test_close_tolerates_exception(self) -> None:
        pool = QdrantPool(QdrantConfig())
        mock_client = MagicMock()
        mock_client.close.side_effect = RuntimeError("connection lost")
        pool._client = mock_client
        pool.close()  # must not raise
        assert pool._client is None

    @pytest.mark.unit
    def test_close_noop_when_no_client(self) -> None:
        pool = QdrantPool(QdrantConfig())
        pool.close()  # must not raise, client is None
        assert pool._client is None


# ---------------------------------------------------------------------------
# TestQdrantHelpers
# ---------------------------------------------------------------------------


class TestQdrantHelpers:
    """Tests for module-level helper functions."""

    @pytest.mark.unit
    def test_deterministic_uuid_consistent(self) -> None:
        u1 = _deterministic_uuid("doc-42")
        u2 = _deterministic_uuid("doc-42")
        assert u1 == u2

    @pytest.mark.unit
    def test_deterministic_uuid_different_inputs(self) -> None:
        u1 = _deterministic_uuid("alpha")
        u2 = _deterministic_uuid("beta")
        assert u1 != u2

    @pytest.mark.unit
    def test_deterministic_uuid_valid_format(self) -> None:
        result = _deterministic_uuid("test")
        parsed = uuid.UUID(result)
        assert parsed.version == 5

    @pytest.mark.unit
    def test_normalize_score_cosine(self) -> None:
        # Qdrant cosine similarity 1.0 (identical) -> (1+1)/2 = 1.0
        assert _normalize_score(1.0, "cosine") == pytest.approx(1.0)
        # similarity 0.0 -> (0+1)/2 = 0.5
        assert _normalize_score(0.0, "cosine") == pytest.approx(0.5)
        # similarity -1.0 (opposite) -> (-1+1)/2 = 0.0
        assert _normalize_score(-1.0, "cosine") == pytest.approx(0.0)

    @pytest.mark.unit
    def test_normalize_score_euclid(self) -> None:
        # distance 0 (identical) -> 1/(1+0) = 1.0
        assert _normalize_score(0.0, "euclid") == pytest.approx(1.0)
        # distance 1.0 -> 1/(1+1) = 0.5
        assert _normalize_score(1.0, "euclid") == pytest.approx(0.5)

    @pytest.mark.unit
    def test_normalize_score_dot(self) -> None:
        assert _normalize_score(0.8, "dot") == pytest.approx(0.8)
        # clamped to [0, 1]
        assert _normalize_score(1.5, "dot") == pytest.approx(1.0)
        assert _normalize_score(-0.3, "dot") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestQdrantVectorStore (mocked client)
# ---------------------------------------------------------------------------


class TestQdrantVectorStore:
    """Tests for QdrantVectorStore with fully mocked qdrant-client.

    The mock must stay active for the entire test because the production
    code does deferred imports (``from qdrant_client.models import ...``)
    inside individual methods like ``add``, ``query``, ``delete``, and
    ``clear``.
    """

    def setup_method(self) -> None:
        QdrantPool.reset()

    def teardown_method(self) -> None:
        QdrantPool.reset()

    def _make_store_with_mock(
        self,
        config: QdrantConfig | None = None,
    ) -> tuple[QdrantVectorStore, MagicMock, MagicMock, dict[str, Any]]:
        """Create a QdrantVectorStore with fully mocked Qdrant client.

        Returns ``(store, mock_client, mock_models, modules_patch)``.
        The caller MUST use ``modules_patch`` in a ``patch.dict`` context
        that stays active for all subsequent calls on the store.
        """
        mock_qdrant, mock_client, mock_models = _build_mock_qdrant_env()
        modules_patch = {
            "qdrant_client": mock_qdrant,
            "qdrant_client.models": mock_models,
        }
        QdrantPool.reset()
        with patch.dict(sys.modules, modules_patch):
            store = QdrantVectorStore(config or QdrantConfig())
        return store, mock_client, mock_models, modules_patch

    # -- add -----------------------------------------------------------------

    @pytest.mark.unit
    def test_add_calls_upsert(self) -> None:
        store, mock_client, _, mods = self._make_store_with_mock()

        with patch.dict(sys.modules, mods):
            store.add(
                ids=["id1", "id2"],
                embeddings=[_unit_vec(3, 0), _unit_vec(3, 1)],
                documents=["doc one", "doc two"],
            )

        mock_client.upsert.assert_called_once()
        call_kwargs = mock_client.upsert.call_args.kwargs
        assert call_kwargs["collection_name"] == "imsp_documents"
        points = call_kwargs["points"]
        assert len(points) == 2

    @pytest.mark.unit
    def test_add_stores_original_id_in_payload(self) -> None:
        store, mock_client, mock_models, mods = self._make_store_with_mock()

        with patch.dict(sys.modules, mods):
            store.add(
                ids=["my-doc"],
                embeddings=[_unit_vec(2, 0)],
                documents=["text"],
            )

        # PointStruct is a MagicMock — verify the kwargs passed to its constructor
        point_call = mock_models.PointStruct.call_args
        assert point_call.kwargs["payload"]["_id"] == "my-doc"
        assert point_call.kwargs["payload"]["document"] == "text"

    @pytest.mark.unit
    def test_add_with_metadata(self) -> None:
        store, mock_client, mock_models, mods = self._make_store_with_mock()

        with patch.dict(sys.modules, mods):
            store.add(
                ids=["m1"],
                embeddings=[_unit_vec(2, 0)],
                documents=["doc"],
                metadatas=[{"source": "crawler", "page": 5}],
            )

        point_call = mock_models.PointStruct.call_args
        assert point_call.kwargs["payload"]["metadata"] == {"source": "crawler", "page": 5}
        assert point_call.kwargs["payload"]["_id"] == "m1"

    @pytest.mark.unit
    def test_add_uuid_is_deterministic(self) -> None:
        store, mock_client, mock_models, mods = self._make_store_with_mock()

        with patch.dict(sys.modules, mods):
            store.add(ids=["doc-x"], embeddings=[_unit_vec(2, 0)], documents=["t"])

        point_call = mock_models.PointStruct.call_args
        expected_uuid = _deterministic_uuid("doc-x")
        assert point_call.kwargs["id"] == expected_uuid

    @pytest.mark.unit
    def test_add_default_metadata_is_empty_dict(self) -> None:
        store, mock_client, mock_models, mods = self._make_store_with_mock()

        with patch.dict(sys.modules, mods):
            store.add(ids=["a"], embeddings=[_unit_vec(2, 0)], documents=["d"])

        point_call = mock_models.PointStruct.call_args
        assert point_call.kwargs["payload"]["metadata"] == {}

    # -- query ---------------------------------------------------------------

    @pytest.mark.unit
    def test_query_returns_results(self) -> None:
        store, mock_client, _, mods = self._make_store_with_mock()

        mock_response = MagicMock()
        mock_response.points = [
            _make_scored_point(
                _deterministic_uuid("d1"),
                0.95,
                {"_id": "d1", "document": "hello", "metadata": {"tag": "ship"}},
            ),
            _make_scored_point(
                _deterministic_uuid("d2"),
                0.70,
                {"_id": "d2", "document": "world", "metadata": {}},
            ),
        ]
        mock_client.query_points.return_value = mock_response

        results = store.query(_unit_vec(3, 0), top_k=2)

        assert len(results) == 2
        # results are sorted by score descending
        assert results[0].id == "d1"
        assert results[0].document == "hello"
        assert results[0].metadata == {"tag": "ship"}
        assert results[1].id == "d2"

    @pytest.mark.unit
    def test_query_empty_returns_empty_list(self) -> None:
        store, mock_client, _, mods = self._make_store_with_mock()

        mock_response = MagicMock()
        mock_response.points = []
        mock_client.query_points.return_value = mock_response

        results = store.query(_unit_vec(3, 0), top_k=5)
        assert results == []

    @pytest.mark.unit
    def test_query_with_where_filter(self) -> None:
        store, mock_client, mock_models, mods = self._make_store_with_mock()

        mock_response = MagicMock()
        mock_response.points = []
        mock_client.query_points.return_value = mock_response

        with patch.dict(sys.modules, mods):
            store.query(_unit_vec(3, 0), top_k=5, where={"tag": "vessel"})

        call_kwargs = mock_client.query_points.call_args.kwargs
        assert "query_filter" in call_kwargs
        assert call_kwargs["query_filter"] is not None

    @pytest.mark.unit
    def test_query_without_filter_omits_key(self) -> None:
        store, mock_client, _, mods = self._make_store_with_mock()

        mock_response = MagicMock()
        mock_response.points = []
        mock_client.query_points.return_value = mock_response

        store.query(_unit_vec(3, 0), top_k=3)

        call_kwargs = mock_client.query_points.call_args.kwargs
        # When where=None, the implementation does not add query_filter key
        assert "query_filter" not in call_kwargs

    @pytest.mark.unit
    def test_query_top_k_forwarded(self) -> None:
        store, mock_client, _, mods = self._make_store_with_mock()

        mock_response = MagicMock()
        mock_response.points = []
        mock_client.query_points.return_value = mock_response

        store.query(_unit_vec(3, 0), top_k=42)

        call_kwargs = mock_client.query_points.call_args.kwargs
        assert call_kwargs["limit"] == 42

    @pytest.mark.unit
    def test_query_score_normalisation_cosine(self) -> None:
        """Cosine similarity 0.8 from Qdrant -> normalised (0.8+1)/2 = 0.9."""
        store, mock_client, _, mods = self._make_store_with_mock()

        mock_response = MagicMock()
        mock_response.points = [
            _make_scored_point("uuid1", 0.8, {"_id": "x", "document": "t", "metadata": {}}),
        ]
        mock_client.query_points.return_value = mock_response

        results = store.query(_unit_vec(3, 0), top_k=1)
        assert results[0].score == pytest.approx(0.9)

    @pytest.mark.unit
    def test_query_score_normalisation_euclid(self) -> None:
        cfg = QdrantConfig(distance="euclid")
        store, mock_client, _, mods = self._make_store_with_mock(config=cfg)

        mock_response = MagicMock()
        mock_response.points = [
            _make_scored_point("uuid1", 1.0, {"_id": "x", "document": "t", "metadata": {}}),
        ]
        mock_client.query_points.return_value = mock_response

        results = store.query(_unit_vec(3, 0), top_k=1)
        # euclid: 1/(1+1) = 0.5
        assert results[0].score == pytest.approx(0.5)

    @pytest.mark.unit
    def test_query_null_score_treated_as_zero(self) -> None:
        store, mock_client, _, mods = self._make_store_with_mock()

        pt = MagicMock()
        pt.id = "uid"
        pt.score = None
        pt.payload = {"_id": "x", "document": "d", "metadata": {}}

        mock_response = MagicMock()
        mock_response.points = [pt]
        mock_client.query_points.return_value = mock_response

        results = store.query(_unit_vec(3, 0), top_k=1)
        # score=None -> raw 0.0 -> cosine normalised (0+1)/2 = 0.5
        assert results[0].score == pytest.approx(0.5)

    # -- delete --------------------------------------------------------------

    @pytest.mark.unit
    def test_delete_calls_delete(self) -> None:
        store, mock_client, _, mods = self._make_store_with_mock()

        with patch.dict(sys.modules, mods):
            store.delete(["id1", "id2"])

        mock_client.delete.assert_called_once()
        call_kwargs = mock_client.delete.call_args.kwargs
        assert call_kwargs["collection_name"] == "imsp_documents"

    @pytest.mark.unit
    def test_delete_converts_ids_to_uuids(self) -> None:
        store, mock_client, mock_models, mods = self._make_store_with_mock()

        with patch.dict(sys.modules, mods):
            store.delete(["my-id"])

        # PointIdsList is a MagicMock — verify its constructor args
        pil_call = mock_models.PointIdsList.call_args
        expected = _deterministic_uuid("my-id")
        assert expected in pil_call.kwargs["points"]

    # -- count ---------------------------------------------------------------

    @pytest.mark.unit
    def test_count_returns_value(self) -> None:
        store, mock_client, _, mods = self._make_store_with_mock()

        mock_count_result = MagicMock()
        mock_count_result.count = 99
        mock_client.count.return_value = mock_count_result

        assert store.count() == 99

    # -- clear ---------------------------------------------------------------

    @pytest.mark.unit
    def test_clear_deletes_and_recreates(self) -> None:
        store, mock_client, _, mods = self._make_store_with_mock()

        with patch.dict(sys.modules, mods):
            store.clear()

        mock_client.delete_collection.assert_called_once()
        del_kwargs = mock_client.delete_collection.call_args.kwargs
        assert del_kwargs["collection_name"] == "imsp_documents"

    # -- is_fallback ---------------------------------------------------------

    @pytest.mark.unit
    def test_is_not_fallback_with_client(self) -> None:
        store, _, _, _ = self._make_store_with_mock()
        assert not store._is_fallback


# ---------------------------------------------------------------------------
# TestQdrantVectorStoreFallback
# ---------------------------------------------------------------------------


class TestQdrantVectorStoreFallback:
    """Tests for the in-memory fallback path when qdrant-client is absent."""

    def setup_method(self) -> None:
        QdrantPool.reset()

    def teardown_method(self) -> None:
        QdrantPool.reset()

    @pytest.mark.unit
    def test_fallback_when_not_installed(self) -> None:
        with patch.dict(sys.modules, {"qdrant_client": None}):
            store = QdrantVectorStore()
        assert store._is_fallback
        assert isinstance(store._fallback, InMemoryVectorStore)

    @pytest.mark.unit
    def test_fallback_delegates_add_and_query(self) -> None:
        with patch.dict(sys.modules, {"qdrant_client": None}):
            store = QdrantVectorStore()
        store.add(ids=["f1"], embeddings=[_unit_vec(3, 0)], documents=["doc"])
        assert store.count() == 1
        results = store.query(_unit_vec(3, 0), top_k=1)
        assert len(results) == 1
        assert results[0].id == "f1"

    @pytest.mark.unit
    def test_fallback_clear(self) -> None:
        with patch.dict(sys.modules, {"qdrant_client": None}):
            store = QdrantVectorStore()
        store.add(ids=["x"], embeddings=[_unit_vec(2, 0)], documents=["x"])
        store.clear()
        assert store.count() == 0

    @pytest.mark.unit
    def test_fallback_delete(self) -> None:
        with patch.dict(sys.modules, {"qdrant_client": None}):
            store = QdrantVectorStore()
        store.add(
            ids=["x", "y"],
            embeddings=[_unit_vec(2, 0), _unit_vec(2, 1)],
            documents=["x", "y"],
        )
        store.delete(["x"])
        assert store.count() == 1

    @pytest.mark.unit
    def test_fallback_query_with_where(self) -> None:
        with patch.dict(sys.modules, {"qdrant_client": None}):
            store = QdrantVectorStore()
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
    def test_fallback_metadata_roundtrip(self) -> None:
        with patch.dict(sys.modules, {"qdrant_client": None}):
            store = QdrantVectorStore()
        store.add(
            ids=["m"],
            embeddings=[_unit_vec(2, 0)],
            documents=["doc"],
            metadatas=[{"source": "test", "page": 3}],
        )
        results = store.query(_unit_vec(2, 0), top_k=1)
        assert results[0].metadata == {"source": "test", "page": 3}


# ---------------------------------------------------------------------------
# TestQdrantFactoryIntegration
# ---------------------------------------------------------------------------


class TestQdrantFactoryIntegration:
    """Test that create_vector_store works with backend='qdrant'."""

    def setup_method(self) -> None:
        QdrantPool.reset()

    def teardown_method(self) -> None:
        QdrantPool.reset()

    @pytest.mark.unit
    def test_create_qdrant_store_falls_back(self) -> None:
        with patch.dict(sys.modules, {"qdrant_client": None}):
            store = create_vector_store(VectorStoreConfig(backend="qdrant"))
        assert isinstance(store, QdrantVectorStore)
        assert store._is_fallback  # type: ignore[union-attr]
        # Still functional
        store.add(ids=["t"], embeddings=[_unit_vec(2, 0)], documents=["t"])  # type: ignore[union-attr]
        assert store.count() == 1  # type: ignore[union-attr]

    @pytest.mark.unit
    def test_default_still_returns_memory(self) -> None:
        store = create_vector_store()
        assert isinstance(store, InMemoryVectorStore)

    @pytest.mark.unit
    def test_factory_chromadb_unchanged(self) -> None:
        """Ensure adding qdrant did not break the chromadb factory path."""
        from rag.engines.vector_store import ChromaVectorStore

        with patch.dict(sys.modules, {"chromadb": None}):
            store = create_vector_store(VectorStoreConfig(backend="chromadb"))
        assert isinstance(store, ChromaVectorStore)


# ---------------------------------------------------------------------------
# TestQdrantProtocolCompliance
# ---------------------------------------------------------------------------


class TestQdrantProtocolCompliance:
    """Verify QdrantVectorStore satisfies the VectorStore protocol."""

    def setup_method(self) -> None:
        QdrantPool.reset()

    def teardown_method(self) -> None:
        QdrantPool.reset()

    @pytest.mark.unit
    def test_implements_vector_store_protocol(self) -> None:
        with patch.dict(sys.modules, {"qdrant_client": None}):
            store = QdrantVectorStore()
        assert isinstance(store, VectorStore)

    @pytest.mark.unit
    def test_has_all_protocol_methods(self) -> None:
        with patch.dict(sys.modules, {"qdrant_client": None}):
            store = QdrantVectorStore()
        for method in ("add", "query", "delete", "count", "clear"):
            assert callable(getattr(store, method, None)), f"missing {method}"
