"""Tests for gateway/middleware/metrics.py — GatewayMetrics."""
from __future__ import annotations

import pytest

from gateway.middleware.metrics import GatewayMetrics, gateway_metrics


# ---------------------------------------------------------------------------
# GatewayMetrics dataclass creation
# ---------------------------------------------------------------------------


class TestGatewayMetricsDefaults:
    """TC-GM: Default state of a freshly constructed GatewayMetrics."""

    @pytest.mark.unit
    def test_tc_gm01_requests_total_default_zero(self):
        """TC-GM01: requests_total starts at 0."""
        m = GatewayMetrics()
        assert m.requests_total == 0

    @pytest.mark.unit
    def test_tc_gm02_errors_total_default_zero(self):
        """TC-GM02: errors_total starts at 0."""
        m = GatewayMetrics()
        assert m.errors_total == 0

    @pytest.mark.unit
    def test_tc_gm03_request_durations_default_empty_list(self):
        """TC-GM03: request_durations starts as an empty list."""
        m = GatewayMetrics()
        assert m.request_durations == []

    @pytest.mark.unit
    def test_tc_gm04_status_codes_default_empty(self):
        """TC-GM04: status_codes starts empty."""
        m = GatewayMetrics()
        assert len(m.status_codes) == 0

    @pytest.mark.unit
    def test_tc_gm05_instances_have_independent_state(self):
        """TC-GM05: Two instances do not share mutable fields."""
        m1 = GatewayMetrics()
        m2 = GatewayMetrics()
        m1.record_request(0.1, 200)
        assert m2.requests_total == 0
        assert m2.request_durations == []


# ---------------------------------------------------------------------------
# record_request()
# ---------------------------------------------------------------------------


class TestRecordRequest:
    """TC-RR: record_request() increments counters correctly."""

    @pytest.mark.unit
    def test_tc_rr01_increments_requests_total(self):
        """TC-RR01: Each call increments requests_total by 1."""
        m = GatewayMetrics()
        m.record_request(0.05, 200)
        assert m.requests_total == 1
        m.record_request(0.1, 200)
        assert m.requests_total == 2

    @pytest.mark.unit
    def test_tc_rr02_appends_duration(self):
        """TC-RR02: Duration value is appended to request_durations."""
        m = GatewayMetrics()
        m.record_request(0.123, 200)
        assert m.request_durations == [0.123]

    @pytest.mark.unit
    def test_tc_rr03_increments_status_code_counter(self):
        """TC-RR03: status_codes[code] increments on each call."""
        m = GatewayMetrics()
        m.record_request(0.1, 200)
        m.record_request(0.2, 200)
        m.record_request(0.1, 404)
        assert m.status_codes[200] == 2
        assert m.status_codes[404] == 1

    @pytest.mark.unit
    def test_tc_rr04_5xx_increments_errors_total(self):
        """TC-RR04: 5xx status codes increment errors_total."""
        m = GatewayMetrics()
        m.record_request(0.05, 500)
        m.record_request(0.05, 503)
        assert m.errors_total == 2

    @pytest.mark.unit
    def test_tc_rr05_4xx_does_not_increment_errors_total(self):
        """TC-RR05: 4xx status codes do NOT increment errors_total."""
        m = GatewayMetrics()
        m.record_request(0.05, 400)
        m.record_request(0.05, 404)
        m.record_request(0.05, 429)
        assert m.errors_total == 0

    @pytest.mark.unit
    def test_tc_rr06_2xx_does_not_increment_errors_total(self):
        """TC-RR06: 2xx status codes do NOT increment errors_total."""
        m = GatewayMetrics()
        m.record_request(0.1, 200)
        m.record_request(0.1, 201)
        m.record_request(0.1, 204)
        assert m.errors_total == 0

    @pytest.mark.unit
    def test_tc_rr07_exactly_500_is_error(self):
        """TC-RR07: Status 500 (boundary) increments errors_total."""
        m = GatewayMetrics()
        m.record_request(0.05, 500)
        assert m.errors_total == 1

    @pytest.mark.unit
    def test_tc_rr08_mixed_requests_accumulate_correctly(self):
        """TC-RR08: Mixed status codes accumulate totals correctly."""
        m = GatewayMetrics()
        for _ in range(3):
            m.record_request(0.1, 200)
        for _ in range(2):
            m.record_request(0.05, 404)
        for _ in range(1):
            m.record_request(0.2, 500)

        assert m.requests_total == 6
        assert m.errors_total == 1
        assert m.status_codes[200] == 3
        assert m.status_codes[404] == 2
        assert m.status_codes[500] == 1
        assert len(m.request_durations) == 6

    @pytest.mark.unit
    def test_tc_rr09_very_fast_request_near_zero(self):
        """TC-RR09: Very fast (near-zero) duration is stored accurately."""
        m = GatewayMetrics()
        m.record_request(0.000001, 200)
        assert m.request_durations[0] == pytest.approx(0.000001)

    @pytest.mark.unit
    def test_tc_rr10_very_slow_request_large_duration(self):
        """TC-RR10: Very slow (large) duration is stored accurately."""
        m = GatewayMetrics()
        m.record_request(120.5, 200)
        assert m.request_durations[0] == pytest.approx(120.5)


# ---------------------------------------------------------------------------
# _histogram_lines()
# ---------------------------------------------------------------------------


class TestHistogramLines:
    """TC-HL: _histogram_lines() produces valid Prometheus histogram output."""

    @pytest.mark.unit
    def test_tc_hl01_includes_help_and_type_lines(self):
        """TC-HL01: Output begins with HELP and TYPE comment lines."""
        m = GatewayMetrics()
        lines = m._histogram_lines()
        assert lines[0].startswith("# HELP gateway_request_duration_seconds")
        assert lines[1].startswith("# TYPE gateway_request_duration_seconds histogram")

    @pytest.mark.unit
    def test_tc_hl02_all_standard_buckets_present(self):
        """TC-HL02: All 11 standard bucket labels are present."""
        m = GatewayMetrics()
        lines = m._histogram_lines()
        bucket_lines = [l for l in lines if "_bucket{le=" in l]
        # 11 finite buckets + 1 +Inf = 12
        assert len(bucket_lines) == 12

    @pytest.mark.unit
    def test_tc_hl03_plus_inf_bucket_equals_total_count(self):
        """TC-HL03: +Inf bucket count matches total requests recorded."""
        m = GatewayMetrics()
        m.record_request(0.01, 200)
        m.record_request(0.5, 200)
        m.record_request(3.0, 200)
        lines = m._histogram_lines()
        inf_line = next(l for l in lines if 'le="+Inf"' in l)
        count = int(inf_line.split()[-1])
        assert count == 3

    @pytest.mark.unit
    def test_tc_hl04_bucket_counts_are_cumulative(self):
        """TC-HL04: Bucket counts are non-decreasing (cumulative histogram)."""
        m = GatewayMetrics()
        for d in [0.001, 0.005, 0.01, 0.1, 1.0]:
            m.record_request(d, 200)
        lines = m._histogram_lines()
        bucket_lines = [l for l in lines if "_bucket{le=" in l and '+Inf' not in l]
        counts = [int(l.split()[-1]) for l in bucket_lines]
        for i in range(len(counts) - 1):
            assert counts[i] <= counts[i + 1], "Histogram buckets must be cumulative"

    @pytest.mark.unit
    def test_tc_hl05_sum_and_count_lines_present(self):
        """TC-HL05: _sum and _count lines appear in output."""
        m = GatewayMetrics()
        m.record_request(0.1, 200)
        lines = m._histogram_lines()
        assert any("_sum" in l for l in lines)
        assert any("_count" in l for l in lines)

    @pytest.mark.unit
    def test_tc_hl06_empty_metrics_all_buckets_zero(self):
        """TC-HL06: With no requests, all bucket counts are 0."""
        m = GatewayMetrics()
        lines = m._histogram_lines()
        bucket_lines = [l for l in lines if "_bucket{le=" in l]
        for line in bucket_lines:
            count = int(line.split()[-1])
            assert count == 0

    @pytest.mark.unit
    def test_tc_hl07_sum_matches_total_duration(self):
        """TC-HL07: _sum value matches sum of all recorded durations."""
        m = GatewayMetrics()
        durations = [0.1, 0.2, 0.3]
        for d in durations:
            m.record_request(d, 200)
        lines = m._histogram_lines()
        sum_line = next(l for l in lines if "_sum" in l and "_count" not in l)
        value = float(sum_line.split()[-1])
        assert value == pytest.approx(sum(durations), abs=1e-5)


# ---------------------------------------------------------------------------
# to_prometheus()
# ---------------------------------------------------------------------------


class TestToPrometheus:
    """TC-PM: to_prometheus() renders a valid Prometheus text-format payload."""

    @pytest.mark.unit
    def test_tc_pm01_output_ends_with_newline(self):
        """TC-PM01: Output ends with a trailing newline."""
        m = GatewayMetrics()
        payload = m.to_prometheus()
        assert payload.endswith("\n")

    @pytest.mark.unit
    def test_tc_pm02_contains_requests_total_metric(self):
        """TC-PM02: Output contains gateway_requests_total metric."""
        m = GatewayMetrics()
        m.record_request(0.1, 200)
        payload = m.to_prometheus()
        assert "gateway_requests_total 1" in payload

    @pytest.mark.unit
    def test_tc_pm03_contains_errors_total_metric(self):
        """TC-PM03: Output contains gateway_errors_total metric."""
        m = GatewayMetrics()
        m.record_request(0.1, 500)
        payload = m.to_prometheus()
        assert "gateway_errors_total 1" in payload

    @pytest.mark.unit
    def test_tc_pm04_active_connections_param_reflected(self):
        """TC-PM04: active_connections parameter appears in output."""
        m = GatewayMetrics()
        payload = m.to_prometheus(active_connections=7)
        assert "gateway_active_connections 7" in payload

    @pytest.mark.unit
    def test_tc_pm05_active_connections_default_zero(self):
        """TC-PM05: Default active_connections is 0."""
        m = GatewayMetrics()
        payload = m.to_prometheus()
        assert "gateway_active_connections 0" in payload

    @pytest.mark.unit
    def test_tc_pm06_status_code_labels_in_output(self):
        """TC-PM06: Per-status-code counters appear with correct labels."""
        m = GatewayMetrics()
        m.record_request(0.1, 200)
        m.record_request(0.1, 404)
        payload = m.to_prometheus()
        assert 'gateway_http_status{code="200"} 1' in payload
        assert 'gateway_http_status{code="404"} 1' in payload

    @pytest.mark.unit
    def test_tc_pm07_histogram_section_present(self):
        """TC-PM07: Histogram section appears in output."""
        m = GatewayMetrics()
        payload = m.to_prometheus()
        assert "gateway_request_duration_seconds" in payload

    @pytest.mark.unit
    def test_tc_pm08_help_and_type_lines_for_all_metrics(self):
        """TC-PM08: All top-level metrics have # HELP and # TYPE lines."""
        m = GatewayMetrics()
        payload = m.to_prometheus()
        for metric in [
            "gateway_requests_total",
            "gateway_errors_total",
            "gateway_active_connections",
            "gateway_http_status",
            "gateway_request_duration_seconds",
        ]:
            assert f"# HELP {metric}" in payload, f"Missing HELP for {metric}"
            assert f"# TYPE {metric}" in payload, f"Missing TYPE for {metric}"

    @pytest.mark.unit
    def test_tc_pm09_empty_metrics_no_status_code_lines(self):
        """TC-PM09: With no requests, no gateway_http_status label lines appear."""
        m = GatewayMetrics()
        payload = m.to_prometheus()
        # HELP/TYPE lines are present but no label lines like {code="..."}
        label_lines = [
            l for l in payload.splitlines()
            if l.startswith("gateway_http_status{")
        ]
        assert label_lines == []

    @pytest.mark.unit
    def test_tc_pm10_multiple_requests_requests_total_accurate(self):
        """TC-PM10: requests_total reflects all recorded requests."""
        m = GatewayMetrics()
        for i in range(10):
            m.record_request(0.05 * i, 200 if i % 2 == 0 else 500)
        payload = m.to_prometheus()
        assert "gateway_requests_total 10" in payload

    @pytest.mark.unit
    def test_tc_pm11_status_codes_sorted_in_output(self):
        """TC-PM11: Status code label lines appear in ascending order."""
        m = GatewayMetrics()
        m.record_request(0.1, 404)
        m.record_request(0.1, 200)
        m.record_request(0.1, 500)
        payload = m.to_prometheus()
        lines = payload.splitlines()
        label_lines = [l for l in lines if l.startswith("gateway_http_status{code=")]
        codes = [int(l.split('"')[1]) for l in label_lines]
        assert codes == sorted(codes)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


class TestModuleSingleton:
    """TC-MS: Module-level gateway_metrics singleton is a GatewayMetrics instance."""

    @pytest.mark.unit
    def test_tc_ms01_singleton_is_gateway_metrics_instance(self):
        """TC-MS01: gateway_metrics is an instance of GatewayMetrics."""
        assert isinstance(gateway_metrics, GatewayMetrics)
