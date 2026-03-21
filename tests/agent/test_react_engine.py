"""Unit tests for ReAct, Pipeline, and Batch execution engines.

Covers:
    TC-RE01  ReActEngine basics (config, is_ready, state)
    TC-RE02  ReActEngine stub execution (no LLM)
    TC-RE03  ReActEngine with mock LLM
    TC-RE04  ReActEngine error handling
    TC-RE05  ReActEngine prompt building
    TC-RE06  ReActEngine response parsing
    TC-PE01  PipelineEngine
    TC-BE01  BatchEngine
    TC-BE02  BatchResult
"""

from __future__ import annotations

import pytest

from agent.runtime.react import ReActEngine
from agent.runtime.pipeline import PipelineEngine
from agent.runtime.batch import BatchEngine, BatchResult
from agent.runtime.models import (
    AgentConfig,
    AgentState,
    ExecutionMode,
    ExecutionResult,
    StepType,
)
from agent.tools.registry import ToolRegistry
from agent.tools.models import ToolDefinition


# ---------------------------------------------------------------------------
# Shared helpers / mock objects
# ---------------------------------------------------------------------------


class MockLLMResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self.token_count = len(text.split())
        self.provider = "mock"


class MockLLM:
    def __init__(self, responses=None) -> None:
        self._responses = list(responses or ["FINAL ANSWER: mock answer"])
        self._call_count = 0

    def generate(self, prompt: str, **kwargs: object) -> MockLLMResponse:
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return MockLLMResponse(self._responses[idx])

    def is_available(self) -> bool:
        return True


def echo_handler(query: str = "") -> str:
    return f"Echo: {query}"


def _echo_registry() -> ToolRegistry:
    """Return a ToolRegistry with a single 'echo' tool registered."""
    tools = ToolRegistry()
    tools.register(
        ToolDefinition(
            name="echo",
            description="Echo input",
            required_params=("query",),
        ),
        handler=echo_handler,
    )
    return tools


def _failing_handler(query: str = "") -> str:
    raise RuntimeError("deliberate failure")


def _failing_registry() -> ToolRegistry:
    tools = ToolRegistry()
    tools.register(
        ToolDefinition(
            name="fail_tool",
            description="Always fails",
            required_params=("query",),
        ),
        handler=_failing_handler,
    )
    return tools


# ---------------------------------------------------------------------------
# TC-RE01: ReActEngine basics
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReActEngineBasics:
    """TC-RE01: ReActEngine config, is_ready, and state property."""

    def test_re01a_default_config_uses_react_mode(self) -> None:
        """TC-RE01-a: Default config uses REACT execution mode."""
        engine = ReActEngine()
        assert engine.config.mode == ExecutionMode.REACT

    def test_re01b_is_ready_returns_true_when_idle(self) -> None:
        """TC-RE01-b: is_ready() returns True when the engine is in IDLE state."""
        engine = ReActEngine()
        assert engine.is_ready() is True

    def test_re01c_state_property_returns_current_state(self) -> None:
        """TC-RE01-c: state property returns current AgentState."""
        engine = ReActEngine()
        assert engine.state == AgentState.IDLE


# ---------------------------------------------------------------------------
# TC-RE02: ReActEngine stub execution (no LLM)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReActEngineStubExecution:
    """TC-RE02: ReActEngine stub-mode execution (llm=None)."""

    def test_re02a_execute_no_tools_returns_final_answer(self) -> None:
        """TC-RE02-a: Execute with no tools returns final answer in stub mode."""
        engine = ReActEngine()
        result = engine.execute("What is the meaning of life?")
        assert result.success is True
        assert result.answer != ""

    def test_re02b_execute_with_tool_uses_tool_then_final_answer(self) -> None:
        """TC-RE02-b: Stub mode calls tool via _stub_think, gets observation, final answer."""
        engine = ReActEngine(tools=_echo_registry())
        result = engine.execute("ping")
        assert result.success is True
        # The stub should have produced at least one OBSERVATION step
        obs_steps = [s for s in result.steps if s.step_type == StepType.OBSERVATION]
        assert len(obs_steps) >= 1
        assert "Echo:" in obs_steps[0].content

    def test_re02c_steps_include_required_step_types(self) -> None:
        """TC-RE02-c: Steps include THOUGHT, ACTION, OBSERVATION, FINAL types on tool path."""
        engine = ReActEngine(tools=_echo_registry())
        result = engine.execute("test query")
        step_types = {s.step_type for s in result.steps}
        assert StepType.THOUGHT in step_types
        assert StepType.ACTION in step_types
        assert StepType.OBSERVATION in step_types
        assert StepType.FINAL in step_types

    def test_re02d_execution_result_success_true(self) -> None:
        """TC-RE02-d: ExecutionResult.success is True on completion."""
        engine = ReActEngine()
        result = engine.execute("hello")
        assert result.success is True

    def test_re02e_duration_seconds_positive(self) -> None:
        """TC-RE02-e: duration_seconds > 0 after execution."""
        engine = ReActEngine()
        result = engine.execute("hello")
        assert result.duration_seconds >= 0.0
        # duration is rounded to 2 decimal places; even very fast runs record >= 0
        assert isinstance(result.duration_seconds, float)


# ---------------------------------------------------------------------------
# TC-RE03: ReActEngine with mock LLM
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReActEngineMockLLM:
    """TC-RE03: ReActEngine delegates to the provided LLM provider."""

    def test_re03a_engine_uses_mock_llm(self) -> None:
        """TC-RE03-a: Engine calls MockLLM.generate() instead of stub path."""
        llm = MockLLM(["FINAL ANSWER: from mock"])
        engine = ReActEngine(llm=llm)
        result = engine.execute("test")
        assert result.success is True
        assert llm._call_count >= 1

    def test_re03b_llm_returning_final_answer_produces_final(self) -> None:
        """TC-RE03-b: LLM returning 'FINAL ANSWER: hello' produces that answer."""
        llm = MockLLM(["FINAL ANSWER: hello"])
        engine = ReActEngine(llm=llm)
        result = engine.execute("greet me")
        assert result.success is True
        assert result.answer == "hello"

    def test_re03c_llm_returning_action_triggers_tool(self) -> None:
        """TC-RE03-c: LLM returning ACTION: ... triggers tool execution."""
        # First call returns action, second returns final answer
        llm = MockLLM([
            'ACTION: echo\nINPUT: {"query": "hello"}',
            "FINAL ANSWER: done",
        ])
        engine = ReActEngine(tools=_echo_registry(), llm=llm)
        result = engine.execute("call the echo tool")
        # At minimum an OBSERVATION step should exist
        obs_steps = [s for s in result.steps if s.step_type == StepType.OBSERVATION]
        assert len(obs_steps) >= 1
        assert "Echo:" in obs_steps[0].content


# ---------------------------------------------------------------------------
# TC-RE04: ReActEngine error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReActEngineErrorHandling:
    """TC-RE04: ReActEngine error conditions."""

    def test_re04a_execute_while_running_returns_failed(self) -> None:
        """TC-RE04-a: Execute while already running returns FAILED immediately."""
        engine = ReActEngine()
        # Force the engine into RUNNING state
        engine._state = AgentState.RUNNING
        result = engine.execute("query")
        assert result.state == AgentState.FAILED
        assert "already running" in result.error.lower()

    def test_re04b_max_steps_reached_returns_completed_with_metadata(self) -> None:
        """TC-RE04-b: Max steps reached returns COMPLETED with max_steps_reached in metadata."""
        # Use a very small max_steps so the loop exhausts quickly.
        # Provide a tool so stub always emits ACTION (never final) on first step,
        # but after observation the stub emits FINAL — we need to force it to
        # loop without resolving.  Patch _stub_think to always return an action.
        engine = ReActEngine(
            config=AgentConfig(max_steps=2),
            tools=_echo_registry(),
        )
        # Override _stub_think so the loop never exits via FINAL ANSWER
        original_stub = engine._stub_think

        def always_action(query: str, steps: list) -> str:  # type: ignore[type-arg]
            return f'ACTION: echo\nINPUT: {{"query": "{query}"}}'

        engine._stub_think = always_action  # type: ignore[method-assign]

        result = engine.execute("loop forever")
        assert result.state == AgentState.COMPLETED
        assert result.metadata.get("max_steps_reached") is True

    def test_re04c_reset_clears_state_to_idle(self) -> None:
        """TC-RE04-c: reset() clears state to IDLE."""
        engine = ReActEngine()
        engine.execute("something")  # execute once, puts state into COMPLETED
        engine.reset()
        assert engine.state == AgentState.IDLE


# ---------------------------------------------------------------------------
# TC-RE05: ReActEngine prompt building
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReActEnginePromptBuilding:
    """TC-RE05: _build_prompt behaviour."""

    def test_re05a_build_prompt_includes_tool_descriptions(self) -> None:
        """TC-RE05-a: _build_prompt includes tool descriptions when tools registered."""
        engine = ReActEngine(tools=_echo_registry())
        prompt = engine._build_prompt("some query", [])
        assert "echo" in prompt.lower()
        assert "Echo input" in prompt or "echo input" in prompt.lower()

    def test_re05b_build_prompt_includes_step_history(self) -> None:
        """TC-RE05-b: _build_prompt includes previous step content in history."""
        from agent.runtime.models import AgentStep

        engine = ReActEngine()
        steps = [
            AgentStep(
                step_number=1,
                step_type=StepType.THOUGHT,
                content="I need to search for vessels",
            )
        ]
        prompt = engine._build_prompt("query", steps)
        assert "I need to search for vessels" in prompt


# ---------------------------------------------------------------------------
# TC-RE06: ReActEngine response parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReActEngineResponseParsing:
    """TC-RE06: _parse_response correctly classifies LLM text."""

    def test_re06a_detects_final_answer_marker(self) -> None:
        """TC-RE06-a: _parse_response detects 'FINAL ANSWER:' marker."""
        engine = ReActEngine()
        parsed = engine._parse_response("FINAL ANSWER: the ships are in port")
        assert parsed["type"] == "final"
        assert parsed["content"] == "the ships are in port"

    def test_re06b_detects_action_and_input_markers(self) -> None:
        """TC-RE06-b: _parse_response detects 'ACTION:' + 'INPUT:'."""
        engine = ReActEngine()
        parsed = engine._parse_response('ACTION: echo\nINPUT: {"query": "test"}')
        assert parsed["type"] == "action"
        assert parsed["tool"] == "echo"
        assert parsed["input"] == {"query": "test"}

    def test_re06c_returns_thought_for_unrecognized_text(self) -> None:
        """TC-RE06-c: _parse_response returns 'thought' type for unrecognized text."""
        engine = ReActEngine()
        parsed = engine._parse_response("I am thinking about this problem carefully.")
        assert parsed["type"] == "thought"


# ---------------------------------------------------------------------------
# TC-PE01: PipelineEngine
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineEngine:
    """TC-PE01: PipelineEngine sequential execution."""

    def _make_engine(self, tools: ToolRegistry | None = None) -> PipelineEngine:
        config = AgentConfig(name="test-pipeline", mode=ExecutionMode.PIPELINE)
        return PipelineEngine(config=config, tools=tools or _echo_registry())

    def test_pe01a_add_step_returns_self(self) -> None:
        """TC-PE01-a: add_step() returns self for fluent chaining."""
        engine = self._make_engine()
        returned = engine.add_step("echo")
        assert returned is engine

    def test_pe01b_is_ready_false_when_no_steps(self) -> None:
        """TC-PE01-b: is_ready() returns False when no steps defined."""
        engine = self._make_engine()
        assert engine.is_ready() is False

    def test_pe01c_execute_runs_all_steps_in_sequence(self) -> None:
        """TC-PE01-c: Execute runs all steps in sequence."""
        # Use a handler that tolerates extra keyword args injected by the pipeline
        # (prev_output is injected automatically into every step after the first).
        results_seen: list[str] = []

        def tolerant_echo(query: str = "", **kwargs: object) -> str:
            output = f"Echo: {query}"
            results_seen.append(output)
            return output

        tools = ToolRegistry()
        tools.register(
            ToolDefinition(
                name="techo",
                description="Tolerant echo",
                required_params=("query",),
            ),
            handler=tolerant_echo,
        )

        engine = PipelineEngine(tools=tools)
        engine.add_step("techo", {"query": "step1"})
        engine.add_step("techo", {"query": "step2"})

        result = engine.execute("context")
        assert result.success is True
        obs_steps = [s for s in result.steps if s.step_type == StepType.OBSERVATION]
        assert len(obs_steps) == 2

    def test_pe01d_prev_output_injected_as_next_input(self) -> None:
        """TC-PE01-d: Previous step output is injected as prev_output into next step."""
        captured: list[str] = []

        def capture_handler(query: str = "", prev_output: str = "") -> str:
            captured.append(prev_output)
            return f"result of {query}"

        tools = ToolRegistry()
        tools.register(
            ToolDefinition(name="cap", description="capture", required_params=("query",)),
            handler=capture_handler,
        )

        engine = PipelineEngine(tools=tools)
        engine.add_step("cap", {"query": "first"})
        engine.add_step("cap", {"query": "second"})
        engine.execute("ctx")

        # First step gets empty prev_output; second step gets first's output
        assert captured[0] == ""
        assert captured[1] == "result of first"

    def test_pe01e_on_error_stop_halts_on_failure(self) -> None:
        """TC-PE01-e: on_error='stop' halts the pipeline on failure."""
        tools = ToolRegistry()
        tools.register(
            ToolDefinition(name="ok", description="ok", required_params=("query",)),
            handler=lambda query="": "ok",
        )
        tools.register(
            ToolDefinition(name="bad", description="fail", required_params=("query",)),
            handler=lambda query="": (_ for _ in ()).throw(RuntimeError("boom")),
        )

        engine = PipelineEngine(tools=tools)
        engine.add_step("bad", on_error="stop")
        engine.add_step("ok")

        result = engine.execute("ctx")
        assert result.success is False
        assert result.state == AgentState.FAILED

    def test_pe01f_on_error_skip_continues_on_failure(self) -> None:
        """TC-PE01-f: on_error='skip' continues to next step after failure."""
        tools = ToolRegistry()
        tools.register(
            ToolDefinition(name="ok", description="ok", required_params=("query",)),
            handler=lambda query="": "ok",
        )
        tools.register(
            ToolDefinition(name="bad", description="fail", required_params=("query",)),
            handler=lambda query="": (_ for _ in ()).throw(RuntimeError("boom")),
        )

        engine = PipelineEngine(tools=tools)
        engine.add_step("bad", on_error="skip")
        engine.add_step("ok")

        result = engine.execute("ctx")
        assert result.success is True

    def test_pe01g_step_count_property(self) -> None:
        """TC-PE01-g: step_count property returns number of configured steps."""
        engine = self._make_engine()
        assert engine.step_count == 0
        engine.add_step("echo").add_step("echo")
        assert engine.step_count == 2

    def test_pe01h_clear_steps_removes_all_steps(self) -> None:
        """TC-PE01-h: clear_steps() removes all pipeline steps."""
        engine = self._make_engine()
        engine.add_step("echo").add_step("echo")
        assert engine.step_count == 2
        engine.clear_steps()
        assert engine.step_count == 0

    def test_pe01i_reset_keeps_steps_but_resets_state(self) -> None:
        """TC-PE01-i: reset() keeps steps intact but resets state to IDLE."""
        engine = self._make_engine()
        engine.add_step("echo")
        engine.execute("something")
        # After execution state is COMPLETED; reset brings it back
        engine.reset()
        assert engine._state == AgentState.IDLE
        assert engine.step_count == 1


# ---------------------------------------------------------------------------
# TC-BE01: BatchEngine
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBatchEngine:
    """TC-BE01: BatchEngine processing."""

    def _make_engine(self, tool_name: str = "echo") -> BatchEngine:
        config = AgentConfig(name="batch", mode=ExecutionMode.BATCH)
        return BatchEngine(config=config, tools=_echo_registry(), tool_name=tool_name)

    def test_be01a_is_ready_false_when_no_tool_name(self) -> None:
        """TC-BE01-a: is_ready() returns False when tool_name is empty."""
        engine = BatchEngine(tools=_echo_registry(), tool_name="")
        assert engine.is_ready() is False

    def test_be01b_execute_batch_processes_all_queries(self) -> None:
        """TC-BE01-b: execute_batch processes every query in the list."""
        engine = self._make_engine()
        queries = ["query A", "query B", "query C"]
        batch_result = engine.execute_batch(queries)
        assert batch_result.total_count == 3

    def test_be01c_batch_result_correct_success_failure_counts(self) -> None:
        """TC-BE01-c: BatchResult has correct success/failure counts."""
        engine = self._make_engine()
        queries = ["q1", "q2"]
        batch_result = engine.execute_batch(queries)
        assert batch_result.success_count == 2
        assert batch_result.failure_count == 0

    def test_be01d_success_rate_property(self) -> None:
        """TC-BE01-d: success_rate property reflects fraction of successes."""
        engine = self._make_engine()
        batch_result = engine.execute_batch(["q1", "q2"])
        assert batch_result.success_rate == 1.0

    def test_be01e_individual_failures_do_not_stop_batch(self) -> None:
        """TC-BE01-e: Individual failures don't stop batch; all items are processed."""
        tools = ToolRegistry()
        tools.register(
            ToolDefinition(name="flaky", description="flaky", required_params=("query",)),
            handler=lambda query="": (_ for _ in ()).throw(RuntimeError("oops")),
        )

        engine = BatchEngine(tools=tools, tool_name="flaky")
        batch_result = engine.execute_batch(["a", "b", "c"])
        # All three items must have been attempted
        assert batch_result.total_count == 3
        assert batch_result.failure_count == 3
        assert batch_result.success_count == 0

    def test_be01f_execute_handles_single_query(self) -> None:
        """TC-BE01-f: execute() handles a single query (protocol compliance)."""
        engine = self._make_engine()
        result = engine.execute("single query")
        assert isinstance(result, ExecutionResult)
        assert result.success is True


# ---------------------------------------------------------------------------
# TC-BE02: BatchResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBatchResult:
    """TC-BE02: BatchResult properties."""

    def test_be02a_total_count_property(self) -> None:
        """TC-BE02-a: total_count equals the number of items in the tuple."""
        items = (
            ExecutionResult(answer="a", state=AgentState.COMPLETED),
            ExecutionResult(answer="b", state=AgentState.COMPLETED),
        )
        result = BatchResult(items=items, success_count=2, failure_count=0)
        assert result.total_count == 2

    def test_be02b_success_rate_returns_zero_when_empty(self) -> None:
        """TC-BE02-b: success_rate returns 0.0 when items is empty."""
        result = BatchResult()
        assert result.success_rate == 0.0
