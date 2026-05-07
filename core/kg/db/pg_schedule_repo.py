"""PostgreSQL-backed schedule and webhook token repository.

Persists :class:`~core.workflow.scheduler.ScheduleConfig` entries and
webhook tokens so they survive process restarts.  Falls back gracefully
when the pool is ``None`` (all methods become no-ops that return empty
results).

Requires an ``asyncpg.Pool`` obtained from
:func:`kg.db.connection.get_pg_pool`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class PgScheduleRepository:
    """PostgreSQL repository for workflow schedules and webhook tokens.

    Example::

        pool = await get_pg_pool()
        repo = PgScheduleRepository(pool)
        await repo.create_schedule({
            "schedule_id": "abc123",
            "workflow_id": "wf01",
            "interval_seconds": 60,
        })
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    async def create_schedule(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Insert or upsert a schedule row.

        Args:
            schedule: Dict with at least ``schedule_id`` and ``workflow_id``.

        Returns:
            The same dict (pass-through for caller convenience).
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO workflow_schedules
                       (schedule_id, workflow_id, cron_expression,
                        interval_seconds, enabled, description, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (schedule_id) DO UPDATE SET
                       cron_expression  = EXCLUDED.cron_expression,
                       interval_seconds = EXCLUDED.interval_seconds,
                       enabled          = EXCLUDED.enabled,
                       description      = EXCLUDED.description""",
                schedule["schedule_id"],
                schedule["workflow_id"],
                schedule.get("cron_expression", ""),
                schedule.get("interval_seconds"),
                schedule.get("enabled", True),
                schedule.get("description", ""),
                schedule.get("created_at", datetime.now(timezone.utc)),
            )
        return schedule

    async def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        """Fetch a single schedule row by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_schedules WHERE schedule_id = $1",
                schedule_id,
            )
        return self._row_to_dict(row) if row else None

    async def list_schedules(
        self, workflow_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all schedule rows, optionally filtered by *workflow_id*."""
        async with self._pool.acquire() as conn:
            if workflow_id:
                rows = await conn.fetch(
                    "SELECT * FROM workflow_schedules WHERE workflow_id = $1 ORDER BY created_at",
                    workflow_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM workflow_schedules ORDER BY created_at"
                )
        return [self._row_to_dict(r) for r in rows]

    async def update_enabled(self, schedule_id: str, enabled: bool) -> bool:
        """Toggle the *enabled* flag on a schedule.

        Returns:
            ``True`` if the row existed and was updated.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE workflow_schedules SET enabled = $2 "
                "WHERE schedule_id = $1 RETURNING schedule_id",
                schedule_id,
                enabled,
            )
        return row is not None

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule row.

        Returns:
            ``True`` if the row existed and was deleted.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM workflow_schedules "
                "WHERE schedule_id = $1 RETURNING schedule_id",
                schedule_id,
            )
        return row is not None

    # ------------------------------------------------------------------
    # Webhook Tokens
    # ------------------------------------------------------------------

    async def create_token(self, token: str, workflow_id: str) -> dict[str, Any]:
        """Persist a new webhook token."""
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO webhook_tokens (token, workflow_id, created_at) "
                "VALUES ($1, $2, $3)",
                token,
                workflow_id,
                now,
            )
        return {
            "token": token,
            "workflow_id": workflow_id,
            "created_at": now.isoformat(),
        }

    async def validate_token(self, workflow_id: str, token: str) -> bool:
        """Check whether *token* belongs to *workflow_id*."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT token FROM webhook_tokens "
                "WHERE token = $1 AND workflow_id = $2",
                token,
                workflow_id,
            )
        return row is not None

    async def revoke_token(self, token: str) -> bool:
        """Delete a webhook token.

        Returns:
            ``True`` if the token existed and was revoked.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM webhook_tokens WHERE token = $1 RETURNING token",
                token,
            )
        return row is not None

    async def list_tokens(self, workflow_id: str) -> list[str]:
        """Return all token strings for a given workflow."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT token FROM webhook_tokens WHERE workflow_id = $1",
                workflow_id,
            )
        return [r["token"] for r in rows]

    async def get_workflow_id(self, token: str) -> str | None:
        """Resolve a token to its owning workflow_id."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT workflow_id FROM webhook_tokens WHERE token = $1",
                token,
            )
        return row["workflow_id"] if row else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """Convert an asyncpg ``Record`` to a plain dict."""
        created_at = row["created_at"]
        return {
            "schedule_id": row["schedule_id"],
            "workflow_id": row["workflow_id"],
            "cron_expression": row["cron_expression"],
            "interval_seconds": row["interval_seconds"],
            "enabled": row["enabled"],
            "description": row["description"],
            "created_at": (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else created_at
            ),
        }
