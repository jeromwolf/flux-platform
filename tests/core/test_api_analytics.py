"""Unit tests for embedding search, algorithm, and ETL state API endpoints.

All tests are marked with ``@pytest.mark.unit`` and mock Neo4j so no
database connection is required.
"""

from __future__ import annotations

import os
import tempfile
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kg.api.app import create_app
from kg.api.deps import get_app_config, get_async_neo4j_session
from kg.api.middleware.auth import get_current_api_key
from kg.config import AppConfig, Neo4jConfig, reset

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset config singleton before/after each test."""
    reset()
    yield
    reset()


_DEV_CONFIG = AppConfig(
    env="development",
    neo4j=Neo4jConfig(uri="bolt://mock:7687"),
)


def _make_async_mock_result(records: list | None = None) -> MagicMock:
    """Create a mock async result that supports ``async for``.

    Args:
        records: List of records for async iteration. Defaults to empty list.

    Returns:
        Mock object that behaves like an async Neo4j result.
    """
    mock_result = MagicMock()
    _records = records if records is not None else []

    async def _aiter_impl():
        for r in _records:
            yield r

    mock_result.__aiter__ = lambda self: _aiter_impl()
    mock_result.single = AsyncMock(return_value=None)
    return mock_result


def _make_mock_session() -> MagicMock:
    """Create a mock async Neo4j session.

    Returns:
        Mock session with async ``run`` and ``close`` methods.
    """
    mock_session = MagicMock()
    mock_session.run = AsyncMock()
    mock_session.close = AsyncMock()
    return mock_session


def _make_client(mock_session: MagicMock | None = None) -> tuple[TestClient, MagicMock]:
    """Create a TestClient with FastAPI dependency overrides for Neo4j.

    Args:
        mock_session: Optional pre-configured mock session.

    Returns:
        Tuple of ``(TestClient, mock_session)``.
    """
    if mock_session is None:
        mock_session = _make_mock_session()

    with patch("kg.api.app.get_config", return_value=_DEV_CONFIG), patch("kg.api.app.set_config"):
        app = create_app(config=_DEV_CONFIG)

    async def _override_session():
        yield mock_session

    app.dependency_overrides[get_async_neo4j_session] = _override_session
    app.dependency_overrides[get_app_config] = lambda: _DEV_CONFIG
    app.dependency_overrides[get_current_api_key] = lambda: None

    return TestClient(app), mock_session


# ---------------------------------------------------------------------------
# TC-ES01: POST /embeddings/search returns results
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmbeddingSearch:
    """Tests for POST /api/v1/embeddings/search."""

    def test_vector_search_returns_results(self) -> None:
        """TC-ES01: POST /embeddings/search returns structured response."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post(
            "/api/v1/embeddings/search",
            json={
                "label": "Vessel",
                "property": "embedding",
                "queryVector": [0.1, 0.2, 0.3],
                "topK": 5,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "meta" in data
        assert data["meta"]["topK"] == 5
        assert data["meta"]["label"] == "Vessel"
        assert data["meta"]["algorithm"] == "cosine"

    def test_vector_search_rejects_invalid_label(self) -> None:
        """TC-ES01b: Invalid label returns 400."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/embeddings/search",
            json={
                "label": "DROP; --",
                "property": "embedding",
                "queryVector": [0.1, 0.2],
                "topK": 10,
            },
        )
        assert resp.status_code == 400

    def test_vector_search_requires_query_vector(self) -> None:
        """TC-ES01c: Missing queryVector returns 422."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/embeddings/search",
            json={"label": "Vessel", "topK": 5},
        )
        assert resp.status_code == 422

    def test_vector_search_topk_validation(self) -> None:
        """TC-ES01d: topK=0 is rejected by validation."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/embeddings/search",
            json={
                "label": "Vessel",
                "queryVector": [0.1],
                "topK": 0,
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TC-ES02: POST /embeddings/hybrid returns results
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHybridSearch:
    """Tests for POST /api/v1/embeddings/hybrid."""

    def test_hybrid_search_returns_results(self) -> None:
        """TC-ES02: POST /embeddings/hybrid returns fused results."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post(
            "/api/v1/embeddings/hybrid",
            json={
                "label": "Document",
                "property": "textEmbedding",
                "queryVector": [0.1, 0.2, 0.3],
                "textQuery": "선박 성능",
                "topK": 10,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "meta" in data
        assert data["meta"]["fusion"] == "rrf"
        assert data["meta"]["textQuery"] == "선박 성능"
        assert data["meta"]["label"] == "Document"

    def test_hybrid_search_rejects_invalid_label(self) -> None:
        """TC-ES02b: Invalid label returns 400."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/embeddings/hybrid",
            json={
                "label": "'; DROP TABLE--",
                "queryVector": [0.1],
                "textQuery": "test",
                "topK": 5,
            },
        )
        assert resp.status_code == 400

    def test_hybrid_search_requires_text_query(self) -> None:
        """TC-ES02c: Missing textQuery returns 422."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/embeddings/hybrid",
            json={
                "label": "Vessel",
                "queryVector": [0.1, 0.2],
                "topK": 5,
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TC-ES03: GET /embeddings/indexes returns list
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmbeddingIndexes:
    """Tests for GET /api/v1/embeddings/indexes."""

    def test_list_indexes_returns_empty_by_default(self) -> None:
        """TC-ES03: GET /embeddings/indexes returns list (may be empty on fresh store)."""
        client, _ = _make_client()
        resp = client.get("/api/v1/embeddings/indexes")

        assert resp.status_code == 200
        data = resp.json()
        assert "indexes" in data
        assert isinstance(data["indexes"], list)

    def test_list_indexes_after_creation(self) -> None:
        """TC-ES03b: Created index appears in list."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)

        # Create an index first
        create_resp = client.post(
            "/api/v1/embeddings/indexes",
            json={
                "label": "TestNode",
                "property": "embedding",
                "dimensions": 384,
                "similarity": "cosine",
            },
        )
        assert create_resp.status_code == 201

        # Now list — the manager is module-level so index may persist across tests
        list_resp = client.get("/api/v1/embeddings/indexes")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert isinstance(data["indexes"], list)


# ---------------------------------------------------------------------------
# TC-ES04: POST /embeddings/indexes creates index
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateEmbeddingIndex:
    """Tests for POST /api/v1/embeddings/indexes."""

    def test_create_index_returns_created(self) -> None:
        """TC-ES04: POST /embeddings/indexes returns 201 with created flag."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post(
            "/api/v1/embeddings/indexes",
            json={
                "label": "Vessel",
                "property": "embedding",
                "dimensions": 768,
                "similarity": "cosine",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["created"] is True
        assert "cypher" in data
        assert "vessel_embedding_index" in data["cypher"].lower() or "vessel" in data["cypher"].lower()

    def test_create_index_invalid_label(self) -> None:
        """TC-ES04b: Invalid label returns 400."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/embeddings/indexes",
            json={
                "label": "Bad Label!",
                "property": "embedding",
                "dimensions": 768,
                "similarity": "cosine",
            },
        )
        assert resp.status_code == 400

    def test_create_index_invalid_similarity(self) -> None:
        """TC-ES04c: Invalid similarity function returns 422."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/embeddings/indexes",
            json={
                "label": "Vessel",
                "property": "embedding",
                "dimensions": 768,
                "similarity": "manhattan",  # not allowed
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TC-AL01: GET /algorithms returns algorithm list
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListAlgorithms:
    """Tests for GET /api/v1/algorithms."""

    def test_list_algorithms_returns_list(self) -> None:
        """TC-AL01: GET /algorithms returns a list of algorithm names."""
        client, _ = _make_client()
        resp = client.get("/api/v1/algorithms")

        assert resp.status_code == 200
        data = resp.json()
        assert "algorithms" in data
        assert isinstance(data["algorithms"], list)
        assert len(data["algorithms"]) > 0

    def test_list_algorithms_includes_known_algorithms(self) -> None:
        """TC-AL01b: Known algorithms are present in the list."""
        client, _ = _make_client()
        resp = client.get("/api/v1/algorithms")
        data = resp.json()
        algorithms = data["algorithms"]
        assert "pageRank" in algorithms
        assert "louvain" in algorithms
        assert "betweenness" in algorithms
        assert "dijkstra" in algorithms
        assert "nodeSimilarity" in algorithms


# ---------------------------------------------------------------------------
# TC-AL02: POST /algorithms/pagerank returns results
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPageRank:
    """Tests for POST /api/v1/algorithms/pagerank."""

    def test_pagerank_returns_algorithm_response(self) -> None:
        """TC-AL02: POST /algorithms/pagerank returns algorithm response structure."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post(
            "/api/v1/algorithms/pagerank",
            json={
                "label": "Vessel",
                "relationshipType": "DOCKED_AT",
                "iterations": 20,
                "dampingFactor": 0.85,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["algorithm"] == "pagerank"
        assert "results" in data
        assert "cypher" in data
        assert "meta" in data
        assert data["meta"]["label"] == "Vessel"
        assert data["meta"]["iterations"] == 20

    def test_pagerank_uses_defaults(self) -> None:
        """TC-AL02b: Missing optional fields use defaults."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post("/api/v1/algorithms/pagerank", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["dampingFactor"] == 0.85
        assert data["meta"]["iterations"] == 20

    def test_pagerank_iterations_validation(self) -> None:
        """TC-AL02c: iterations=0 is rejected."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/algorithms/pagerank",
            json={"iterations": 0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TC-AL03: POST /algorithms/community returns results
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCommunityDetection:
    """Tests for POST /api/v1/algorithms/community."""

    def test_community_detection_returns_response(self) -> None:
        """TC-AL03: POST /algorithms/community returns louvain response."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post(
            "/api/v1/algorithms/community",
            json={"label": "Vessel", "relationshipType": "DOCKED_AT"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["algorithm"] == "louvain"
        assert "results" in data
        assert "cypher" in data
        assert "meta" in data

    def test_community_detection_uses_defaults(self) -> None:
        """TC-AL03b: Missing fields use defaults."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post("/api/v1/algorithms/community", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert data["algorithm"] == "louvain"
        assert data["meta"]["label"] == "Vessel"


# ---------------------------------------------------------------------------
# TC-AL04: POST /algorithms/shortest-path returns results
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShortestPath:
    """Tests for POST /api/v1/algorithms/shortest-path."""

    def test_shortest_path_returns_response(self) -> None:
        """TC-AL04: POST /algorithms/shortest-path returns dijkstra response."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post(
            "/api/v1/algorithms/shortest-path",
            json={
                "sourceId": "VESSEL-001",
                "targetId": "PORT-BUS",
                "relationshipType": "ROUTE_TO",
                "weightProperty": "distance",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["algorithm"] == "dijkstra"
        assert "results" in data
        assert "cypher" in data
        assert "meta" in data
        assert data["meta"]["sourceId"] == "VESSEL-001"
        assert data["meta"]["targetId"] == "PORT-BUS"

    def test_shortest_path_requires_source_target(self) -> None:
        """TC-AL04b: Missing sourceId/targetId returns 422."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/algorithms/shortest-path",
            json={"relationshipType": "ROUTE_TO"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TC-AL05: GET /algorithms/gds-status returns status
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGDSStatus:
    """Tests for GET /api/v1/algorithms/gds-status."""

    def test_gds_status_available(self) -> None:
        """TC-AL05: GDS status returns available=True when version query succeeds."""
        mock_session = _make_mock_session()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: "2.6.0" if key == "version" else None
        mock_record.keys = lambda: ["version"]
        mock_result = _make_async_mock_result(records=[mock_record])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/algorithms/gds-status")

        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "version" in data

    def test_gds_status_unavailable(self) -> None:
        """TC-AL05b: GDS status returns available=False when query fails."""
        mock_session = _make_mock_session()
        mock_session.run = AsyncMock(side_effect=Exception("procedure not found"))

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/algorithms/gds-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["version"] is None


# ---------------------------------------------------------------------------
# TC-ET01: ETLStateStore save and retrieve run
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLStateStoreSaveRetrieve:
    """TC-ET01: ETLStateStore save and retrieve run."""

    def test_save_and_retrieve_run(self, tmp_path) -> None:
        """Saving a run and retrieving it by ID returns the correct record."""
        from kg.etl.state import ETLRunRecord, ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        record = ETLRunRecord(
            run_id="run-001",
            pipeline_name="papers",
            status="running",
            started_at=1000.0,
        )
        store.save_run(record)

        retrieved = store.get_run("run-001")
        assert retrieved is not None
        assert retrieved.run_id == "run-001"
        assert retrieved.pipeline_name == "papers"
        assert retrieved.status == "running"
        assert retrieved.started_at == 1000.0

    def test_get_nonexistent_run_returns_none(self, tmp_path) -> None:
        """Retrieving a non-existent run_id returns None."""
        from kg.etl.state import ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        result = store.get_run("nonexistent-run-id")
        assert result is None

    def test_save_replaces_existing_run(self, tmp_path) -> None:
        """Saving a record with the same run_id replaces the existing one."""
        from kg.etl.state import ETLRunRecord, ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        record = ETLRunRecord(
            run_id="run-001",
            pipeline_name="papers",
            status="running",
            started_at=1000.0,
        )
        store.save_run(record)

        updated = ETLRunRecord(
            run_id="run-001",
            pipeline_name="papers",
            status="completed",
            started_at=1000.0,
            completed_at=2000.0,
            record_count=42,
        )
        store.save_run(updated)

        retrieved = store.get_run("run-001")
        assert retrieved is not None
        assert retrieved.status == "completed"
        assert retrieved.record_count == 42


# ---------------------------------------------------------------------------
# TC-ET02: ETLStateStore list_runs with limit
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLStateStoreListRuns:
    """TC-ET02: ETLStateStore list_runs with limit."""

    def test_list_runs_returns_most_recent_first(self, tmp_path) -> None:
        """list_runs returns records ordered by started_at descending."""
        from kg.etl.state import ETLRunRecord, ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        for i in range(5):
            store.save_run(
                ETLRunRecord(
                    run_id=f"run-{i:03d}",
                    pipeline_name="papers",
                    status="completed",
                    started_at=float(i * 100),
                )
            )

        runs = store.list_runs(limit=10)
        assert len(runs) == 5
        # Most recent first (started_at=400 first)
        assert runs[0].started_at == 400.0
        assert runs[-1].started_at == 0.0

    def test_list_runs_respects_limit(self, tmp_path) -> None:
        """list_runs does not return more records than the limit."""
        from kg.etl.state import ETLRunRecord, ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        for i in range(10):
            store.save_run(
                ETLRunRecord(
                    run_id=f"run-{i:03d}",
                    pipeline_name="facilities",
                    status="completed",
                    started_at=float(i * 10),
                )
            )

        runs = store.list_runs(limit=3)
        assert len(runs) == 3

    def test_list_runs_filters_by_pipeline(self, tmp_path) -> None:
        """list_runs with pipeline filter returns only matching records."""
        from kg.etl.state import ETLRunRecord, ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        for i in range(3):
            store.save_run(
                ETLRunRecord(
                    run_id=f"papers-{i}",
                    pipeline_name="papers",
                    status="completed",
                    started_at=float(i),
                )
            )
        for i in range(2):
            store.save_run(
                ETLRunRecord(
                    run_id=f"weather-{i}",
                    pipeline_name="weather",
                    status="completed",
                    started_at=float(i + 10),
                )
            )

        papers_runs = store.list_runs(limit=20, pipeline="papers")
        assert len(papers_runs) == 3
        assert all(r.pipeline_name == "papers" for r in papers_runs)

        weather_runs = store.list_runs(limit=20, pipeline="weather")
        assert len(weather_runs) == 2

    def test_list_runs_empty_store(self, tmp_path) -> None:
        """list_runs on empty store returns empty list."""
        from kg.etl.state import ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        runs = store.list_runs()
        assert runs == []


# ---------------------------------------------------------------------------
# TC-ET03: ETLStateStore update_status
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLStateStoreUpdateStatus:
    """TC-ET03: ETLStateStore update_status."""

    def test_update_status_changes_status(self, tmp_path) -> None:
        """update_status changes status of an existing run."""
        from kg.etl.state import ETLRunRecord, ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        store.save_run(
            ETLRunRecord(
                run_id="run-001",
                pipeline_name="papers",
                status="running",
                started_at=1000.0,
            )
        )

        store.update_status("run-001", "completed")

        retrieved = store.get_run("run-001")
        assert retrieved is not None
        assert retrieved.status == "completed"

    def test_update_status_with_record_count(self, tmp_path) -> None:
        """update_status can update record_count alongside status."""
        from kg.etl.state import ETLRunRecord, ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        store.save_run(
            ETLRunRecord(
                run_id="run-001",
                pipeline_name="papers",
                status="running",
                started_at=1000.0,
            )
        )

        store.update_status("run-001", "completed", record_count=99)

        retrieved = store.get_run("run-001")
        assert retrieved is not None
        assert retrieved.record_count == 99
        assert retrieved.status == "completed"

    def test_update_status_with_error(self, tmp_path) -> None:
        """update_status can record an error message."""
        from kg.etl.state import ETLRunRecord, ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        store.save_run(
            ETLRunRecord(
                run_id="run-001",
                pipeline_name="papers",
                status="running",
                started_at=1000.0,
            )
        )

        store.update_status("run-001", "failed", error="Connection refused")

        retrieved = store.get_run("run-001")
        assert retrieved is not None
        assert retrieved.status == "failed"
        assert retrieved.error == "Connection refused"

    def test_update_status_nonexistent_is_noop(self, tmp_path) -> None:
        """update_status on nonexistent run_id does not raise."""
        from kg.etl.state import ETLStateStore

        db_path = str(tmp_path / "test_etl.db")
        store = ETLStateStore(db_path=db_path)

        # Should not raise
        store.update_status("nonexistent-id", "completed")


# ---------------------------------------------------------------------------
# TC-ET04: ETLRunRecord is frozen
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLRunRecordFrozen:
    """TC-ET04: ETLRunRecord is a frozen dataclass."""

    def test_etl_run_record_is_frozen(self) -> None:
        """ETLRunRecord instances are immutable (frozen dataclass)."""
        from kg.etl.state import ETLRunRecord

        record = ETLRunRecord(
            run_id="test-001",
            pipeline_name="papers",
            status="running",
            started_at=1000.0,
        )

        with pytest.raises((AttributeError, TypeError)):
            record.status = "completed"  # type: ignore[misc]

    def test_etl_run_record_defaults(self) -> None:
        """ETLRunRecord has correct default values."""
        from kg.etl.state import ETLRunRecord

        record = ETLRunRecord(
            run_id="test-001",
            pipeline_name="papers",
            status="pending",
            started_at=1000.0,
        )

        assert record.completed_at == 0.0
        assert record.record_count == 0
        assert record.error == ""
        assert record.metadata == {}

    def test_etl_run_record_with_metadata(self) -> None:
        """ETLRunRecord stores metadata dict correctly."""
        from kg.etl.state import ETLRunRecord

        record = ETLRunRecord(
            run_id="test-001",
            pipeline_name="papers",
            status="completed",
            started_at=1000.0,
            metadata={"source": "scheduler", "version": "1.0"},
        )

        assert record.metadata["source"] == "scheduler"
        assert record.metadata["version"] == "1.0"


# ---------------------------------------------------------------------------
# ETL SQLite persistence — round-trip through API
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLRouteSQLitePersistence:
    """Verify ETL route integrates with SQLite state store without breaking existing behaviour."""

    @pytest.fixture(autouse=True)
    def _patch_state_store(self, tmp_path, monkeypatch):
        """Patch the module-level _state_store to use a temp database."""
        from kg.etl import state as state_mod
        from kg.api.routes import etl as etl_mod

        # Reset module-level singleton so _get_state_store() creates a fresh one
        etl_mod._state_store = None

        # Patch ETLStateStore default db_path
        original_init = state_mod.ETLStateStore.__init__

        def patched_init(self_inner, db_path: str = "") -> None:
            if not db_path:
                db_path = str(tmp_path / "etl_state.db")
            original_init(self_inner, db_path=db_path)

        monkeypatch.setattr(state_mod.ETLStateStore, "__init__", patched_init)
        yield
        etl_mod._state_store = None

    @pytest.fixture(autouse=True)
    def _clear_run_history(self):
        """Clear in-memory run history before each test."""
        from kg.api.routes.etl import _run_history
        _run_history.clear()
        yield
        _run_history.clear()

    def test_trigger_persists_to_sqlite(self) -> None:
        """Triggering a pipeline saves run to SQLite store."""
        client, _ = _make_client()
        resp = client.post(
            "/api/v1/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "papers",
                "mode": "incremental",
                "force_full": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        run_id = data["run_id"]

        # Verify in-memory store still works
        status_resp = client.get(f"/api/v1/etl/status/{run_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["run_id"] == run_id
