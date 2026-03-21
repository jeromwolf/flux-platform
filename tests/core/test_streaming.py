"""Unit tests for core/kg/streaming/ package.

All tests are marked @pytest.mark.unit and require no external dependencies.
PYTHONPATH: core:domains
"""

from __future__ import annotations

import dataclasses

import pytest

from kg.streaming import (
    InMemoryConsumer,
    StreamConsumer,
    ProcessingMode,
    StreamConfig,
    StreamMessage,
    PersistentDLQManager,
    StreamProcessor,
)
from kg.streaming.models import ProcessingMode, StreamConfig, StreamMessage
from kg.streaming.consumer import InMemoryConsumer, StreamConsumer
from kg.streaming.processor import StreamProcessor, ProcessResult, MessageHandler
from kg.streaming.persistent_dlq import PersistentDLQManager
from kg.etl.models import RecordEnvelope


# ---------------------------------------------------------------------------
# ProcessingMode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProcessingMode:
    """Tests for the ProcessingMode string enum."""

    @pytest.mark.unit
    def test_three_modes(self):
        """REALTIME, MICRO_BATCH, and BATCH must all exist."""
        assert ProcessingMode.REALTIME
        assert ProcessingMode.MICRO_BATCH
        assert ProcessingMode.BATCH

    @pytest.mark.unit
    def test_str_enum(self):
        """ProcessingMode values must be instances of str."""
        assert isinstance(ProcessingMode.REALTIME, str)
        assert isinstance(ProcessingMode.MICRO_BATCH, str)
        assert isinstance(ProcessingMode.BATCH, str)


# ---------------------------------------------------------------------------
# StreamConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStreamConfig:
    """Tests for StreamConfig frozen dataclass."""

    @pytest.mark.unit
    def test_defaults(self):
        """Default StreamConfig must use MICRO_BATCH mode and batch_size=100."""
        config = StreamConfig(name="my_stream")
        assert config.mode == ProcessingMode.MICRO_BATCH
        assert config.batch_size == 100
        assert config.max_retries == 3
        assert config.dlq_enabled is True

    @pytest.mark.unit
    def test_frozen(self):
        """Assignment to any field must raise FrozenInstanceError."""
        config = StreamConfig(name="immutable")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            config.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StreamMessage
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStreamMessage:
    """Tests for StreamMessage frozen dataclass."""

    @pytest.mark.unit
    def test_creation(self):
        """StreamMessage must store id, topic, and payload correctly."""
        msg = StreamMessage(
            id="msg-1",
            topic="vessels",
            payload={"imo": "1234567", "name": "Arctic Star"},
        )
        assert msg.id == "msg-1"
        assert msg.topic == "vessels"
        assert msg.payload["imo"] == "1234567"

    @pytest.mark.unit
    def test_frozen(self):
        """Assignment to any field must raise FrozenInstanceError."""
        msg = StreamMessage(id="x", topic="t", payload={})
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            msg.id = "changed"  # type: ignore[misc]

    @pytest.mark.unit
    def test_to_record_envelope(self):
        """to_record_envelope must produce a RecordEnvelope with matching fields."""
        msg = StreamMessage(
            id="msg-42",
            topic="port_calls",
            payload={"port": "Busan", "eta": "2026-03-20"},
        )
        envelope = msg.to_record_envelope()
        assert isinstance(envelope, RecordEnvelope)
        assert envelope.record_id == "msg-42"
        assert envelope.source == "port_calls"
        assert envelope.data["port"] == "Busan"

    @pytest.mark.unit
    def test_auto_timestamp(self):
        """timestamp must be auto-populated when not provided."""
        msg = StreamMessage(id="ts-test", topic="t", payload={})
        assert msg.timestamp != ""
        assert len(msg.timestamp) > 0


# ---------------------------------------------------------------------------
# InMemoryConsumer
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInMemoryConsumer:
    """Tests for InMemoryConsumer in-memory stream consumer."""

    @pytest.fixture
    def consumer(self) -> InMemoryConsumer:
        return InMemoryConsumer(name="test-consumer")

    def _make_msg(self, msg_id: str, topic: str) -> StreamMessage:
        return StreamMessage(id=msg_id, topic=topic, payload={"key": "value"})

    @pytest.mark.unit
    def test_name(self, consumer):
        """name property must return the configured name."""
        assert consumer.name == "test-consumer"

    @pytest.mark.unit
    def test_subscribe_and_publish(self, consumer):
        """Subscribing then publishing to a topic must allow consumption."""
        consumer.subscribe(["vessels"])
        msg = self._make_msg("m1", "vessels")
        consumer.publish("vessels", msg)
        consumed = consumer.consume("vessels")
        assert len(consumed) == 1
        assert consumed[0].id == "m1"

    @pytest.mark.unit
    def test_consume_empty(self, consumer):
        """Consuming from an unknown or empty topic must return an empty list."""
        result = consumer.consume("nonexistent_topic")
        assert result == []

    @pytest.mark.unit
    def test_consume_respects_max(self, consumer):
        """max_messages must limit the number of messages returned."""
        consumer.subscribe(["vessels"])
        for i in range(5):
            consumer.publish("vessels", self._make_msg(f"m{i}", "vessels"))
        result = consumer.consume("vessels", max_messages=3)
        assert len(result) == 3

    @pytest.mark.unit
    def test_commit(self, consumer):
        """commit must record the message ID in the committed set."""
        consumer.subscribe(["vessels"])
        msg = self._make_msg("commit-me", "vessels")
        consumer.publish("vessels", msg)
        consumed = consumer.consume("vessels")
        consumer.commit(consumed[0])
        assert "commit-me" in consumer._committed

    @pytest.mark.unit
    def test_close_clears(self, consumer):
        """close must empty all topic queues."""
        consumer.subscribe(["vessels"])
        consumer.publish("vessels", self._make_msg("m1", "vessels"))
        consumer.close()
        assert consumer.consume("vessels") == []

    @pytest.mark.unit
    def test_is_stream_consumer(self):
        """InMemoryConsumer must be an instance of the StreamConsumer ABC."""
        c = InMemoryConsumer()
        assert isinstance(c, StreamConsumer)


# ---------------------------------------------------------------------------
# StreamProcessor
# ---------------------------------------------------------------------------


class SimpleHandler:
    """Minimal MessageHandler that converts each StreamMessage to a RecordEnvelope."""

    def handle(self, messages: list[StreamMessage]) -> list[RecordEnvelope]:
        return [msg.to_record_envelope() for msg in messages]


@pytest.mark.unit
class TestStreamProcessor:
    """Tests for StreamProcessor orchestration logic."""

    @pytest.fixture
    def config(self) -> StreamConfig:
        return StreamConfig(name="test_stream")

    @pytest.fixture
    def consumer(self) -> InMemoryConsumer:
        return InMemoryConsumer(name="proc-consumer")

    @pytest.fixture
    def processor(self, config, consumer) -> StreamProcessor:
        return StreamProcessor(config=config, consumer=consumer)

    def _make_msgs(self, count: int, topic: str = "t") -> list[StreamMessage]:
        return [
            StreamMessage(id=f"msg-{i}", topic=topic, payload={"n": i})
            for i in range(count)
        ]

    @pytest.mark.unit
    def test_add_handler_fluent(self, processor):
        """add_handler must return the processor itself (fluent interface)."""
        result = processor.add_handler(SimpleHandler())
        assert result is processor

    @pytest.mark.unit
    def test_process_batch(self, processor):
        """process_batch with a valid handler must return a successful ProcessResult."""
        processor.add_handler(SimpleHandler())
        msgs = self._make_msgs(3)
        result = processor.process_batch(msgs)
        assert isinstance(result, ProcessResult)
        assert result.processed == 3
        assert result.failed == 0

    @pytest.mark.unit
    def test_flush_empty(self, processor):
        """flush with an empty buffer must return ProcessResult with zeros."""
        processor.add_handler(SimpleHandler())
        result = processor.flush()
        assert result.processed == 0
        assert result.failed == 0

    @pytest.mark.unit
    def test_receive_and_buffer(self, processor, consumer):
        """receive_and_buffer must move messages from consumer into the internal buffer."""
        consumer.subscribe(["events"])
        for i in range(4):
            consumer.publish(
                "events",
                StreamMessage(id=f"e{i}", topic="events", payload={}),
            )
        added = processor.receive_and_buffer("events", max_messages=4)
        assert added == 4
        assert processor.buffer_size == 4

    @pytest.mark.unit
    def test_buffer_size(self, processor, consumer):
        """buffer_size must reflect the current number of buffered messages."""
        assert processor.buffer_size == 0
        consumer.subscribe(["x"])
        consumer.publish("x", StreamMessage(id="a", topic="x", payload={}))
        processor.receive_and_buffer("x")
        assert processor.buffer_size == 1

    @pytest.mark.unit
    def test_handler_protocol(self):
        """SimpleHandler must satisfy the MessageHandler Protocol at runtime."""
        handler = SimpleHandler()
        assert isinstance(handler, MessageHandler)


# ---------------------------------------------------------------------------
# PersistentDLQManager
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPersistentDLQManager:
    """Tests for PersistentDLQManager file-backed DLQ."""

    def _make_envelope(self, record_id: str = "rec-1") -> RecordEnvelope:
        return RecordEnvelope(
            data={"key": "value"},
            source="test_source",
            record_id=record_id,
        )

    @pytest.mark.unit
    def test_add_and_size(self, tmp_path):
        """Adding an entry must increment the size by one."""
        dlq = PersistentDLQManager(file_path=tmp_path / "dlq.jsonl")
        assert dlq.size == 0
        dlq.add(self._make_envelope(), ["error msg"])
        assert dlq.size == 1

    @pytest.mark.unit
    def test_get_entries(self, tmp_path):
        """get_entries must return the list of added entries."""
        dlq = PersistentDLQManager(file_path=tmp_path / "dlq.jsonl")
        env = self._make_envelope("r1")
        dlq.add(env, ["err"])
        entries = dlq.get_entries()
        assert len(entries) == 1
        assert entries[0].record.record_id == "r1"

    @pytest.mark.unit
    def test_retry_eligible(self, tmp_path):
        """retry_eligible must exclude entries that have reached the retry limit."""
        dlq = PersistentDLQManager(file_path=tmp_path / "dlq.jsonl")
        dlq.add(self._make_envelope("r1"), ["e"])
        dlq.add(self._make_envelope("r2"), ["e"])

        # Manually bump retry_count on the first entry to exceed the limit
        dlq._entries[0].retry_count = 5

        eligible = dlq.retry_eligible(max_retries=3)
        # Only r2 should be eligible (retry_count == 0 < 3)
        assert len(eligible) == 1
        assert eligible[0].record.record_id == "r2"

    @pytest.mark.unit
    def test_clear(self, tmp_path):
        """clear must remove all in-memory entries and truncate the file."""
        path = tmp_path / "dlq.jsonl"
        dlq = PersistentDLQManager(file_path=path)
        dlq.add(self._make_envelope(), ["err"])
        dlq.clear()
        assert dlq.size == 0
        assert path.read_text(encoding="utf-8") == ""

    @pytest.mark.unit
    def test_persistence(self, tmp_path):
        """Entries added to one manager instance must be loadable by a new instance."""
        path = tmp_path / "dlq.jsonl"
        dlq1 = PersistentDLQManager(file_path=path)
        dlq1.add(self._make_envelope("persist-1"), ["persisted error"])

        dlq2 = PersistentDLQManager(file_path=path)
        dlq2.load()
        assert dlq2.size == 1
        assert dlq2.get_entries()[0].record.record_id == "persist-1"

    @pytest.mark.unit
    def test_file_created(self, tmp_path):
        """The backing .jsonl file must exist on disk after an add call."""
        path = tmp_path / "dlq.jsonl"
        dlq = PersistentDLQManager(file_path=path)
        dlq.add(self._make_envelope(), ["err"])
        assert path.exists()
        assert path.stat().st_size > 0
