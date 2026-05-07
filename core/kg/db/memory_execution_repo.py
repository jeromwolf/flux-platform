"""In-memory execution repository for testing/development."""
from __future__ import annotations

from typing import Any


class InMemoryExecutionRepository:
    """In-memory execution repository (no persistence)."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def create(self, execution: dict[str, Any]) -> dict[str, Any]:
        self._store[execution["id"]] = execution
        return execution

    async def update(self, execution_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if execution_id not in self._store:
            return None
        self._store[execution_id].update(data)
        return self._store[execution_id]

    async def get(self, execution_id: str) -> dict[str, Any] | None:
        return self._store.get(execution_id)

    async def list_by_workflow(
        self, workflow_id: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        results = [
            e for e in self._store.values() if e.get("workflow_id") == workflow_id
        ]
        results.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return results[offset:offset + limit]

    async def delete(self, execution_id: str) -> bool:
        if execution_id in self._store:
            del self._store[execution_id]
            return True
        return False

    async def count_by_workflow(self, workflow_id: str) -> int:
        return sum(1 for e in self._store.values() if e.get("workflow_id") == workflow_id)

    async def count_running_by_workflow(self, workflow_id: str) -> int:
        """Count running/pending executions for a workflow."""
        return sum(
            1 for e in self._store.values()
            if e.get("workflow_id") == workflow_id and e.get("status") in ("running", "pending")
        )

    async def count_running_total(self) -> int:
        """Count all running/pending executions."""
        return sum(
            1 for e in self._store.values()
            if e.get("status") in ("running", "pending")
        )
