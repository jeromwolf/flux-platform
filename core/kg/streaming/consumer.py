"""Stream consumer abstractions for the streaming ingestion framework.

Provides:
- StreamConsumer: ABC defining the consumer interface
- InMemoryConsumer: in-memory implementation for Y1 testing and development
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kg.streaming.models import StreamMessage


class StreamConsumer(ABC):
    """Abstract base class for stream consumers.

    Concrete implementations wrap real message brokers (e.g. Kafka, Pulsar)
    or testing stubs such as InMemoryConsumer.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier for this consumer instance."""

    @abstractmethod
    def subscribe(self, topics: list[str]) -> None:
        """Subscribe to one or more topics.

        Args:
            topics: List of topic names to subscribe to.
        """

    @abstractmethod
    def consume(self, topic: str, max_messages: int = 100) -> list[StreamMessage]:
        """Fetch messages from a topic.

        Args:
            topic: Topic name to read from.
            max_messages: Maximum number of messages to return.

        Returns:
            List of StreamMessage objects, up to ``max_messages`` in length.
        """

    @abstractmethod
    def commit(self, message: StreamMessage) -> None:
        """Acknowledge successful processing of a message.

        Args:
            message: The message to acknowledge.
        """

    @abstractmethod
    def close(self) -> None:
        """Release resources held by this consumer."""


class InMemoryConsumer(StreamConsumer):
    """In-memory stream consumer for testing and local development.

    Messages are stored in per-topic queues and consumed from the front
    (FIFO order).  Committed message IDs are tracked in a set so tests can
    verify acknowledgement behaviour.

    Attributes:
        _name: Consumer identifier passed at construction time.
        _queues: Mapping from topic name to ordered list of pending messages.
        _committed: Set of message IDs that have been committed.
    """

    def __init__(self, name: str = "in-memory") -> None:
        """Initialise the consumer with an optional name.

        Args:
            name: Human-readable identifier; defaults to ``"in-memory"``.
        """
        self._name: str = name
        self._queues: dict[str, list[StreamMessage]] = {}
        self._committed: set[str] = set()

    # ------------------------------------------------------------------
    # StreamConsumer interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Human-readable identifier for this consumer instance."""
        return self._name

    def subscribe(self, topics: list[str]) -> None:
        """Create empty queues for each topic if they do not already exist.

        Args:
            topics: List of topic names to subscribe to.
        """
        for topic in topics:
            if topic not in self._queues:
                self._queues[topic] = []

    def consume(self, topic: str, max_messages: int = 100) -> list[StreamMessage]:
        """Pop up to ``max_messages`` messages from the front of the queue.

        If the topic has not been subscribed to, an empty list is returned.

        Args:
            topic: Topic name to read from.
            max_messages: Maximum number of messages to return.

        Returns:
            List of StreamMessage objects removed from the queue.
        """
        queue = self._queues.get(topic, [])
        batch = queue[:max_messages]
        self._queues[topic] = queue[max_messages:]
        return batch

    def commit(self, message: StreamMessage) -> None:
        """Mark a message as successfully processed.

        Args:
            message: The message to acknowledge.
        """
        self._committed.add(message.id)

    def close(self) -> None:
        """Clear all topic queues and committed message records."""
        self._queues.clear()
        self._committed.clear()

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def publish(self, topic: str, message: StreamMessage) -> None:
        """Append a message to the given topic queue.

        Creates the queue if it does not exist.  This method is intended for
        use in tests to seed messages before calling ``consume``.

        Args:
            topic: Target topic name.
            message: Message to enqueue.
        """
        if topic not in self._queues:
            self._queues[topic] = []
        self._queues[topic].append(message)
