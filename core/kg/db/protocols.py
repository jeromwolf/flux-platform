"""Repository protocol definitions for the database layer.

Protocols define the interface contract; concrete implementations
(in-memory or PostgreSQL) must satisfy these signatures.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WorkflowRepository(Protocol):
    """Protocol for workflow persistence.

    Implementations may use in-memory storage (development/testing)
    or a relational backend such as PostgreSQL (production).
    """

    async def create(
        self,
        wf_id: str,
        name: str,
        description: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        viewport: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist a new workflow record.

        Args:
            wf_id: Unique identifier for the workflow (short UUID).
            name: Human-readable workflow name.
            description: Optional description text.
            nodes: VueFlow node list serialised as dicts.
            edges: VueFlow edge list serialised as dicts.
            viewport: VueFlow viewport state (x, y, zoom).

        Returns:
            Full workflow record including ``created_at`` / ``updated_at``.
        """
        ...

    async def get(self, wf_id: str) -> dict[str, Any] | None:
        """Retrieve a single workflow by ID.

        Args:
            wf_id: Unique workflow identifier.

        Returns:
            Workflow record dict, or None if not found.
        """
        ...

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all stored workflows.

        Returns:
            List of workflow record dicts (may be empty).
        """
        ...

    async def update(
        self,
        wf_id: str,
        name: str,
        description: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        viewport: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Replace workflow content (full update semantics).

        Args:
            wf_id: Unique workflow identifier.
            name: New name.
            description: New description.
            nodes: New node list.
            edges: New edge list.
            viewport: New viewport state.

        Returns:
            Updated workflow record, or None if wf_id does not exist.
        """
        ...

    async def delete(self, wf_id: str) -> bool:
        """Remove a workflow by ID.

        Args:
            wf_id: Unique workflow identifier.

        Returns:
            True if the record existed and was deleted, False otherwise.
        """
        ...


@runtime_checkable
class DocumentRepository(Protocol):
    """Protocol for document metadata persistence.

    Tracks uploaded document metadata; binary content is stored separately
    in object storage (MinIO / S3).
    """

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
        """Persist a new document metadata record.

        Args:
            doc_id: SHA-256 prefix identifier derived from file content.
            filename: Original uploaded filename.
            size: File size in bytes.
            content_type: MIME type of the uploaded file.
            description: Optional human-readable description.
            status: Ingestion status (e.g. ``"uploaded"``, ``"ingested"``).
            chunks: Number of RAG chunks created during ingestion.

        Returns:
            Full document metadata record including ``created_at``.
        """
        ...

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
            Tuple of (document list, total count).
        """
        ...

    async def delete(self, doc_id: str) -> bool:
        """Remove a document metadata record by ID.

        Args:
            doc_id: SHA-256 prefix identifier.

        Returns:
            True if the record existed and was deleted, False otherwise.
        """
        ...
