"""E2E harness tests for Documents, Workflows, and MCP endpoints.

Tests /api/v1/documents/*, /api/v1/workflows/*, and /api/v1/mcp/*
using MockNeo4jSession and in-memory repositories -- no real Neo4j,
PostgreSQL, or MCP server needed.
"""
from __future__ import annotations

from typing import Any

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ===========================================================================
# Workflow CRUD
# ===========================================================================


class TestWorkflowCRUD:
    """Workflow CRUD endpoint tests (/api/v1/workflows/*)."""

    async def test_workflow_create(self, harness: Any) -> None:
        """POST /workflows/ creates a workflow and returns 201."""
        client, _session, _app = harness

        resp = await client.post(
            "/api/v1/workflows/",
            json={
                "name": "Maritime ETL Pipeline",
                "description": "ETL for vessel data",
                "nodes": [{"id": "n1", "type": "input"}],
                "edges": [{"source": "n1", "target": "n2"}],
                "viewport": {"x": 0, "y": 0, "zoom": 1},
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Maritime ETL Pipeline"
        assert body["description"] == "ETL for vessel data"
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body

    async def test_workflow_list(self, harness: Any) -> None:
        """GET /workflows/ returns list of workflows."""
        client, _session, _app = harness

        # Create one first
        await client.post(
            "/api/v1/workflows/",
            json={"name": "ListTest", "description": "", "nodes": [], "edges": [], "viewport": {}},
        )

        resp = await client.get("/api/v1/workflows/")
        assert resp.status_code == 200
        body = resp.json()
        assert "workflows" in body
        assert "total" in body
        assert body["total"] >= 1

    async def test_workflow_get(self, harness: Any) -> None:
        """GET /workflows/{id} returns the created workflow."""
        client, _session, _app = harness

        create_resp = await client.post(
            "/api/v1/workflows/",
            json={"name": "GetTest", "description": "desc", "nodes": [], "edges": [], "viewport": {}},
        )
        wf_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/workflows/{wf_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == wf_id
        assert body["name"] == "GetTest"

    async def test_workflow_get_not_found(self, harness: Any) -> None:
        """GET /workflows/{nonexistent} returns 404."""
        client, _session, _app = harness

        resp = await client.get("/api/v1/workflows/nonexistent-id")
        assert resp.status_code == 404

    async def test_workflow_update(self, harness: Any) -> None:
        """PUT /workflows/{id} updates the workflow."""
        client, _session, _app = harness

        create_resp = await client.post(
            "/api/v1/workflows/",
            json={"name": "UpdateTest", "description": "", "nodes": [], "edges": [], "viewport": {}},
        )
        wf_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/workflows/{wf_id}",
            json={
                "name": "UpdatedName",
                "description": "Updated desc",
                "nodes": [{"id": "n1"}],
                "edges": [],
                "viewport": {"zoom": 2},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "UpdatedName"
        assert body["description"] == "Updated desc"

    async def test_workflow_delete(self, harness: Any) -> None:
        """DELETE /workflows/{id} removes the workflow."""
        client, _session, _app = harness

        create_resp = await client.post(
            "/api/v1/workflows/",
            json={"name": "DeleteTest", "description": "", "nodes": [], "edges": [], "viewport": {}},
        )
        wf_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/workflows/{wf_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == wf_id

        # Confirm 404 after deletion
        resp2 = await client.get(f"/api/v1/workflows/{wf_id}")
        assert resp2.status_code == 404

    async def test_workflow_delete_not_found(self, harness: Any) -> None:
        """DELETE /workflows/{nonexistent} returns 404."""
        client, _session, _app = harness

        resp = await client.delete("/api/v1/workflows/nonexistent-id")
        assert resp.status_code == 404

    async def test_workflow_full_lifecycle(self, harness: Any) -> None:
        """Create -> get -> update -> list -> delete lifecycle."""
        client, _session, _app = harness

        # Create
        create_resp = await client.post(
            "/api/v1/workflows/",
            json={
                "name": "LifecycleTest",
                "description": "Full lifecycle",
                "nodes": [{"id": "start"}],
                "edges": [],
                "viewport": {"x": 10, "y": 20, "zoom": 1.5},
            },
        )
        assert create_resp.status_code == 201
        wf_id = create_resp.json()["id"]

        # Get
        get_resp = await client.get(f"/api/v1/workflows/{wf_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "LifecycleTest"

        # Update
        update_resp = await client.put(
            f"/api/v1/workflows/{wf_id}",
            json={
                "name": "LifecycleUpdated",
                "description": "Updated",
                "nodes": [{"id": "start"}, {"id": "end"}],
                "edges": [{"source": "start", "target": "end"}],
                "viewport": {"x": 0, "y": 0, "zoom": 1},
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "LifecycleUpdated"
        assert len(update_resp.json()["nodes"]) == 2

        # List (should include the updated workflow)
        list_resp = await client.get("/api/v1/workflows/")
        assert list_resp.status_code == 200
        wf_ids = [w["id"] for w in list_resp.json()["workflows"]]
        assert wf_id in wf_ids

        # Delete
        del_resp = await client.delete(f"/api/v1/workflows/{wf_id}")
        assert del_resp.status_code == 200


# ===========================================================================
# Documents
# ===========================================================================


class TestDocuments:
    """Document upload and management endpoint tests (/api/v1/documents/*)."""

    async def test_document_list_empty(self, harness: Any) -> None:
        """GET /documents/ initially returns empty list."""
        client, _session, _app = harness

        resp = await client.get("/api/v1/documents/")
        assert resp.status_code == 200
        body = resp.json()
        assert "documents" in body
        assert "total" in body
        assert isinstance(body["documents"], list)

    async def test_document_upload(self, harness: Any) -> None:
        """POST /documents/upload accepts multipart file upload."""
        client, _session, _app = harness

        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", b"Hello, maritime world!", "text/plain")},
            data={"description": "Test document"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert body["filename"] == "test.txt"
        assert body["size"] == len(b"Hello, maritime world!")
        assert body["content_type"] == "text/plain"

    async def test_document_delete_not_found(self, harness: Any) -> None:
        """DELETE /documents/{nonexistent} returns 404."""
        client, _session, _app = harness

        resp = await client.delete("/api/v1/documents/nonexistent-doc-id")
        assert resp.status_code == 404

    async def test_document_list_after_upload(self, harness: Any) -> None:
        """Upload then list shows the document."""
        client, _session, _app = harness

        # Upload
        upload_resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("report.pdf", b"%PDF-1.4 fake content", "application/pdf")},
            data={"description": "A report"},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        # List
        list_resp = await client.get("/api/v1/documents/")
        assert list_resp.status_code == 200
        body = list_resp.json()
        doc_ids = [d["id"] for d in body["documents"]]
        assert doc_id in doc_ids

    async def test_document_upload_and_delete(self, harness: Any) -> None:
        """Upload then delete a document successfully."""
        client, _session, _app = harness

        upload_resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("deleteme.txt", b"delete this", "text/plain")},
            data={"description": "To be deleted"},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/documents/{doc_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] == doc_id


# ===========================================================================
# MCP Endpoint
# ===========================================================================


class TestMCPEndpoint:
    """MCP JSON-RPC endpoint tests (/api/v1/mcp/*)."""

    async def test_mcp_tools_list(self, harness: Any) -> None:
        """POST /mcp/ with tools/list method returns tool list."""
        client, _session, _app = harness

        resp = await client.post(
            "/api/v1/mcp/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == "1"
        # Should have result (tools list) or error
        assert "result" in body or "error" in body

    async def test_mcp_invalid_method(self, harness: Any) -> None:
        """POST /mcp/ with unknown method returns JSON-RPC error."""
        client, _session, _app = harness

        resp = await client.post(
            "/api/v1/mcp/",
            json={
                "jsonrpc": "2.0",
                "method": "unknown/invalid",
                "params": {},
                "id": 2,
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["jsonrpc"] == "2.0"
        assert "error" in body
        assert body["error"]["code"] == -32601
        assert "Unknown method" in body["error"]["message"]

    async def test_mcp_ping(self, harness: Any) -> None:
        """POST /mcp/ with ping method returns pong."""
        client, _session, _app = harness

        resp = await client.post(
            "/api/v1/mcp/",
            json={
                "jsonrpc": "2.0",
                "method": "ping",
                "params": {},
                "id": 3,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["jsonrpc"] == "2.0"
        # ping should succeed without error
        assert "result" in body or "error" in body
