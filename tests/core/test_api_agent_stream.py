"""Unit tests for agent SSE streaming and session management endpoints.

Covers:
    test_stream_endpoint_returns_sse_content_type
    test_stream_has_start_event
    test_stream_has_done_event
    test_session_list_returns_empty_by_default
    test_session_history_returns_empty
    test_session_delete
    test_agent_chat_with_session_id

All tests are marked ``@pytest.mark.unit`` and work without live external
services. Agent runtime and memory imports are patched with unittest.mock.
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
    """TestClient with auth and DB dependencies overridden."""
    reset()
    cfg = AppConfig(
        neo4j=Neo4jConfig(uri="bolt://localhost:7687", user="neo4j", password="test"),
        env="development",
    )
    app = create_app(cfg)

    async def _fake_session():
        yield MagicMock()

    app.dependency_overrides[get_async_neo4j_session] = _fake_session
    return TestClient(app, headers={"X-API-Key": "test-key"})


# ---------------------------------------------------------------------------
# Helpers: minimal fake objects
# ---------------------------------------------------------------------------


def _make_execution_result(answer: str = "Stream answer") -> MagicMock:
    """Build a minimal fake ExecutionResult with representative steps."""
    thought_step = MagicMock()
    thought_step.step_type = MagicMock()
    thought_step.step_type.value = "thought"
    thought_step.content = "Thinking about vessels..."
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
    obs_step.content = "Found 1 vessel."
    obs_step.tool_name = "vessel_search"
    obs_step.tool_output = "Found 1 vessel."

    result = MagicMock()
    result.answer = answer
    result.steps = (thought_step, action_step, obs_step)
    return result


def _make_agent_modules(result: MagicMock | None = None) -> dict[str, Any]:
    """Build the sys.modules patch dict for agent imports."""
    if result is None:
        result = _make_execution_result()

    mock_engine = MagicMock()
    mock_engine.execute.return_value = result
    mock_engine_cls = MagicMock(return_value=mock_engine)

    mock_registry = MagicMock()
    mock_registry_factory = MagicMock(return_value=mock_registry)
    mock_config_cls = MagicMock(return_value=MagicMock())
    mock_execution_mode = MagicMock(REACT="react")

    return {
        "agent": MagicMock(),
        "agent.runtime": MagicMock(),
        "agent.runtime.react": MagicMock(ReActEngine=mock_engine_cls),
        "agent.runtime.models": MagicMock(
            AgentConfig=mock_config_cls,
            ExecutionMode=mock_execution_mode,
        ),
        "agent.tools": MagicMock(),
        "agent.tools.builtins": MagicMock(create_builtin_registry=mock_registry_factory),
    }


# ---------------------------------------------------------------------------
# SSE streaming tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_stream_endpoint_returns_sse_content_type(client: TestClient) -> None:
    """POST /agent/chat/stream returns Content-Type: text/event-stream."""
    modules = _make_agent_modules()
    with patch.dict("sys.modules", modules):
        response = client.post(
            "/api/v1/agent/chat/stream",
            json={"message": "Find vessels", "mode": "react", "max_steps": 3},
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


@pytest.mark.unit
def test_stream_has_start_event(client: TestClient) -> None:
    """SSE stream begins with a 'start' event containing the original query."""
    modules = _make_agent_modules()
    with patch.dict("sys.modules", modules):
        response = client.post(
            "/api/v1/agent/chat/stream",
            json={"message": "Find vessels", "mode": "react", "max_steps": 3},
        )

    assert response.status_code == 200
    text = response.text
    # Parse SSE events from the body
    events = _parse_sse_events(text)
    assert len(events) > 0

    start_events = [e for e in events if e.get("type") == "start"]
    assert len(start_events) == 1
    assert start_events[0]["query"] == "Find vessels"


@pytest.mark.unit
def test_stream_has_done_event(client: TestClient) -> None:
    """SSE stream ends with a 'done' event."""
    modules = _make_agent_modules()
    with patch.dict("sys.modules", modules):
        response = client.post(
            "/api/v1/agent/chat/stream",
            json={"message": "Test query", "mode": "react", "max_steps": 3},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(done_events) == 1


@pytest.mark.unit
def test_stream_has_answer_event(client: TestClient) -> None:
    """SSE stream includes an 'answer' event with content and tool_calls count."""
    fake_result = _make_execution_result(answer="Busan Pioneer found")
    modules = _make_agent_modules(result=fake_result)
    with patch.dict("sys.modules", modules):
        response = client.post(
            "/api/v1/agent/chat/stream",
            json={"message": "Find vessels", "mode": "react", "max_steps": 3},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    answer_events = [e for e in events if e.get("type") == "answer"]
    assert len(answer_events) == 1
    assert answer_events[0]["content"] == "Busan Pioneer found"
    assert "tool_calls" in answer_events[0]


@pytest.mark.unit
def test_stream_has_step_events(client: TestClient) -> None:
    """SSE stream includes 'step' events for each reasoning step."""
    fake_result = _make_execution_result()
    modules = _make_agent_modules(result=fake_result)
    with patch.dict("sys.modules", modules):
        response = client.post(
            "/api/v1/agent/chat/stream",
            json={"message": "Find vessels", "mode": "react", "max_steps": 5},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    step_events = [e for e in events if e.get("type") == "step"]
    # The fake result has 3 steps (thought, action, observation)
    assert len(step_events) == 3


@pytest.mark.unit
def test_stream_import_error_returns_error_event(client: TestClient) -> None:
    """When agent runtime is unavailable, stream yields an error event."""
    with patch.dict(
        "sys.modules",
        {
            "agent": None,
            "agent.runtime": None,
            "agent.runtime.react": None,
            "agent.runtime.models": None,
            "agent.tools": None,
            "agent.tools.builtins": None,
        },
    ):
        response = client.post(
            "/api/v1/agent/chat/stream",
            json={"message": "Test", "mode": "react", "max_steps": 3},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) >= 1


# ---------------------------------------------------------------------------
# Session management tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_session_list_returns_empty_by_default(client: TestClient) -> None:
    """GET /agent/sessions returns empty list when no sessions exist."""
    mock_provider = MagicMock()
    mock_provider.list_sessions.return_value = []
    mock_factory = MagicMock(return_value=mock_provider)

    with patch.dict(
        "sys.modules",
        {
            "agent": MagicMock(),
            "agent.memory": MagicMock(),
            "agent.memory.factory": MagicMock(create_memory_provider=mock_factory),
        },
    ):
        response = client.get("/api/v1/agent/sessions")

    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "count" in data
    assert data["sessions"] == []
    assert data["count"] == 0


@pytest.mark.unit
def test_session_list_returns_sessions(client: TestClient) -> None:
    """GET /agent/sessions returns the list of active sessions."""
    mock_provider = MagicMock()
    mock_provider.list_sessions.return_value = ["session-a", "session-b"]
    mock_factory = MagicMock(return_value=mock_provider)

    with patch.dict(
        "sys.modules",
        {
            "agent": MagicMock(),
            "agent.memory": MagicMock(),
            "agent.memory.factory": MagicMock(create_memory_provider=mock_factory),
        },
    ):
        response = client.get("/api/v1/agent/sessions")

    assert response.status_code == 200
    data = response.json()
    assert set(data["sessions"]) == {"session-a", "session-b"}
    assert data["count"] == 2


@pytest.mark.unit
def test_session_history_returns_empty(client: TestClient) -> None:
    """GET /agent/sessions/{id}/history returns empty list for unknown session."""
    mock_provider = MagicMock()
    mock_provider.get_history.return_value = []
    mock_factory = MagicMock(return_value=mock_provider)

    with patch.dict(
        "sys.modules",
        {
            "agent": MagicMock(),
            "agent.memory": MagicMock(),
            "agent.memory.factory": MagicMock(create_memory_provider=mock_factory),
        },
    ):
        response = client.get("/api/v1/agent/sessions/nonexistent/history")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "nonexistent"
    assert data["messages"] == []
    assert data["count"] == 0


@pytest.mark.unit
def test_session_history_returns_entries(client: TestClient) -> None:
    """GET /agent/sessions/{id}/history returns formatted history entries."""
    from agent.memory.models import MemoryEntry, MemoryType

    entries = [
        MemoryEntry(role=MemoryType.USER, content="Hello"),
        MemoryEntry(role=MemoryType.ASSISTANT, content="Hi there"),
    ]
    mock_provider = MagicMock()
    mock_provider.get_history.return_value = entries
    mock_factory = MagicMock(return_value=mock_provider)

    with patch.dict(
        "sys.modules",
        {
            "agent": MagicMock(),
            "agent.memory": MagicMock(),
            "agent.memory.factory": MagicMock(create_memory_provider=mock_factory),
        },
    ):
        response = client.get("/api/v1/agent/sessions/my-session/history?limit=10")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "my-session"
    assert data["count"] == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Hello"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == "Hi there"


@pytest.mark.unit
def test_session_delete(client: TestClient) -> None:
    """DELETE /agent/sessions/{id} clears the session and returns the deleted id."""
    mock_provider = MagicMock()
    mock_provider.clear.return_value = None
    mock_factory = MagicMock(return_value=mock_provider)

    with patch.dict(
        "sys.modules",
        {
            "agent": MagicMock(),
            "agent.memory": MagicMock(),
            "agent.memory.factory": MagicMock(create_memory_provider=mock_factory),
        },
    ):
        response = client.delete("/api/v1/agent/sessions/session-xyz")

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == "session-xyz"
    mock_provider.clear.assert_called_once_with("session-xyz")


@pytest.mark.unit
def test_session_delete_error_returns_500(client: TestClient) -> None:
    """DELETE /agent/sessions/{id} returns 500 when clear() raises an exception."""
    mock_provider = MagicMock()
    mock_provider.clear.side_effect = RuntimeError("disk full")
    mock_factory = MagicMock(return_value=mock_provider)

    with patch.dict(
        "sys.modules",
        {
            "agent": MagicMock(),
            "agent.memory": MagicMock(),
            "agent.memory.factory": MagicMock(create_memory_provider=mock_factory),
        },
    ):
        response = client.delete("/api/v1/agent/sessions/bad-session")

    assert response.status_code == 500
    assert "disk full" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Agent chat with session_id
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_agent_chat_with_session_id(client: TestClient) -> None:
    """POST /agent/chat forwards session_id to the engine's execute() call."""
    fake_result = _make_execution_result(answer="Session-aware answer")

    mock_engine = MagicMock()
    mock_engine.execute.return_value = fake_result
    mock_engine_cls = MagicMock(return_value=mock_engine)

    mock_registry = MagicMock()
    mock_registry_factory = MagicMock(return_value=mock_registry)
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
            "agent.tools": MagicMock(),
            "agent.tools.builtins": MagicMock(create_builtin_registry=mock_registry_factory),
        },
    ):
        response = client.post(
            "/api/v1/agent/chat",
            json={
                "message": "Find vessels",
                "mode": "react",
                "max_steps": 5,
                "session_id": "my-test-session",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Session-aware answer"
    # Verify execute was called with session_id keyword argument
    mock_engine.execute.assert_called_once_with(
        "Find vessels", session_id="my-test-session"
    )


@pytest.mark.unit
def test_agent_chat_without_session_id_uses_default(client: TestClient) -> None:
    """POST /agent/chat defaults session_id to 'default' when not provided."""
    fake_result = _make_execution_result()

    mock_engine = MagicMock()
    mock_engine.execute.return_value = fake_result
    mock_engine_cls = MagicMock(return_value=mock_engine)

    mock_registry = MagicMock()
    mock_registry_factory = MagicMock(return_value=mock_registry)
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
            "agent.tools": MagicMock(),
            "agent.tools.builtins": MagicMock(create_builtin_registry=mock_registry_factory),
        },
    ):
        response = client.post(
            "/api/v1/agent/chat",
            json={"message": "Hello", "mode": "react", "max_steps": 3},
        )

    assert response.status_code == 200
    mock_engine.execute.assert_called_once_with("Hello", session_id="default")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_sse_events(body: str) -> list[dict[str, Any]]:
    """Parse SSE ``data:`` lines from raw response body.

    Returns a list of decoded JSON objects (one per event).
    """
    import json

    events: list[dict[str, Any]] = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload:
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    pass
    return events
