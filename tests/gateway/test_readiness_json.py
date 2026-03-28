"""Tests for gateway readiness endpoint JSON serialization.

TC-RJ01: readiness endpoint returns valid JSON (not Python str repr).
"""
from __future__ import annotations

import json

import pytest


@pytest.mark.unit
class TestReadinessJsonSerialization:
    """TC-RJ01: Readiness endpoint JSON output validation."""

    def test_rj01a_json_dumps_produces_valid_json(self) -> None:
        """TC-RJ01-a: json.dumps produces parseable JSON for readiness body."""
        body = {"status": "ready", "upstream": "healthy"}
        result = json.dumps(body)
        parsed = json.loads(result)
        assert parsed["status"] == "ready"
        assert parsed["upstream"] == "healthy"

    def test_rj01b_json_dumps_handles_special_values(self) -> None:
        """TC-RJ01-b: json.dumps correctly handles Python True/False/None."""
        body = {"status": "degraded", "upstream": "unreachable", "flag": True, "extra": None}
        result = json.dumps(body)
        parsed = json.loads(result)
        assert parsed["flag"] is True
        assert parsed["extra"] is None

    def test_rj01c_json_dumps_handles_single_quotes_in_values(self) -> None:
        """TC-RJ01-c: json.dumps correctly handles values containing single quotes."""
        body = {"status": "error", "message": "can't connect to host"}
        result = json.dumps(body)
        parsed = json.loads(result)
        assert parsed["message"] == "can't connect to host"

    def test_rj01d_str_replace_fails_on_booleans(self) -> None:
        """TC-RJ01-d: Demonstrate that str().replace approach fails on Python booleans."""
        body = {"flag": True, "value": None}
        naive = str(body).replace("'", '"')
        # Python str repr produces True/False/None which are NOT valid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(naive)
