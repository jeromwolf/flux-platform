"""File-based persistent memory provider."""
from __future__ import annotations

import json
from pathlib import Path

from agent.memory.models import MemoryEntry, MemoryType


class FileMemoryProvider:
    """Persists conversation memory to JSON files, one per session.

    Each session is stored as a separate JSON file under *storage_dir*.
    The provider caches loaded sessions in memory to avoid redundant
    disk reads, and writes back on every ``add`` call.

    Args:
        storage_dir: Directory where session JSON files are stored.
        max_messages: Maximum number of messages to retain per session.
            Older messages are evicted when the limit is exceeded.
    """

    def __init__(
        self,
        storage_dir: str = ".imsp/memory",
        max_messages: int = 100,
    ) -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._max_messages = max_messages
        self._sessions: dict[str, list[MemoryEntry]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _session_path(self, session_id: str) -> Path:
        """Return the file path for *session_id*, sanitising special chars."""
        safe_id = session_id.replace("/", "_").replace("..", "_")
        return self._storage_dir / f"{safe_id}.json"

    def _load_session(self, session_id: str) -> list[MemoryEntry]:
        """Load session from disk cache or in-memory cache."""
        if session_id in self._sessions:
            return self._sessions[session_id]

        path = self._session_path(session_id)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            entries: list[MemoryEntry] = [
                MemoryEntry(
                    role=MemoryType(e["role"]),
                    content=e["content"],
                    metadata=e.get("metadata", {}),
                )
                for e in data
            ]
            self._sessions[session_id] = entries
            return entries

        self._sessions[session_id] = []
        return self._sessions[session_id]

    def _save_session(self, session_id: str) -> None:
        """Serialise session entries to disk."""
        entries = self._sessions.get(session_id, [])
        path = self._session_path(session_id)
        data = [
            {
                "role": e.role.value if isinstance(e.role, MemoryType) else str(e.role),
                "content": e.content,
                "metadata": e.metadata,
            }
            for e in entries
        ]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, entry: MemoryEntry, session_id: str = "default") -> None:
        """Append *entry* to *session_id* and persist to disk.

        If the total message count exceeds *max_messages*, the oldest
        messages are dropped to keep the session within budget.

        Args:
            entry: The :class:`MemoryEntry` to store.
            session_id: Identifier for the conversation session.
        """
        entries = self._load_session(session_id)
        entries.append(entry)
        if len(entries) > self._max_messages:
            self._sessions[session_id] = entries[-self._max_messages:]
        self._save_session(session_id)

    def get_history(
        self,
        session_id: str = "default",
        limit: int | None = None,
    ) -> list[MemoryEntry]:
        """Return stored entries for *session_id*.

        Args:
            session_id: The session to retrieve.
            limit: If given, return only the *limit* most-recent entries.

        Returns:
            List of :class:`MemoryEntry` objects (oldest-first).
        """
        entries = self._load_session(session_id)
        if limit:
            return list(entries[-limit:])
        return list(entries)

    def clear(self, session_id: str = "default") -> None:
        """Delete all messages for *session_id* from memory and disk.

        Args:
            session_id: The session to clear.
        """
        self._sessions.pop(session_id, None)
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()

    def list_sessions(self) -> list[str]:
        """Return sorted list of all persisted session IDs.

        Returns:
            Sorted list of session identifier strings.
        """
        return sorted(p.stem for p in self._storage_dir.glob("*.json"))
