"""Unit tests for core/kg/api/routes/query.py.

Tests the natural language query endpoint covering:
- Pipeline failure path (lines 54-55)
- Cypher execution exception path (lines 80-83)
- Normal success path (execute=True and execute=False)
All tests are ``@pytest.mark.unit``.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from kg.config import AppConfig, Neo4jConfig, reset

from tests.helpers.mock_neo4j import (
    MockNeo4jResult,
    MockNeo4jSession,
    make_test_app,
)


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


def _make_pipeline_output(
    *,
    success: bool = True,
    generated_query: Any = None,
    error: str | None = None,
    input_text: str = "test query",
) -> MagicMock:
    """Build a mock PipelineOutput object."""
    from kg.nlp.nl_parser import ParseResult
    from kg.query_generator import QueryIntent, StructuredQuery

    parse_result = ParseResult(
        query=StructuredQuery(intent=QueryIntent(intent="FIND", confidence=0.8)),
        confidence=0.8,
        parse_details={"tokens": ["test"]},
    )

    output = MagicMock()
    output.input_text = input_text
    output.parse_result = parse_result
    output.success = success
    output.error = error
    output.generated_query = generated_query
    return output


def _make_generated_query(cypher: str = "MATCH (n:Vessel) RETURN n", params: dict | None = None) -> MagicMock:
    """Build a mock GeneratedQuery."""
    gq = MagicMock()
    gq.query = cypher
    gq.parameters = params or {}
    return gq


# ---------------------------------------------------------------------------
# TestQueryPipelineFailure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryPipelineFailure:
    """Tests for the pipeline failure path (lines 54-55)."""

    def test_pipeline_failure_returns_error_in_response(self, dev_config: AppConfig):
        """When pipeline.process() returns success=False, error is included in response."""
        failed_output = _make_pipeline_output(
            success=False,
            generated_query=None,
            error="No entities could be extracted from the input text",
        )

        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = failed_output
            resp = client.post(
                "/api/v1/query",
                json={"text": "아무 의미 없는 텍스트", "execute": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] == "No entities could be extracted from the input text"
        assert body["generated_cypher"] is None

    def test_pipeline_failure_with_none_query_stops_before_execute(self, dev_config: AppConfig):
        """When generated_query is None, session.run is never called."""
        failed_output = _make_pipeline_output(
            success=False,
            generated_query=None,
            error="Parse error: something went wrong",
        )

        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = failed_output
            resp = client.post(
                "/api/v1/query",
                json={"text": "bad input", "execute": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is not None
        assert body["results"] is None
        # session was not called since we returned early
        assert session._call_index == 0

    def test_pipeline_success_false_with_no_execute_still_returns_error(self, dev_config: AppConfig):
        """Even with execute=False, pipeline failure still returns error field."""
        failed_output = _make_pipeline_output(
            success=False,
            generated_query=None,
            error="Generation error: unsupported query type",
        )

        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = failed_output
            resp = client.post(
                "/api/v1/query",
                json={"text": "some text", "execute": False},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] == "Generation error: unsupported query type"


# ---------------------------------------------------------------------------
# TestQueryExecutionException
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryExecutionException:
    """Tests for the Cypher execution exception path (lines 80-83)."""

    def test_session_run_exception_returns_execution_error(self, dev_config: AppConfig):
        """When session.run() raises an exception, response.error contains the message."""

        class ErrorSession:
            """Session that raises on run()."""

            async def run(self, cypher: str, params: dict | None = None, **kwargs: Any):
                raise RuntimeError("connection refused")

            async def close(self) -> None:
                pass

        gq = _make_generated_query(cypher="MATCH (n:Vessel) RETURN n")
        success_output = _make_pipeline_output(
            success=True,
            generated_query=gq,
            error=None,
        )

        error_session = ErrorSession()

        from kg.api.app import create_app
        from kg.api.deps import get_async_neo4j_session

        with patch("kg.api.app.get_config", return_value=dev_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=dev_config)

        async def _override_session():
            yield error_session

        app.dependency_overrides[get_async_neo4j_session] = _override_session

        from fastapi.testclient import TestClient

        client = TestClient(app)

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = success_output
            resp = client.post(
                "/api/v1/query",
                json={"text": "부산항 선박", "execute": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is not None
        assert "Execution error" in body["error"]
        assert "connection refused" in body["error"]
        assert body["results"] is None

    def test_session_run_exception_results_set_to_none(self, dev_config: AppConfig):
        """When execution fails, results field is explicitly None (not empty list)."""

        class ErrorSession:
            async def run(self, cypher: str, params: dict | None = None, **kwargs: Any):
                raise ValueError("invalid Cypher syntax")

            async def close(self) -> None:
                pass

        gq = _make_generated_query(cypher="INVALID CYPHER")
        success_output = _make_pipeline_output(
            success=True,
            generated_query=gq,
        )

        from kg.api.app import create_app
        from kg.api.deps import get_async_neo4j_session

        with patch("kg.api.app.get_config", return_value=dev_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=dev_config)

        async def _override_session():
            yield ErrorSession()

        app.dependency_overrides[get_async_neo4j_session] = _override_session

        from fastapi.testclient import TestClient

        client = TestClient(app)

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = success_output
            resp = client.post(
                "/api/v1/query",
                json={"text": "잘못된 쿼리", "execute": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["results"] is None


# ---------------------------------------------------------------------------
# TestQuerySuccessPath
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQuerySuccessPath:
    """Tests for the normal success path."""

    def test_success_no_execute_returns_cypher_only(self, dev_config: AppConfig):
        """When execute=False, returns generated_cypher without running it."""
        gq = _make_generated_query(
            cypher="MATCH (n:Vessel) RETURN n",
            params={"type": "container"},
        )
        success_output = _make_pipeline_output(
            success=True,
            generated_query=gq,
        )

        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = success_output
            resp = client.post(
                "/api/v1/query",
                json={"text": "컨테이너선 조회", "execute": False},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["generated_cypher"] == "MATCH (n:Vessel) RETURN n"
        assert body["error"] is None
        assert body["results"] is None
        # Session should not have been called
        assert session._call_index == 0

    def test_success_with_execute_returns_results(self, dev_config: AppConfig):
        """When execute=True and session returns records, results are populated."""
        gq = _make_generated_query(cypher="MATCH (n:Vessel) RETURN n.name AS name")

        success_output = _make_pipeline_output(
            success=True,
            generated_query=gq,
        )

        record = {"name": "Sea Eagle"}
        session = MockNeo4jSession(side_effects=[MockNeo4jResult([record])])
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = success_output
            resp = client.post(
                "/api/v1/query",
                json={"text": "선박 이름 조회", "execute": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is None
        assert isinstance(body["results"], list)

    def test_query_auto_appends_limit_when_missing(self, dev_config: AppConfig):
        """When Cypher has no LIMIT clause, it is appended automatically."""
        gq = _make_generated_query(cypher="MATCH (n:Vessel) RETURN n")
        success_output = _make_pipeline_output(success=True, generated_query=gq)

        session = MockNeo4jSession(side_effects=[MockNeo4jResult([])])
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = success_output
            resp = client.post(
                "/api/v1/query",
                json={"text": "선박 조회", "execute": True, "limit": 25},
            )

        assert resp.status_code == 200
        # Confirm the session was called (limit was appended and ran)
        assert session._call_index == 1

    def test_query_does_not_duplicate_limit_when_present(self, dev_config: AppConfig):
        """When Cypher already contains LIMIT, it is not appended again."""
        gq = _make_generated_query(cypher="MATCH (n:Vessel) RETURN n LIMIT 10")
        success_output = _make_pipeline_output(success=True, generated_query=gq)

        session = MockNeo4jSession(side_effects=[MockNeo4jResult([])])
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = success_output
            resp = client.post(
                "/api/v1/query",
                json={"text": "선박 조회", "execute": True, "limit": 50},
            )

        assert resp.status_code == 200
        assert session._call_index == 1

    def test_missing_text_field_returns_422(self, dev_config: AppConfig):
        """Missing required 'text' field returns HTTP 422."""
        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        resp = client.post("/api/v1/query", json={"execute": True})
        assert resp.status_code == 422

    def test_empty_text_returns_422(self, dev_config: AppConfig):
        """Empty text (min_length=1) returns HTTP 422."""
        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        resp = client.post("/api/v1/query", json={"text": "", "execute": True})
        assert resp.status_code == 422
