"""Batch execution engine.

Processes multiple queries through the same tool/pipeline configuration.
Collects results for all items.

Usage::

    engine = BatchEngine(
        config=AgentConfig(name="batch-processor", mode=ExecutionMode.BATCH),
        tools=tools,
        tool_name="extract",
    )
    queries = ["Process doc A", "Process doc B", "Process doc C"]
    result = engine.execute_batch(queries)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

from agent.runtime.models import (
    AgentConfig,
    AgentState,
    AgentStep,
    ExecutionMode,
    ExecutionResult,
    StepType,
)
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchItem:
    """A single item in a batch."""

    query: str
    inputs: dict[str, Any] = field(default_factory=dict)
    index: int = 0


@dataclass(frozen=True)
class BatchResult:
    """Result of batch processing."""

    items: tuple[ExecutionResult, ...] = ()
    total_duration_seconds: float = 0.0
    success_count: int = 0
    failure_count: int = 0

    @property
    def total_count(self) -> int:
        """Total number of items processed."""
        return len(self.items)

    @property
    def success_rate(self) -> float:
        """Fraction of successful items, in range 0.0–1.0."""
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count


class BatchEngine:
    """Batch processor implementing AgentRuntime protocol.

    Iterates over a list of queries, invokes the configured default tool
    for each one, and collects results into a ``BatchResult``. Individual
    item failures never stop the batch; the engine always attempts every
    item.

    Example::

        engine = BatchEngine(
            config=AgentConfig(name="batch-processor", mode=ExecutionMode.BATCH),
            tools=registry,
            tool_name="extract",
        )
        result = engine.execute_batch(["doc A", "doc B", "doc C"])
        print(result.success_rate)
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        tools: Optional[ToolRegistry] = None,
        tool_name: str = "",
    ) -> None:
        self._config = config or AgentConfig(
            name="batch", mode=ExecutionMode.BATCH
        )
        self._tools = tools or ToolRegistry()
        self._tool_name = tool_name
        self._state: AgentState = AgentState.IDLE

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def config(self) -> AgentConfig:
        """Return the agent configuration."""
        return self._config

    # ------------------------------------------------------------------
    # AgentRuntime protocol
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Ready if a tool name is set and that tool is registered."""
        if not self._tool_name:
            return False
        return self._tools.get(self._tool_name) is not None

    def execute(self, query: str, **kwargs: object) -> ExecutionResult:
        """Execute a single query via the configured default tool.

        Provided for AgentRuntime protocol compliance. Equivalent to
        calling ``execute_batch([query]).items[0]``.

        Args:
            query: The query to process.
            **kwargs: Forwarded as extra inputs to the tool.

        Returns:
            ExecutionResult for the single query.
        """
        extra_inputs = {k: v for k, v in kwargs.items()}
        return self._run_single(
            BatchItem(query=query, inputs=extra_inputs, index=0)
        )

    # ------------------------------------------------------------------
    # Batch API
    # ------------------------------------------------------------------

    def execute_batch(
        self,
        queries: List[str],
        inputs_list: Optional[List[dict[str, Any]]] = None,
    ) -> BatchResult:
        """Process multiple queries through the configured tool.

        Each query is wrapped in a ``BatchItem`` and executed
        independently. Failures are recorded but never stop the batch.

        Args:
            queries: Ordered list of query strings to process.
            inputs_list: Optional per-item extra inputs. When provided its
                length must match ``queries``. Items may be ``None`` or
                empty dicts.

        Returns:
            BatchResult with per-item ExecutionResults and summary stats.
        """
        if inputs_list is None:
            inputs_list = [{} for _ in queries]

        batch_start = time.monotonic()
        results: List[ExecutionResult] = []
        success_count = 0
        failure_count = 0

        for idx, (query, extra_inputs) in enumerate(zip(queries, inputs_list)):
            item = BatchItem(
                query=query,
                inputs=extra_inputs or {},
                index=idx,
            )
            result = self._run_single(item)
            results.append(result)
            if result.success:
                success_count += 1
            else:
                failure_count += 1

        total_duration = round(time.monotonic() - batch_start, 4)

        return BatchResult(
            items=tuple(results),
            total_duration_seconds=total_duration,
            success_count=success_count,
            failure_count=failure_count,
        )

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset to IDLE state."""
        self._state = AgentState.IDLE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_single(self, item: BatchItem) -> ExecutionResult:
        """Execute the configured tool for a single BatchItem.

        Builds ACTION + OBSERVATION AgentSteps and wraps the outcome in
        an ExecutionResult. Any exception from the tool layer is caught
        and returned as a FAILED result so the batch continues.

        Args:
            item: The batch item to process.

        Returns:
            ExecutionResult for this item.
        """
        if not self._tool_name:
            return ExecutionResult(
                answer="",
                state=AgentState.FAILED,
                error="No tool_name configured for BatchEngine.",
            )

        merged_inputs: dict[str, Any] = {**item.inputs, "query": item.query}

        item_start = time.monotonic()
        agent_steps: List[AgentStep] = []

        # ACTION
        agent_steps.append(
            AgentStep(
                step_number=1,
                step_type=StepType.ACTION,
                content=f"Batch item {item.index}: calling tool '{self._tool_name}'",
                tool_name=self._tool_name,
                tool_input=merged_inputs,
            )
        )

        tool_result = self._tools.execute(self._tool_name, merged_inputs)
        duration_ms = round((time.monotonic() - item_start) * 1000, 2)

        # OBSERVATION
        obs_content = (
            tool_result.output
            if tool_result.success
            else f"ERROR: {tool_result.error}"
        )
        agent_steps.append(
            AgentStep(
                step_number=2,
                step_type=StepType.OBSERVATION,
                content=obs_content,
                tool_name=self._tool_name,
                tool_output=tool_result.output,
                duration_ms=duration_ms,
            )
        )

        total_duration = round(time.monotonic() - item_start, 4)

        if tool_result.success:
            # FINAL
            agent_steps.append(
                AgentStep(
                    step_number=3,
                    step_type=StepType.FINAL,
                    content=tool_result.output,
                )
            )
            return ExecutionResult(
                answer=tool_result.output,
                state=AgentState.COMPLETED,
                steps=tuple(agent_steps),
                duration_seconds=total_duration,
            )

        logger.warning(
            "Batch item %d ('%s') failed: %s",
            item.index,
            item.query[:60],
            tool_result.error,
        )
        agent_steps.append(
            AgentStep(
                step_number=3,
                step_type=StepType.FINAL,
                content=f"Failed: {tool_result.error}",
            )
        )
        return ExecutionResult(
            answer="",
            state=AgentState.FAILED,
            steps=tuple(agent_steps),
            duration_seconds=total_duration,
            error=tool_result.error,
        )
