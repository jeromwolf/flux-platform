"""Data models for workflow execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ExecutionStatus(str, Enum):
    """Workflow execution lifecycle status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class NodeStatus(str, Enum):
    """Individual node execution status."""

    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class TriggerType(str, Enum):
    """How an execution was triggered."""

    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    EVENT = "event"


@dataclass
class NodeExecutionResult:
    """Result of executing a single node."""

    node_id: str
    node_type: str
    status: NodeStatus = NodeStatus.IDLE
    input_data: list[dict[str, Any]] = field(default_factory=list)
    output_data: list[dict[str, Any]] = field(default_factory=list)
    error_message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "status": self.status.value,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ExecutionResult:
    """Complete workflow execution result."""

    execution_id: str = field(default_factory=lambda: uuid4().hex[:12])
    workflow_id: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    trigger_type: TriggerType = TriggerType.MANUAL
    node_results: dict[str, NodeExecutionResult] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for DB/API response."""
        return {
            "id": self.execution_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "trigger_type": self.trigger_type.value,
            "node_results": {
                nid: nr.to_dict() for nid, nr in self.node_results.items()
            },
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error_message": self.error_message,
        }
