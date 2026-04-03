"""E2E harness tests for POST /api/v1/query (NL -> Cypher pipeline).

Uses MockNeo4jSession -- no real Neo4j instance required.
The TextToCypherPipeline.process() is patched to return controlled outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from tests.helpers.mock_neo4j import (
    MockNeo4jSession,
    MockNeo4jResult,
    make_neo4j_node,
)
from tests.e2e.conftest import _reset

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ---------------------------------------------------------------------------
# Helpers: lightweight stand-ins for pipeline dataclasses
# ---------------------------------------------------------------------------


def _make_pipeline_output(
    input_text: str,
    success: bool = True,
    query: str | None = None,
    parameters: dict[str, Any] | None = None,
    error: str | None = None,
    confidence: float = 0.85,
) -> MagicMock:
    """Build a mock PipelineOutput with the fields that the query route reads."""
    output = MagicMock()
    output.input_text = input_text
    output.success = success
    output.error = error

    parse_result = MagicMock()
    parse_result.confidence = confidence
    parse_result.parse_details = {"entities": ["Vessel"]}
    output.parse_result = parse_result

    if query is not None:
        gen = MagicMock()
        gen.query = query
        gen.parameters = parameters or {}
        output.generated_query = gen
    else:
        output.generated_query = None

    return output


# ===========================================================================
# TestNLQueryHarness
# ===========================================================================


class TestNLQueryHarness:
    """Tests for POST /api/v1/query."""

    async def test_query_execute_true(self, harness: Any) -> None:
        """Pipeline generates Cypher, execute=True runs it and returns rows."""
        client, session, _app = harness

        mock_output = _make_pipeline_output(
            input_text="부산항 근처 컨테이너선",
            success=True,
            query="MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v.name AS name",
            parameters={"port": "부산항"},
        )

        # Mock session returns one row when Cypher is executed
        _reset(session, [MockNeo4jResult([{"name": "한진부산호"}])])

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = mock_output
            resp = await client.post(
                "/api/v1/query",
                json={"text": "부산항 근처 컨테이너선", "execute": True, "limit": 50},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["input_text"] == "부산항 근처 컨테이너선"
        assert body["generated_cypher"] is not None
        assert body["results"] is not None
        assert len(body["results"]) >= 1
        assert body["confidence"] > 0

    async def test_query_execute_false(self, harness: Any) -> None:
        """Pipeline generates Cypher, execute=False skips Neo4j call."""
        client, session, _app = harness

        mock_output = _make_pipeline_output(
            input_text="선박 목록",
            success=True,
            query="MATCH (v:Vessel) RETURN v",
            parameters={},
        )

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = mock_output
            resp = await client.post(
                "/api/v1/query",
                json={"text": "선박 목록", "execute": False},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["generated_cypher"] is not None
        # No results because execute=False
        assert body["results"] is None

    async def test_query_empty_text(self, harness: Any) -> None:
        """Empty text triggers Pydantic validation error (422)."""
        client, session, _app = harness

        resp = await client.post(
            "/api/v1/query",
            json={"text": "", "execute": True},
        )
        assert resp.status_code == 422

    async def test_query_pipeline_error(self, harness: Any) -> None:
        """Pipeline failure returns error in response body."""
        client, session, _app = harness

        mock_output = _make_pipeline_output(
            input_text="잘못된 쿼리",
            success=False,
            query=None,
            error="Parse error: unrecognized entity",
            confidence=0.0,
        )

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = mock_output
            resp = await client.post(
                "/api/v1/query",
                json={"text": "잘못된 쿼리", "execute": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is not None
        assert "Parse error" in body["error"]
        assert body["generated_cypher"] is None

    async def test_query_korean_text(self, harness: Any) -> None:
        """Korean input text is properly handled end-to-end."""
        client, session, _app = harness

        mock_output = _make_pipeline_output(
            input_text="대한해협 통과하는 유조선",
            success=True,
            query="MATCH (v:Tanker)-[:PASSES_THROUGH]->(s:SeaArea {name: $area}) RETURN v",
            parameters={"area": "대한해협"},
            confidence=0.92,
        )

        _reset(session, [MockNeo4jResult([{"v": "탱커1호"}])])

        with patch("kg.api.routes.query._pipeline") as mock_pipeline:
            mock_pipeline.process.return_value = mock_output
            resp = await client.post(
                "/api/v1/query",
                json={"text": "대한해협 통과하는 유조선", "execute": True, "limit": 10},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["input_text"] == "대한해협 통과하는 유조선"
        assert body["confidence"] == pytest.approx(0.92, abs=0.01)
        assert body["generated_cypher"] is not None
        assert body["results"] is not None
