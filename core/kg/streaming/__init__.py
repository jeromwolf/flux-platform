"""Streaming framework for real-time KG data ingestion."""

from kg.streaming.consumer import InMemoryConsumer, StreamConsumer
from kg.streaming.models import ProcessingMode, StreamConfig, StreamMessage
from kg.streaming.persistent_dlq import PersistentDLQManager
from kg.streaming.processor import StreamProcessor

__all__ = [
    "InMemoryConsumer",
    "PersistentDLQManager",
    "ProcessingMode",
    "StreamConfig",
    "StreamConsumer",
    "StreamMessage",
    "StreamProcessor",
]
