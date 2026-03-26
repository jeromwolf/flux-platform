"""PostgreSQL-backed document metadata repository.

Satisfies the :class:`~kg.db.protocols.DocumentRepository` protocol using
an asyncpg connection pool for all persistence operations.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class PgDocumentRepository:
    """PostgreSQL implementation of DocumentRepository.

    Requires an ``asyncpg.Pool`` obtained from
    :func:`kg.db.connection.get_pg_pool`.  Binary file content is **not**
    managed here; callers are responsible for storing content in object
    storage (MinIO / S3) before calling :meth:`create`.

    Example::

        pool = await get_pg_pool()
        repo = PgDocumentRepository(pool)
        doc = await repo.create("abc123", "report.pdf", 1024,
                                "application/pdf", "", "uploaded", 0)
        docs, total = await repo.list()
        assert total == 1
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

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

        Uses ``INSERT ... ON CONFLICT (id) DO UPDATE`` semantics so that
        re-uploading a file with the same SHA-256 prefix updates metadata
        rather than raising a unique-constraint violation.

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
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO documents
                       (id, filename, size, content_type, description, status, chunks, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (id) DO UPDATE SET
                       filename     = EXCLUDED.filename,
                       description  = EXCLUDED.description,
                       status       = EXCLUDED.status,
                       chunks       = EXCLUDED.chunks""",
                doc_id,
                filename,
                size,
                content_type,
                description,
                status,
                chunks,
                now,
            )
        return {
            "id": doc_id,
            "filename": filename,
            "size": size,
            "content_type": content_type,
            "description": description,
            "status": status,
            "chunks": chunks,
            "created_at": now.isoformat(),
        }

    async def list(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a paginated slice of document records.

        Uses a window function to retrieve the total count in a single
        query, avoiding a separate ``COUNT(*)`` round-trip.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip before returning.

        Returns:
            Tuple of (document list slice, total count of all documents).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT *, count(*) OVER() AS total_count
                   FROM documents
                   ORDER BY created_at DESC
                   LIMIT $1 OFFSET $2""",
                limit,
                offset,
            )
        if not rows:
            return [], 0
        total = int(rows[0]["total_count"])
        docs = [self._row_to_dict(r) for r in rows]
        return docs, total

    async def delete(self, doc_id: str) -> bool:
        """Remove a document metadata record by ID.

        Args:
            doc_id: SHA-256 prefix identifier.

        Returns:
            ``True`` if the record existed and was deleted, ``False`` otherwise.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM documents WHERE id = $1 RETURNING id", doc_id
            )
        return row is not None

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """Convert an asyncpg ``Record`` to a plain dict.

        Strips the synthetic ``total_count`` window-function column if
        present so callers receive a clean document record.

        Args:
            row: An asyncpg ``Record`` (or any mapping) representing a document row.

        Returns:
            Plain ``dict`` with an ISO-formatted ``created_at`` string.
        """
        created_at = row["created_at"]
        return {
            "id": row["id"],
            "filename": row["filename"],
            "size": row["size"],
            "content_type": row["content_type"],
            "description": row["description"],
            "status": row["status"],
            "chunks": row["chunks"],
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        }
