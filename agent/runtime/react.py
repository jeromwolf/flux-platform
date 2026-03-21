"""ReAct (Reason+Act) execution engine.

Implements the classic ReAct loop:
1. THOUGHT: LLM reasons about the query and available tools
2. ACTION: LLM selects a tool and provides input
3. OBSERVATION: Tool executes and returns result
4. Repeat until FINAL answer or max_steps reached

Usage::

    from agent.runtime.react import ReActEngine
    from agent.tools.registry import ToolRegistry

    tools = ToolRegistry()
    tools.register(ToolDefinition(name="search", ...), handler=search_fn)

    engine = ReActEngine(
        config=AgentConfig(name="qa-agent", max_steps=5),
        tools=tools,
        llm=my_llm_provider,  # or None for stub mode
    )
    result = engine.execute("What vessels are in Busan port?")
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from agent.memory.buffer import BufferMemory
from agent.memory.models import MemoryType
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


class ReActEngine:
    """ReAct execution engine implementing AgentRuntime protocol.

    When no LLM provider is given, operates in "stub mode" where
    the engine simulates the ReAct loop using rule-based parsing.
    This allows testing the execution flow without an actual LLM.
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        tools: Optional[ToolRegistry] = None,
        llm: Any = None,  # LLMProvider protocol
        memory: Optional[BufferMemory] = None,
    ) -> None:
        self._config = config or AgentConfig(mode=ExecutionMode.REACT)
        self._tools = tools or ToolRegistry()
        self._llm = llm
        self._memory = memory or BufferMemory(max_messages=100)
        self._state = AgentState.IDLE

    @property
    def config(self) -> AgentConfig:
        return self._config

    @property
    def state(self) -> AgentState:
        return self._state

    def is_ready(self) -> bool:
        """Engine is ready if it is in IDLE state."""
        return self._state == AgentState.IDLE

    def execute(self, query: str, **kwargs: object) -> ExecutionResult:
        """Execute the ReAct loop for a query.

        Steps:
        1. Build system prompt with available tools
        2. Loop: generate thought -> parse action -> execute tool -> observe
        3. Return final answer or timeout/error

        Args:
            query: The user query to process.
            **kwargs: Additional execution parameters (unused in V1).

        Returns:
            ExecutionResult containing the answer and full execution trace.
        """
        if self._state == AgentState.RUNNING:
            return ExecutionResult(
                answer="",
                state=AgentState.FAILED,
                error="Engine is already running",
            )

        self._state = AgentState.RUNNING
        start_time = time.monotonic()
        steps: list[AgentStep] = []
        total_tokens = 0

        try:
            # Add query to memory
            self._memory.add(MemoryType.USER, query)

            for step_num in range(1, self._config.max_steps + 1):
                # Check timeout
                elapsed = time.monotonic() - start_time
                if elapsed > self._config.timeout:
                    self._state = AgentState.TIMEOUT
                    return ExecutionResult(
                        answer="",
                        state=AgentState.TIMEOUT,
                        steps=tuple(steps),
                        total_tokens=total_tokens,
                        duration_seconds=round(elapsed, 2),
                        error="Execution timed out",
                    )

                # 1. THOUGHT: Generate reasoning
                thought_prompt = self._build_prompt(query, steps)
                thought_response = self._generate(thought_prompt)

                if thought_response is not None:
                    total_tokens += getattr(thought_response, "token_count", 0)
                    thought_text = thought_response.text
                else:
                    thought_text = self._stub_think(query, steps)

                step_start_ms = round((time.monotonic() - start_time) * 1000, 2)
                thought_step = AgentStep(
                    step_number=step_num,
                    step_type=StepType.THOUGHT,
                    content=thought_text,
                    duration_ms=step_start_ms,
                )
                steps.append(thought_step)

                if self._config.verbose:
                    logger.info("Step %d THOUGHT: %s", step_num, thought_text[:100])

                # 2. Parse: Is this a final answer or a tool call?
                parsed = self._parse_response(thought_text)

                if parsed["type"] == "final":
                    # FINAL answer
                    final_step = AgentStep(
                        step_number=step_num,
                        step_type=StepType.FINAL,
                        content=parsed["content"],
                    )
                    steps.append(final_step)
                    self._memory.add(MemoryType.ASSISTANT, parsed["content"])
                    self._state = AgentState.COMPLETED
                    return ExecutionResult(
                        answer=parsed["content"],
                        state=AgentState.COMPLETED,
                        steps=tuple(steps),
                        total_tokens=total_tokens,
                        duration_seconds=round(time.monotonic() - start_time, 2),
                    )

                elif parsed["type"] == "action":
                    # ACTION: Execute tool
                    tool_name = parsed["tool"]
                    tool_input = parsed["input"]

                    action_step = AgentStep(
                        step_number=step_num,
                        step_type=StepType.ACTION,
                        content=f"Using tool: {tool_name}",
                        tool_name=tool_name,
                        tool_input=tool_input,
                    )
                    steps.append(action_step)

                    if self._config.verbose:
                        logger.info(
                            "Step %d ACTION: %s(%s)", step_num, tool_name, tool_input
                        )

                    # 3. OBSERVATION: Tool result
                    tool_start = time.monotonic()
                    tool_result = self._tools.execute(tool_name, tool_input)
                    tool_duration = round((time.monotonic() - tool_start) * 1000, 2)

                    obs_content = (
                        tool_result.output
                        if tool_result.success
                        else f"Error: {tool_result.error}"
                    )
                    obs_step = AgentStep(
                        step_number=step_num,
                        step_type=StepType.OBSERVATION,
                        content=obs_content,
                        tool_name=tool_name,
                        tool_output=obs_content,
                        duration_ms=tool_duration,
                    )
                    steps.append(obs_step)
                    self._memory.add(MemoryType.TOOL, f"[{tool_name}] {obs_content}")

                    if self._config.verbose:
                        logger.info(
                            "Step %d OBSERVATION: %s", step_num, obs_content[:100]
                        )

                else:
                    # No clear action or final — treat as thought continuation
                    continue

            # Max steps reached without final answer
            self._state = AgentState.COMPLETED
            last_thought = next(
                (
                    s.content
                    for s in reversed(steps)
                    if s.step_type == StepType.THOUGHT
                ),
                "Maximum steps reached without a conclusive answer.",
            )
            return ExecutionResult(
                answer=last_thought,
                state=AgentState.COMPLETED,
                steps=tuple(steps),
                total_tokens=total_tokens,
                duration_seconds=round(time.monotonic() - start_time, 2),
                metadata={"max_steps_reached": True},
            )

        except Exception as exc:
            self._state = AgentState.FAILED
            logger.error("ReAct execution failed: %s", exc)
            return ExecutionResult(
                answer="",
                state=AgentState.FAILED,
                steps=tuple(steps),
                total_tokens=total_tokens,
                duration_seconds=round(time.monotonic() - start_time, 2),
                error=str(exc),
            )
        finally:
            # If we exited via return inside the try block, state is already set.
            # Only reset to IDLE if execution somehow left it as RUNNING.
            if self._state == AgentState.RUNNING:
                self._state = AgentState.IDLE

    def reset(self) -> None:
        """Reset engine to IDLE state and clear memory."""
        self._state = AgentState.IDLE
        self._memory.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate(self, prompt: str) -> Any:
        """Call LLM provider if available.

        Returns the LLMResponse object, or None if no provider is set
        or the provider call fails.
        """
        if self._llm is None:
            return None
        try:
            return self._llm.generate(prompt)
        except Exception as exc:
            logger.warning("LLM generation failed: %s", exc)
            return None

    def _build_prompt(self, query: str, steps: list[AgentStep]) -> str:
        """Build the prompt with tool descriptions and conversation history.

        Args:
            query: The original user query.
            steps: Steps executed so far (last 6 used for context window).

        Returns:
            Formatted prompt string for the LLM.
        """
        tools_desc = ""
        if self._tools.tool_count > 0:
            tool_lines: list[str] = []
            for tool in self._tools.list_tools():
                params = (
                    ", ".join(tool.required_params) if tool.required_params else "none"
                )
                tool_lines.append(
                    f"- {tool.name}: {tool.description} (params: {params})"
                )
            tools_desc = "Available tools:\n" + "\n".join(tool_lines) + "\n\n"

        history = ""
        if steps:
            history_lines: list[str] = []
            for s in steps[-6:]:  # Last 6 steps for context
                history_lines.append(f"[{s.step_type.value}] {s.content}")
            history = "Previous steps:\n" + "\n".join(history_lines) + "\n\n"

        return (
            f"{tools_desc}{history}"
            f"Query: {query}\n\n"
            f"Think step by step. If you can answer directly, respond with:\n"
            f"FINAL ANSWER: <your answer>\n\n"
            f"If you need to use a tool, respond with:\n"
            f"ACTION: <tool_name>\n"
            f"INPUT: <json input>\n"
        )

    def _parse_response(self, text: str) -> dict[str, Any]:
        """Parse LLM response to extract action or final answer.

        Precedence:
        1. FINAL ANSWER / FINAL / ANSWER marker -> return final answer
        2. ACTION marker -> parse tool name and INPUT block
        3. Fallback -> return as thought continuation

        Args:
            text: Raw LLM response text.

        Returns:
            Dict with key "type" set to "final", "action", or "thought".
        """
        text_upper = text.upper()

        # Check for final answer
        for marker in ("FINAL ANSWER:", "FINAL:", "ANSWER:"):
            idx = text_upper.find(marker)
            if idx >= 0:
                answer = text[idx + len(marker):].strip()
                return {"type": "final", "content": answer}

        # Check for action
        action_idx = text_upper.find("ACTION:")
        if action_idx >= 0:
            action_text = text[action_idx + 7:].strip()
            tool_name = action_text.split("\n")[0].strip()

            # Parse input block
            tool_input: dict[str, Any] = {}
            input_idx = text_upper.find("INPUT:")
            if input_idx >= 0:
                input_text = text[input_idx + 6:].strip()
                try:
                    tool_input = json.loads(input_text)
                except json.JSONDecodeError:
                    # Fall back to treating first line as a plain query string
                    tool_input = {"query": input_text.split("\n")[0].strip()}

            return {"type": "action", "tool": tool_name, "input": tool_input}

        # No clear directive — return as thought
        return {"type": "thought", "content": text}

    def _stub_think(self, query: str, steps: list[AgentStep]) -> str:
        """Generate stub thinking when no LLM is available.

        In stub mode:
        - If tools are available and no OBSERVATION step yet, invokes
          the first registered tool with the original query.
        - Otherwise returns a synthetic final answer so the loop exits.

        Args:
            query: The original user query.
            steps: Steps executed so far.

        Returns:
            A synthetic response string that _parse_response can interpret.
        """
        has_observation = any(
            s.step_type == StepType.OBSERVATION for s in steps
        )

        if not has_observation and self._tools.tool_count > 0:
            tool_name = self._tools.tool_names[0]
            return f'ACTION: {tool_name}\nINPUT: {{"query": "{query}"}}'

        return f"FINAL ANSWER: [Stub response for: {query}]"
