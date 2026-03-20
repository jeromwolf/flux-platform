"""Unit tests for the ETL trigger API endpoints.

All tests are marked with ``@pytest.mark.unit`` and mock Neo4j so no
database connection is required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kg.api.app import create_app
from kg.api.deps import get_app_config, get_async_neo4j_session
from kg.api.middleware.auth import get_current_api_key
from kg.config import AppConfig, Neo4jConfig, reset

# ---------------------------------------------------------------------------
# Fixtures
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


def _make_mock_session() -> MagicMock:
    """Create a mock async Neo4j session."""
    mock_session = MagicMock()
    mock_session.run = AsyncMock()
    mock_session.close = AsyncMock()
    return mock_session


def _make_client(mock_session: MagicMock | None = None) -> tuple[TestClient, MagicMock]:
    """Create a TestClient with dependency overrides for Neo4j.

    Returns:
        Tuple of (TestClient, mock_session).
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


@pytest.fixture(autouse=True)
def _clear_etl_history():
    """Clear the in-memory ETL run history before each test."""
    from kg.api.routes.etl import _run_history
    _run_history.clear()
    yield
    _run_history.clear()


# ---------------------------------------------------------------------------
# TestETLTrigger
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLTrigger:
    """Test POST /api/etl/trigger endpoint."""

    def test_trigger_papers_pipeline(self) -> None:
        """Trigger papers pipeline returns success response."""
        client, _ = _make_client()
        resp = client.post(
            "/api/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "papers",
                "mode": "incremental",
                "force_full": False,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_name"] == "papers"
        assert data["status"] in ("COMPLETED", "RUNNING")
        assert "run_id" in data
        assert len(data["run_id"]) > 0  # UUID format

    def test_trigger_unknown_pipeline(self) -> None:
        """Triggering unknown pipeline returns 400 error."""
        client, _ = _make_client()
        resp = client.post(
            "/api/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "unknown_pipeline",
                "mode": "incremental",
                "force_full": False,
            },
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "Unknown pipeline" in data["detail"]

    def test_trigger_full_mode(self) -> None:
        """Trigger with mode=full sets FULL mode."""
        client, _ = _make_client()
        resp = client.post(
            "/api/etl/trigger",
            json={
                "source": "schedule",
                "pipeline_name": "facilities",
                "mode": "full",
                "force_full": False,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_name"] == "facilities"
        assert data["status"] in ("COMPLETED", "RUNNING")

    def test_trigger_force_full(self) -> None:
        """Trigger with force_full=true applies FULL mode."""
        client, _ = _make_client()
        resp = client.post(
            "/api/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "weather",
                "mode": "incremental",
                "force_full": True,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_name"] == "weather"
        assert data["status"] in ("COMPLETED", "RUNNING")

    def test_trigger_returns_run_id(self) -> None:
        """Trigger response contains valid run_id (UUID format)."""
        client, _ = _make_client()
        resp = client.post(
            "/api/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "accidents",
                "mode": "incremental",
                "force_full": False,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        run_id = data["run_id"]
        # Check UUID format (8-4-4-4-12 hex digits)
        parts = run_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4


# ---------------------------------------------------------------------------
# TestETLWebhook
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLWebhook:
    """Test POST /api/etl/webhook/{source} endpoint."""

    def test_webhook_data_changed(self) -> None:
        """Webhook with data_changed event triggers pipeline."""
        client, _ = _make_client()
        resp = client.post(
            "/api/etl/webhook/papers",
            json={
                "event": "data_changed",
                "entity_type": "Document",
                "data": {"count": 10},
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_name"] == "papers"
        assert data["status"] in ("COMPLETED", "RUNNING")
        assert "run_id" in data

    def test_webhook_unknown_source(self) -> None:
        """Webhook with unknown source returns 400."""
        client, _ = _make_client()
        resp = client.post(
            "/api/etl/webhook/unknown_source",
            json={
                "event": "file_created",
                "data": {},
            },
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "Unknown webhook source" in data["detail"]

    def test_webhook_creates_run(self) -> None:
        """Webhook creates a run record in history."""
        client, _ = _make_client()
        resp = client.post(
            "/api/etl/webhook/facilities",
            json={
                "event": "file_created",
                "data": {"filename": "test.csv"},
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        run_id = data["run_id"]

        # Check that run exists in history
        status_resp = client.get(f"/api/etl/status/{run_id}")
        assert status_resp.status_code == 200


# ---------------------------------------------------------------------------
# TestETLStatus
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLStatus:
    """Test GET /api/etl/status/{run_id} endpoint."""

    def test_get_status_existing(self) -> None:
        """Get status for existing run returns details."""
        client, _ = _make_client()

        # Create a run first
        trigger_resp = client.post(
            "/api/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "papers",
                "mode": "incremental",
                "force_full": False,
            },
        )
        run_id = trigger_resp.json()["run_id"]

        # Get status
        resp = client.get(f"/api/etl/status/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["pipeline_name"] == "papers"
        assert "status" in data

    def test_get_status_not_found(self) -> None:
        """Get status for non-existent run returns 404."""
        client, _ = _make_client()
        resp = client.get("/api/etl/status/00000000-0000-0000-0000-000000000000")

        assert resp.status_code == 404
        data = resp.json()
        assert "not found" in data["detail"]

    def test_status_fields(self) -> None:
        """Status response contains all required fields."""
        client, _ = _make_client()

        # Create a run
        trigger_resp = client.post(
            "/api/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "weather",
                "mode": "incremental",
                "force_full": False,
            },
        )
        run_id = trigger_resp.json()["run_id"]

        # Get status
        resp = client.get(f"/api/etl/status/{run_id}")
        data = resp.json()

        # Verify all required fields
        assert "run_id" in data
        assert "pipeline_name" in data
        assert "status" in data
        assert "records_processed" in data
        assert "records_failed" in data
        assert "records_skipped" in data
        assert "duration_seconds" in data
        assert "started_at" in data
        assert "errors" in data


# ---------------------------------------------------------------------------
# TestETLHistory
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLHistory:
    """Test GET /api/etl/history endpoint."""

    def test_get_history_empty(self) -> None:
        """Get history with no runs returns empty list."""
        client, _ = _make_client()
        resp = client.get("/api/etl/history")

        assert resp.status_code == 200
        data = resp.json()
        assert data["runs"] == []
        assert data["total"] == 0

    def test_get_history_with_runs(self) -> None:
        """Get history with multiple runs returns sorted list."""
        client, _ = _make_client()

        # Create multiple runs
        for pipeline_name in ["papers", "facilities", "weather"]:
            client.post(
                "/api/etl/trigger",
                json={
                    "source": "manual",
                    "pipeline_name": pipeline_name,
                    "mode": "incremental",
                    "force_full": False,
                },
            )

        # Get history
        resp = client.get("/api/etl/history?limit=10")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 3
        assert len(data["runs"]) == 3

        # Verify runs are sorted by started_at descending (most recent first)
        started_times = [run["started_at"] for run in data["runs"]]
        assert started_times == sorted(started_times, reverse=True)


# ---------------------------------------------------------------------------
# TestETLPipelines
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestETLPipelines:
    """Test GET /api/etl/pipelines endpoint."""

    def test_list_pipelines(self) -> None:
        """List pipelines returns all registered pipelines."""
        client, _ = _make_client()
        resp = client.get("/api/etl/pipelines")

        assert resp.status_code == 200
        data = resp.json()

        # Verify we have 6 pipelines
        assert len(data) == 6
        pipeline_names = {p["name"] for p in data}
        assert pipeline_names == {
            "papers",
            "facilities",
            "weather",
            "accidents",
            "relations",
            "facility_data",
        }

    def test_pipeline_info(self) -> None:
        """Each pipeline info contains required fields."""
        client, _ = _make_client()
        resp = client.get("/api/etl/pipelines")

        assert resp.status_code == 200
        data = resp.json()

        for pipeline in data:
            assert "name" in pipeline
            assert "description" in pipeline
            assert "schedule" in pipeline
            assert "entity_type" in pipeline
            assert len(pipeline["description"]) > 0
            assert len(pipeline["schedule"]) > 0
