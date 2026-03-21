"""Pipeline execution engine.

Executes a predefined sequence of steps (tools) in order.
Each step's output feeds into the next step as context.

Usage::

    engine = PipelineEngine(
        config=AgentConfig(name="etl-pipeline", mode=ExecutionMode.PIPELINE),
        tools=tools,
    )
    engine.add_step("extract", {"source": "papers"})
    engine.add_step("transform", {"format": "json"})
    engine.add_step("load", {"target": "neo4j"})
    result = engine.execute("Process papers dataset")
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
class PipelineStep:
    """A predefined step in a pipeline."""

    tool_name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    on_error: str = "stop"  # "stop", "skip", "retry"
    max_retries: int = 1


class PipelineEngine:
    """Sequential pipeline executor implementing AgentRuntime protocol.

    Executes steps in order, passing each step's output as ``prev_output``
    into the next step's inputs. Errors are handled per-step according to
    the ``on_error`` policy: ``"stop"`` halts the entire pipeline,
    ``"skip"`` continues to the next step, and ``"retry"`` retries up to
    ``max_retries`` times before applying the fallback policy.

    Example::

        engine = PipelineEngine(
            config=AgentConfig(name="etl-pipeline", mode=ExecutionMode.PIPELINE),
            tools=registry,
        )
        engine.add_step("extract", {"source": "papers"})
        engine.add_step("transform", {"format": "json"})
        engine.add_step("load", {"target": "neo4j"})
        result = engine.execute("Process papers dataset")
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        tools: Optional[ToolRegistry] = None,
    ) -> None:
        self._config = config or AgentConfig(
            name="pipeline", mode=ExecutionMode.PIPELINE
        )
        self._tools = tools or ToolRegistry()
        self._steps: List[PipelineStep] = []
        self._state: AgentState = AgentState.IDLE

    # ------------------------------------------------------------------
    # Builder API
    # ------------------------------------------------------------------

    def add_step(
        self,
        tool_name: str,
        inputs: Optional[dict[str, Any]] = None,
        description: str = "",
        on_error: str = "stop",
        max_retries: int = 1,
    ) -> PipelineEngine:
        """Add a step to the pipeline. Returns self for chaining.

        Args:
            tool_name: Name of the registered tool to call.
            inputs: Static input parameters for the tool.
            description: Human-readable description of this step.
            on_error: Error policy — ``"stop"``, ``"skip"``, or ``"retry"``.
            max_retries: Maximum retry attempts when ``on_error="retry"``.

        Returns:
            Self for method chaining.
        """
        self._steps.append(
            PipelineStep(
                tool_name=tool_name,
                inputs=inputs or {},
                description=description,
                on_error=on_error,
                max_retries=max_retries,
            )
        )
        return self

    def clear_steps(self) -> None:
        """Remove all pipeline steps."""
        self._steps.clear()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def step_count(self) -> int:
        """Number of steps currently defined."""
        return len(self._steps)

    @property
    def config(self) -> AgentConfig:
        """Return the agent configuration."""
        return self._config

    # ------------------------------------------------------------------
    # AgentRuntime protocol
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Ready if at least one step is defined."""
        return len(self._steps) > 0

    def execute(self, query: str, **kwargs: object) -> ExecutionResult:
        """Execute all pipeline steps sequentially.

        Each step creates an ACTION AgentStep followed by an OBSERVATION
        AgentStep. The output of each step is passed to the next step as
        ``prev_output`` in its inputs. On completion a FINAL step
        summarises all outputs.

        Error handling per step:
        - ``on_error="stop"``  — marks pipeline FAILED immediately.
        - ``on_error="skip"``  — logs the error, continues to next step.
        - ``on_error="retry"`` — retries up to ``max_retries`` times,
          then falls back to ``"stop"`` behaviour.

        Args:
            query: The user query / context passed to the pipeline.
            **kwargs: Unused additional parameters (protocol compatibility).

        Returns:
            ExecutionResult with full execution trace.
        """
        if not self.is_ready():
            return ExecutionResult(
                answer="",
                state=AgentState.FAILED,
                error="Pipeline has no steps defined.",
            )

        self._state = AgentState.RUNNING
        pipeline_start = time.monotonic()
        agent_steps: List[AgentStep] = []
        successful_outputs: List[str] = []
        prev_output: str = ""
        step_number = 1
        failed = False
        fail_error = ""

        for ps in self._steps:
            # Merge static inputs with context injected by previous step
            merged_inputs: dict[str, Any] = {**ps.inputs}
            if prev_output:
                merged_inputs["prev_output"] = prev_output
            # Always provide the original query as context
            merged_inputs.setdefault("query", query)

            # ACTION step
            action_step = AgentStep(
                step_number=step_number,
                step_type=StepType.ACTION,
                content=ps.description or f"Calling tool '{ps.tool_name}'",
                tool_name=ps.tool_name,
                tool_input=merged_inputs,
            )
            agent_steps.append(action_step)
            step_number += 1

            # Execute with retry support
            tool_result = None
            attempts = 0
            max_attempts = ps.max_retries if ps.on_error == "retry" else 1

            while attempts < max_attempts:
                attempts += 1
                step_start = time.monotonic()
                tool_result = self._tools.execute(ps.tool_name, merged_inputs)
                duration_ms = round((time.monotonic() - step_start) * 1000, 2)

                if tool_result.success or ps.on_error != "retry":
                    break

                logger.warning(
                    "Step '%s' attempt %d/%d failed: %s",
                    ps.tool_name,
                    attempts,
                    max_attempts,
                    tool_result.error,
                )

            # OBSERVATION step
            obs_content = (
                tool_result.output
                if tool_result.success
                else f"ERROR: {tool_result.error}"
            )
            obs_step = AgentStep(
                step_number=step_number,
                step_type=StepType.OBSERVATION,
                content=obs_content,
                tool_name=ps.tool_name,
                tool_output=tool_result.output,
                duration_ms=duration_ms,
            )
            agent_steps.append(obs_step)
            step_number += 1

            if tool_result.success:
                prev_output = tool_result.output
                successful_outputs.append(tool_result.output)
            else:
                logger.error(
                    "Pipeline step '%s' failed: %s", ps.tool_name, tool_result.error
                )
                if ps.on_error == "skip":
                    prev_output = ""
                    continue
                else:
                    # "stop" or exhausted retries
                    failed = True
                    fail_error = (
                        f"Step '{ps.tool_name}' failed: {tool_result.error}"
                    )
                    break

        total_duration = round(time.monotonic() - pipeline_start, 4)

        if failed:
            self._state = AgentState.FAILED
            # FINAL step records the failure
            agent_steps.append(
                AgentStep(
                    step_number=step_number,
                    step_type=StepType.FINAL,
                    content=fail_error,
                )
            )
            return ExecutionResult(
                answer="",
                state=AgentState.FAILED,
                steps=tuple(agent_steps),
                duration_seconds=total_duration,
                error=fail_error,
            )

        final_answer = "\n".join(successful_outputs) if successful_outputs else ""
        self._state = AgentState.COMPLETED

        agent_steps.append(
            AgentStep(
                step_number=step_number,
                step_type=StepType.FINAL,
                content=final_answer,
            )
        )

        return ExecutionResult(
            answer=final_answer,
            state=AgentState.COMPLETED,
            steps=tuple(agent_steps),
            duration_seconds=total_duration,
        )

    def reset(self) -> None:
        """Reset to IDLE state, keeping steps intact."""
        self._state = AgentState.IDLE
