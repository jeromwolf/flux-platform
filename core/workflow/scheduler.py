"""Workflow scheduler — APScheduler-based cron/interval triggers.

Supports optional PostgreSQL persistence via *schedule_repo* / *token_repo*
parameters.  When no repository is provided, all state lives in memory only
(original behaviour preserved as fallback).
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduleConfig:
    """Configuration for a scheduled workflow execution."""

    schedule_id: str = field(default_factory=lambda: uuid4().hex[:12])
    workflow_id: str = ""
    cron_expression: str = ""  # Standard cron: "*/5 * * * *"
    interval_seconds: int | None = None  # Alternative: run every N seconds
    enabled: bool = True
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowScheduler:
    """Manages scheduled workflow executions.

    Uses asyncio-based scheduling (no external dependency).
    When *schedule_repo* is provided, schedule configs are persisted to
    PostgreSQL and reloaded on :meth:`start`.

    Args:
        execute_fn: Async function to call when schedule triggers.
            Signature: (workflow_id: str, trigger_type: str) -> None
        schedule_repo: Optional PgScheduleRepository for persistence.
    """

    def __init__(
        self,
        execute_fn: Callable[[str, str], Awaitable[None]] | None = None,
        schedule_repo: Any | None = None,
    ) -> None:
        self._execute_fn = execute_fn
        self._schedule_repo = schedule_repo
        self._schedules: dict[str, ScheduleConfig] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self) -> None:
        """Start the scheduler.

        If a PG repo is available, reloads persisted schedules first,
        then resumes all enabled ones.
        """
        if self._schedule_repo is not None:
            await self._load_from_db()
        self._running = True
        logger.info("Workflow scheduler started (%d schedules)", len(self._schedules))
        for schedule in self._schedules.values():
            if schedule.enabled:
                self._start_schedule_task(schedule)

    async def stop(self) -> None:
        """Stop the scheduler and cancel all running tasks."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        logger.info("Workflow scheduler stopped")

    async def add_schedule(self, config: ScheduleConfig) -> ScheduleConfig:
        """Add a new schedule.

        Args:
            config: Schedule configuration.

        Returns:
            The added ScheduleConfig.

        Raises:
            ValueError: If cron_expression and interval_seconds are both empty.
        """
        if not config.cron_expression and not config.interval_seconds:
            raise ValueError("Either cron_expression or interval_seconds must be set")

        self._schedules[config.schedule_id] = config

        # Persist to PostgreSQL if available
        if self._schedule_repo is not None:
            try:
                await self._schedule_repo.create_schedule(
                    self._config_to_dict(config)
                )
            except Exception:
                logger.exception("Failed to persist schedule to PG: %s", config.schedule_id)

        if self._running and config.enabled:
            self._start_schedule_task(config)

        logger.info(
            "Schedule added: id=%s workflow=%s cron=%s interval=%s",
            config.schedule_id,
            config.workflow_id,
            config.cron_expression,
            config.interval_seconds,
        )
        return config

    async def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule by ID."""
        if schedule_id not in self._schedules:
            return False

        # Cancel running task
        if schedule_id in self._tasks:
            self._tasks[schedule_id].cancel()
            del self._tasks[schedule_id]

        del self._schedules[schedule_id]

        # Remove from PostgreSQL if available
        if self._schedule_repo is not None:
            try:
                await self._schedule_repo.delete_schedule(schedule_id)
            except Exception:
                logger.exception("Failed to delete schedule from PG: %s", schedule_id)

        logger.info("Schedule removed: id=%s", schedule_id)
        return True

    async def enable_schedule(self, schedule_id: str) -> bool:
        """Enable a paused schedule."""
        if schedule_id not in self._schedules:
            return False

        old = self._schedules[schedule_id]
        self._schedules[schedule_id] = ScheduleConfig(
            schedule_id=old.schedule_id,
            workflow_id=old.workflow_id,
            cron_expression=old.cron_expression,
            interval_seconds=old.interval_seconds,
            enabled=True,
            description=old.description,
            created_at=old.created_at,
        )

        # Persist to PostgreSQL if available
        if self._schedule_repo is not None:
            try:
                await self._schedule_repo.update_enabled(schedule_id, True)
            except Exception:
                logger.exception("Failed to update schedule enabled in PG: %s", schedule_id)

        if self._running:
            self._start_schedule_task(self._schedules[schedule_id])
        return True

    async def disable_schedule(self, schedule_id: str) -> bool:
        """Disable (pause) a schedule."""
        if schedule_id not in self._schedules:
            return False

        old = self._schedules[schedule_id]
        self._schedules[schedule_id] = ScheduleConfig(
            schedule_id=old.schedule_id,
            workflow_id=old.workflow_id,
            cron_expression=old.cron_expression,
            interval_seconds=old.interval_seconds,
            enabled=False,
            description=old.description,
            created_at=old.created_at,
        )

        # Persist to PostgreSQL if available
        if self._schedule_repo is not None:
            try:
                await self._schedule_repo.update_enabled(schedule_id, False)
            except Exception:
                logger.exception("Failed to update schedule disabled in PG: %s", schedule_id)

        if schedule_id in self._tasks:
            self._tasks[schedule_id].cancel()
            del self._tasks[schedule_id]
        return True

    def get_schedule(self, schedule_id: str) -> ScheduleConfig | None:
        """Get a schedule by ID."""
        return self._schedules.get(schedule_id)

    def list_schedules(self, workflow_id: str | None = None) -> list[ScheduleConfig]:
        """List all schedules, optionally filtered by workflow_id."""
        schedules = list(self._schedules.values())
        if workflow_id:
            schedules = [s for s in schedules if s.workflow_id == workflow_id]
        return schedules

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    async def _load_from_db(self) -> None:
        """Populate in-memory schedule dict from PostgreSQL."""
        try:
            rows = await self._schedule_repo.list_schedules()
            for row in rows:
                created_at = row.get("created_at")
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                elif created_at is None:
                    created_at = datetime.now(timezone.utc)
                config = ScheduleConfig(
                    schedule_id=row["schedule_id"],
                    workflow_id=row["workflow_id"],
                    cron_expression=row.get("cron_expression", ""),
                    interval_seconds=row.get("interval_seconds"),
                    enabled=row.get("enabled", True),
                    description=row.get("description", ""),
                    created_at=created_at,
                )
                self._schedules[config.schedule_id] = config
            logger.info("Loaded %d schedules from PostgreSQL", len(rows))
        except Exception:
            logger.exception("Failed to load schedules from PostgreSQL")

    @staticmethod
    def _config_to_dict(config: ScheduleConfig) -> dict[str, Any]:
        """Convert a ScheduleConfig to a plain dict for persistence."""
        return {
            "schedule_id": config.schedule_id,
            "workflow_id": config.workflow_id,
            "cron_expression": config.cron_expression,
            "interval_seconds": config.interval_seconds,
            "enabled": config.enabled,
            "description": config.description,
            "created_at": config.created_at,
        }

    # ------------------------------------------------------------------
    # Asyncio task management
    # ------------------------------------------------------------------

    def _start_schedule_task(self, config: ScheduleConfig) -> None:
        """Start an asyncio task for a schedule."""
        if config.schedule_id in self._tasks:
            self._tasks[config.schedule_id].cancel()

        if config.interval_seconds:
            task = asyncio.create_task(
                self._interval_loop(config),
                name=f"schedule:{config.schedule_id}",
            )
        elif config.cron_expression:
            task = asyncio.create_task(
                self._cron_loop(config),
                name=f"schedule:{config.schedule_id}",
            )
        else:
            return

        self._tasks[config.schedule_id] = task

    async def _interval_loop(self, config: ScheduleConfig) -> None:
        """Run workflow at fixed intervals."""
        try:
            while self._running:
                await asyncio.sleep(config.interval_seconds or 60)
                if not self._running:
                    break
                await self._trigger(config)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Interval schedule error: %s", config.schedule_id)

    async def _cron_loop(self, config: ScheduleConfig) -> None:
        """Run workflow on cron schedule (simplified: check every 60s)."""
        try:
            while self._running:
                next_run = self._next_cron_time(config.cron_expression)
                wait_seconds = max(
                    0, (next_run - datetime.now(timezone.utc)).total_seconds()
                )
                await asyncio.sleep(wait_seconds)
                if not self._running:
                    break
                await self._trigger(config)
                # Wait at least 60s to avoid double-firing
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Cron schedule error: %s", config.schedule_id)

    async def _trigger(self, config: ScheduleConfig) -> None:
        """Trigger a workflow execution."""
        logger.info(
            "Schedule triggered: id=%s workflow=%s",
            config.schedule_id,
            config.workflow_id,
        )
        if self._execute_fn:
            try:
                await self._execute_fn(config.workflow_id, "schedule")
            except Exception:
                logger.exception(
                    "Scheduled execution failed: workflow=%s", config.workflow_id
                )

    @staticmethod
    def _next_cron_time(cron_expr: str) -> datetime:
        """Calculate next cron execution time (simplified parser).

        Supports: "*/N * * * *" (every N minutes), "0 N * * *" (daily at hour N).
        Falls back to 60s from now for complex expressions.
        """
        now = datetime.now(timezone.utc)
        parts = cron_expr.strip().split()

        if len(parts) >= 5:
            minute_part = parts[0]
            hour_part = parts[1]

            # Every N minutes: */N * * * *
            match = re.match(r"\*/(\d+)", minute_part)
            if match:
                interval = int(match.group(1))
                next_minute = ((now.minute // interval) + 1) * interval
                if next_minute >= 60:
                    next_time = now.replace(
                        minute=next_minute % 60, second=0, microsecond=0
                    )
                    next_time = next_time.replace(hour=(now.hour + 1) % 24)
                else:
                    next_time = now.replace(minute=next_minute, second=0, microsecond=0)
                return next_time

            # Daily at specific hour: 0 H * * *
            if minute_part.isdigit() and hour_part.isdigit():
                target_hour = int(hour_part)
                target_minute = int(minute_part)
                next_time = now.replace(
                    hour=target_hour, minute=target_minute, second=0, microsecond=0
                )
                if next_time <= now:
                    next_time += timedelta(days=1)
                return next_time

        # Fallback: 60 seconds from now
        return now + timedelta(seconds=60)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_count(self) -> int:
        return len(self._tasks)


# --- Webhook Token Management ---


class WebhookTokenManager:
    """Manages webhook tokens for workflow triggering.

    Each workflow can have one or more webhook URLs that trigger execution
    when called from external services.

    When *token_repo* is provided, tokens are persisted to PostgreSQL and
    the in-memory cache is used as a fast read-through layer.

    Args:
        token_repo: Optional PgScheduleRepository for persistence.
    """

    def __init__(self, token_repo: Any | None = None) -> None:
        self._token_repo = token_repo
        # Maps token -> workflow_id
        self._tokens: dict[str, str] = {}
        # Maps workflow_id -> set of tokens
        self._workflow_tokens: dict[str, set[str]] = {}

    async def load_from_db(self) -> None:
        """Populate in-memory cache from PostgreSQL.

        Called once at startup so that hot-path lookups hit memory.
        """
        if self._token_repo is None:
            return
        try:
            # Iterate all tokens via PG (no single "list_all" method, so we
            # use a raw query through the repo's pool).
            async with self._token_repo._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT token, workflow_id FROM webhook_tokens"
                )
            for row in rows:
                token = row["token"]
                wf_id = row["workflow_id"]
                self._tokens[token] = wf_id
                if wf_id not in self._workflow_tokens:
                    self._workflow_tokens[wf_id] = set()
                self._workflow_tokens[wf_id].add(token)
            logger.info("Loaded %d webhook tokens from PostgreSQL", len(rows))
        except Exception:
            logger.exception("Failed to load webhook tokens from PostgreSQL")

    async def create_token(self, workflow_id: str) -> str:
        """Create a new webhook token for a workflow.

        Returns:
            The generated token string.
        """
        token = uuid4().hex[:24]
        self._tokens[token] = workflow_id
        if workflow_id not in self._workflow_tokens:
            self._workflow_tokens[workflow_id] = set()
        self._workflow_tokens[workflow_id].add(token)

        # Persist to PostgreSQL if available
        if self._token_repo is not None:
            try:
                await self._token_repo.create_token(token, workflow_id)
            except Exception:
                logger.exception("Failed to persist webhook token to PG")

        logger.info("Webhook token created for workflow=%s", workflow_id)
        return token

    async def validate_token(self, workflow_id: str, token: str) -> bool:
        """Check if a token is valid for the given workflow."""
        # Fast path: check in-memory cache
        if self._tokens.get(token) == workflow_id:
            return True
        # Slow path: check PG if available (handles tokens added by other instances)
        if self._token_repo is not None:
            try:
                valid = await self._token_repo.validate_token(workflow_id, token)
                if valid:
                    # Backfill cache
                    self._tokens[token] = workflow_id
                    if workflow_id not in self._workflow_tokens:
                        self._workflow_tokens[workflow_id] = set()
                    self._workflow_tokens[workflow_id].add(token)
                return valid
            except Exception:
                logger.exception("Failed to validate token from PG")
        return False

    async def revoke_token(self, token: str) -> bool:
        """Revoke a webhook token."""
        workflow_id = self._tokens.pop(token, None)
        if workflow_id and workflow_id in self._workflow_tokens:
            self._workflow_tokens[workflow_id].discard(token)

        # Remove from PostgreSQL if available
        if self._token_repo is not None:
            try:
                return await self._token_repo.revoke_token(token)
            except Exception:
                logger.exception("Failed to revoke token from PG")

        return workflow_id is not None

    async def get_workflow_tokens(self, workflow_id: str) -> list[str]:
        """Get all tokens for a workflow."""
        # If PG is available, authoritative answer comes from there
        if self._token_repo is not None:
            try:
                return await self._token_repo.list_tokens(workflow_id)
            except Exception:
                logger.exception("Failed to list tokens from PG")
        return list(self._workflow_tokens.get(workflow_id, set()))

    async def get_workflow_id(self, token: str) -> str | None:
        """Look up workflow_id by token."""
        # Fast path: memory cache
        wf_id = self._tokens.get(token)
        if wf_id is not None:
            return wf_id
        # Slow path: PG lookup
        if self._token_repo is not None:
            try:
                wf_id = await self._token_repo.get_workflow_id(token)
                if wf_id is not None:
                    # Backfill cache
                    self._tokens[token] = wf_id
                    if wf_id not in self._workflow_tokens:
                        self._workflow_tokens[wf_id] = set()
                    self._workflow_tokens[wf_id].add(token)
                return wf_id
            except Exception:
                logger.exception("Failed to get workflow_id from PG")
        return None
