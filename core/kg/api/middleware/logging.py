"""Structured JSON logging for the Maritime KG API.

Provides a JSON formatter that outputs structured log records suitable
for log aggregation systems (ELK, Loki, CloudWatch).

Usage::

    from kg.api.middleware.logging import setup_json_logging
    setup_json_logging(level="INFO")
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Include extra fields passed via logging.info("msg", extra={...})
        for key in ("request_id", "trace_id", "span_id", "parent_span_id", "method", "path", "status_code", "duration_ms", "client_ip"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_json_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON formatter.

    Args:
        level: Log level string (e.g. "INFO", "DEBUG").
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
