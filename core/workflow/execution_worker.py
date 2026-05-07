"""Redis-backed workflow execution worker.

Replaces in-process asyncio.create_task with a durable queue that
survives gateway restarts. Uses Redis LIST as a simple task queue.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

REDIS_QUEUE_KEY = "imsp:workflow:execution_queue"
DEFAULT_MAX_WORKERS = 5


class ExecutionWorker:
    """Redis-backed workflow execution worker.

    Consumes execution tasks from a Redis list and runs them with
    configurable concurrency. Recovers pending/running tasks on startup.

    Args:
        execution_repo: Repository for execution persistence.
        workflow_repo: Repository for loading workflow definitions.
        redis_url: Redis connection URL.
        max_workers: Maximum concurrent executions.
        ws_manager: Optional WebSocket manager for status push.
    """

    def __init__(
        self,
        execution_repo: Any = None,
        workflow_repo: Any = None,
        redis_url: str = "",
        max_workers: int = DEFAULT_MAX_WORKERS,
        ws_manager: Any = None,
    ) -> None:
        self._execution_repo = execution_repo
        self._workflow_repo = workflow_repo
        self._redis_url = redis_url or os.environ.get(
            "REDIS_URL", "redis://localhost:6379/1"
        )
        self._max_workers = max_workers
        self._ws_manager = ws_manager
        self._redis: Any = None
        self._running = False
        self._consumer_task: asyncio.Task | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._active_tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        """Start the execution worker. Connect to Redis and begin consuming."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            await self._redis.ping()
            logger.info("Execution worker connected to Redis")
        except Exception as exc:
            logger.warning(
                "Redis not available for execution worker: %s. "
                "Falling back to in-process mode.",
                exc,
            )
            self._redis = None

        self._running = True
        self._semaphore = asyncio.Semaphore(self._max_workers)

        # Recover stale executions
        await self._recover_stale_executions()

        # Start consumer loop
        if self._redis:
            self._consumer_task = asyncio.create_task(
                self._consume_loop(),
                name="execution-worker-consumer",
            )

        logger.info(
            "Execution worker started (max_workers=%d, redis=%s)",
            self._max_workers,
            "connected" if self._redis else "in-process",
        )

    async def stop(self) -> None:
        """Stop the worker gracefully. Wait for active tasks to complete."""
        self._running = False

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        # Wait for active tasks (with timeout)
        if self._active_tasks:
            logger.info(
                "Waiting for %d active execution(s) to complete...",
                len(self._active_tasks),
            )
            done, pending = await asyncio.wait(
                self._active_tasks.values(),
                timeout=30.0,
            )
            for task in pending:
                task.cancel()

        if self._redis:
            await self._redis.close()

        logger.info("Execution worker stopped")

    async def enqueue(
        self,
        execution_id: str,
        workflow_id: str,
        trigger_type: str = "manual",
        initial_data: list[dict[str, Any]] | None = None,
    ) -> None:
        """Enqueue a workflow execution.

        Args:
            execution_id: Unique execution identifier.
            workflow_id: Workflow to execute.
            trigger_type: How it was triggered.
            initial_data: Optional initial data for source nodes.
        """
        task_payload = json.dumps({
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "trigger_type": trigger_type,
            "initial_data": initial_data,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        })

        if self._redis:
            await self._redis.lpush(REDIS_QUEUE_KEY, task_payload)
            logger.info("Execution enqueued to Redis: %s", execution_id)
        else:
            # Fallback: in-process execution
            await self._execute_task(json.loads(task_payload))

    async def _consume_loop(self) -> None:
        """Main consumer loop: BRPOP from Redis and execute."""
        while self._running:
            try:
                # BRPOP with 2s timeout to allow checking self._running
                result = await self._redis.brpop(REDIS_QUEUE_KEY, timeout=2)
                if result is None:
                    continue

                _, payload_str = result
                payload = json.loads(payload_str)

                # Acquire semaphore (limits concurrency)
                await self._semaphore.acquire()

                task = asyncio.create_task(
                    self._execute_with_semaphore(payload),
                    name=f"exec:{payload.get('execution_id', 'unknown')}",
                )
                exec_id = payload["execution_id"]
                self._active_tasks[exec_id] = task
                task.add_done_callback(
                    lambda t, eid=exec_id: self._active_tasks.pop(eid, None)
                )

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in execution consumer loop")
                await asyncio.sleep(1)

    async def _execute_with_semaphore(self, payload: dict[str, Any]) -> None:
        """Execute task and release semaphore when done."""
        try:
            await self._execute_task(payload)
        finally:
            self._semaphore.release()

    async def _execute_task(self, payload: dict[str, Any]) -> None:
        """Execute a single workflow task."""
        from core.workflow.executor import WorkflowExecutor
        from core.workflow.models import NodeStatus, TriggerType

        execution_id = payload["execution_id"]
        workflow_id = payload["workflow_id"]
        trigger_type_str = payload.get("trigger_type", "manual")
        initial_data = payload.get("initial_data")

        logger.info(
            "Starting execution: %s (workflow=%s)", execution_id, workflow_id
        )

        # Map trigger type
        trigger_map = {
            "manual": TriggerType.MANUAL,
            "schedule": TriggerType.SCHEDULE,
            "webhook": TriggerType.WEBHOOK,
            "event": TriggerType.EVENT,
        }
        trigger_type = trigger_map.get(trigger_type_str, TriggerType.MANUAL)

        # Load workflow
        if not self._workflow_repo:
            logger.error(
                "No workflow repo -- cannot execute %s", execution_id
            )
            return

        wf = await self._workflow_repo.get(workflow_id)
        if wf is None:
            logger.error("Workflow not found: %s", workflow_id)
            if self._execution_repo:
                await self._execution_repo.update(execution_id, {
                    "status": "error",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": f"Workflow {workflow_id} not found",
                })
            return

        # Create status callback for WebSocket push
        async def on_status_change(
            exec_id: str,
            node_id: str,
            status: NodeStatus,
            extra: dict,
        ) -> None:
            if self._ws_manager:
                try:
                    from gateway.ws.models import WSMessage, WSMessageType

                    msg = WSMessage(
                        type=WSMessageType.NODE_STATUS,
                        payload={
                            "execution_id": exec_id,
                            "node_id": node_id,
                            "status": status.value,
                            **extra,
                        },
                        room=f"execution:{exec_id}",
                    )
                    await self._ws_manager.broadcast_to_room(
                        f"workflow:{workflow_id}", msg
                    )
                except Exception:
                    pass

        # Execute
        executor = WorkflowExecutor(on_status_change=on_status_change)

        try:
            # Update status to running
            if self._execution_repo:
                await self._execution_repo.update(
                    execution_id, {"status": "running"}
                )

            result = await executor.execute(wf, trigger_type, initial_data)

            # Persist result
            if self._execution_repo:
                await self._execution_repo.update(execution_id, {
                    "status": result.status.value,
                    "finished_at": (
                        result.finished_at.isoformat()
                        if result.finished_at
                        else None
                    ),
                    "error_message": result.error_message,
                    "node_results": {
                        nid: nr.to_dict()
                        for nid, nr in result.node_results.items()
                    },
                })

            logger.info(
                "Execution completed: %s (status=%s)",
                execution_id,
                result.status.value,
            )

        except Exception as exc:
            logger.exception("Execution failed: %s", execution_id)
            if self._execution_repo:
                await self._execution_repo.update(execution_id, {
                    "status": "error",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": str(exc),
                })

    async def _recover_stale_executions(self) -> None:
        """Find executions stuck in 'running' or 'pending' and re-enqueue."""
        if not self._execution_repo:
            return

        try:
            stale = await self._get_stale_executions()
            if stale:
                logger.info("Recovering %d stale execution(s)", len(stale))
                for exec_data in stale:
                    await self.enqueue(
                        execution_id=exec_data["id"],
                        workflow_id=exec_data["workflow_id"],
                        trigger_type=exec_data.get("trigger_type", "manual"),
                    )
        except Exception:
            logger.warning(
                "Failed to recover stale executions", exc_info=True
            )

    async def _get_stale_executions(self) -> list[dict[str, Any]]:
        """Get executions that need recovery."""
        repo = self._execution_repo
        if hasattr(repo, "_pool"):
            # PG repo -- direct SQL query
            async with repo._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, workflow_id, trigger_type "
                    "FROM workflow_executions "
                    "WHERE status IN ('running', 'pending')"
                )
                return [dict(r) for r in rows]
        elif hasattr(repo, "_store"):
            # Memory repo
            return [
                e
                for e in repo._store.values()
                if e.get("status") in ("running", "pending")
            ]
        return []

    @property
    def active_count(self) -> int:
        """Number of currently running executions."""
        return len(self._active_tasks)

    @property
    def is_running(self) -> bool:
        """Whether the worker is currently running."""
        return self._running
