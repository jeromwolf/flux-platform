"""Extended unit tests for Document upload API — covers the RAG ingestion
exception path (lines 85-86 of core/kg/api/routes/documents.py).

When ``DocumentPipeline.ingest_text`` raises any exception the upload must
still succeed and the document status must NOT be ``"ingested"``.
"""
from __future__ import annotations

import io
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kg.api.app import create_app
from kg.api.deps import get_async_neo4j_session
from kg.config import AppConfig, Neo4jConfig, reset


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client_with_failing_rag() -> TestClient:
    """TestClient whose RAG pipeline always raises on ingest_text.

    The fixture patches ``rag.documents.pipeline.DocumentPipeline`` so that
    ``ingest_text`` raises a ``RuntimeError``.  This exercises the bare-except
    handler at lines 85-86 of routes/documents.py.
    """
    reset()
    cfg = AppConfig(
        neo4j=Neo4jConfig(uri="bolt://localhost:7687", user="neo4j", password="test"),
        env="development",
    )
    app = create_app(cfg)

    async def _fake_session() -> Any:
        yield MagicMock()

    app.dependency_overrides[get_async_neo4j_session] = _fake_session

    from kg.db.memory_document_repo import InMemoryDocumentRepository
    from kg.db.memory_workflow_repo import InMemoryWorkflowRepository

    app.state.workflow_repo = InMemoryWorkflowRepository()
    app.state.document_repo = InMemoryDocumentRepository()

    return TestClient(app, headers={"X-API-Key": "test-key"})


@pytest.fixture(autouse=True)
def _clear_docs(client_with_failing_rag: TestClient) -> None:
    """Reset the document store before each test."""
    client_with_failing_rag.app.state.document_repo.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_kwargs(
    filename: str = "test.txt",
    content: bytes = b"some content",
    content_type: str = "text/plain",
) -> dict[str, Any]:
    return {
        "files": {"file": (filename, io.BytesIO(content), content_type)},
        "data": {"description": "desc"},
    }


# ---------------------------------------------------------------------------
# Tests — RAG ingestion exception path (lines 85-86)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUploadRagIngestionException:
    """Upload succeeds even when RAG pipeline raises an exception."""

    def test_upload_succeeds_when_pipeline_raises(
        self, client_with_failing_rag: TestClient
    ) -> None:
        """HTTP 201 returned even if DocumentPipeline.ingest_text raises."""
        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.ingest_text.side_effect = RuntimeError(
            "Simulated RAG failure"
        )
        mock_pipeline_cls = MagicMock(return_value=mock_pipeline_instance)

        with patch.dict(
            "sys.modules",
            {
                "rag.documents.pipeline": MagicMock(
                    DocumentPipeline=mock_pipeline_cls
                ),
                "rag.documents.models": MagicMock(
                    DocumentType=MagicMock(
                        PDF="pdf",
                        HWP="hwp",
                        TXT="txt",
                        MARKDOWN="md",
                        HTML="html",
                        CSV="csv",
                    )
                ),
            },
        ):
            response = client_with_failing_rag.post(
                "/api/v1/documents/upload",
                **_upload_kwargs("colreg.txt", b"COLREG text content", "text/plain"),
            )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["filename"] == "colreg.txt"
        # Status must NOT be "ingested" because the pipeline raised
        assert data["status"] != "ingested"
        assert data["status"] == "uploaded"

    def test_upload_chunks_zero_when_pipeline_raises(
        self, client_with_failing_rag: TestClient
    ) -> None:
        """chunks defaults to 0 when ingestion raises."""
        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.ingest_text.side_effect = ValueError("bad input")
        mock_pipeline_cls = MagicMock(return_value=mock_pipeline_instance)

        with patch.dict(
            "sys.modules",
            {
                "rag.documents.pipeline": MagicMock(
                    DocumentPipeline=mock_pipeline_cls
                ),
                "rag.documents.models": MagicMock(
                    DocumentType=MagicMock(
                        PDF="pdf",
                        HWP="hwp",
                        TXT="txt",
                        MARKDOWN="md",
                        HTML="html",
                        CSV="csv",
                    )
                ),
            },
        ):
            response = client_with_failing_rag.post(
                "/api/v1/documents/upload",
                **_upload_kwargs("vessel.txt", b"vessel data here", "text/plain"),
            )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["chunks"] == 0

    def test_document_still_stored_when_pipeline_raises(
        self, client_with_failing_rag: TestClient
    ) -> None:
        """Document is persisted in repository even when ingestion fails."""
        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.ingest_text.side_effect = ConnectionError(
            "Ollama unavailable"
        )
        mock_pipeline_cls = MagicMock(return_value=mock_pipeline_instance)

        with patch.dict(
            "sys.modules",
            {
                "rag.documents.pipeline": MagicMock(
                    DocumentPipeline=mock_pipeline_cls
                ),
                "rag.documents.models": MagicMock(
                    DocumentType=MagicMock(
                        PDF="pdf",
                        HWP="hwp",
                        TXT="txt",
                        MARKDOWN="md",
                        HTML="html",
                        CSV="csv",
                    )
                ),
            },
        ):
            upload_resp = client_with_failing_rag.post(
                "/api/v1/documents/upload",
                **_upload_kwargs("port.txt", b"port data content here", "text/plain"),
            )

        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        # Document must appear in the list
        list_resp = client_with_failing_rag.get("/api/v1/documents/")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 1
        assert list_resp.json()["documents"][0]["id"] == doc_id
