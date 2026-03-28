"""Unit tests for RAG and Agent REST API endpoints.

All tests are marked ``@pytest.mark.unit`` and work without live external
services. RAG engine, Document pipeline, and Agent runtime are injected via
app.state singletons (set directly on the test app) so no GPU / Neo4j /
Ollama is required.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kg.api.app import create_app
from kg.api.deps import get_async_neo4j_session
from kg.config import AppConfig, Neo4jConfig, reset


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient with auth dependency overridden."""
    reset()
    cfg = AppConfig(
        neo4j=Neo4jConfig(uri="bolt://localhost:7687", user="neo4j", password="test"),
        env="development",
    )
    app = create_app(cfg)

    # Override async Neo4j session so the app starts without a real DB
    async def _fake_session():
        yield MagicMock()

    app.dependency_overrides[get_async_neo4j_session] = _fake_session

    return TestClient(app, headers={"X-API-Key": "test-key"})


# ---------------------------------------------------------------------------
# Helpers: minimal fake objects matching the real dataclasses
# ---------------------------------------------------------------------------


def _make_rag_result(answer: str = "Test answer", chunks: int = 2) -> MagicMock:
    """Build a minimal fake RAGResult."""
    chunk_list = []
    for i in range(chunks):
        chunk = MagicMock()
        chunk.content = f"chunk content {i}"
        chunk.doc_id = f"doc-{i}"

        rc = MagicMock()
        rc.chunk = chunk
        rc.score = 0.8 - i * 0.1
        chunk_list.append(rc)

    result = MagicMock()
    result.answer = answer
    result.retrieved_chunks = tuple(chunk_list)
    result.chunk_count = len(chunk_list)
    return result


def _make_ingestion_result(doc_id: str = "abc123", chunks_created: int = 3) -> MagicMock:
    """Build a minimal fake IngestionResult."""
    result = MagicMock()
    result.doc_id = doc_id
    result.chunks_created = chunks_created
    result.success = True
    return result


def _make_execution_result(answer: str = "Agent answer") -> MagicMock:
    """Build a minimal fake ExecutionResult."""
    thought_step = MagicMock()
    thought_step.step_type = MagicMock()
    thought_step.step_type.value = "thought"
    thought_step.content = "Thinking about the query..."
    thought_step.tool_name = ""
    thought_step.tool_output = ""

    action_step = MagicMock()
    action_step.step_type = MagicMock()
    action_step.step_type.value = "action"
    action_step.content = "Using tool: vessel_search"
    action_step.tool_name = "vessel_search"
    action_step.tool_output = ""

    obs_step = MagicMock()
    obs_step.step_type = MagicMock()
    obs_step.step_type.value = "observation"
    obs_step.content = "Found 2 vessels."
    obs_step.tool_name = "vessel_search"
    obs_step.tool_output = "Found 2 vessels."

    result = MagicMock()
    result.answer = answer
    result.steps = (thought_step, action_step, obs_step)
    result.state = MagicMock()
    result.state.value = "completed"
    return result


def _make_tool_result(
    tool_name: str = "vessel_search",
    output: str = '{"vessels": []}',
    success: bool = True,
) -> MagicMock:
    """Build a minimal fake ToolResult."""
    result = MagicMock()
    result.tool_name = tool_name
    result.output = output
    result.success = success
    result.error = "" if success else "Tool error"
    return result


def _make_tool_definition(name: str, description: str = "A tool") -> MagicMock:
    """Build a minimal fake ToolDefinition."""
    td = MagicMock()
    td.name = name
    td.description = description
    td.parameters = {}
    return td


# ---------------------------------------------------------------------------
# RAG endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rag_query_returns_response(client: TestClient) -> None:
    """Set rag_engine on app.state and verify the /rag/query response shape."""
    fake_result = _make_rag_result(answer="COLREG is an international convention.", chunks=2)

    mock_engine = MagicMock()
    mock_engine.query.return_value = fake_result

    client.app.state.rag_engine = mock_engine  # type: ignore[union-attr]
    try:
        response = client.post(
            "/api/v1/rag/query",
            json={"query": "What is COLREG?", "mode": "hybrid", "top_k": 5},
        )
    finally:
        client.app.state.rag_engine = None  # type: ignore[union-attr]

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "What is COLREG?"
    assert data["answer"] == "COLREG is an international convention."
    assert data["mode"] == "hybrid"
    assert "chunks" in data
    assert "scores" in data
    assert "total_chunks" in data


@pytest.mark.unit
def test_rag_query_empty_text_rejected(client: TestClient) -> None:
    """Empty query string must return HTTP 422 (validation error)."""
    response = client.post(
        "/api/v1/rag/query",
        json={"query": "", "mode": "hybrid", "top_k": 5},
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_rag_query_unavailable_returns_503(client: TestClient) -> None:
    """When rag_engine is None in app.state, /rag/query returns 503."""
    client.app.state.rag_engine = None  # type: ignore[union-attr]
    response = client.post(
        "/api/v1/rag/query",
        json={"query": "What is COLREG?", "mode": "hybrid", "top_k": 5},
    )
    assert response.status_code == 503


@pytest.mark.unit
def test_rag_document_upload(client: TestClient) -> None:
    """Set document_pipeline on app.state and verify the /rag/documents response."""
    fake_ingestion = _make_ingestion_result(chunks_created=4)

    mock_pipeline = MagicMock()
    mock_pipeline.ingest_document.return_value = fake_ingestion

    with patch.dict(
        "sys.modules",
        {
            "rag": MagicMock(),
            "rag.documents": MagicMock(),
            "rag.documents.models": MagicMock(
                Document=MagicMock(),
                DocumentType=MagicMock(TXT="txt", MARKDOWN="markdown", HTML="html", CSV="csv"),
            ),
        },
    ):
        client.app.state.document_pipeline = mock_pipeline  # type: ignore[union-attr]
        try:
            response = client.post(
                "/api/v1/rag/documents",
                json={
                    "title": "COLREG Overview",
                    "content": "This document describes COLREG rules.",
                    "doc_type": "txt",
                    "metadata": {"source": "imo.org"},
                },
            )
        finally:
            client.app.state.document_pipeline = None  # type: ignore[union-attr]

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "COLREG Overview"
    assert "doc_id" in data
    assert data["chunks_created"] == 4
    assert data["message"] == "Document ingested successfully"


@pytest.mark.unit
def test_rag_document_upload_unavailable_returns_503(client: TestClient) -> None:
    """When document_pipeline is None in app.state, /rag/documents returns 503."""
    client.app.state.document_pipeline = None  # type: ignore[union-attr]
    response = client.post(
        "/api/v1/rag/documents",
        json={
            "title": "Test",
            "content": "Test content.",
            "doc_type": "txt",
            "metadata": {},
        },
    )
    assert response.status_code == 503


@pytest.mark.unit
def test_rag_status(client: TestClient) -> None:
    """GET /rag/status returns availability information."""
    with patch.dict(
        "sys.modules",
        {
            "rag": MagicMock(),
            "rag.engines": MagicMock(),
            "rag.engines.orchestrator": MagicMock(HybridRAGEngine=MagicMock()),
        },
    ):
        response = client.get("/api/v1/rag/status")

    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "engine" in data
    assert data["engine"] == "HybridRAGEngine"


# ---------------------------------------------------------------------------
# Agent endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_agent_chat_returns_response(client: TestClient) -> None:
    """Set tool_registry on app.state and verify the /agent/chat response shape."""
    fake_result = _make_execution_result(answer="The vessel BUSAN PIONEER is at Busan port.")

    mock_engine = MagicMock()
    mock_engine.execute.return_value = fake_result
    mock_engine_cls = MagicMock(return_value=mock_engine)

    mock_registry = MagicMock()
    mock_config_cls = MagicMock(return_value=MagicMock())
    mock_execution_mode = MagicMock(REACT="react")

    with patch.dict(
        "sys.modules",
        {
            "agent": MagicMock(),
            "agent.runtime": MagicMock(),
            "agent.runtime.react": MagicMock(ReActEngine=mock_engine_cls),
            "agent.runtime.models": MagicMock(
                AgentConfig=mock_config_cls,
                ExecutionMode=mock_execution_mode,
            ),
        },
    ):
        client.app.state.tool_registry = mock_registry  # type: ignore[union-attr]
        try:
            response = client.post(
                "/api/v1/agent/chat",
                json={"message": "Find vessels in Busan port", "mode": "react", "max_steps": 5},
            )
        finally:
            client.app.state.tool_registry = None  # type: ignore[union-attr]

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Find vessels in Busan port"
    assert data["answer"] == "The vessel BUSAN PIONEER is at Busan port."
    assert data["mode"] == "react"
    assert "steps" in data
    assert "tools_used" in data


@pytest.mark.unit
def test_agent_chat_unavailable_returns_503(client: TestClient) -> None:
    """When tool_registry is None in app.state, /agent/chat returns 503."""
    client.app.state.tool_registry = None  # type: ignore[union-attr]
    with patch.dict(
        "sys.modules",
        {
            "agent": MagicMock(),
            "agent.runtime": MagicMock(),
            "agent.runtime.react": MagicMock(),
            "agent.runtime.models": MagicMock(),
        },
    ):
        response = client.post(
            "/api/v1/agent/chat",
            json={"message": "Find vessels", "mode": "react", "max_steps": 5},
        )
    assert response.status_code == 503


@pytest.mark.unit
def test_agent_tool_execute(client: TestClient) -> None:
    """Execute a builtin tool directly via /agent/tools/execute."""
    fake_tool_def = _make_tool_definition("vessel_search", "Search for vessels")
    fake_result = _make_tool_result(
        tool_name="vessel_search",
        output='{"vessels": [{"name": "BUSAN PIONEER"}]}',
        success=True,
    )

    mock_registry = MagicMock()
    mock_registry.get.return_value = fake_tool_def
    mock_registry.execute.return_value = fake_result

    client.app.state.tool_registry = mock_registry  # type: ignore[union-attr]
    try:
        response = client.post(
            "/api/v1/agent/tools/execute",
            json={"tool_name": "vessel_search", "parameters": {"query": "BUSAN"}},
        )
    finally:
        client.app.state.tool_registry = None  # type: ignore[union-attr]

    assert response.status_code == 200
    data = response.json()
    assert data["tool_name"] == "vessel_search"
    assert data["success"] is True
    assert "output" in data
    assert data["error"] is None


@pytest.mark.unit
def test_agent_tool_not_found(client: TestClient) -> None:
    """Unknown tool name returns HTTP 404."""
    mock_registry = MagicMock()
    mock_registry.get.return_value = None  # tool not registered

    client.app.state.tool_registry = mock_registry  # type: ignore[union-attr]
    try:
        response = client.post(
            "/api/v1/agent/tools/execute",
            json={"tool_name": "nonexistent_tool", "parameters": {}},
        )
    finally:
        client.app.state.tool_registry = None  # type: ignore[union-attr]

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.unit
def test_agent_list_tools(client: TestClient) -> None:
    """GET /agent/tools lists all 7 builtin tools."""
    tool_names = [
        "kg_query",
        "kg_schema",
        "cypher_execute",
        "vessel_search",
        "port_info",
        "route_query",
        "document_search",
    ]
    fake_tools = [_make_tool_definition(name) for name in tool_names]

    mock_registry = MagicMock()
    mock_registry.list_tools.return_value = fake_tools

    client.app.state.tool_registry = mock_registry  # type: ignore[union-attr]
    try:
        response = client.get("/api/v1/agent/tools")
    finally:
        client.app.state.tool_registry = None  # type: ignore[union-attr]

    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    returned_names = [t["name"] for t in data["tools"]]
    assert len(returned_names) == 7
    for name in tool_names:
        assert name in returned_names


@pytest.mark.unit
def test_agent_list_tools_unavailable(client: TestClient) -> None:
    """GET /agent/tools returns empty list when tool_registry is None."""
    client.app.state.tool_registry = None  # type: ignore[union-attr]
    response = client.get("/api/v1/agent/tools")
    assert response.status_code == 200
    data = response.json()
    assert data["tools"] == []
    assert "error" in data


@pytest.mark.unit
def test_agent_status(client: TestClient) -> None:
    """GET /agent/status returns engine and tool information."""
    mock_registry = MagicMock()
    mock_registry.list_tools.return_value = [MagicMock()] * 7

    mock_react = MagicMock()
    mock_pipeline = MagicMock()
    mock_batch = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "agent": MagicMock(),
            "agent.runtime": MagicMock(),
            "agent.runtime.react": MagicMock(ReActEngine=mock_react),
            "agent.runtime.pipeline": MagicMock(PipelineEngine=mock_pipeline),
            "agent.runtime.batch": MagicMock(BatchEngine=mock_batch),
        },
    ):
        client.app.state.tool_registry = mock_registry  # type: ignore[union-attr]
        try:
            response = client.get("/api/v1/agent/status")
        finally:
            client.app.state.tool_registry = None  # type: ignore[union-attr]

    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "engines" in data
    assert "tools_count" in data
