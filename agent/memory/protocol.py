"""Memory protocol definition."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from agent.memory.models import MemoryEntry, MemoryType


@runtime_checkable
class ConversationMemory(Protocol):
    """Protocol for conversation memory implementations."""

    def add(self, role: MemoryType, content: str) -> None:
        """Add a message to memory."""
        ...

    def get_history(self, limit: int = -1) -> list[MemoryEntry]:
        """Get conversation history, optionally limited."""
        ...

    def clear(self) -> None:
        """Clear all memory."""
        ...

    @property
    def message_count(self) -> int:
        """Number of messages in memory."""
        ...
