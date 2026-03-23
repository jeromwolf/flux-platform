"""Tests for AccessLogMiddleware structured JSON logging."""
from __future__ import annotations

import json
import logging

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper — minimal app with AccessLogMiddleware
# ---------------------------------------------------------------------------


def _make_access_log_app() -> FastAPI:
    from gateway.middleware.access_log import AccessLogMiddleware
    from gateway.middleware.request_id import RequestIDMiddleware

    app = FastAPI()
    # Starlette applies add_middleware in LIFO order (last added = outermost).
    # Add AccessLog first so RequestID (added second) runs before it on the
    # way in, ensuring request.state.request_id is set when AccessLog reads it.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def _ping():
        return {"ok": True}

    @app.get("/error")
    async def _error():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="not found")

    @app.get("/server-error")
    async def _server_error():
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="internal error")

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAccessLogMiddleware:
    """Tests for AccessLogMiddleware."""

    @pytest.mark.unit
    def test_access_log_middleware_logs_json(self, caplog):
        """Each request emits a valid JSON log entry via gateway.access logger."""
        app = _make_access_log_app()
        client = TestClient(app, raise_server_exceptions=False)

        with caplog.at_level(logging.INFO, logger="gateway.access"):
            client.get("/ping")

        # Find the JSON log record from our middleware
        json_records = [r for r in caplog.records if r.name == "gateway.access"]
        assert len(json_records) >= 1, "Expected at least one access log entry"

        record = json_records[-1]
        entry = json.loads(record.getMessage())

        assert entry["method"] == "GET"
        assert entry["path"] == "/ping"
        assert entry["status"] == 200
        assert "duration_ms" in entry
        assert isinstance(entry["duration_ms"], float)
        assert "timestamp" in entry
        assert "level" in entry

    @pytest.mark.unit
    def test_access_log_includes_request_id(self, caplog):
        """Log entry includes the request_id set by RequestIDMiddleware."""
        app = _make_access_log_app()
        client = TestClient(app, raise_server_exceptions=False)

        custom_id = "test-req-id-abc"
        with caplog.at_level(logging.INFO, logger="gateway.access"):
            client.get("/ping", headers={"X-Request-ID": custom_id})

        json_records = [r for r in caplog.records if r.name == "gateway.access"]
        assert json_records, "No access log records emitted"

        entry = json.loads(json_records[-1].getMessage())
        assert entry["request_id"] == custom_id

    @pytest.mark.unit
    def test_access_log_level_based_on_status(self, caplog):
        """Log level field matches HTTP status: INFO < 400, WARN 4xx, ERROR 5xx."""
        app = _make_access_log_app()
        client = TestClient(app, raise_server_exceptions=False)

        results: dict[int, str] = {}

        with caplog.at_level(logging.INFO, logger="gateway.access"):
            client.get("/ping")           # 200
            client.get("/error")          # 404
            client.get("/server-error")   # 500

        json_records = [r for r in caplog.records if r.name == "gateway.access"]
        for record in json_records:
            entry = json.loads(record.getMessage())
            results[entry["status"]] = entry["level"]

        assert results.get(200) == "INFO"
        assert results.get(404) == "WARN"
        assert results.get(500) == "ERROR"

    @pytest.mark.unit
    def test_access_log_no_none_values(self, caplog):
        """Log entries must not contain None values (clean JSON)."""
        app = _make_access_log_app()
        client = TestClient(app, raise_server_exceptions=False)

        with caplog.at_level(logging.INFO, logger="gateway.access"):
            client.get("/ping")

        json_records = [r for r in caplog.records if r.name == "gateway.access"]
        assert json_records

        entry = json.loads(json_records[-1].getMessage())
        for key, value in entry.items():
            assert value is not None, f"Key '{key}' has None value"

    @pytest.mark.unit
    def test_access_log_contains_required_fields(self, caplog):
        """Every log entry includes the mandatory fields."""
        app = _make_access_log_app()
        client = TestClient(app, raise_server_exceptions=False)

        with caplog.at_level(logging.INFO, logger="gateway.access"):
            client.get("/ping")

        json_records = [r for r in caplog.records if r.name == "gateway.access"]
        assert json_records

        entry = json.loads(json_records[-1].getMessage())
        required = {"timestamp", "level", "method", "path", "status", "duration_ms"}
        for field in required:
            assert field in entry, f"Missing required field: {field}"
