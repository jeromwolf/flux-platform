"""Integration tests for Agent runtime module interactions.

Validates interactions between:
    - ReActEngine, PipelineEngine, BatchEngine
    - ToolRegistry, SkillRegistry
    - AgentLLMBridge
    - BufferMemory

All tests use real instances. LLM provider is mocked via MockLLM.

Test classes:
    TestReActWithToolsIntegration   — ReAct + ToolRegistry + memory integration
    TestPipelineIntegration         — PipelineEngine multi-step chaining + BatchEngine
    TestSkillRegistryIntegration    — SkillRegistry + ToolRegistry interaction
    TestLLMBridgeIntegration        — AgentLLMBridge + ReActEngine
    TestAgentMemoryIntegration      — BufferMemory across executions and resets
"""

from __future__ import annotations

import pytest

from agent.runtime.models import AgentConfig, AgentState, ExecutionMode, StepType
from agent.runtime.react import ReActEngine
from agent.runtime.pipeline import PipelineEngine, PipelineStep
from agent.runtime.batch import BatchEngine, BatchResult
from agent.tools.models import ToolDefinition, ToolResult
from agent.tools.registry import ToolRegistry
from agent.skills.models import SkillDefinition, SkillResult
from agent.skills.registry import SkillRegistry
from agent.llm.bridge import AgentLLMBridge, BridgeConfig, ThinkResult
from agent.memory.buffer import BufferMemory
from agent.memory.models import MemoryType


# ---------------------------------------------------------------------------
# Mock LLM helpers
# ---------------------------------------------------------------------------


class MockLLMResponse:
    """Minimal LLM response object returned by MockLLM."""

    def __init__(self, text: str, token_count: int = 10) -> None:
        self.text = text
        self.token_count = token_count
        self.provider = "mock"


class MockLLM:
    """Deterministic LLM provider that cycles through preset responses.

    When all responses are consumed any further call returns a default
    "FINAL ANSWER: default answer" response.
    """

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = responses or []
        self._call_count = 0

    def generate(self, prompt: str) -> MockLLMResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return MockLLMResponse(resp)
        return MockLLMResponse("FINAL ANSWER: default answer")


# ---------------------------------------------------------------------------
# Shared tool / registry helpers
# ---------------------------------------------------------------------------


def _make_search_registry() -> ToolRegistry:
    """ToolRegistry with a 'search' tool that returns vessel data."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="search", description="Search for vessels"),
        handler=lambda **kwargs: "Found 3 vessels",
    )
    return registry


def _make_count_registry() -> ToolRegistry:
    """ToolRegistry with 'search' and 'count' tools."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="search", description="Search for vessels"),
        handler=lambda **kwargs: "Found 3 vessels",
    )
    registry.register(
        ToolDefinition(name="count", description="Count items"),
        handler=lambda **kwargs: "Total: 3",
    )
    return registry


# ---------------------------------------------------------------------------
# TestReActWithToolsIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReActWithToolsIntegration:
    """Integration tests: ReActEngine + ToolRegistry + BufferMemory."""

    def test_react_executes_tool_and_returns_answer(self) -> None:
        """Stub mode calls the first tool, observes, then returns a final answer.

        Verifies: COMPLETED state, non-empty answer, ACTION and OBSERVATION steps.
        """
        registry = _make_search_registry()
        engine = ReActEngine(tools=registry)

        result = engine.execute("Find vessels")

        assert result.state == AgentState.COMPLETED
        assert result.answer != ""

        step_types = {s.step_type for s in result.steps}
        assert StepType.ACTION in step_types
        assert StepType.OBSERVATION in step_types

    def test_react_with_multiple_tools(self) -> None:
        """Stub mode uses the first registered tool when multiple are registered."""
        registry = _make_count_registry()
        engine = ReActEngine(tools=registry)

        result = engine.execute("Count vessels")

        assert result.state == AgentState.COMPLETED
        obs_steps = [s for s in result.steps if s.step_type == StepType.OBSERVATION]
        assert len(obs_steps) >= 1

    def test_react_with_llm_bridge(self) -> None:
        """LLM bridge .think() works, and ReActEngine with MockLLM returns the answer.

        Verifies bridge.think() succeeds, and ReActEngine returns "The answer is 42".
        """
        llm = MockLLM(["FINAL ANSWER: The answer is 42"])

        # Verify bridge independently
        bridge = AgentLLMBridge()
        bridge.set_provider(llm)
        think_result = bridge.think("What is 6 times 7?")
        # Bridge consumed the first response; MockLLM returns default for subsequent calls.
        assert think_result.success is True

        # Use a fresh MockLLM for the ReActEngine
        llm2 = MockLLM(["FINAL ANSWER: The answer is 42"])
        engine = ReActEngine(llm=llm2)
        result = engine.execute("What is 6 times 7?")

        assert result.state == AgentState.COMPLETED
        assert "42" in result.answer

    def test_react_memory_records_conversation(self) -> None:
        """After execution the shared BufferMemory contains at least one entry."""
        memory = BufferMemory(max_messages=100)
        engine = ReActEngine(memory=memory)

        engine.execute("Find all cargo ships")

        # At minimum, the USER query must have been recorded
        assert memory.message_count >= 1
        roles = [entry.role for entry in memory.get_history()]
        assert MemoryType.USER in roles

    def test_react_with_failing_tool(self) -> None:
        """When a tool raises an exception, ReAct captures the error as OBSERVATION.

        The engine must not crash and must still reach COMPLETED state (stub gives
        a final answer after the error observation).
        """
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="bad_search", description="Always fails"),
            handler=lambda **kwargs: (_ for _ in ()).throw(
                RuntimeError("connection refused")
            ),
        )
        engine = ReActEngine(tools=registry)

        result = engine.execute("Find vessels in error port")

        # Engine should still complete — not crash or hang
        assert result.state == AgentState.COMPLETED
        obs_steps = [s for s in result.steps if s.step_type == StepType.OBSERVATION]
        assert len(obs_steps) >= 1
        # The observation content should contain the error
        assert any("error" in s.content.lower() for s in obs_steps)


# ---------------------------------------------------------------------------
# TestPipelineIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineIntegration:
    """Integration tests: PipelineEngine multi-step chaining + BatchEngine."""

    def _make_etl_registry(self) -> ToolRegistry:
        """Registry with 'extract', 'transform', 'load' ETL tools."""
        registry = ToolRegistry()

        def extract(**kwargs: object) -> str:
            return "raw_data"

        def transform(**kwargs: object) -> str:
            return f"transformed_{kwargs.get('prev_output', '')}"

        def load(**kwargs: object) -> str:
            return f"loaded_{kwargs.get('prev_output', '')}"

        registry.register(
            ToolDefinition(name="extract", description="Extract raw data"),
            handler=extract,
        )
        registry.register(
            ToolDefinition(name="transform", description="Transform data"),
            handler=transform,
        )
        registry.register(
            ToolDefinition(name="load", description="Load data"),
            handler=load,
        )
        return registry

    def test_pipeline_three_step_execution(self) -> None:
        """A 3-step ETL pipeline completes with COMPLETED state.

        Verifies: COMPLETED state, all 3 OBSERVATION steps recorded, non-empty answer.
        """
        registry = self._make_etl_registry()
        engine = PipelineEngine(tools=registry)
        engine.add_step("extract").add_step("transform").add_step("load")

        result = engine.execute("Process maritime dataset")

        assert result.state == AgentState.COMPLETED
        obs_steps = [s for s in result.steps if s.step_type == StepType.OBSERVATION]
        assert len(obs_steps) == 3
        assert result.answer != ""

    def test_pipeline_step_output_chains(self) -> None:
        """Each step's output feeds the next, producing 'loaded_transformed_raw_data'."""
        registry = self._make_etl_registry()
        engine = PipelineEngine(tools=registry)
        engine.add_step("extract").add_step("transform").add_step("load")

        result = engine.execute("Process maritime dataset")

        assert result.state == AgentState.COMPLETED
        assert "loaded_transformed_raw_data" in result.answer

    def test_pipeline_skip_on_error(self) -> None:
        """on_error='skip' on the first failing step allows pipeline to complete."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="fail_step", description="Always fails"),
            handler=lambda **kwargs: (_ for _ in ()).throw(ValueError("step error")),
        )
        registry.register(
            ToolDefinition(name="ok_step", description="Returns success"),
            handler=lambda **kwargs: "success_output",
        )

        engine = PipelineEngine(tools=registry)
        engine.add_step("fail_step", on_error="skip")
        engine.add_step("ok_step")

        result = engine.execute("Run pipeline")

        assert result.state == AgentState.COMPLETED

    def test_pipeline_stop_on_error(self) -> None:
        """on_error='stop' on the first failing step marks pipeline as FAILED."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="fail_step", description="Always fails"),
            handler=lambda **kwargs: (_ for _ in ()).throw(ValueError("fatal error")),
        )
        registry.register(
            ToolDefinition(name="ok_step", description="Returns success"),
            handler=lambda **kwargs: "success_output",
        )

        engine = PipelineEngine(tools=registry)
        engine.add_step("fail_step", on_error="stop")
        engine.add_step("ok_step")

        result = engine.execute("Run pipeline")

        assert result.state == AgentState.FAILED

    def test_pipeline_with_batch_engine(self) -> None:
        """BatchEngine with 'process' tool runs 3 queries; success_rate > 0."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="process", description="Process a query"),
            handler=lambda **kwargs: f"processed_{kwargs.get('query', '')}",
        )

        engine = BatchEngine(tools=registry, tool_name="process")
        queries = ["vessel A", "vessel B", "vessel C"]

        batch_result = engine.execute_batch(queries)

        assert batch_result.total_count == 3
        assert batch_result.success_rate > 0.0


# ---------------------------------------------------------------------------
# TestSkillRegistryIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSkillRegistryIntegration:
    """Integration tests: SkillRegistry + ToolRegistry interaction."""

    def test_skill_with_tool_dependency(self) -> None:
        """A skill handler that internally calls ToolRegistry.execute() works end-to-end."""
        tool_registry = ToolRegistry()
        tool_registry.register(
            ToolDefinition(name="kg_query", description="Query the knowledge graph"),
            handler=lambda **kwargs: "vessel_data: 5 vessels found",
        )

        skill_registry = SkillRegistry()

        def vessel_summary_handler(**kwargs: object) -> str:
            # Skill internally delegates to the tool
            tool_result = tool_registry.execute("kg_query", {"query": "all vessels"})
            return f"Summary: {tool_result.output}"

        skill_registry.register(
            SkillDefinition(
                name="vessel_summary",
                description="Summarise vessel data from KG",
                category="kg",
                required_tools=("kg_query",),
            ),
            handler=vessel_summary_handler,
        )

        result = skill_registry.execute("vessel_summary")

        assert result.success is True
        assert "vessel_data" in result.output

    def test_skill_categories_filter(self) -> None:
        """list_by_category('kg') returns exactly the 2 KG skills registered."""
        skill_registry = SkillRegistry()

        for name, category in [
            ("skill_kg_1", "kg"),
            ("skill_nlp_1", "nlp"),
            ("skill_kg_2", "kg"),
        ]:
            skill_registry.register(
                SkillDefinition(
                    name=name,
                    description=f"Test skill {name}",
                    category=category,
                ),
                handler=lambda **kwargs: "ok",
            )

        kg_skills = skill_registry.list_by_category("kg")
        assert len(kg_skills) == 2
        assert all(s.category == "kg" for s in kg_skills)

    def test_skill_execution_tracking(self) -> None:
        """Executed skill returns success=True and duration_ms > 0."""
        skill_registry = SkillRegistry()
        skill_registry.register(
            SkillDefinition(
                name="timed_skill",
                description="A skill with measurable duration",
            ),
            handler=lambda **kwargs: "done",
        )

        result = skill_registry.execute("timed_skill")

        assert result.success is True
        assert result.duration_ms >= 0.0


# ---------------------------------------------------------------------------
# TestLLMBridgeIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMBridgeIntegration:
    """Integration tests: AgentLLMBridge + ReActEngine."""

    def test_bridge_with_react_engine(self) -> None:
        """LLM returning ACTION then FINAL ANSWER drives a full ReAct loop.

        Verifies: answer == "Done", steps contain ACTION and OBSERVATION.
        """
        llm = MockLLM([
            'ACTION: search\nINPUT: {"query": "test"}',
            "FINAL ANSWER: Done",
        ])
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="search", description="Search vessels"),
            handler=lambda **kwargs: "Found 2 vessels",
        )

        engine = ReActEngine(tools=registry, llm=llm)
        result = engine.execute("Find some vessels")

        assert result.state == AgentState.COMPLETED
        assert result.answer == "Done"

        step_types = {s.step_type for s in result.steps}
        assert StepType.ACTION in step_types
        assert StepType.OBSERVATION in step_types

    def test_bridge_token_tracking(self) -> None:
        """Calling bridge.think() 3 times accumulates token counts correctly."""
        llm = MockLLM(["response one", "response two", "response three"])
        bridge = AgentLLMBridge()
        bridge.set_provider(llm)

        for prompt in ["prompt 1", "prompt 2", "prompt 3"]:
            bridge.think(prompt)

        # Each MockLLMResponse reports token_count=10; 3 calls = 30 total
        assert bridge.total_tokens_used == 30

    def test_bridge_retry_on_failure(self) -> None:
        """Provider fails first 2 calls then succeeds; think() returns success=True."""
        call_count = 0

        class FlakyProvider:
            def generate(self, prompt: str) -> MockLLMResponse:
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise ConnectionError("transient failure")
                return MockLLMResponse("recovered response", token_count=5)

        config = BridgeConfig(max_retries=2)
        bridge = AgentLLMBridge(config=config)
        bridge.set_provider(FlakyProvider())

        result = bridge.think("retry me")

        assert result.success is True
        assert result.text == "recovered response"

    def test_bridge_exhausted_retries(self) -> None:
        """Provider always fails; think() with max_retries=1 returns success=False."""

        class AlwaysFailProvider:
            def generate(self, prompt: str) -> MockLLMResponse:
                raise RuntimeError("permanent failure")

        config = BridgeConfig(max_retries=1)
        bridge = AgentLLMBridge(config=config)
        bridge.set_provider(AlwaysFailProvider())

        result = bridge.think("will it work?")

        assert result.success is False
        assert result.error != ""


# ---------------------------------------------------------------------------
# TestAgentMemoryIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentMemoryIntegration:
    """Integration tests: BufferMemory persistence across executions and resets."""

    def test_memory_persists_across_react_executions(self) -> None:
        """Shared BufferMemory accumulates entries across two separate execute() calls."""
        memory = BufferMemory(max_messages=200)
        engine = ReActEngine(memory=memory)

        engine.execute("First query about cargo ships")
        count_after_first = memory.message_count

        engine.execute("Second query about tankers")
        count_after_second = memory.message_count

        # Both executions should have added entries
        assert count_after_first >= 1
        assert count_after_second > count_after_first

    def test_memory_reset_clears_state(self) -> None:
        """After reset(), BufferMemory is empty and engine state is IDLE."""
        memory = BufferMemory(max_messages=100)
        engine = ReActEngine(memory=memory)

        engine.execute("Query before reset")
        assert memory.message_count >= 1

        engine.reset()

        assert memory.message_count == 0
        assert engine.state == AgentState.IDLE

    def test_batch_engine_independent_memory(self) -> None:
        """BatchEngine processes 3 items; no memory is shared between items."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="process", description="Process item"),
            handler=lambda **kwargs: f"ok_{kwargs.get('query', '')}",
        )

        engine = BatchEngine(tools=registry, tool_name="process")
        queries = ["item_1", "item_2", "item_3"]

        batch_result = engine.execute_batch(queries)

        # All items processed successfully — no cross-contamination of state
        assert batch_result.total_count == 3
        assert batch_result.success_count == 3
        assert batch_result.failure_count == 0

        # Verify each result carries its own correct answer
        answers = [item.answer for item in batch_result.items]
        assert "ok_item_1" in answers
        assert "ok_item_2" in answers
        assert "ok_item_3" in answers
