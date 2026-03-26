"""PostgreSQL-backed workflow repository.

Satisfies the :class:`~kg.db.protocols.WorkflowRepository` protocol using
an asyncpg connection pool for all persistence operations.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class PgWorkflowRepository:
    """PostgreSQL implementation of WorkflowRepository.

    Requires an ``asyncpg.Pool`` obtained from
    :func:`kg.db.connection.get_pg_pool`.  All operations acquire a
    connection from the pool and release it automatically via the async
    context manager.

    Example::

        pool = await get_pg_pool()
        repo = PgWorkflowRepository(pool)
        wf = await repo.create("abc123", "My Flow", "", [], [], {})
        assert await repo.get("abc123") == wf
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

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
            Full workflow record dict including ``created_at`` / ``updated_at``.
        """
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO workflows
                       (id, name, description, nodes, edges, viewport, created_at, updated_at)
                   VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7, $8)
                   ON CONFLICT (id) DO UPDATE SET
                       name = EXCLUDED.name,
                       description = EXCLUDED.description,
                       nodes = EXCLUDED.nodes,
                       edges = EXCLUDED.edges,
                       viewport = EXCLUDED.viewport,
                       updated_at = EXCLUDED.updated_at""",
                wf_id,
                name,
                description,
                json.dumps(nodes),
                json.dumps(edges),
                json.dumps(viewport),
                now,
                now,
            )
        return {
            "id": wf_id,
            "name": name,
            "description": description,
            "nodes": nodes,
            "edges": edges,
            "viewport": viewport,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    async def get(self, wf_id: str) -> dict[str, Any] | None:
        """Retrieve a single workflow by ID.

        Args:
            wf_id: Unique workflow identifier.

        Returns:
            Workflow record dict, or ``None`` if not found.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflows WHERE id = $1", wf_id
            )
        if row is None:
            return None
        return self._row_to_dict(row)

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all stored workflows ordered by last update (descending).

        Returns:
            List of workflow record dicts (may be empty).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM workflows ORDER BY updated_at DESC"
            )
        return [self._row_to_dict(r) for r in rows]

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

        Preserves the original ``created_at`` timestamp and refreshes
        ``updated_at`` to the current UTC time.

        Args:
            wf_id: Unique workflow identifier.
            name: New name.
            description: New description.
            nodes: New node list.
            edges: New edge list.
            viewport: New viewport state.

        Returns:
            Updated workflow record dict, or ``None`` if wf_id does not exist.
        """
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE workflows
                   SET name        = $2,
                       description = $3,
                       nodes       = $4::jsonb,
                       edges       = $5::jsonb,
                       viewport    = $6::jsonb,
                       updated_at  = $7
                   WHERE id = $1
                   RETURNING *""",
                wf_id,
                name,
                description,
                json.dumps(nodes),
                json.dumps(edges),
                json.dumps(viewport),
                now,
            )
        if row is None:
            return None
        return self._row_to_dict(row)

    async def delete(self, wf_id: str) -> bool:
        """Remove a workflow by ID.

        Args:
            wf_id: Unique workflow identifier.

        Returns:
            ``True`` if the record existed and was deleted, ``False`` otherwise.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM workflows WHERE id = $1 RETURNING id", wf_id
            )
        return row is not None

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """Convert an asyncpg ``Record`` to a plain dict.

        asyncpg returns JSONB columns as already-parsed Python objects; this
        method also handles the edge case where they arrive as raw JSON strings
        (e.g. when using a mock or alternative driver).

        Args:
            row: An asyncpg ``Record`` (or any mapping) representing a workflow row.

        Returns:
            Plain ``dict`` with ISO-formatted timestamp strings.
        """
        nodes = row["nodes"]
        edges = row["edges"]
        viewport = row["viewport"]
        if isinstance(nodes, str):
            nodes = json.loads(nodes)
        if isinstance(edges, str):
            edges = json.loads(edges)
        if isinstance(viewport, str):
            viewport = json.loads(viewport)
        created_at = row["created_at"]
        updated_at = row["updated_at"]
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "nodes": nodes,
            "edges": edges,
            "viewport": viewport,
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
            "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
        }
