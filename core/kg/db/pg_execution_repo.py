"""PostgreSQL-backed workflow execution repository."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class PgExecutionRepository:
    """PostgreSQL repository for workflow execution records."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def create(self, execution: dict[str, Any]) -> dict[str, Any]:
        """Insert a new execution record."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO workflow_executions
                       (id, workflow_id, status, trigger_type, started_at, finished_at, error_message, node_results)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)""",
                execution["id"],
                execution["workflow_id"],
                execution["status"],
                execution["trigger_type"],
                execution.get("started_at", datetime.now(timezone.utc)),
                execution.get("finished_at"),
                execution.get("error_message", ""),
                json.dumps(execution.get("node_results", {})),
            )
        return execution

    async def update(self, execution_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update an execution record."""
        sets = []
        values = []
        idx = 1

        for key in ["status", "finished_at", "error_message"]:
            if key in data:
                idx += 1
                sets.append(f"{key} = ${idx}")
                values.append(data[key])

        if "node_results" in data:
            idx += 1
            sets.append(f"node_results = ${idx}::jsonb")
            values.append(json.dumps(data["node_results"]))

        if not sets:
            return await self.get(execution_id)

        query = f"UPDATE workflow_executions SET {', '.join(sets)} WHERE id = $1 RETURNING *"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, execution_id, *values)

        if row is None:
            return None
        return self._row_to_dict(row)

    async def get(self, execution_id: str) -> dict[str, Any] | None:
        """Get a single execution by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_executions WHERE id = $1", execution_id
            )
        if row is None:
            return None
        return self._row_to_dict(row)

    async def list_by_workflow(
        self, workflow_id: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List executions for a workflow, newest first."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM workflow_executions
                   WHERE workflow_id = $1
                   ORDER BY started_at DESC
                   LIMIT $2 OFFSET $3""",
                workflow_id, limit, offset,
            )
        return [self._row_to_dict(r) for r in rows]

    async def delete(self, execution_id: str) -> bool:
        """Delete an execution record."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM workflow_executions WHERE id = $1 RETURNING id",
                execution_id,
            )
        return row is not None

    async def count_by_workflow(self, workflow_id: str) -> int:
        """Count executions for a workflow."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM workflow_executions WHERE workflow_id = $1",
                workflow_id,
            )
        return row["cnt"] if row else 0

    async def count_running_by_workflow(self, workflow_id: str) -> int:
        """Count running/pending executions for a workflow."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM workflow_executions WHERE workflow_id = $1 AND status IN ('running', 'pending')",
                workflow_id,
            )
        return row["cnt"] if row else 0

    async def count_running_total(self) -> int:
        """Count all running/pending executions."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM workflow_executions WHERE status IN ('running', 'pending')"
            )
        return row["cnt"] if row else 0

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        node_results = row["node_results"]
        if isinstance(node_results, str):
            node_results = json.loads(node_results)
        started_at = row["started_at"]
        finished_at = row["finished_at"]
        return {
            "id": row["id"],
            "workflow_id": row["workflow_id"],
            "status": row["status"],
            "trigger_type": row["trigger_type"],
            "started_at": started_at.isoformat() if hasattr(started_at, "isoformat") else started_at,
            "finished_at": finished_at.isoformat() if finished_at and hasattr(finished_at, "isoformat") else finished_at,
            "error_message": row["error_message"],
            "node_results": node_results,
        }
