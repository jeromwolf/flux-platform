"""Agent runtime protocol definition."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from agent.runtime.models import AgentConfig, ExecutionResult


@runtime_checkable
class AgentRuntime(Protocol):
    """Protocol for agent runtime implementations.

    All agent execution engines (ReAct, Pipeline, Batch) must
    implement this protocol.
    """

    @property
    def config(self) -> AgentConfig:
        """Return the agent configuration."""
        ...

    def execute(self, query: str, **kwargs: object) -> ExecutionResult:
        """Execute an agent query.

        Args:
            query: The user query to process.
            **kwargs: Additional execution parameters.

        Returns:
            ExecutionResult containing the answer and execution trace.
        """
        ...

    def is_ready(self) -> bool:
        """Check if the runtime is ready to execute."""
        ...
