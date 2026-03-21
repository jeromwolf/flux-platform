"""Unit tests for agent LLM bridge and skill registry.

Covers:
    TC-LB01  BridgeConfig dataclass
    TC-LB02  ThinkResult dataclass
    TC-LB03  AgentLLMBridge without provider
    TC-LB04  AgentLLMBridge with mock provider
    TC-LB05  AgentLLMBridge error handling
    TC-LB06  AgentLLMBridge prompt formatting
    TC-SK01  SkillDefinition dataclass
    TC-SK02  SkillResult dataclass
    TC-SK03  SkillRegistry
"""

from __future__ import annotations

import dataclasses

import pytest

from agent.llm.bridge import AgentLLMBridge, BridgeConfig, ThinkResult
from agent.skills.models import SkillDefinition, SkillResult
from agent.skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# Mock provider helpers
# ---------------------------------------------------------------------------


class MockResponse:
    def __init__(self, text: str = "mock response") -> None:
        self.text = text
        self.token_count = 5
        self.provider = "mock"


class MockProvider:
    def __init__(
        self,
        responses: list[MockResponse] | None = None,
        fail_count: int = 0,
    ) -> None:
        self._responses = responses or [MockResponse()]
        self._fail_count = fail_count
        self._calls = 0

    def generate(self, prompt: str, **kwargs: object) -> MockResponse:
        self._calls += 1
        if self._calls <= self._fail_count:
            raise RuntimeError("Provider error")
        idx = min(self._calls - self._fail_count - 1, len(self._responses) - 1)
        return self._responses[idx]

    def is_available(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# TC-LB01: BridgeConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBridgeConfig:
    """TC-LB01: BridgeConfig dataclass."""

    def test_lb01a_default_values(self) -> None:
        """TC-LB01-a: Default values match spec."""
        cfg = BridgeConfig()
        assert cfg.system_prompt == "You are a helpful AI assistant with access to tools."
        assert cfg.max_retries == 2
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 2048

    def test_lb01b_frozen(self) -> None:
        """TC-LB01-b: BridgeConfig is immutable (frozen dataclass)."""
        cfg = BridgeConfig()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            cfg.max_retries = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-LB02: ThinkResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestThinkResult:
    """TC-LB02: ThinkResult dataclass."""

    def test_lb02a_default_success_is_true(self) -> None:
        """TC-LB02-a: success defaults to True."""
        result = ThinkResult(text="hello")
        assert result.success is True

    def test_lb02b_frozen(self) -> None:
        """TC-LB02-b: ThinkResult is immutable (frozen dataclass)."""
        result = ThinkResult(text="hello")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            result.text = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-LB03: AgentLLMBridge without provider
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentLLMBridgeNoProvider:
    """TC-LB03: AgentLLMBridge without provider."""

    def test_lb03a_has_provider_is_false(self) -> None:
        """TC-LB03-a: has_provider returns False before set_provider is called."""
        bridge = AgentLLMBridge()
        assert bridge.has_provider is False

    def test_lb03b_think_returns_failure_when_no_provider(self) -> None:
        """TC-LB03-b: think() returns ThinkResult with success=False when no provider configured."""
        bridge = AgentLLMBridge()
        result = bridge.think("What should I do?")
        assert isinstance(result, ThinkResult)
        assert result.success is False
        assert result.error != ""

    def test_lb03c_total_tokens_used_is_zero(self) -> None:
        """TC-LB03-c: total_tokens_used starts at 0."""
        bridge = AgentLLMBridge()
        assert bridge.total_tokens_used == 0


# ---------------------------------------------------------------------------
# TC-LB04: AgentLLMBridge with mock provider
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentLLMBridgeWithProvider:
    """TC-LB04: AgentLLMBridge with mock provider."""

    def _bridge_with_provider(
        self,
        provider: MockProvider | None = None,
        config: BridgeConfig | None = None,
    ) -> AgentLLMBridge:
        bridge = AgentLLMBridge(config=config)
        bridge.set_provider(provider or MockProvider())
        return bridge

    def test_lb04a_set_provider_returns_self(self) -> None:
        """TC-LB04-a: set_provider returns self for chaining."""
        bridge = AgentLLMBridge()
        provider = MockProvider()
        returned = bridge.set_provider(provider)
        assert returned is bridge

    def test_lb04b_has_provider_true_after_set(self) -> None:
        """TC-LB04-b: has_provider is True after set_provider is called."""
        bridge = self._bridge_with_provider()
        assert bridge.has_provider is True

    def test_lb04c_think_calls_provider_and_returns_text(self) -> None:
        """TC-LB04-c: think() calls provider.generate and returns its text."""
        provider = MockProvider(responses=[MockResponse(text="vessel found")])
        bridge = self._bridge_with_provider(provider)
        result = bridge.think("Find vessels")
        assert result.success is True
        assert result.text == "vessel found"
        assert provider._calls == 1

    def test_lb04d_total_tokens_accumulates_across_calls(self) -> None:
        """TC-LB04-d: total_tokens_used accumulates over multiple think() calls."""
        provider = MockProvider(
            responses=[MockResponse(text="a"), MockResponse(text="b")]
        )
        bridge = self._bridge_with_provider(provider)
        bridge.think("first query")
        assert bridge.total_tokens_used == 5  # one MockResponse.token_count
        bridge.think("second query")
        assert bridge.total_tokens_used == 10  # two calls

    def test_lb04e_reset_token_count_resets_to_zero(self) -> None:
        """TC-LB04-e: reset_token_count() sets total_tokens_used back to 0."""
        provider = MockProvider(
            responses=[MockResponse(text="x"), MockResponse(text="y")]
        )
        bridge = self._bridge_with_provider(provider)
        bridge.think("query")
        assert bridge.total_tokens_used > 0
        bridge.reset_token_count()
        assert bridge.total_tokens_used == 0

    def test_lb04f_think_with_custom_system_prompt(self) -> None:
        """TC-LB04-f: think() with custom system_prompt succeeds and passes prompt to provider."""
        provider = MockProvider(responses=[MockResponse(text="custom response")])
        bridge = self._bridge_with_provider(provider)
        result = bridge.think("Do something", system_prompt="You are a maritime expert.")
        assert result.success is True
        assert result.text == "custom response"


# ---------------------------------------------------------------------------
# TC-LB05: AgentLLMBridge error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentLLMBridgeErrorHandling:
    """TC-LB05: AgentLLMBridge error handling and retries."""

    def test_lb05a_provider_exception_retried_max_retries_times(self) -> None:
        """TC-LB05-a: Provider raising exception is retried max_retries times (total attempts = max_retries + 1)."""
        config = BridgeConfig(max_retries=2)
        # Provider always fails
        provider = MockProvider(fail_count=999)
        bridge = AgentLLMBridge(config=config)
        bridge.set_provider(provider)
        bridge.think("any prompt")
        # total attempts = max_retries + 1 = 3
        assert provider._calls == 3

    def test_lb05b_all_retries_fail_returns_failure_result(self) -> None:
        """TC-LB05-b: After all retries exhausted, returns ThinkResult with success=False."""
        config = BridgeConfig(max_retries=1)
        provider = MockProvider(fail_count=999)
        bridge = AgentLLMBridge(config=config)
        bridge.set_provider(provider)
        result = bridge.think("will fail")
        assert result.success is False
        assert result.error != ""

    def test_lb05c_provider_fails_once_then_succeeds_on_retry(self) -> None:
        """TC-LB05-c: Provider that fails once succeeds on first retry."""
        config = BridgeConfig(max_retries=2)
        provider = MockProvider(
            responses=[MockResponse(text="retry success")],
            fail_count=1,
        )
        bridge = AgentLLMBridge(config=config)
        bridge.set_provider(provider)
        result = bridge.think("try again")
        assert result.success is True
        assert result.text == "retry success"
        # 1 failing call + 1 succeeding call = 2 total
        assert provider._calls == 2


# ---------------------------------------------------------------------------
# TC-LB06: AgentLLMBridge prompt formatting
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentLLMBridgePromptFormatting:
    """TC-LB06: AgentLLMBridge _format_prompt."""

    def _bridge(self) -> AgentLLMBridge:
        return AgentLLMBridge()

    def test_lb06a_format_prompt_includes_system_and_user_sections(self) -> None:
        """TC-LB06-a: _format_prompt output includes [System] and [User] sections."""
        bridge = self._bridge()
        formatted = bridge._format_prompt("Find all vessels")
        assert "[System]" in formatted
        assert "[User]" in formatted
        assert "Find all vessels" in formatted

    def test_lb06b_custom_system_prompt_overrides_default(self) -> None:
        """TC-LB06-b: Custom system_prompt in _format_prompt overrides BridgeConfig default."""
        custom_system = "You are a maritime navigation specialist."
        bridge = self._bridge()
        formatted = bridge._format_prompt("navigate", system_prompt=custom_system)
        assert custom_system in formatted
        # Default system prompt should NOT appear when overridden
        assert "You are a helpful AI assistant" not in formatted


# ---------------------------------------------------------------------------
# TC-SK01: SkillDefinition
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSkillDefinition:
    """TC-SK01: SkillDefinition dataclass."""

    def test_sk01a_construction_with_required_fields(self) -> None:
        """TC-SK01-a: Constructs correctly with required fields."""
        skill = SkillDefinition(
            name="summarise_voyage",
            description="Summarises a vessel voyage from KG data.",
        )
        assert skill.name == "summarise_voyage"
        assert skill.description == "Summarises a vessel voyage from KG data."

    def test_sk01b_default_category_is_general(self) -> None:
        """TC-SK01-b: Default category is 'general'."""
        skill = SkillDefinition(name="my_skill", description="Does things.")
        assert skill.category == "general"

    def test_sk01c_validate_passes_for_valid_skill(self) -> None:
        """TC-SK01-c: validate() returns empty list for a valid skill."""
        skill = SkillDefinition(name="valid_skill", description="A valid skill.")
        errors = skill.validate()
        assert errors == []

    def test_sk01d_validate_catches_empty_name(self) -> None:
        """TC-SK01-d: validate() returns an error when name is empty."""
        skill = SkillDefinition(name="", description="Has no name.")
        errors = skill.validate()
        assert len(errors) >= 1
        assert any("name" in e.lower() for e in errors)

    def test_sk01e_validate_catches_empty_description(self) -> None:
        """TC-SK01-e: validate() returns an error when description is empty."""
        skill = SkillDefinition(name="no_desc", description="")
        errors = skill.validate()
        assert len(errors) >= 1
        assert any("description" in e.lower() for e in errors)

    def test_sk01f_frozen(self) -> None:
        """TC-SK01-f: SkillDefinition is immutable (frozen dataclass)."""
        skill = SkillDefinition(name="immutable", description="Cannot change.")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            skill.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-SK02: SkillResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSkillResult:
    """TC-SK02: SkillResult dataclass."""

    def test_sk02a_default_success_is_true(self) -> None:
        """TC-SK02-a: success defaults to True."""
        result = SkillResult(skill_name="my_skill", output="done")
        assert result.success is True

    def test_sk02b_frozen(self) -> None:
        """TC-SK02-b: SkillResult is immutable (frozen dataclass)."""
        result = SkillResult(skill_name="my_skill", output="done")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            result.output = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-SK03: SkillRegistry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSkillRegistry:
    """TC-SK03: SkillRegistry."""

    def _make_registry(self) -> SkillRegistry:
        return SkillRegistry()

    def _voyage_skill(self, category: str = "kg") -> SkillDefinition:
        return SkillDefinition(
            name="summarise_voyage",
            description="Summarises a vessel voyage.",
            category=category,
        )

    def _alert_skill(self, category: str = "nlp") -> SkillDefinition:
        return SkillDefinition(
            name="generate_alert",
            description="Generates a maritime alert.",
            category=category,
        )

    def test_sk03a_empty_on_creation(self) -> None:
        """TC-SK03-a: Fresh registry has skill_count == 0."""
        registry = self._make_registry()
        assert registry.skill_count == 0

    def test_sk03b_register_returns_self(self) -> None:
        """TC-SK03-b: register() returns self for method chaining."""
        registry = self._make_registry()
        returned = registry.register(self._voyage_skill(), handler=lambda: "done")
        assert returned is registry

    def test_sk03c_get_returns_registered_skill(self) -> None:
        """TC-SK03-c: get() returns the SkillDefinition for a registered skill."""
        registry = self._make_registry()
        registry.register(self._voyage_skill(), handler=lambda: "ok")
        result = registry.get("summarise_voyage")
        assert result is not None
        assert result.name == "summarise_voyage"

    def test_sk03d_get_returns_none_for_unknown(self) -> None:
        """TC-SK03-d: get() returns None for an unknown skill name."""
        registry = self._make_registry()
        assert registry.get("nonexistent_skill") is None

    def test_sk03e_execute_runs_handler(self) -> None:
        """TC-SK03-e: execute() invokes the handler and returns a successful SkillResult."""
        registry = self._make_registry()
        registry.register(
            self._voyage_skill(),
            handler=lambda vessel_id: f"Summary for {vessel_id}",
        )
        result = registry.execute("summarise_voyage", {"vessel_id": "IMO1234567"})
        assert result.success is True
        assert "IMO1234567" in result.output

    def test_sk03f_execute_unknown_skill_returns_error(self) -> None:
        """TC-SK03-f: execute() on unknown skill returns SkillResult with success=False."""
        registry = self._make_registry()
        result = registry.execute("ghost_skill")
        assert result.success is False
        assert "ghost_skill" in result.error.lower() or "unknown" in result.error.lower()

    def test_sk03g_execute_handles_handler_exception(self) -> None:
        """TC-SK03-g: When handler raises, execute() returns SkillResult with success=False."""
        registry = self._make_registry()

        def failing_handler() -> str:
            raise ValueError("something exploded")

        registry.register(self._voyage_skill(), handler=failing_handler)
        result = registry.execute("summarise_voyage")
        assert result.success is False
        assert "something exploded" in result.error

    def test_sk03h_skill_names_property(self) -> None:
        """TC-SK03-h: skill_names returns list of all registered skill names."""
        registry = self._make_registry()
        assert registry.skill_names == []
        registry.register(self._voyage_skill(), handler=lambda: "a")
        registry.register(self._alert_skill(), handler=lambda: "b")
        assert set(registry.skill_names) == {"summarise_voyage", "generate_alert"}

    def test_sk03i_list_skills_returns_all(self) -> None:
        """TC-SK03-i: list_skills() returns all registered SkillDefinitions."""
        registry = self._make_registry()
        registry.register(self._voyage_skill(), handler=lambda: "a")
        registry.register(self._alert_skill(), handler=lambda: "b")
        skills = registry.list_skills()
        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"summarise_voyage", "generate_alert"}

    def test_sk03j_list_by_category_filters_correctly(self) -> None:
        """TC-SK03-j: list_by_category() returns only skills with the given category."""
        registry = self._make_registry()
        registry.register(self._voyage_skill(category="kg"), handler=lambda: "a")
        registry.register(self._alert_skill(category="nlp"), handler=lambda: "b")
        registry.register(
            SkillDefinition(name="extra_kg", description="Extra KG skill.", category="kg"),
            handler=lambda: "c",
        )

        kg_skills = registry.list_by_category("kg")
        assert len(kg_skills) == 2
        assert all(s.category == "kg" for s in kg_skills)

        nlp_skills = registry.list_by_category("nlp")
        assert len(nlp_skills) == 1
        assert nlp_skills[0].name == "generate_alert"

        assert registry.list_by_category("etl") == []

    def test_sk03k_clear_removes_all(self) -> None:
        """TC-SK03-k: clear() removes all registered skills and handlers."""
        registry = self._make_registry()
        registry.register(self._voyage_skill(), handler=lambda: "a")
        registry.register(self._alert_skill(), handler=lambda: "b")
        assert registry.skill_count == 2

        registry.clear()
        assert registry.skill_count == 0
        assert registry.skill_names == []
        assert registry.list_skills() == []
