"""Data models for the ETL pipeline framework.

Provides:
- PipelineConfig: immutable pipeline configuration
- PipelineResult: execution result with metrics
- PipelineStatus: pipeline lifecycle states
- RecordEnvelope: wrapper for individual records flowing through the pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PipelineStatus(str, Enum):
    """Lifecycle status of an ETL pipeline run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ETLMode(str, Enum):
    """ETL execution mode."""

    FULL = "full"               # 전체 재구축
    INCREMENTAL = "incremental" # 변경분만 업데이트


@dataclass
class IncrementalConfig:
    """Configuration for incremental ETL updates.

    Attributes:
        last_update_time: ISO timestamp of last successful run.
        change_field: Field name to detect changes (e.g., 'updatedAt', 'modified').
        cleanup_orphans: Whether to remove disconnected nodes after update.
    """

    last_update_time: str | None = None
    change_field: str = "updatedAt"
    cleanup_orphans: bool = False


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable configuration for an ETL pipeline.

    Attributes:
        name: Human-readable pipeline identifier.
        batch_size: Number of records per Neo4j batch write.
        max_retries: Maximum retry attempts for failed records.
        retry_delay: Seconds between retries.
        dlq_enabled: Whether to route failures to the Dead Letter Queue.
        validate: Whether to run validation rules before transforms.
    """

    name: str
    batch_size: int = 500
    max_retries: int = 3
    retry_delay: float = 1.0
    dlq_enabled: bool = True
    validate: bool = True


@dataclass
class PipelineResult:
    """Aggregated result from a pipeline execution.

    Attributes:
        records_processed: Number of records successfully loaded.
        records_failed: Number of records that failed and were sent to DLQ.
        records_skipped: Number of records skipped (validation failure, etc.).
        errors: Collected error messages from the run.
        duration_seconds: Wall-clock duration of the pipeline run.
        started_at: Timestamp when the run started.
        completed_at: Timestamp when the run finished.
    """

    records_processed: int = 0
    records_failed: int = 0
    records_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    mode: str = "full"
    total_input: int = 0
    filtered_count: int = 0


@dataclass
class RecordEnvelope:
    """Wrapper for a single record flowing through the ETL pipeline.

    Attributes:
        data: The actual record payload as a dictionary.
        source: Origin identifier (e.g. crawler name, file path).
        record_id: Unique identifier for this record.
        timestamp: When the record was created or ingested.
        metadata: Arbitrary key-value metadata.
        errors: Error messages accumulated during processing.
    """

    data: dict[str, Any]
    source: str
    record_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
