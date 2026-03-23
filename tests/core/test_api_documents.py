"""Unit tests for Document upload and management REST API endpoints.

All tests are marked ``@pytest.mark.unit`` and require no live external
services.  The in-memory ``_documents`` list is cleared between test
functions via the ``clean_docs`` autouse fixture so tests are isolated.
"""
from __future__ import annotations

import io
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import kg.api.routes.documents as docs_module
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
def clean_docs() -> None:
    """Clear the in-memory document store before each test."""
    docs_module._documents.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_upload_file(
    filename: str = "report.txt",
    content: bytes = b"Hello maritime world",
    content_type: str = "text/plain",
) -> dict[str, Any]:
    """Build kwargs for TestClient multipart upload."""
    return {
        "files": {"file": (filename, io.BytesIO(content), content_type)},
        "data": {"description": "test doc"},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upload_document(client: TestClient) -> None:
    """POST /documents/upload returns 201 with document metadata."""
    kwargs = _make_upload_file("colreg.txt", b"COLREG rule text here", "text/plain")
    response = client.post("/api/v1/documents/upload", **kwargs)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["filename"] == "colreg.txt"
    assert data["size"] == len(b"COLREG rule text here")
    assert "id" in data
    assert len(data["id"]) == 16  # SHA-256 prefix
    assert data["content_type"] == "text/plain"
    assert data["status"] in ("uploaded", "ingested")
    assert isinstance(data["chunks"], int)


@pytest.mark.unit
def test_upload_document_appears_in_list(client: TestClient) -> None:
    """After upload the document must appear in the list endpoint."""
    kwargs = _make_upload_file("vessel.md", b"# Vessel Data", "text/markdown")
    upload_resp = client.post("/api/v1/documents/upload", **kwargs)
    assert upload_resp.status_code == 201

    list_resp = client.get("/api/v1/documents/")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    assert data["documents"][0]["filename"] == "vessel.md"


@pytest.mark.unit
def test_list_documents_empty(client: TestClient) -> None:
    """GET /documents/ returns empty list when nothing is uploaded."""
    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["documents"] == []


@pytest.mark.unit
def test_list_documents_multiple(client: TestClient) -> None:
    """Multiple uploads accumulate in the list with correct total."""
    for i in range(3):
        kwargs = _make_upload_file(f"file_{i}.txt", f"content {i}".encode(), "text/plain")
        resp = client.post("/api/v1/documents/upload", **kwargs)
        assert resp.status_code == 201

    list_resp = client.get("/api/v1/documents/")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 3
    assert len(data["documents"]) == 3


@pytest.mark.unit
def test_delete_document(client: TestClient) -> None:
    """DELETE /documents/{id} removes the document and returns the deleted ID."""
    kwargs = _make_upload_file("to_delete.txt", b"temporary", "text/plain")
    upload_resp = client.post("/api/v1/documents/upload", **kwargs)
    doc_id = upload_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] == doc_id

    # Confirm removed from list
    list_resp = client.get("/api/v1/documents/")
    assert list_resp.json()["total"] == 0


@pytest.mark.unit
def test_delete_nonexistent_document(client: TestClient) -> None:
    """DELETE with an unknown ID returns 404."""
    response = client.delete("/api/v1/documents/nonexistent00")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.unit
def test_upload_too_large(client: TestClient) -> None:
    """Files exceeding 50 MB must be rejected with HTTP 413."""
    big_content = b"x" * (50 * 1024 * 1024 + 1)  # 50 MB + 1 byte
    kwargs = _make_upload_file("huge.bin", big_content, "application/octet-stream")
    response = client.post("/api/v1/documents/upload", **kwargs)
    assert response.status_code == 413
    assert "50MB" in response.json()["detail"]


@pytest.mark.unit
def test_upload_deduplicates_by_content(client: TestClient) -> None:
    """Two uploads of identical content produce the same doc ID (SHA-256)."""
    content = b"same content for both uploads"
    kwargs = _make_upload_file("a.txt", content, "text/plain")
    resp1 = client.post("/api/v1/documents/upload", **kwargs)
    resp2 = client.post("/api/v1/documents/upload", **kwargs)
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    # IDs are deterministic from content hash
    assert resp1.json()["id"] == resp2.json()["id"]
