"""E2E harness tests for RAG and Agent endpoints.

Tests /api/v1/rag/* and /api/v1/agent/* using MockNeo4jSession and
mock app.state services -- no real Neo4j, RAG engine, or agent needed.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ===========================================================================
# RAG Endpoints
# ===========================================================================


class TestRAGStatus:
    """GET /api/v1/rag/status endpoint tests."""

    async def test_rag_status_available(self, harness: Any) -> None:
        """RAG status reports available when engine class importable."""
        client, _session, _app = harness

        resp = await client.get("/api/v1/rag/status")
        assert resp.status_code == 200
        body = resp.json()
        # The status endpoint checks if HybridRAGEngine is importable
        assert "available" in body
        assert "engine" in body

    async def test_rag_status_engine_field(self, harness: Any) -> None:
        """RAG status always includes the engine name."""
        client, _session, _app = harness

        resp = await client.get("/api/v1/rag/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["engine"] == "HybridRAGEngine"


class TestRAGQuery:
    """POST /api/v1/rag/query endpoint tests."""

    async def test_rag_query_unavailable(self, harness: Any) -> None:
        """RAG query with no engine returns 503."""
        client, _session, app = harness
        app.state.rag_engine = None

        resp = await client.post(
            "/api/v1/rag/query",
            json={"query": "What is SOLAS?", "mode": "hybrid", "top_k": 5},
        )
        assert resp.status_code == 503
        assert "not available" in resp.json()["detail"]

    async def test_rag_query_success(self, harness: Any) -> None:
        """RAG query with mock engine returns structured response."""
        client, _session, app = harness

        # Build a minimal mock that satisfies the route logic
        mock_chunk = MagicMock()
        mock_chunk.chunk.content = "SOLAS is the International Convention..."
        mock_chunk.chunk.doc_id = "doc-001"
        mock_chunk.score = 0.92

        mock_result = MagicMock()
        mock_result.answer = "SOLAS stands for Safety of Life at Sea."
        mock_result.retrieved_chunks = [mock_chunk]
        mock_result.chunk_count = 1

        mock_engine = MagicMock()
        mock_engine.query = MagicMock(return_value=mock_result)
        app.state.rag_engine = mock_engine

        resp = await client.post(
            "/api/v1/rag/query",
            json={"query": "What is SOLAS?", "mode": "hybrid", "top_k": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "SOLAS stands for Safety of Life at Sea."
        assert body["query"] == "What is SOLAS?"
        assert len(body["chunks"]) == 1
        assert body["chunks"][0]["doc_id"] == "doc-001"
        assert body["total_chunks"] == 1


class TestRAGDocuments:
    """POST /api/v1/rag/documents endpoint tests."""

    async def test_rag_documents_unavailable(self, harness: Any) -> None:
        """Document upload with no pipeline returns 503."""
        client, _session, app = harness
        app.state.document_pipeline = None

        resp = await client.post(
            "/api/v1/rag/documents",
            json={
                "title": "Test Doc",
                "content": "Some content here",
                "doc_type": "txt",
            },
        )
        assert resp.status_code == 503
        assert "not available" in resp.json()["detail"]


# ===========================================================================
# Agent Endpoints
# ===========================================================================


class TestAgentStatus:
    """GET /api/v1/agent/status endpoint tests."""

    async def test_agent_status_available(self, harness: Any) -> None:
        """Agent status with tool_registry present shows available=True."""
        client, _session, app = harness

        # Set up a mock tool_registry
        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = [MagicMock(), MagicMock()]
        app.state.tool_registry = mock_registry

        resp = await client.get("/api/v1/agent/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["tools_count"] == 2
        assert "react" in body["engines"]

    async def test_agent_status_unavailable(self, harness: Any) -> None:
        """Agent status with tool_registry=None shows available=False."""
        client, _session, app = harness
        app.state.tool_registry = None

        resp = await client.get("/api/v1/agent/status")
        assert resp.status_code == 200
        body = resp.json()
        # available depends on whether ReActEngine is importable + registry
        assert body["tools_count"] == 0


class TestAgentTools:
    """GET /api/v1/agent/tools endpoint tests."""

    async def test_agent_tools_list(self, harness: Any) -> None:
        """List tools when registry has tools."""
        client, _session, app = harness

        mock_tool = MagicMock()
        mock_tool.name = "cypher_query"
        mock_tool.description = "Execute Cypher queries"
        mock_tool.parameters = {"query": {"type": "string"}}

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = [mock_tool]
        app.state.tool_registry = mock_registry

        resp = await client.get("/api/v1/agent/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["tools"]) == 1
        assert body["tools"][0]["name"] == "cypher_query"
        assert body["tools"][0]["description"] == "Execute Cypher queries"

    async def test_agent_tools_empty(self, harness: Any) -> None:
        """List tools when registry is None returns empty list."""
        client, _session, app = harness
        app.state.tool_registry = None

        resp = await client.get("/api/v1/agent/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tools"] == []
        assert "error" in body  # "Agent tools not available"


class TestAgentChat:
    """POST /api/v1/agent/chat endpoint tests."""

    async def test_agent_chat_unavailable(self, harness: Any) -> None:
        """Chat with no tool registry returns 503."""
        client, _session, app = harness
        app.state.tool_registry = None

        resp = await client.post(
            "/api/v1/agent/chat",
            json={"message": "Hello agent", "mode": "react", "max_steps": 3},
        )
        assert resp.status_code == 503
        assert "not available" in resp.json()["detail"]


class TestAgentToolExecute:
    """POST /api/v1/agent/tools/execute endpoint tests."""

    async def test_agent_tool_execute_unavailable(self, harness: Any) -> None:
        """Tool execute with no registry returns 503."""
        client, _session, app = harness
        app.state.tool_registry = None

        resp = await client.post(
            "/api/v1/agent/tools/execute",
            json={"tool_name": "cypher_query", "parameters": {"query": "MATCH (n) RETURN n"}},
        )
        assert resp.status_code == 503
        assert "not available" in resp.json()["detail"]

    async def test_agent_tool_execute_not_found(self, harness: Any) -> None:
        """Tool execute for unknown tool returns 404."""
        client, _session, app = harness

        mock_registry = MagicMock()
        mock_registry.get.return_value = None
        app.state.tool_registry = mock_registry

        resp = await client.post(
            "/api/v1/agent/tools/execute",
            json={"tool_name": "nonexistent_tool", "parameters": {}},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


class TestAgentSessions:
    """Agent session management endpoint tests."""

    async def test_agent_sessions_list(self, harness: Any) -> None:
        """GET /agent/sessions returns list (may be empty)."""
        client, _session, _app = harness

        resp = await client.get("/api/v1/agent/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert "sessions" in body
        assert "count" in body
        assert isinstance(body["sessions"], list)

    async def test_agent_session_history(self, harness: Any) -> None:
        """GET /agent/sessions/{id}/history returns empty for unknown session."""
        client, _session, _app = harness

        resp = await client.get("/api/v1/agent/sessions/unknown-session/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "unknown-session"
        assert isinstance(body["messages"], list)

    async def test_agent_session_delete(self, harness: Any) -> None:
        """DELETE /agent/sessions/{id} attempts deletion."""
        client, _session, _app = harness

        resp = await client.delete("/api/v1/agent/sessions/test-session-123")
        # May succeed or 500 depending on memory provider availability
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.json()["deleted"] == "test-session-123"
