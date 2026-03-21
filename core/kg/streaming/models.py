"""Data models for the streaming ingestion framework.

Provides:
- ProcessingMode: message processing strategy enum
- StreamConfig: immutable stream configuration
- StreamMessage: individual message flowing through the stream
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from kg.etl.models import RecordEnvelope


class ProcessingMode(str, Enum):
    """Message processing strategy for a stream.

    Attributes:
        REALTIME: Process each message immediately upon receipt.
        MICRO_BATCH: Accumulate messages and process in small batches.
        BATCH: Accumulate all messages and process them at once.
    """

    REALTIME = "realtime"
    MICRO_BATCH = "micro_batch"
    BATCH = "batch"


@dataclass(frozen=True)
class StreamConfig:
    """Immutable configuration for a stream processor.

    Attributes:
        name: Human-readable stream identifier.
        mode: Processing strategy to apply.
        batch_size: Maximum number of messages per micro-batch flush.
        batch_timeout_seconds: Maximum seconds to wait before flushing a batch.
        max_retries: Maximum retry attempts for failed messages.
        dlq_enabled: Whether to route failures to the Dead Letter Queue.
    """

    name: str
    mode: ProcessingMode = ProcessingMode.MICRO_BATCH
    batch_size: int = 100
    batch_timeout_seconds: float = 5.0
    max_retries: int = 3
    dlq_enabled: bool = True


@dataclass(frozen=True)
class StreamMessage:
    """An individual message flowing through the streaming pipeline.

    Uses an immutable tuple of pairs for headers to satisfy the frozen
    dataclass constraint (plain dicts are mutable and therefore incompatible).

    Attributes:
        id: Unique message identifier.
        topic: Source topic or channel name.
        payload: Message body as a key-value dictionary.
        timestamp: ISO 8601 creation timestamp; defaults to current UTC time.
        headers: Immutable sequence of (key, value) header pairs.
        partition: Partition index for partitioned topics.
        offset: Byte or sequence offset within the partition.
    """

    id: str
    topic: str
    payload: dict[str, Any]
    timestamp: str = ""
    headers: tuple[tuple[str, str], ...] = ()
    partition: int = 0
    offset: int = 0

    def __post_init__(self) -> None:
        """Populate timestamp with current UTC time if not provided."""
        if not self.timestamp:
            # frozen=True prevents direct assignment; use object.__setattr__
            object.__setattr__(
                self,
                "timestamp",
                datetime.now(tz=timezone.utc).isoformat(),
            )

    def to_record_envelope(self) -> RecordEnvelope:
        """Convert this StreamMessage to an ETL RecordEnvelope.

        Returns:
            A RecordEnvelope whose ``data`` contains the message payload,
            ``source`` is the topic, and ``record_id`` is this message's id.
        """
        return RecordEnvelope(
            data=dict(self.payload),
            source=self.topic,
            record_id=self.id,
            metadata={
                "partition": self.partition,
                "offset": self.offset,
                "headers": dict(self.headers),
            },
        )
