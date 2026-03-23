"""Memory provider factory."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryConfig:
    """Configuration for the memory provider factory.

    Attributes:
        backend: Storage backend — ``"buffer"``, ``"file"``, or ``"redis"``.
        max_messages: Maximum messages retained per session (buffer/file/redis).
        storage_dir: Directory for the file backend.
        redis_url: Connection URL for the Redis backend.
    """

    backend: str = "file"
    max_messages: int = 100
    storage_dir: str = ".imsp/memory"
    redis_url: str = "redis://localhost:6379"


def create_memory_provider(config: MemoryConfig | None = None):
    """Instantiate and return the appropriate memory provider.

    Backend resolution order:

    1. Use ``config.backend`` if *config* is provided.
    2. Otherwise read the ``MEMORY_BACKEND`` environment variable.
    3. Fall back to ``"file"`` if the variable is unset.

    Supported backends:

    * ``"redis"``   — :class:`~agent.memory.redis_provider.RedisMemoryProvider`
      (auto-falls-back to file when Redis is unreachable).
    * ``"file"``    — :class:`~agent.memory.file_provider.FileMemoryProvider`.
    * ``"buffer"``  — :class:`~agent.memory.buffer.BufferMemory` (in-memory only).

    Args:
        config: Optional :class:`MemoryConfig`.  When *None*, settings are
            read from environment variables.

    Returns:
        A memory provider instance.
    """
    if config is None:
        backend = os.environ.get("MEMORY_BACKEND", "file")
        config = MemoryConfig(backend=backend)

    if config.backend == "redis":
        from agent.memory.redis_provider import RedisMemoryProvider

        return RedisMemoryProvider(
            redis_url=config.redis_url,
            max_messages=config.max_messages,
        )

    if config.backend == "file":
        from agent.memory.file_provider import FileMemoryProvider

        return FileMemoryProvider(
            storage_dir=config.storage_dir,
            max_messages=config.max_messages,
        )

    # Default / "buffer"
    from agent.memory.buffer import BufferMemory

    return BufferMemory(max_messages=config.max_messages)
