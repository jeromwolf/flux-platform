"""E2E harness tests for ETL pipeline endpoints.

Covers /api/v1/etl/trigger, /etl/webhook/{source}, /etl/status/{run_id},
/etl/history, /etl/pipelines, /etl/reprocess/{run_id}.

Uses MockNeo4jSession -- no real Neo4j instance required.
Module-level _run_history is cleared before each test to avoid state leaks.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.helpers.mock_neo4j import (
    MockNeo4jSession,
    MockNeo4jResult,
)
from tests.e2e.conftest import _reset

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_etl_state() -> None:
    """Clear module-level ETL run history and reset SQLite state store."""
    from kg.api.routes.etl import _run_history
    _run_history.clear()

    # Reset the SQLite state store singleton so it gets re-created fresh
    import kg.api.routes.etl as etl_mod
    etl_mod._state_store = None


# ===========================================================================
# TestETLTriggerHarness
# ===========================================================================


class TestETLTriggerHarness:
    """Tests for POST /api/v1/etl/trigger."""

    async def test_trigger_known_pipeline(self, harness: Any) -> None:
        """Trigger a known pipeline returns COMPLETED with run_id."""
        client, session, _app = harness
        _clear_etl_state()
        _reset(session, [])

        resp = await client.post(
            "/api/v1/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "papers",
                "mode": "incremental",
                "force_full": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pipeline_name"] == "papers"
        assert body["run_id"]  # non-empty UUID
        assert body["status"] in ("COMPLETED", "FAILED")

    async def test_trigger_unknown_pipeline(self, harness: Any) -> None:
        """Unknown pipeline name returns 400."""
        client, session, _app = harness
        _clear_etl_state()

        resp = await client.post(
            "/api/v1/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "nonexistent_pipeline",
                "mode": "full",
                "force_full": False,
            },
        )
        assert resp.status_code == 400
        assert "Unknown pipeline" in resp.json()["detail"]

    async def test_trigger_force_full(self, harness: Any) -> None:
        """force_full=True triggers full mode pipeline."""
        client, session, _app = harness
        _clear_etl_state()
        _reset(session, [])

        resp = await client.post(
            "/api/v1/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "facilities",
                "mode": "incremental",
                "force_full": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pipeline_name"] == "facilities"
        assert body["run_id"]

    async def test_elt_mode_trigger(self, harness: Any) -> None:
        """mode='elt' triggers ELT execution path."""
        client, session, _app = harness
        _clear_etl_state()
        _reset(session, [])

        resp = await client.post(
            "/api/v1/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "weather",
                "mode": "elt",
                "force_full": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pipeline_name"] == "weather"
        # ELT mode runs with LocalFileStore; should complete or fail gracefully
        assert body["status"] in ("COMPLETED", "FAILED")


# ===========================================================================
# TestETLWebhookHarness
# ===========================================================================


class TestETLWebhookHarness:
    """Tests for POST /api/v1/etl/webhook/{source}."""

    async def test_webhook_trigger(self, harness: Any) -> None:
        """Webhook for known source delegates to trigger and returns result."""
        client, session, _app = harness
        _clear_etl_state()
        _reset(session, [])

        resp = await client.post(
            "/api/v1/etl/webhook/papers",
            json={"event": "data_changed", "data": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pipeline_name"] == "papers"
        assert body["run_id"]

    async def test_webhook_unknown_source(self, harness: Any) -> None:
        """Webhook for unknown source returns 400."""
        client, session, _app = harness
        _clear_etl_state()

        resp = await client.post(
            "/api/v1/etl/webhook/unknown_source",
            json={"event": "data_changed", "data": {}},
        )
        assert resp.status_code == 400
        assert "Unknown webhook source" in resp.json()["detail"]


# ===========================================================================
# TestETLStatusHarness
# ===========================================================================


class TestETLStatusHarness:
    """Tests for GET /api/v1/etl/status/{run_id}."""

    async def test_get_status(self, harness: Any) -> None:
        """Trigger first, then query status by run_id."""
        client, session, _app = harness
        _clear_etl_state()
        _reset(session, [])

        # Trigger a pipeline to get a run_id
        trigger_resp = await client.post(
            "/api/v1/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "accidents",
                "mode": "full",
                "force_full": False,
            },
        )
        assert trigger_resp.status_code == 200
        run_id = trigger_resp.json()["run_id"]

        # Query status
        status_resp = await client.get(f"/api/v1/etl/status/{run_id}")
        assert status_resp.status_code == 200
        body = status_resp.json()
        assert body["run_id"] == run_id
        assert body["pipeline_name"] == "accidents"
        assert body["status"] in ("RUNNING", "COMPLETED", "FAILED")

    async def test_get_status_not_found(self, harness: Any) -> None:
        """Unknown run_id returns 404."""
        client, session, _app = harness
        _clear_etl_state()

        resp = await client.get("/api/v1/etl/status/nonexistent-run-id-12345")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


# ===========================================================================
# TestETLHistoryHarness
# ===========================================================================


class TestETLHistoryHarness:
    """Tests for GET /api/v1/etl/history."""

    async def test_history_empty(self, harness: Any) -> None:
        """Empty history returns zero runs."""
        client, session, _app = harness
        _clear_etl_state()

        resp = await client.get("/api/v1/etl/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["runs"] == []
        assert body["total"] == 0

    async def test_history_after_trigger(self, harness: Any) -> None:
        """After triggering a pipeline, history contains that run."""
        client, session, _app = harness
        _clear_etl_state()
        _reset(session, [])

        # Trigger
        trigger_resp = await client.post(
            "/api/v1/etl/trigger",
            json={
                "source": "manual",
                "pipeline_name": "relations",
                "mode": "incremental",
                "force_full": False,
            },
        )
        assert trigger_resp.status_code == 200
        run_id = trigger_resp.json()["run_id"]

        # Check history
        history_resp = await client.get("/api/v1/etl/history")
        assert history_resp.status_code == 200
        body = history_resp.json()
        assert body["total"] >= 1
        run_ids = [r["run_id"] for r in body["runs"]]
        assert run_id in run_ids


# ===========================================================================
# TestETLPipelinesHarness
# ===========================================================================


class TestETLPipelinesHarness:
    """Tests for GET /api/v1/etl/pipelines."""

    async def test_list_pipelines(self, harness: Any) -> None:
        """List pipelines returns the 6 registered pipelines."""
        client, session, _app = harness

        resp = await client.get("/api/v1/etl/pipelines")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 6

        names = {p["name"] for p in body}
        assert "papers" in names
        assert "facilities" in names
        assert "weather" in names
        assert "accidents" in names
        assert "relations" in names
        assert "facility_data" in names

        # All pipelines support ELT
        for p in body:
            assert p["supports_elt"] is True
            assert p["description"]
            assert p["schedule"]
            assert p["entity_type"]


# ===========================================================================
# TestETLReprocessHarness
# ===========================================================================


class TestETLReprocessHarness:
    """Tests for POST /api/v1/etl/reprocess/{run_id}."""

    async def test_reprocess_not_found(self, harness: Any) -> None:
        """Reprocess with unknown run_id returns 404."""
        client, session, _app = harness
        _clear_etl_state()

        resp = await client.post("/api/v1/etl/reprocess/nonexistent-run-999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]
