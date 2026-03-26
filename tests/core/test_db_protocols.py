"""Tests for database repository protocols and in-memory implementations."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from kg.db.protocols import DocumentRepository, WorkflowRepository
from kg.db.memory_workflow_repo import InMemoryWorkflowRepository
from kg.db.memory_document_repo import InMemoryDocumentRepository


def run(coro: Any) -> Any:
    """Run a coroutine synchronously for test purposes."""
    return asyncio.run(coro)


@pytest.mark.unit
class TestProtocolConformance:
    """Verify that in-memory implementations satisfy Protocol checks."""

    def test_workflow_repo_is_protocol(self) -> None:
        repo = InMemoryWorkflowRepository()
        assert isinstance(repo, WorkflowRepository)

    def test_document_repo_is_protocol(self) -> None:
        repo = InMemoryDocumentRepository()
        assert isinstance(repo, DocumentRepository)


@pytest.mark.unit
class TestInMemoryWorkflowRepo:
    """Unit tests for InMemoryWorkflowRepository."""

    def setup_method(self) -> None:
        self.repo = InMemoryWorkflowRepository()

    def test_create_and_get(self) -> None:
        wf = run(
            self.repo.create(
                wf_id="test1234",
                name="Test WF",
                description="desc",
                nodes=[{"id": "n1"}],
                edges=[],
                viewport={"zoom": 1},
            )
        )
        assert wf["id"] == "test1234"
        assert wf["name"] == "Test WF"
        assert "created_at" in wf
        assert "updated_at" in wf

        fetched = run(self.repo.get("test1234"))
        assert fetched is not None
        assert fetched["name"] == "Test WF"

    def test_get_nonexistent(self) -> None:
        result = run(self.repo.get("nope"))
        assert result is None

    def test_list_all(self) -> None:
        run(self.repo.create("w1", "WF1", "", [], [], {}))
        run(self.repo.create("w2", "WF2", "", [], [], {}))
        wfs = run(self.repo.list_all())
        assert len(wfs) == 2

    def test_list_all_empty(self) -> None:
        wfs = run(self.repo.list_all())
        assert wfs == []

    def test_update(self) -> None:
        run(self.repo.create("w1", "Old", "", [], [], {}))
        updated = run(self.repo.update("w1", "New", "updated", [{"id": "n1"}], [], {}))
        assert updated is not None
        assert updated["name"] == "New"
        assert updated["description"] == "updated"
        assert updated["nodes"] == [{"id": "n1"}]

    def test_update_preserves_created_at(self) -> None:
        wf = run(self.repo.create("w1", "Old", "", [], [], {}))
        original_created_at = wf["created_at"]
        updated = run(self.repo.update("w1", "New", "", [], [], {}))
        assert updated is not None
        assert updated["created_at"] == original_created_at

    def test_update_nonexistent(self) -> None:
        result = run(self.repo.update("nope", "N", "", [], [], {}))
        assert result is None

    def test_delete(self) -> None:
        run(self.repo.create("w1", "WF", "", [], [], {}))
        assert run(self.repo.delete("w1")) is True
        assert run(self.repo.get("w1")) is None

    def test_delete_nonexistent(self) -> None:
        assert run(self.repo.delete("nope")) is False

    def test_clear(self) -> None:
        run(self.repo.create("w1", "WF", "", [], [], {}))
        self.repo.clear()
        assert run(self.repo.list_all()) == []

    def test_create_stores_all_fields(self) -> None:
        nodes = [{"id": "n1", "type": "custom"}]
        edges = [{"id": "e1", "source": "n1", "target": "n2"}]
        viewport = {"x": 10, "y": 20, "zoom": 1.5}
        wf = run(self.repo.create("w99", "Full WF", "Full desc", nodes, edges, viewport))
        assert wf["nodes"] == nodes
        assert wf["edges"] == edges
        assert wf["viewport"] == viewport
        assert wf["description"] == "Full desc"


@pytest.mark.unit
class TestInMemoryDocumentRepo:
    """Unit tests for InMemoryDocumentRepository."""

    def setup_method(self) -> None:
        self.repo = InMemoryDocumentRepository()

    def test_create_and_list(self) -> None:
        doc = run(
            self.repo.create(
                doc_id="abc123",
                filename="test.pdf",
                size=1024,
                content_type="application/pdf",
                description="Test",
                status="uploaded",
                chunks=3,
            )
        )
        assert doc["id"] == "abc123"
        assert doc["filename"] == "test.pdf"
        assert "created_at" in doc

        docs, total = run(self.repo.list())
        assert total == 1
        assert docs[0]["id"] == "abc123"

    def test_list_pagination(self) -> None:
        for i in range(5):
            run(self.repo.create(f"d{i}", f"f{i}.txt", 100, "text/plain", "", "uploaded", 0))
        docs, total = run(self.repo.list(limit=2, offset=1))
        assert total == 5
        assert len(docs) == 2

    def test_list_pagination_offset_beyond_total(self) -> None:
        run(self.repo.create("d1", "f.txt", 100, "text/plain", "", "uploaded", 0))
        docs, total = run(self.repo.list(limit=10, offset=5))
        assert total == 1
        assert docs == []

    def test_list_empty(self) -> None:
        docs, total = run(self.repo.list())
        assert total == 0
        assert docs == []

    def test_delete(self) -> None:
        run(self.repo.create("d1", "f.txt", 100, "text/plain", "", "uploaded", 0))
        assert run(self.repo.delete("d1")) is True
        docs, total = run(self.repo.list())
        assert total == 0

    def test_delete_nonexistent(self) -> None:
        assert run(self.repo.delete("nope")) is False

    def test_clear(self) -> None:
        run(self.repo.create("d1", "f.txt", 100, "text/plain", "", "uploaded", 0))
        self.repo.clear()
        docs, total = run(self.repo.list())
        assert total == 0

    def test_create_stores_all_fields(self) -> None:
        doc = run(
            self.repo.create("x1", "report.docx", 2048, "application/docx", "Annual report", "ingested", 10)
        )
        assert doc["size"] == 2048
        assert doc["content_type"] == "application/docx"
        assert doc["description"] == "Annual report"
        assert doc["status"] == "ingested"
        assert doc["chunks"] == 10
