"""Unit tests for the POST /api/query endpoint.

All tests are marked with ``@pytest.mark.unit`` and mock Neo4j so no
database connection is required.
"""

from __future__ import annotations

from typing import Any
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


def _make_async_mock_result(records: list | None = None, single_value: Any = None) -> MagicMock:
    """Create a mock async result that supports ``async for`` and ``await .single()``."""
    mock_result = MagicMock()
    _records = records if records is not None else []

    async def _aiter_impl():
        for r in _records:
            yield r

    mock_result.__aiter__ = lambda self: _aiter_impl()
    mock_result.single = AsyncMock(return_value=single_value)
    return mock_result


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


# ---------------------------------------------------------------------------
# Valid queries
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryEndpointValid:
    """Test POST /api/query with valid Korean text."""

    def test_query_with_korean_text_returns_cypher(self) -> None:
        """Valid Korean text returns generated Cypher in the response."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post("/api/query", json={"text": "부산항 선박"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["input_text"] == "부산항 선박"
        assert data["generated_cypher"] is not None
        assert "MATCH" in data["generated_cypher"]
        assert data["confidence"] > 0
        assert isinstance(data["parse_details"], dict)

    def test_query_returns_execution_results(self) -> None:
        """When execute=True, results from Neo4j are included."""
        mock_session = _make_mock_session()

        # Mock a result record
        mock_record = {"name": "Test Vessel", "type": "ContainerShip"}
        mock_result = _make_async_mock_result(records=[mock_record])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.post(
            "/api/query",
            json={"text": "선박 목록", "execute": True, "limit": 10},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] is not None
        assert isinstance(data["results"], list)


# ---------------------------------------------------------------------------
# execute=False (parse-only, no Neo4j)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryEndpointNoExecute:
    """Test POST /api/query with execute=False (parse-only)."""

    def test_parse_only_does_not_call_neo4j(self) -> None:
        """With execute=False, session.run should not be called."""
        mock_session = _make_mock_session()

        client, _ = _make_client(mock_session)
        resp = client.post(
            "/api/query",
            json={"text": "항구 정보", "execute": False},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["generated_cypher"] is not None
        assert data["results"] is None
        # Verify session.run was NOT called
        mock_session.run.assert_not_called()

    def test_parse_only_returns_parse_details(self) -> None:
        """Parse-only mode still returns confidence and parse_details."""
        client, _ = _make_client()
        resp = client.post(
            "/api/query",
            json={"text": "컨테이너선 현황", "execute": False},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence"] > 0
        assert "detected_intent" in data["parse_details"]


# ---------------------------------------------------------------------------
# Empty / invalid text
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryEndpointInvalid:
    """Test POST /api/query with empty or invalid input."""

    def test_empty_text_returns_422(self) -> None:
        """Empty text field triggers Pydantic validation error (422)."""
        client, _ = _make_client()
        resp = client.post("/api/query", json={"text": ""})

        # FastAPI min_length=1 validation returns 422
        assert resp.status_code == 422
