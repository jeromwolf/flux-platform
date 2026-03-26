"""In-memory document metadata repository implementation.

Used as a drop-in fallback when PostgreSQL / MinIO are unavailable (local
development, unit tests).  Satisfies the
:class:`~kg.db.protocols.DocumentRepository` protocol.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class InMemoryDocumentRepository:
    """In-memory document repository (fallback when PostgreSQL unavailable).

    Metadata records are stored in an ordered list.  Binary file content is
    **not** managed here; callers are responsible for storing content in
    object storage (MinIO / S3) before calling :meth:`create`.

    Example::

        repo = InMemoryDocumentRepository()
        doc = await repo.create("abc123", "report.pdf", 1024,
                                "application/pdf", "", "uploaded", 0)
        docs, total = await repo.list()
        assert total == 1
    """

    def __init__(self) -> None:
        self._documents: list[dict[str, Any]] = []

    async def create(
        self,
        doc_id: str,
        filename: str,
        size: int,
        content_type: str,
        description: str,
        status: str,
        chunks: int,
    ) -> dict[str, Any]:
        """Persist a new document metadata record in memory.

        Args:
            doc_id: SHA-256 prefix identifier derived from file content.
            filename: Original uploaded filename.
            size: File size in bytes.
            content_type: MIME type of the uploaded file.
            description: Optional human-readable description.
            status: Ingestion status (e.g. ``"uploaded"``, ``"ingested"``).
            chunks: Number of RAG chunks created during ingestion.

        Returns:
            Full document metadata dict including ``created_at``.
        """
        doc: dict[str, Any] = {
            "id": doc_id,
            "filename": filename,
            "size": size,
            "content_type": content_type,
            "description": description,
            "status": status,
            "chunks": chunks,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # UPSERT semantics: remove any existing entry with same doc_id
        self._documents = [d for d in self._documents if d["id"] != doc_id]
        self._documents.append(doc)
        return doc

    async def list(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a paginated slice of document records.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip before returning.

        Returns:
            Tuple of (document list slice, total count of all documents).
        """
        total = len(self._documents)
        return self._documents[offset : offset + limit], total

    async def delete(self, doc_id: str) -> bool:
        """Remove a document metadata record by ID.

        Args:
            doc_id: SHA-256 prefix identifier.

        Returns:
            True if the record existed and was deleted, False otherwise.
        """
        before = len(self._documents)
        self._documents = [d for d in self._documents if d["id"] != doc_id]
        return len(self._documents) < before

    def clear(self) -> None:
        """Remove all document records from the store.

        Primarily used in test teardown to reset state between test cases.
        """
        self._documents.clear()
