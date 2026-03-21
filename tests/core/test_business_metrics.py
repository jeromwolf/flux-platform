"""Unit tests for business metrics helpers."""
from __future__ import annotations

import pytest

from kg.api.middleware.metrics import _MetricsStore, get_metrics_store, reset_metrics
from kg.api.middleware.business_metrics import (
    record_kg_query,
    record_etl_processed,
    record_cypher_error,
)


@pytest.fixture(autouse=True)
def _clean_metrics():
    """각 테스트 전후 메트릭 초기화."""
    reset_metrics()
    yield
    reset_metrics()


@pytest.mark.unit
class TestMetricsStoreBusinessMetrics:
    """Tests for _MetricsStore.record_business_metric()."""

    def test_record_increments_counter(self):
        store = _MetricsStore()
        store.record_business_metric("test_counter", {"label": "a"})
        store.record_business_metric("test_counter", {"label": "a"})
        output = store.format_prometheus()
        assert 'test_counter{label="a"} 2' in output

    def test_different_labels_separate(self):
        store = _MetricsStore()
        store.record_business_metric("test", {"type": "a"})
        store.record_business_metric("test", {"type": "b"})
        output = store.format_prometheus()
        assert 'test{type="a"} 1' in output
        assert 'test{type="b"} 1' in output

    def test_custom_value(self):
        store = _MetricsStore()
        store.record_business_metric("records", {"pipeline": "x"}, 100)
        output = store.format_prometheus()
        assert 'records{pipeline="x"} 100' in output

    def test_no_business_metrics_no_section(self):
        store = _MetricsStore()
        output = store.format_prometheus()
        assert "imsp_business_metrics" not in output


@pytest.mark.unit
class TestBusinessMetricHelpers:
    """Tests for convenience metric functions."""

    def test_record_kg_query_success(self):
        record_kg_query("text2cypher", success=True)
        output = get_metrics_store().format_prometheus()
        assert "imsp_kg_queries_total" in output
        assert "success" in output

    def test_record_kg_query_error(self):
        record_kg_query("cypher", success=False)
        output = get_metrics_store().format_prometheus()
        assert "error" in output

    def test_record_etl_processed(self):
        record_etl_processed("papers", 50)
        output = get_metrics_store().format_prometheus()
        assert "imsp_etl_records_processed_total" in output
        assert "50" in output

    def test_record_cypher_error(self):
        record_cypher_error("syntax")
        output = get_metrics_store().format_prometheus()
        assert "imsp_cypher_errors_total" in output
        assert "syntax" in output

    def test_existing_http_metrics_preserved(self):
        """기존 http_* 메트릭이 유지됨."""
        store = get_metrics_store()
        store.record_request("GET", "/test", 200, 0.01)
        output = store.format_prometheus()
        assert "http_requests_total" in output
