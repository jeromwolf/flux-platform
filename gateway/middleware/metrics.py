"""Prometheus-format metrics collector for the IMSP API Gateway."""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class GatewayMetrics:
    """Simple in-process metrics store.

    Tracks request counts, error counts, status code distribution, and
    request durations.  Use :meth:`to_prometheus` to render a Prometheus
    text-format scrape payload.

    Attributes:
        requests_total: Cumulative count of all handled requests.
        errors_total: Cumulative count of requests that resulted in HTTP 5xx.
        request_durations: Wall-clock durations (seconds) for all requests.
        status_codes: Map of HTTP status code → request count.
    """

    requests_total: int = 0
    errors_total: int = 0
    request_durations: list[float] = field(default_factory=list)
    status_codes: dict[int, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    def record_request(self, duration: float, status_code: int) -> None:
        """Record a completed request.

        Args:
            duration: Request wall-clock time in seconds.
            status_code: HTTP response status code.
        """
        self.requests_total += 1
        self.request_durations.append(duration)
        self.status_codes[status_code] += 1
        if status_code >= 500:
            self.errors_total += 1

    # ------------------------------------------------------------------
    # Histogram helpers
    # ------------------------------------------------------------------

    _BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def _histogram_lines(self) -> list[str]:
        """Render duration histogram in Prometheus text format."""
        lines: list[str] = []
        lines.append(
            "# HELP gateway_request_duration_seconds Request duration histogram"
        )
        lines.append(
            "# TYPE gateway_request_duration_seconds histogram"
        )

        durations = self.request_durations
        total_count = len(durations)
        total_sum = sum(durations)

        for le in self._BUCKETS:
            bucket_count = sum(1 for d in durations if d <= le)
            lines.append(
                f'gateway_request_duration_seconds_bucket{{le="{le}"}} {bucket_count}'
            )
        lines.append(
            f'gateway_request_duration_seconds_bucket{{le="+Inf"}} {total_count}'
        )
        lines.append(
            f"gateway_request_duration_seconds_sum {total_sum:.6f}"
        )
        lines.append(
            f"gateway_request_duration_seconds_count {total_count}"
        )
        return lines

    # ------------------------------------------------------------------
    # Prometheus text format rendering
    # ------------------------------------------------------------------

    def to_prometheus(self, active_connections: int = 0) -> str:
        """Render all metrics as a Prometheus text-format payload.

        Args:
            active_connections: Current WebSocket connection count from the
                :class:`~gateway.ws.manager.ConnectionManager`.

        Returns:
            UTF-8 string in Prometheus text exposition format (ending with
            a trailing newline).
        """
        lines: list[str] = []

        # --- requests_total ---
        lines.append("# HELP gateway_requests_total Total requests")
        lines.append("# TYPE gateway_requests_total counter")
        lines.append(f"gateway_requests_total {self.requests_total}")

        # --- errors_total ---
        lines.append("# HELP gateway_errors_total Total errors")
        lines.append("# TYPE gateway_errors_total counter")
        lines.append(f"gateway_errors_total {self.errors_total}")

        # --- active_connections ---
        lines.append(
            "# HELP gateway_active_connections Active WebSocket connections"
        )
        lines.append("# TYPE gateway_active_connections gauge")
        lines.append(f"gateway_active_connections {active_connections}")

        # --- per-status-code counters ---
        lines.append(
            "# HELP gateway_http_status HTTP response counts by status code"
        )
        lines.append("# TYPE gateway_http_status counter")
        for code, count in sorted(self.status_codes.items()):
            lines.append(f'gateway_http_status{{code="{code}"}} {count}')

        # --- duration histogram ---
        lines.extend(self._histogram_lines())

        return "\n".join(lines) + "\n"


# Module-level singleton shared across the gateway application.
gateway_metrics = GatewayMetrics()
