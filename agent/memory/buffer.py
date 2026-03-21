"""Buffer memory implementation."""
from __future__ import annotations

from agent.memory.models import MemoryEntry, MemoryType


class BufferMemory:
    """Simple buffer memory that stores all messages.

    Satisfies the ConversationMemory protocol via duck typing.

    Args:
        max_messages: Maximum messages to retain. 0 = unlimited.
    """

    def __init__(self, max_messages: int = 0) -> None:
        self._messages: list[MemoryEntry] = []
        self._max = max_messages

    def add(self, role: MemoryType, content: str) -> None:
        """Add a message to the buffer."""
        entry = MemoryEntry(role=role, content=content)
        self._messages.append(entry)
        if self._max > 0 and len(self._messages) > self._max:
            self._messages = self._messages[-self._max:]

    def get_history(self, limit: int = -1) -> list[MemoryEntry]:
        """Get message history."""
        if limit <= 0:
            return list(self._messages)
        return list(self._messages[-limit:])

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()

    @property
    def message_count(self) -> int:
        """Number of messages."""
        return len(self._messages)
