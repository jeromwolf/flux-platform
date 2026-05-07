"""Tests for workflow execution API routes."""
import importlib
import pytest
from unittest.mock import AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.kg.api.routes.executions import router as executions_router
from core.workflow.registry import NodeRegistry
import core.workflow.nodes.data_input as _data_input_mod
import core.workflow.nodes.http_request as _http_request_mod
import core.workflow.nodes.crawler as _crawler_mod
import core.workflow.nodes.transform as _transform_mod
import core.workflow.nodes.llm as _llm_mod
import core.workflow.nodes.neo4j_output as _neo4j_output_mod


@pytest.fixture(autouse=True)
def _ensure_nodes_registered():
    """Ensure built-in nodes are registered (survives registry clears from other tests)."""
    if not NodeRegistry.has("input"):
        importlib.reload(_data_input_mod)
        importlib.reload(_http_request_mod)
        importlib.reload(_crawler_mod)
        importlib.reload(_transform_mod)
        importlib.reload(_llm_mod)
        importlib.reload(_neo4j_output_mod)
    yield


@pytest.fixture
def app():
    """Create test FastAPI app with execution routes."""
    app = FastAPI()
    app.include_router(executions_router, prefix="/v1")

    # Mock repos
    mock_wf_repo = AsyncMock()
    mock_wf_repo.get = AsyncMock(return_value={
        "id": "test1234",
        "name": "Test",
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {"type": "input", "label": "Input", "params": {}},
                "position": {"x": 0, "y": 0},
            },
        ],
        "edges": [],
    })

    mock_exec_repo = AsyncMock()
    mock_exec_repo.create = AsyncMock(return_value={})
    mock_exec_repo.get = AsyncMock(return_value={
        "id": "exec123",
        "workflow_id": "test1234",
        "status": "success",
        "trigger_type": "manual",
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:00:01+00:00",
        "error_message": "",
        "node_results": {},
    })
    mock_exec_repo.list_by_workflow = AsyncMock(return_value=[])
    mock_exec_repo.count_by_workflow = AsyncMock(return_value=0)
    mock_exec_repo.count_running_by_workflow = AsyncMock(return_value=0)
    mock_exec_repo.count_running_total = AsyncMock(return_value=0)
    mock_exec_repo.delete = AsyncMock(return_value=True)

    app.state.workflow_repo = mock_wf_repo
    app.state.execution_repo = mock_exec_repo

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestExecutionAPI:
    def test_execute_workflow(self, client):
        response = client.post("/v1/workflows/test1234/execute")
        assert response.status_code == 202
        data = response.json()
        assert data["workflow_id"] == "test1234"
        assert data["status"] == "pending"

    def test_execute_not_found(self, client, app):
        app.state.workflow_repo.get = AsyncMock(return_value=None)
        response = client.post("/v1/workflows/missing/execute")
        assert response.status_code == 404

    def test_execute_no_nodes(self, client, app):
        app.state.workflow_repo.get = AsyncMock(return_value={
            "id": "test1234",
            "name": "Empty",
            "nodes": [],
            "edges": [],
        })
        response = client.post("/v1/workflows/test1234/execute")
        assert response.status_code == 400

    def test_list_executions(self, client):
        response = client.get("/v1/workflows/test1234/executions")
        assert response.status_code == 200
        data = response.json()
        assert "executions" in data
        assert "total" in data

    def test_get_execution(self, client):
        response = client.get("/v1/executions/exec123")
        assert response.status_code == 200
        assert response.json()["id"] == "exec123"

    def test_get_execution_not_found(self, client, app):
        app.state.execution_repo.get = AsyncMock(return_value=None)
        response = client.get("/v1/executions/missing")
        assert response.status_code == 404

    def test_delete_execution(self, client):
        response = client.delete("/v1/executions/exec123")
        assert response.status_code == 200
        assert response.json()["deleted"] == "exec123"

    def test_delete_execution_not_found(self, client, app):
        app.state.execution_repo.delete = AsyncMock(return_value=False)
        response = client.delete("/v1/executions/missing")
        assert response.status_code == 404

    @pytest.mark.unit
    def test_execute_workflow_per_workflow_limit(self, client, app):
        app.state.execution_repo.count_running_by_workflow = AsyncMock(return_value=3)
        response = client.post("/v1/workflows/test1234/execute")
        assert response.status_code == 429

    @pytest.mark.unit
    def test_execute_workflow_total_limit(self, client, app):
        app.state.execution_repo.count_running_by_workflow = AsyncMock(return_value=0)
        app.state.execution_repo.count_running_total = AsyncMock(return_value=10)
        response = client.post("/v1/workflows/test1234/execute")
        assert response.status_code == 429

    def test_list_node_types(self, client):
        response = client.get("/v1/nodes/types")
        assert response.status_code == 200
        types = response.json()
        assert isinstance(types, list)
        # Should have 6 built-in types
        names = {t["name"] for t in types}
        assert "input" in names
        assert "api" in names

    def test_get_node_type_schema(self, client):
        response = client.get("/v1/nodes/types/input/schema")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "input"
        assert "parameter_schema" in data

    def test_get_node_type_schema_not_found(self, client):
        response = client.get("/v1/nodes/types/nonexistent/schema")
        assert response.status_code == 404


class TestMemoryExecutionRepo:
    @pytest.mark.asyncio
    async def test_crud(self):
        from core.kg.db.memory_execution_repo import InMemoryExecutionRepository

        repo = InMemoryExecutionRepository()

        # Create
        exec_data = {
            "id": "ex1",
            "workflow_id": "wf1",
            "status": "running",
            "trigger_type": "manual",
        }
        await repo.create(exec_data)

        # Get
        result = await repo.get("ex1")
        assert result is not None
        assert result["status"] == "running"

        # Update
        updated = await repo.update("ex1", {"status": "success"})
        assert updated["status"] == "success"

        # List
        items = await repo.list_by_workflow("wf1")
        assert len(items) == 1

        # Count
        count = await repo.count_by_workflow("wf1")
        assert count == 1

        # Delete
        assert await repo.delete("ex1")
        assert await repo.get("ex1") is None

    @pytest.mark.asyncio
    async def test_update_missing(self):
        from core.kg.db.memory_execution_repo import InMemoryExecutionRepository

        repo = InMemoryExecutionRepository()
        result = await repo.update("nonexistent", {"status": "done"})
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_missing(self):
        from core.kg.db.memory_execution_repo import InMemoryExecutionRepository

        repo = InMemoryExecutionRepository()
        assert not await repo.delete("nonexistent")

    @pytest.mark.asyncio
    async def test_list_pagination(self):
        from core.kg.db.memory_execution_repo import InMemoryExecutionRepository

        repo = InMemoryExecutionRepository()
        for i in range(5):
            await repo.create({
                "id": f"ex{i}",
                "workflow_id": "wf1",
                "status": "success",
                "started_at": f"2026-01-01T00:00:0{i}+00:00",
            })

        items = await repo.list_by_workflow("wf1", limit=2, offset=0)
        assert len(items) == 2

        items = await repo.list_by_workflow("wf1", limit=2, offset=3)
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_count_empty(self):
        from core.kg.db.memory_execution_repo import InMemoryExecutionRepository

        repo = InMemoryExecutionRepository()
        count = await repo.count_by_workflow("nonexistent")
        assert count == 0
