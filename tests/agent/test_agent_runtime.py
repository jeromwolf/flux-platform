"""Unit tests for agent runtime skeleton modules.

Covers:
    TC-AR01  ExecutionMode enum
    TC-AR02  StepType enum
    TC-AR03  AgentConfig dataclass
    TC-AR04  AgentStep dataclass
    TC-AR05  ExecutionResult dataclass
    TC-AR06  AgentState enum
    TC-AR07  ToolDefinition.validate_input
    TC-AR08  ToolResult dataclass
    TC-AR09  ToolRegistry
    TC-AR10  MemoryEntry dataclass
    TC-AR11  MemoryType enum
    TC-AR12  BufferMemory
    TC-AR13  ConversationMemory protocol
"""

from __future__ import annotations

import dataclasses

import pytest

from agent.runtime.models import (
    AgentConfig,
    AgentState,
    AgentStep,
    ExecutionMode,
    ExecutionResult,
    StepType,
)
from agent.tools.models import ToolDefinition, ToolResult
from agent.tools.registry import ToolRegistry
from agent.memory.models import MemoryEntry, MemoryType
from agent.memory.buffer import BufferMemory
from agent.memory.protocol import ConversationMemory


# ---------------------------------------------------------------------------
# TC-AR01: ExecutionMode enum
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExecutionMode:
    """TC-AR01: ExecutionMode enum."""

    def test_ar01a_has_required_members(self) -> None:
        """TC-AR01-a: Has REACT, PIPELINE, BATCH values."""
        assert hasattr(ExecutionMode, "REACT")
        assert hasattr(ExecutionMode, "PIPELINE")
        assert hasattr(ExecutionMode, "BATCH")

    def test_ar01b_values_are_strings(self) -> None:
        """TC-AR01-b: Values are strings."""
        assert isinstance(ExecutionMode.REACT.value, str)
        assert isinstance(ExecutionMode.PIPELINE.value, str)
        assert isinstance(ExecutionMode.BATCH.value, str)


# ---------------------------------------------------------------------------
# TC-AR02: StepType enum
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStepType:
    """TC-AR02: StepType enum."""

    def test_ar02a_has_required_members(self) -> None:
        """TC-AR02-a: Has THOUGHT, ACTION, OBSERVATION, FINAL."""
        assert hasattr(StepType, "THOUGHT")
        assert hasattr(StepType, "ACTION")
        assert hasattr(StepType, "OBSERVATION")
        assert hasattr(StepType, "FINAL")


# ---------------------------------------------------------------------------
# TC-AR03: AgentConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentConfig:
    """TC-AR03: AgentConfig dataclass."""

    def test_ar03a_default_values(self) -> None:
        """TC-AR03-a: Default values are applied correctly."""
        cfg = AgentConfig()
        assert cfg.name == "default"
        assert cfg.mode == ExecutionMode.REACT
        assert cfg.max_steps == 10
        assert isinstance(cfg.timeout, float)
        assert isinstance(cfg.temperature, float)
        assert isinstance(cfg.model, str)
        assert isinstance(cfg.verbose, bool)

    def test_ar03b_custom_values(self) -> None:
        """TC-AR03-b: Custom values override defaults."""
        cfg = AgentConfig(
            name="my-agent",
            mode=ExecutionMode.PIPELINE,
            max_steps=20,
            timeout=60.0,
            temperature=0.3,
            model="llama3",
            verbose=True,
        )
        assert cfg.name == "my-agent"
        assert cfg.mode == ExecutionMode.PIPELINE
        assert cfg.max_steps == 20
        assert cfg.timeout == 60.0
        assert cfg.temperature == 0.3
        assert cfg.model == "llama3"
        assert cfg.verbose is True

    def test_ar03c_frozen(self) -> None:
        """TC-AR03-c: AgentConfig is immutable (frozen dataclass)."""
        cfg = AgentConfig()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            cfg.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-AR04: AgentStep
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentStep:
    """TC-AR04: AgentStep dataclass."""

    def test_ar04a_construction_with_required_fields(self) -> None:
        """TC-AR04-a: Constructs correctly with required fields."""
        step = AgentStep(
            step_number=1,
            step_type=StepType.THOUGHT,
            content="Planning the next action",
        )
        assert step.step_number == 1
        assert step.step_type == StepType.THOUGHT
        assert step.content == "Planning the next action"

    def test_ar04b_default_empty_tool_fields(self) -> None:
        """TC-AR04-b: tool_name, tool_input, tool_output default to empty."""
        step = AgentStep(step_number=1, step_type=StepType.THOUGHT, content="x")
        assert step.tool_name == ""
        assert step.tool_input == {}
        assert step.tool_output == ""

    def test_ar04c_timestamp_auto_set(self) -> None:
        """TC-AR04-c: timestamp is automatically set to a positive float."""
        step = AgentStep(step_number=1, step_type=StepType.ACTION, content="act")
        assert isinstance(step.timestamp, float)
        assert step.timestamp > 0.0


# ---------------------------------------------------------------------------
# TC-AR05: ExecutionResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExecutionResult:
    """TC-AR05: ExecutionResult dataclass."""

    def _completed_result(self) -> ExecutionResult:
        return ExecutionResult(answer="done", state=AgentState.COMPLETED)

    def _failed_result(self) -> ExecutionResult:
        return ExecutionResult(
            answer="",
            state=AgentState.FAILED,
            error="something went wrong",
        )

    def _result_with_steps(self) -> ExecutionResult:
        steps = tuple(
            AgentStep(step_number=i, step_type=StepType.THOUGHT, content=f"step {i}")
            for i in range(1, 4)
        )
        return ExecutionResult(answer="ok", state=AgentState.COMPLETED, steps=steps)

    def test_ar05a_success_true_when_completed(self) -> None:
        """TC-AR05-a: success returns True when state is COMPLETED."""
        assert self._completed_result().success is True

    def test_ar05b_success_false_when_failed(self) -> None:
        """TC-AR05-b: success returns False when state is FAILED."""
        assert self._failed_result().success is False

    def test_ar05c_step_count_property(self) -> None:
        """TC-AR05-c: step_count returns the number of steps."""
        result = self._result_with_steps()
        assert result.step_count == 3

    def test_ar05d_frozen(self) -> None:
        """TC-AR05-d: ExecutionResult is immutable (frozen dataclass)."""
        result = self._completed_result()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            result.answer = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-AR06: AgentState enum
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentState:
    """TC-AR06: AgentState enum."""

    def test_ar06a_has_required_members(self) -> None:
        """TC-AR06-a: Has IDLE, RUNNING, COMPLETED, FAILED, TIMEOUT."""
        assert hasattr(AgentState, "IDLE")
        assert hasattr(AgentState, "RUNNING")
        assert hasattr(AgentState, "COMPLETED")
        assert hasattr(AgentState, "FAILED")
        assert hasattr(AgentState, "TIMEOUT")


# ---------------------------------------------------------------------------
# TC-AR07: ToolDefinition
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestToolDefinition:
    """TC-AR07: ToolDefinition validate_input."""

    def _search_tool(self) -> ToolDefinition:
        return ToolDefinition(
            name="search",
            description="Search the knowledge graph",
            parameters={"query": {"type": "string"}, "limit": {"type": "integer"}},
            required_params=("query",),
        )

    def test_ar07a_validate_input_passes_with_all_required_params(self) -> None:
        """TC-AR07-a: validate_input returns empty list when all required params present."""
        tool = self._search_tool()
        errors = tool.validate_input({"query": "vessels", "limit": 10})
        assert errors == []

    def test_ar07b_validate_input_returns_errors_for_missing_params(self) -> None:
        """TC-AR07-b: validate_input returns error messages for missing params."""
        tool = self._search_tool()
        errors = tool.validate_input({})
        assert len(errors) == 1
        assert "query" in errors[0]

    def test_ar07c_is_dangerous_default_false(self) -> None:
        """TC-AR07-c: is_dangerous defaults to False."""
        tool = ToolDefinition(name="safe-tool", description="Harmless")
        assert tool.is_dangerous is False


# ---------------------------------------------------------------------------
# TC-AR08: ToolResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestToolResult:
    """TC-AR08: ToolResult dataclass."""

    def test_ar08a_default_success_true(self) -> None:
        """TC-AR08-a: success defaults to True."""
        result = ToolResult(tool_name="search", output="found 3 results")
        assert result.success is True

    def test_ar08b_can_set_error(self) -> None:
        """TC-AR08-b: Can construct with error and success=False."""
        result = ToolResult(
            tool_name="search",
            output="",
            success=False,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"


# ---------------------------------------------------------------------------
# TC-AR09: ToolRegistry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestToolRegistry:
    """TC-AR09: ToolRegistry."""

    def _make_registry(self) -> ToolRegistry:
        return ToolRegistry()

    def _echo_tool_def(self) -> ToolDefinition:
        return ToolDefinition(
            name="echo",
            description="Echo the message back",
            required_params=("message",),
        )

    def _add_tool_def(self) -> ToolDefinition:
        return ToolDefinition(
            name="add",
            description="Add two numbers",
            required_params=("a", "b"),
        )

    def test_ar09a_register_and_get_tool(self) -> None:
        """TC-AR09-a: Register a tool and retrieve its definition."""
        registry = self._make_registry()
        defn = self._echo_tool_def()
        registry.register(defn, handler=lambda message: message)
        retrieved = registry.get("echo")
        assert retrieved is not None
        assert retrieved.name == "echo"

    def test_ar09b_execute_registered_tool(self) -> None:
        """TC-AR09-b: Executing a registered tool returns success result."""
        registry = self._make_registry()
        registry.register(
            self._echo_tool_def(),
            handler=lambda message: f"echo: {message}",
        )
        result = registry.execute("echo", {"message": "hello"})
        assert result.success is True
        assert "hello" in result.output

    def test_ar09c_execute_unknown_tool_returns_error(self) -> None:
        """TC-AR09-c: Executing an unknown tool returns error result."""
        registry = self._make_registry()
        result = registry.execute("nonexistent")
        assert result.success is False
        assert "nonexistent" in result.error.lower() or "unknown" in result.error.lower()

    def test_ar09d_execute_with_missing_required_params_returns_error(self) -> None:
        """TC-AR09-d: Executing with missing required params returns error."""
        registry = self._make_registry()
        registry.register(
            self._echo_tool_def(),
            handler=lambda message: message,
        )
        result = registry.execute("echo", {})
        assert result.success is False
        assert "message" in result.error

    def test_ar09e_execute_tool_raising_exception_returns_error(self) -> None:
        """TC-AR09-e: When the handler raises, returns error result."""
        registry = self._make_registry()
        registry.register(
            self._echo_tool_def(),
            handler=lambda message: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        result = registry.execute("echo", {"message": "hi"})
        assert result.success is False
        assert "boom" in result.error

    def test_ar09f_tool_names_count_list_tools(self) -> None:
        """TC-AR09-f: tool_names, tool_count, list_tools reflect registered tools."""
        registry = self._make_registry()
        assert registry.tool_count == 0
        assert registry.tool_names == []
        assert registry.list_tools() == []

        registry.register(self._echo_tool_def(), handler=lambda message: message)
        registry.register(self._add_tool_def(), handler=lambda a, b: a + b)

        assert registry.tool_count == 2
        assert set(registry.tool_names) == {"echo", "add"}
        names_from_list = {t.name for t in registry.list_tools()}
        assert names_from_list == {"echo", "add"}

    def test_ar09g_clear_removes_all_tools(self) -> None:
        """TC-AR09-g: clear() removes all registered tools."""
        registry = self._make_registry()
        registry.register(self._echo_tool_def(), handler=lambda message: message)
        assert registry.tool_count == 1

        registry.clear()
        assert registry.tool_count == 0
        assert registry.tool_names == []

    def test_ar09h_fluent_chaining_on_register(self) -> None:
        """TC-AR09-h: register() returns the registry itself for chaining."""
        registry = self._make_registry()
        returned = registry.register(
            self._echo_tool_def(),
            handler=lambda message: message,
        )
        assert returned is registry

        # Chaining two registrations
        (
            registry
            .register(self._add_tool_def(), handler=lambda a, b: a + b)
        )
        assert registry.tool_count == 2


# ---------------------------------------------------------------------------
# TC-AR10: MemoryEntry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMemoryEntry:
    """TC-AR10: MemoryEntry dataclass."""

    def test_ar10a_construction_with_role_and_content(self) -> None:
        """TC-AR10-a: Constructs with role and content."""
        entry = MemoryEntry(role=MemoryType.USER, content="Hello, agent!")
        assert entry.role == MemoryType.USER
        assert entry.content == "Hello, agent!"

    def test_ar10b_frozen(self) -> None:
        """TC-AR10-b: MemoryEntry is immutable (frozen dataclass)."""
        entry = MemoryEntry(role=MemoryType.USER, content="hi")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            entry.content = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-AR11: MemoryType enum
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMemoryType:
    """TC-AR11: MemoryType enum."""

    def test_ar11a_has_required_members(self) -> None:
        """TC-AR11-a: Has USER, ASSISTANT, SYSTEM, TOOL."""
        assert hasattr(MemoryType, "USER")
        assert hasattr(MemoryType, "ASSISTANT")
        assert hasattr(MemoryType, "SYSTEM")
        assert hasattr(MemoryType, "TOOL")


# ---------------------------------------------------------------------------
# TC-AR12: BufferMemory
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBufferMemory:
    """TC-AR12: BufferMemory."""

    def test_ar12a_empty_on_creation(self) -> None:
        """TC-AR12-a: Fresh BufferMemory has no messages."""
        mem = BufferMemory()
        assert mem.message_count == 0
        assert mem.get_history() == []

    def test_ar12b_add_and_get_history(self) -> None:
        """TC-AR12-b: add() appends entries retrievable via get_history()."""
        mem = BufferMemory()
        mem.add(MemoryType.USER, "Hi")
        mem.add(MemoryType.ASSISTANT, "Hello!")
        history = mem.get_history()
        assert len(history) == 2
        assert history[0].role == MemoryType.USER
        assert history[0].content == "Hi"
        assert history[1].role == MemoryType.ASSISTANT
        assert history[1].content == "Hello!"

    def test_ar12c_get_history_with_limit(self) -> None:
        """TC-AR12-c: get_history(limit) returns last N messages."""
        mem = BufferMemory()
        for i in range(5):
            mem.add(MemoryType.USER, f"msg {i}")
        history = mem.get_history(limit=3)
        assert len(history) == 3
        assert history[-1].content == "msg 4"

    def test_ar12d_max_messages_ring_buffer(self) -> None:
        """TC-AR12-d: max_messages enforces a ring buffer, keeping only last N."""
        mem = BufferMemory(max_messages=3)
        for i in range(6):
            mem.add(MemoryType.USER, f"msg {i}")
        assert mem.message_count == 3
        history = mem.get_history()
        contents = [e.content for e in history]
        assert contents == ["msg 3", "msg 4", "msg 5"]

    def test_ar12e_clear_removes_all_messages(self) -> None:
        """TC-AR12-e: clear() empties the buffer."""
        mem = BufferMemory()
        mem.add(MemoryType.USER, "hi")
        mem.add(MemoryType.ASSISTANT, "hello")
        mem.clear()
        assert mem.message_count == 0
        assert mem.get_history() == []

    def test_ar12f_message_count_property(self) -> None:
        """TC-AR12-f: message_count reflects actual number of entries."""
        mem = BufferMemory()
        assert mem.message_count == 0
        mem.add(MemoryType.SYSTEM, "You are a helpful assistant.")
        assert mem.message_count == 1
        mem.add(MemoryType.USER, "query")
        assert mem.message_count == 2


# ---------------------------------------------------------------------------
# TC-AR13: ConversationMemory protocol
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConversationMemoryProtocol:
    """TC-AR13: ConversationMemory protocol."""

    def test_ar13a_buffer_memory_satisfies_protocol(self) -> None:
        """TC-AR13-a: BufferMemory satisfies ConversationMemory (isinstance check)."""
        mem = BufferMemory()
        assert isinstance(mem, ConversationMemory)
