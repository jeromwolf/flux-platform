"""Unit tests for Cypher timeout and result-limit guards.

Covers:
- _ensure_result_limit() helper: LIMIT injection / no-duplicate logic
- CypherRequest model: timeout_ms / limit field validation
- execute_cypher endpoint: timeout forwarded to session.run(), LIMIT auto-appended
- timeout_ms exceeding server ceiling is clamped to _MAX_CYPHER_TIMEOUT_MS
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kg.api.routes.cypher import (
    _DEFAULT_RESULT_LIMIT,
    _MAX_CYPHER_TIMEOUT_MS,
    _ensure_result_limit,
)
from kg.config import AppConfig, Neo4jConfig, reset
from tests.helpers.mock_neo4j import MockNeo4jResult, MockNeo4jSession, make_test_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config():
    reset()
    yield
    reset()


@pytest.fixture
def dev_config() -> AppConfig:
    return AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))


# ---------------------------------------------------------------------------
# TestEnsureResultLimit
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnsureResultLimit:
    """Tests for _ensure_result_limit() pure helper."""

    def test_appends_limit_when_absent(self):
        """LIMIT is appended when the query has RETURN but no LIMIT clause."""
        q = "MATCH (n:Vessel) RETURN n"
        result = _ensure_result_limit(q, limit=100)
        assert "LIMIT 100" in result

    def test_does_not_duplicate_when_limit_present(self):
        """LIMIT is not appended again when already present."""
        q = "MATCH (n:Vessel) RETURN n LIMIT 10"
        result = _ensure_result_limit(q, limit=100)
        assert result.upper().count("LIMIT") == 1

    def test_strips_trailing_semicolon(self):
        """Trailing semicolon is removed before appending LIMIT."""
        q = "MATCH (n) RETURN n;"
        result = _ensure_result_limit(q, limit=50)
        assert not result.endswith(";")
        assert "LIMIT 50" in result

    def test_ignores_limit_in_comment(self):
        """LIMIT in a comment line should not suppress the guard."""
        q = "// LIMIT 99\nMATCH (n:Vessel) RETURN n"
        result = _ensure_result_limit(q, limit=200)
        assert "LIMIT 200" in result

    def test_case_insensitive_limit_detection(self):
        """Lowercase 'limit' is recognised as an existing LIMIT clause."""
        q = "MATCH (n) RETURN n limit 5"
        result = _ensure_result_limit(q, limit=500)
        assert result.upper().count("LIMIT") == 1

    def test_default_limit_value(self):
        """When limit is omitted, _DEFAULT_RESULT_LIMIT is used."""
        q = "MATCH (n) RETURN n"
        result = _ensure_result_limit(q)
        assert f"LIMIT {_DEFAULT_RESULT_LIMIT}" in result

    def test_write_query_create_no_limit_appended(self):
        """CREATE query without RETURN must not have LIMIT appended."""
        q = "CREATE (n:Vessel {name: 'MV Test'})"
        result = _ensure_result_limit(q, limit=100)
        assert "LIMIT" not in result.upper()

    def test_write_query_merge_no_limit_appended(self):
        """MERGE query without RETURN must not have LIMIT appended."""
        q = "MERGE (n:Port {code: 'BUSAP'}) SET n.updated = true"
        result = _ensure_result_limit(q, limit=100)
        assert "LIMIT" not in result.upper()

    def test_query_ending_with_with_no_limit_appended(self):
        """Query ending with WITH (no RETURN) must not have LIMIT appended."""
        q = "MATCH (n:Vessel) WITH n.name AS name"
        result = _ensure_result_limit(q, limit=100)
        assert "LIMIT" not in result.upper()

    def test_write_query_with_return_gets_limit(self):
        """MERGE ... RETURN query (write + read) should still get LIMIT."""
        q = "MERGE (n:Vessel {name: 'MV Test'}) RETURN n"
        result = _ensure_result_limit(q, limit=100)
        assert "LIMIT 100" in result


# ---------------------------------------------------------------------------
# TestCypherRequestModel
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCypherRequestModel:
    """Pydantic validation tests for CypherRequest."""

    def test_defaults_are_set(self):
        """Default timeout_ms and limit are applied when not supplied."""
        from kg.api.models import CypherRequest

        req = CypherRequest(cypher="MATCH (n) RETURN n")
        assert req.timeout_ms == 30_000
        assert req.limit == 10_000

    def test_timeout_ms_below_minimum_rejected(self):
        """timeout_ms < 1000 is rejected by Pydantic."""
        from pydantic import ValidationError

        from kg.api.models import CypherRequest

        with pytest.raises(ValidationError):
            CypherRequest(cypher="MATCH (n) RETURN n", timeout_ms=500)

    def test_timeout_ms_above_maximum_rejected(self):
        """timeout_ms > 120000 is rejected by Pydantic."""
        from pydantic import ValidationError

        from kg.api.models import CypherRequest

        with pytest.raises(ValidationError):
            CypherRequest(cypher="MATCH (n) RETURN n", timeout_ms=200_000)

    def test_limit_below_minimum_rejected(self):
        """limit < 1 is rejected by Pydantic."""
        from pydantic import ValidationError

        from kg.api.models import CypherRequest

        with pytest.raises(ValidationError):
            CypherRequest(cypher="MATCH (n) RETURN n", limit=0)

    def test_limit_above_maximum_rejected(self):
        """limit > 50000 is rejected by Pydantic."""
        from pydantic import ValidationError

        from kg.api.models import CypherRequest

        with pytest.raises(ValidationError):
            CypherRequest(cypher="MATCH (n) RETURN n", limit=100_000)

    def test_valid_custom_timeout_and_limit(self):
        """Custom timeout_ms and limit within range are accepted."""
        from kg.api.models import CypherRequest

        req = CypherRequest(cypher="MATCH (n) RETURN n", timeout_ms=5_000, limit=500)
        assert req.timeout_ms == 5_000
        assert req.limit == 500


# ---------------------------------------------------------------------------
# TestExecuteCypherTimeout
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExecuteCypherTimeout:
    """Tests that execute_cypher forwards timeout to session.run()."""

    def test_timeout_forwarded_to_session_run(self, dev_config: AppConfig):
        """session.run() is called with timeout= equal to timeout_ms/1000."""
        captured: dict[str, Any] = {}

        class CapturingSession:
            async def run(self, cypher: str, params: dict | None = None, **kwargs: Any) -> MockNeo4jResult:
                captured.update(kwargs)
                return MockNeo4jResult([])

            async def close(self) -> None:
                pass

        session = CapturingSession()

        from kg.api.app import create_app
        from kg.api.deps import get_async_neo4j_session

        with patch("kg.api.app.get_config", return_value=dev_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=dev_config)

        async def _override():
            yield session

        app.dependency_overrides[get_async_neo4j_session] = _override

        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/api/v1/cypher/execute",
            json={
                "cypher": "MATCH (n:Vessel) RETURN n.name AS name LIMIT 1",
                "timeout_ms": 15_000,
            },
        )

        assert resp.status_code == 200
        assert "timeout" in captured
        assert captured["timeout"] == pytest.approx(15.0, abs=0.001)

    def test_timeout_clamped_to_server_ceiling(self, dev_config: AppConfig):
        """Caller-supplied timeout_ms is clamped to _MAX_CYPHER_TIMEOUT_MS."""
        captured: dict[str, Any] = {}

        class CapturingSession:
            async def run(self, cypher: str, params: dict | None = None, **kwargs: Any) -> MockNeo4jResult:
                captured.update(kwargs)
                return MockNeo4jResult([])

            async def close(self) -> None:
                pass

        session = CapturingSession()

        from kg.api.app import create_app
        from kg.api.deps import get_async_neo4j_session

        with patch("kg.api.app.get_config", return_value=dev_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=dev_config)

        async def _override():
            yield session

        app.dependency_overrides[get_async_neo4j_session] = _override

        from fastapi.testclient import TestClient

        client = TestClient(app)
        # Send maximum allowed by Pydantic (120s)
        resp = client.post(
            "/api/v1/cypher/execute",
            json={
                "cypher": "MATCH (n:Vessel) RETURN n.name LIMIT 1",
                "timeout_ms": 120_000,
            },
        )

        assert resp.status_code == 200
        max_timeout_s = _MAX_CYPHER_TIMEOUT_MS / 1000.0
        assert captured["timeout"] == pytest.approx(max_timeout_s, abs=0.001)

    def test_limit_auto_appended_to_unlimited_query(self, dev_config: AppConfig):
        """Queries without LIMIT are automatically bounded by the request limit."""
        captured_cypher: list[str] = []

        class CapturingSession:
            async def run(self, cypher: str, params: dict | None = None, **kwargs: Any) -> MockNeo4jResult:
                captured_cypher.append(cypher)
                return MockNeo4jResult([])

            async def close(self) -> None:
                pass

        session = CapturingSession()

        from kg.api.app import create_app
        from kg.api.deps import get_async_neo4j_session

        with patch("kg.api.app.get_config", return_value=dev_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=dev_config)

        async def _override():
            yield session

        app.dependency_overrides[get_async_neo4j_session] = _override

        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/api/v1/cypher/execute",
            json={
                "cypher": "MATCH (n:Vessel) RETURN n.name",
                "limit": 777,
            },
        )

        assert resp.status_code == 200
        assert len(captured_cypher) == 1
        assert "LIMIT 777" in captured_cypher[0]

    def test_existing_limit_not_duplicated(self, dev_config: AppConfig):
        """A query that already contains LIMIT is not modified."""
        captured_cypher: list[str] = []

        class CapturingSession:
            async def run(self, cypher: str, params: dict | None = None, **kwargs: Any) -> MockNeo4jResult:
                captured_cypher.append(cypher)
                return MockNeo4jResult([])

            async def close(self) -> None:
                pass

        session = CapturingSession()

        from kg.api.app import create_app
        from kg.api.deps import get_async_neo4j_session

        with patch("kg.api.app.get_config", return_value=dev_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=dev_config)

        async def _override():
            yield session

        app.dependency_overrides[get_async_neo4j_session] = _override

        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/api/v1/cypher/execute",
            json={
                "cypher": "MATCH (n:Vessel) RETURN n.name LIMIT 5",
                "limit": 1000,
            },
        )

        assert resp.status_code == 200
        assert len(captured_cypher) == 1
        assert captured_cypher[0].upper().count("LIMIT") == 1
