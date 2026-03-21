"""Stream processor for the real-time KG ingestion framework.

Provides:
- MessageHandler: Protocol that concrete handlers must satisfy
- ProcessResult: frozen dataclass summarising a processing run
- StreamProcessor: orchestrates consume → handle → DLQ routing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from kg.etl.dlq import DLQManager
from kg.etl.models import RecordEnvelope
from kg.streaming.consumer import StreamConsumer
from kg.streaming.models import StreamConfig, StreamMessage


@runtime_checkable
class MessageHandler(Protocol):
    """Protocol for objects that transform StreamMessages into RecordEnvelopes.

    Any class that implements ``handle`` with the correct signature satisfies
    this protocol; no explicit inheritance is required.
    """

    def handle(self, messages: list[StreamMessage]) -> list[RecordEnvelope]:
        """Process a batch of messages and return ETL-ready envelopes.

        Args:
            messages: Batch of StreamMessage objects to process.

        Returns:
            List of RecordEnvelope objects ready for ETL loading.
        """
        ...


@dataclass(frozen=True)
class ProcessResult:
    """Summary of a single processing run.

    Attributes:
        processed: Number of messages successfully handled.
        failed: Number of messages that raised an error during handling.
        dlq_count: Number of messages routed to the Dead Letter Queue.
        errors: Collected error messages from failed records.
    """

    processed: int = 0
    failed: int = 0
    dlq_count: int = 0
    errors: list[str] = field(default_factory=list)


class StreamProcessor:
    """Orchestrates message consumption, handling, and DLQ routing.

    The processor supports a fluent interface for registering a
    ``MessageHandler``.  Messages are buffered internally and flushed either
    on demand (``flush``) or when a batch is processed directly
    (``process_batch``).

    Attributes:
        _config: Immutable stream configuration.
        _consumer: Underlying stream consumer used to fetch messages.
        _handler: Optional message handler; must be set before processing.
        _buffer: Messages awaiting processing.
        _dlq: Dead Letter Queue for failed messages.
    """

    def __init__(
        self,
        config: StreamConfig,
        consumer: StreamConsumer,
        handler: MessageHandler | None = None,
    ) -> None:
        """Initialise the processor.

        Args:
            config: Stream configuration (name, mode, batch sizes, etc.).
            consumer: Consumer used to fetch messages from topics.
            handler: Optional initial message handler.
        """
        self._config: StreamConfig = config
        self._consumer: StreamConsumer = consumer
        self._handler: MessageHandler | None = handler
        self._buffer: list[StreamMessage] = []
        self._dlq: DLQManager = DLQManager()

    # ------------------------------------------------------------------
    # Fluent builder
    # ------------------------------------------------------------------

    def add_handler(self, handler: MessageHandler) -> StreamProcessor:
        """Register a message handler and return ``self`` for chaining.

        Args:
            handler: Handler that satisfies the MessageHandler Protocol.

        Returns:
            This StreamProcessor instance (fluent interface).
        """
        self._handler = handler
        return self

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process_batch(self, messages: list[StreamMessage]) -> ProcessResult:
        """Process a list of messages through the registered handler.

        Each message that the handler fails to process is routed to the DLQ
        when ``config.dlq_enabled`` is ``True``.

        Args:
            messages: Messages to process.

        Returns:
            ProcessResult summarising outcomes for this batch.

        Raises:
            RuntimeError: If no handler has been registered.
        """
        if not messages:
            return ProcessResult()

        if self._handler is None:
            raise RuntimeError(
                "No MessageHandler registered. Call add_handler() before processing."
            )

        errors: list[str] = []
        processed = 0
        failed = 0
        dlq_count = 0

        try:
            envelopes = self._handler.handle(messages)
            processed = len(envelopes)
        except Exception as exc:  # noqa: BLE001
            # Handler raised for the entire batch — send every message to DLQ.
            error_msg = f"Handler error: {exc}"
            errors.append(error_msg)
            failed = len(messages)

            if self._config.dlq_enabled:
                for msg in messages:
                    envelope = msg.to_record_envelope()
                    self._dlq.add(envelope, [error_msg])
                    dlq_count += 1

        return ProcessResult(
            processed=processed,
            failed=failed,
            dlq_count=dlq_count,
            errors=errors,
        )

    def flush(self) -> ProcessResult:
        """Process all buffered messages and clear the buffer.

        Returns:
            ProcessResult summarising outcomes for the flushed batch.
        """
        messages = list(self._buffer)
        self._buffer.clear()
        return self.process_batch(messages)

    def receive_and_buffer(self, topic: str, max_messages: int = 100) -> int:
        """Fetch messages from the consumer and append them to the buffer.

        Args:
            topic: Topic to read from.
            max_messages: Maximum messages to fetch in a single call.

        Returns:
            Number of messages added to the buffer.
        """
        messages = self._consumer.consume(topic, max_messages)
        self._buffer.extend(messages)
        return len(messages)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def buffer_size(self) -> int:
        """Number of messages currently waiting in the buffer."""
        return len(self._buffer)

    @property
    def dlq(self) -> DLQManager:
        """The Dead Letter Queue associated with this processor."""
        return self._dlq
