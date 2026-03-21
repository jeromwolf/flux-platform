"""Agent runtime data models."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionMode(str, Enum):
    """Agent execution mode."""
    REACT = "react"
    PIPELINE = "pipeline"
    BATCH = "batch"


class StepType(str, Enum):
    """Type of agent execution step."""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    FINAL = "final"


@dataclass(frozen=True)
class AgentConfig:
    """Agent configuration."""
    name: str = "default"
    mode: ExecutionMode = ExecutionMode.REACT
    max_steps: int = 10
    timeout: float = 120.0
    temperature: float = 0.7
    model: str = "mistral"
    verbose: bool = False


@dataclass(frozen=True)
class AgentStep:
    """A single step in agent execution."""
    step_number: int
    step_type: StepType
    content: str
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    tool_output: str = ""
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class AgentState(str, Enum):
    """Agent execution state."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class ExecutionResult:
    """Result of an agent execution."""
    answer: str
    state: AgentState
    steps: tuple[AgentStep, ...] = ()
    total_tokens: int = 0
    duration_seconds: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Whether execution completed successfully."""
        return self.state == AgentState.COMPLETED

    @property
    def step_count(self) -> int:
        """Number of steps executed."""
        return len(self.steps)
