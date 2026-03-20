"""Unit tests for observability infrastructure (logging + metrics)."""

from __future__ import annotations

import json
import logging
import sys

import pytest

from kg.api.middleware.logging import JSONFormatter, setup_json_logging
from kg.api.middleware.metrics import (
    MetricsMiddleware,
    _MetricsStore,
    get_metrics_store,
    reset_metrics,
)

# =========================================================================
# JSON Logging
# =========================================================================


@pytest.mark.unit
class TestJSONFormatter:
    """Tests for the structured JSON log formatter."""

    def test_format_basic_message(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "Hello world"
        assert data["level"] == "INFO"
        assert data["logger"] == "test"

    def test_format_includes_timestamp(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "timestamp" in data

    def test_format_includes_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert data["exception"]["message"] == "test error"

    def test_format_includes_extra_fields(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="request",
            args=(),
            exc_info=None,
        )
        record.request_id = "abc-123"  # type: ignore[attr-defined]
        record.method = "GET"  # type: ignore[attr-defined]
        record.path = "/api/health"  # type: ignore[attr-defined]
        record.status_code = 200  # type: ignore[attr-defined]
        record.duration_ms = 42.5  # type: ignore[attr-defined]
        output = formatter.format(record)
        data = json.loads(output)
        assert data["request_id"] == "abc-123"
        assert data["method"] == "GET"
        assert data["duration_ms"] == 42.5

    def test_output_is_valid_json(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="한국어 메시지",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "한국어 메시지"


@pytest.mark.unit
class TestSetupJsonLogging:
    def test_setup_configures_handler(self):
        setup_json_logging(level="DEBUG")
        root = logging.getLogger()
        assert any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)
        # Cleanup
        root.handlers = [
            h for h in root.handlers if not isinstance(h.formatter, JSONFormatter)
        ]


# =========================================================================
# Metrics Store
# =========================================================================


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset_metrics()
    yield
    reset_metrics()


@pytest.mark.unit
class TestMetricsStore:
    """Tests for the thread-safe metrics store."""

    def test_record_request(self):
        store = _MetricsStore()
        store.record_request("GET", "/api/health", 200, 0.05)
        output = store.format_prometheus()
        assert (
            'http_requests_total{method="GET",path="/api/health",status="200"} 1'
            in output
        )

    def test_multiple_requests(self):
        store = _MetricsStore()
        store.record_request("GET", "/api/health", 200, 0.05)
        store.record_request("GET", "/api/health", 200, 0.03)
        store.record_request("POST", "/api/query", 200, 0.10)
        output = store.format_prometheus()
        assert (
            'http_requests_total{method="GET",path="/api/health",status="200"} 2'
            in output
        )
        assert (
            'http_requests_total{method="POST",path="/api/query",status="200"} 1'
            in output
        )

    def test_error_counting(self):
        store = _MetricsStore()
        store.record_request("GET", "/api/missing", 404, 0.01)
        store.record_request("POST", "/api/query", 500, 0.02)
        output = store.format_prometheus()
        assert (
            'http_errors_total{method="GET",path="/api/missing",error_class="4xx"} 1'
            in output
        )
        assert (
            'http_errors_total{method="POST",path="/api/query",error_class="5xx"} 1'
            in output
        )

    def test_duration_tracking(self):
        store = _MetricsStore()
        store.record_request("GET", "/api/health", 200, 0.050)
        store.record_request("GET", "/api/health", 200, 0.030)
        output = store.format_prometheus()
        assert (
            'http_request_duration_seconds_sum{method="GET",path="/api/health",status="200"}'
            in output
        )
        assert (
            'http_request_duration_seconds_count{method="GET",path="/api/health",status="200"} 2'
            in output
        )

    def test_active_requests(self):
        store = _MetricsStore()
        store.increment_active()
        store.increment_active()
        output = store.format_prometheus()
        assert "http_requests_active 2" in output
        store.decrement_active()
        output = store.format_prometheus()
        assert "http_requests_active 1" in output

    def test_format_prometheus_valid(self):
        store = _MetricsStore()
        output = store.format_prometheus()
        assert "# HELP" in output
        assert "# TYPE" in output

    def test_reset_metrics(self):
        store = get_metrics_store()
        store.record_request("GET", "/test", 200, 0.01)
        reset_metrics()
        new_store = get_metrics_store()
        output = new_store.format_prometheus()
        assert 'status="200"' not in output


@pytest.mark.unit
class TestMetricsMiddleware:
    def test_normalize_path_uuid(self):
        result = MetricsMiddleware._normalize_path(
            "/api/etl/status/550e8400-e29b-41d4-a716-446655440000"
        )
        assert result == "/api/etl/status/{id}"

    def test_normalize_path_numeric(self):
        result = MetricsMiddleware._normalize_path("/api/items/12345")
        assert result == "/api/items/{id}"

    def test_normalize_path_no_change(self):
        result = MetricsMiddleware._normalize_path("/api/health")
        assert result == "/api/health"

    def test_normalize_path_mixed(self):
        result = MetricsMiddleware._normalize_path("/api/users/42/posts")
        assert result == "/api/users/{id}/posts"
