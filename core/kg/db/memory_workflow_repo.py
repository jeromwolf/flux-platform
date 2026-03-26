"""In-memory workflow repository implementation.

Used as a drop-in fallback when PostgreSQL is unavailable (local development,
unit tests).  Satisfies the :class:`~kg.db.protocols.WorkflowRepository`
protocol.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class InMemoryWorkflowRepository:
    """In-memory workflow repository (fallback when PostgreSQL unavailable).

    State is held in a plain dict keyed by workflow ID.  The repository is
    not thread-safe; use a single instance per event-loop or protect with an
    ``asyncio.Lock`` if accessed from multiple coroutines simultaneously.

    Example::

        repo = InMemoryWorkflowRepository()
        wf = await repo.create("abc123", "My Flow", "", [], [], {})
        assert await repo.get("abc123") == wf
    """

    def __init__(self) -> None:
        self._workflows: dict[str, dict[str, Any]] = {}

    async def create(
        self,
        wf_id: str,
        name: str,
        description: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        viewport: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist a new workflow record in memory.

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
        now = datetime.now(timezone.utc).isoformat()
        wf: dict[str, Any] = {
            "id": wf_id,
            "name": name,
            "description": description,
            "nodes": nodes,
            "edges": edges,
            "viewport": viewport,
            "created_at": now,
            "updated_at": now,
        }
        self._workflows[wf_id] = wf
        return wf

    async def get(self, wf_id: str) -> dict[str, Any] | None:
        """Retrieve a single workflow by ID.

        Args:
            wf_id: Unique workflow identifier.

        Returns:
            Workflow record dict, or None if not found.
        """
        return self._workflows.get(wf_id)

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all stored workflows.

        Returns:
            List of workflow record dicts (insertion order, may be empty).
        """
        return list(self._workflows.values())

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
            Updated workflow record dict, or None if wf_id does not exist.
        """
        if wf_id not in self._workflows:
            return None
        existing = self._workflows[wf_id]
        now = datetime.now(timezone.utc).isoformat()
        updated: dict[str, Any] = {
            "id": wf_id,
            "name": name,
            "description": description,
            "nodes": nodes,
            "edges": edges,
            "viewport": viewport,
            "created_at": existing["created_at"],
            "updated_at": now,
        }
        self._workflows[wf_id] = updated
        return updated

    async def delete(self, wf_id: str) -> bool:
        """Remove a workflow by ID.

        Args:
            wf_id: Unique workflow identifier.

        Returns:
            True if the record existed and was deleted, False otherwise.
        """
        return self._workflows.pop(wf_id, None) is not None

    def clear(self) -> None:
        """Remove all workflows from the store.

        Primarily used in test teardown to reset state between test cases.
        """
        self._workflows.clear()
