"""Unit tests for Workflow CRUD REST API endpoints.

All tests are marked ``@pytest.mark.unit`` and require no live external
services.  The in-memory ``_workflows`` dict is cleared between test
functions via the ``clean_wf`` autouse fixture so tests are isolated.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import kg.api.routes.workflows as wf_module
from kg.api.app import create_app
from kg.api.deps import get_async_neo4j_session
from kg.config import AppConfig, Neo4jConfig, reset


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient with Neo4j auth dependency overridden."""
    reset()
    cfg = AppConfig(
        neo4j=Neo4jConfig(uri="bolt://localhost:7687", user="neo4j", password="test"),
        env="development",
    )
    app = create_app(cfg)

    async def _fake_session() -> Any:
        yield MagicMock()

    app.dependency_overrides[get_async_neo4j_session] = _fake_session

    return TestClient(app, headers={"X-API-Key": "test-key"})


@pytest.fixture(autouse=True)
def clean_wf() -> None:
    """Clear the in-memory workflow store before each test."""
    wf_module._workflows.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_payload(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid WorkflowData payload."""
    base: dict[str, Any] = {
        "name": "Test Workflow",
        "description": "A workflow for unit testing",
        "nodes": [
            {
                "id": "1",
                "type": "custom",
                "position": {"x": 100, "y": 100},
                "data": {"label": "데이터 수집"},
            }
        ],
        "edges": [
            {"id": "e1-2", "source": "1", "target": "2", "animated": True}
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_workflow(client: TestClient) -> None:
    """POST /workflows/ returns 201 with assigned ID and timestamps."""
    response = client.post("/api/v1/workflows/", json=_sample_payload())

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "Test Workflow"
    assert data["description"] == "A workflow for unit testing"
    assert "id" in data
    assert len(data["id"]) > 0
    assert "created_at" in data
    assert "updated_at" in data
    assert data["created_at"] == data["updated_at"]  # newly created
    assert len(data["nodes"]) == 1
    assert len(data["edges"]) == 1


@pytest.mark.unit
def test_create_workflow_defaults(client: TestClient) -> None:
    """Empty POST body uses sensible defaults."""
    response = client.post("/api/v1/workflows/", json={})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Untitled Workflow"
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["viewport"] == {}


@pytest.mark.unit
def test_list_workflows(client: TestClient) -> None:
    """GET /workflows/ returns all created workflows."""
    # Create two workflows
    for i in range(2):
        resp = client.post("/api/v1/workflows/", json=_sample_payload(name=f"WF {i}"))
        assert resp.status_code == 201

    list_resp = client.get("/api/v1/workflows/")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["workflows"]) == 2
    names = {wf["name"] for wf in data["workflows"]}
    assert names == {"WF 0", "WF 1"}


@pytest.mark.unit
def test_list_workflows_empty(client: TestClient) -> None:
    """GET /workflows/ returns empty list when nothing is stored."""
    response = client.get("/api/v1/workflows/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["workflows"] == []


@pytest.mark.unit
def test_get_workflow(client: TestClient) -> None:
    """GET /workflows/{id} returns the matching workflow."""
    create_resp = client.post("/api/v1/workflows/", json=_sample_payload())
    wf_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/v1/workflows/{wf_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == wf_id
    assert data["name"] == "Test Workflow"


@pytest.mark.unit
def test_get_nonexistent_workflow(client: TestClient) -> None:
    """GET with an unknown ID returns 404."""
    response = client.get("/api/v1/workflows/deadbeef")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.unit
def test_update_workflow(client: TestClient) -> None:
    """PUT /workflows/{id} replaces the workflow content."""
    create_resp = client.post("/api/v1/workflows/", json=_sample_payload())
    wf_id = create_resp.json()["id"]
    created_at = create_resp.json()["created_at"]

    updated_payload = _sample_payload(
        name="Updated Workflow",
        nodes=[],
        edges=[],
    )
    update_resp = client.put(f"/api/v1/workflows/{wf_id}", json=updated_payload)

    assert update_resp.status_code == 200, update_resp.text
    data = update_resp.json()
    assert data["id"] == wf_id
    assert data["name"] == "Updated Workflow"
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["created_at"] == created_at  # preserved
    assert data["updated_at"] != created_at  # bumped


@pytest.mark.unit
def test_update_nonexistent_workflow(client: TestClient) -> None:
    """PUT with an unknown ID returns 404."""
    response = client.put("/api/v1/workflows/nope0000", json=_sample_payload())
    assert response.status_code == 404


@pytest.mark.unit
def test_delete_workflow(client: TestClient) -> None:
    """DELETE /workflows/{id} removes the workflow and returns deleted ID."""
    create_resp = client.post("/api/v1/workflows/", json=_sample_payload())
    wf_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/workflows/{wf_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] == wf_id

    # Confirm removed
    get_resp = client.get(f"/api/v1/workflows/{wf_id}")
    assert get_resp.status_code == 404


@pytest.mark.unit
def test_delete_nonexistent_workflow(client: TestClient) -> None:
    """DELETE with an unknown ID returns 404."""
    response = client.delete("/api/v1/workflows/unknown0")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.unit
def test_workflow_id_is_short_uuid(client: TestClient) -> None:
    """Workflow IDs are 8-character short UUIDs."""
    resp = client.post("/api/v1/workflows/", json={})
    assert resp.status_code == 201
    wf_id = resp.json()["id"]
    assert len(wf_id) == 8
    # All hex characters (UUID prefix)
    assert all(c in "0123456789abcdef-" for c in wf_id)


@pytest.mark.unit
def test_workflow_nodes_edges_roundtrip(client: TestClient) -> None:
    """Nodes and edges survive a full create → get roundtrip unchanged."""
    nodes = [
        {"id": "a", "type": "custom", "position": {"x": 0, "y": 0}, "data": {"label": "A"}},
        {"id": "b", "type": "custom", "position": {"x": 200, "y": 0}, "data": {"label": "B"}},
    ]
    edges = [{"id": "a-b", "source": "a", "target": "b"}]

    create_resp = client.post(
        "/api/v1/workflows/",
        json={"name": "Roundtrip", "nodes": nodes, "edges": edges},
    )
    wf_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/v1/workflows/{wf_id}")
    data = get_resp.json()
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["nodes"][0]["id"] == "a"
    assert data["edges"][0]["source"] == "a"
