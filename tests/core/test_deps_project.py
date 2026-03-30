"""Tests for get_project_context FastAPI dependency.

Verifies that the dependency extracts KGProjectContext from the
X-KG-Project request header correctly, including fallback, validation,
and error handling. No real server or Neo4j needed.
"""
from __future__ import annotations

import pytest
from starlette.requests import Request

from kg.api.deps import get_project_context
from kg.project import DEFAULT_PROJECT


def _make_request(headers: dict[str, str] | None = None) -> Request:
    """Create a minimal Starlette Request with given headers."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
    }
    return Request(scope)


# ---------------------------------------------------------------------------
# get_project_context
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetProjectContext:
    """Tests for get_project_context()."""

    def test_no_header_returns_default(self) -> None:
        req = _make_request()
        ctx = get_project_context(req)
        assert ctx.name == DEFAULT_PROJECT

    def test_valid_header(self) -> None:
        req = _make_request({"x-kg-project": "DevKG"})
        ctx = get_project_context(req)
        assert ctx.name == "DevKG"
        assert ctx.label == "KG_DevKG"

    def test_empty_header_returns_default(self) -> None:
        req = _make_request({"x-kg-project": ""})
        ctx = get_project_context(req)
        assert ctx.name == DEFAULT_PROJECT

    def test_invalid_header_raises_400(self) -> None:
        from fastapi import HTTPException

        req = _make_request({"x-kg-project": "invalid-name"})
        with pytest.raises(HTTPException) as exc_info:
            get_project_context(req)
        assert exc_info.value.status_code == 400

    def test_invalid_starts_with_number_raises_400(self) -> None:
        from fastapi import HTTPException

        req = _make_request({"x-kg-project": "123abc"})
        with pytest.raises(HTTPException) as exc_info:
            get_project_context(req)
        assert exc_info.value.status_code == 400

    def test_case_sensitive(self) -> None:
        req = _make_request({"x-kg-project": "devKG"})
        ctx = get_project_context(req)
        assert ctx.name == "devKG"

    def test_whitespace_stripped(self) -> None:
        req = _make_request({"x-kg-project": "  TestProject  "})
        ctx = get_project_context(req)
        assert ctx.name == "TestProject"

    def test_underscore_name(self) -> None:
        req = _make_request({"x-kg-project": "my_project_2026"})
        ctx = get_project_context(req)
        assert ctx.name == "my_project_2026"
        assert ctx.label == "KG_my_project_2026"
