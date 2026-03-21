"""LLM Provider abstraction unit tests.

TC-LP01 ~ TC-LP08: LLMProvider protocol, registry, and built-in providers.
All tests run without network — pure Python only.
"""

from __future__ import annotations

import pytest

from kg.llm import LLMConfig, LLMProvider, LLMResponse, ProviderInfo, ProviderRegistry
from kg.llm.models import ProviderType
from kg.llm.providers import AnthropicProvider, OllamaProvider, OpenAIProvider


# =============================================================================
# TC-LP01: LLMConfig
# =============================================================================


@pytest.mark.unit
class TestLLMConfig:
    """LLMConfig frozen dataclass tests."""

    def test_default_values(self) -> None:
        """TC-LP01-a: Default config has sensible defaults."""
        cfg = LLMConfig()
        assert cfg.provider == "ollama"
        assert cfg.model == "mistral"
        assert cfg.timeout == 30.0
        assert cfg.max_tokens == 2048

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-LP01-b: from_env reads environment variables."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        cfg = LLMConfig.from_env()
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4"
        assert cfg.api_key == "sk-test"

    def test_validate_valid(self) -> None:
        """TC-LP01-c: Valid config returns no errors."""
        cfg = LLMConfig()
        errors = cfg.validate()
        assert len(errors) == 0

    def test_validate_invalid_temperature(self) -> None:
        """TC-LP01-d: Temperature > 2.0 is invalid."""
        cfg = LLMConfig(temperature=3.0)
        errors = cfg.validate()
        assert any("temperature" in e for e in errors)

    def test_validate_requires_api_key(self) -> None:
        """TC-LP01-e: OpenAI/Anthropic require api_key."""
        cfg = LLMConfig(provider="openai", api_key="")
        errors = cfg.validate()
        assert any("api_key" in e for e in errors)

    def test_frozen(self) -> None:
        """TC-LP01-f: LLMConfig is frozen."""
        cfg = LLMConfig()
        with pytest.raises(AttributeError):
            cfg.provider = "test"  # type: ignore[misc]

    def test_validate_negative_timeout(self) -> None:
        """TC-LP01-g: Negative timeout is invalid."""
        cfg = LLMConfig(timeout=-1)
        errors = cfg.validate()
        assert any("timeout" in e for e in errors)

    def test_validate_negative_max_tokens(self) -> None:
        """TC-LP01-h: Negative max_tokens is invalid."""
        cfg = LLMConfig(max_tokens=0)
        errors = cfg.validate()
        assert any("max_tokens" in e for e in errors)


# =============================================================================
# TC-LP02: LLMResponse
# =============================================================================


@pytest.mark.unit
class TestLLMResponse:
    """LLMResponse frozen dataclass tests."""

    def test_creation(self) -> None:
        """TC-LP02-a: LLMResponse is created with correct fields."""
        resp = LLMResponse(text="hello", model="gpt-4", provider="openai")
        assert resp.text == "hello"
        assert resp.model == "gpt-4"

    def test_token_count(self) -> None:
        """TC-LP02-b: token_count computes from prompt + completion."""
        resp = LLMResponse(
            text="hi", model="m", provider="p",
            prompt_tokens=10, completion_tokens=5, total_tokens=0,
        )
        assert resp.token_count == 15

    def test_token_count_prefers_total(self) -> None:
        """TC-LP02-c: total_tokens takes precedence when non-zero."""
        resp = LLMResponse(
            text="hi", model="m", provider="p",
            prompt_tokens=10, completion_tokens=5, total_tokens=20,
        )
        assert resp.token_count == 20

    def test_frozen(self) -> None:
        """TC-LP02-d: LLMResponse is frozen."""
        resp = LLMResponse(text="hi", model="m", provider="p")
        with pytest.raises(AttributeError):
            resp.text = "new"  # type: ignore[misc]


# =============================================================================
# TC-LP03: ProviderInfo
# =============================================================================


@pytest.mark.unit
class TestProviderInfo:
    """ProviderInfo tests."""

    def test_creation(self) -> None:
        """TC-LP03-a: ProviderInfo with defaults."""
        info = ProviderInfo(name="test", provider_type=ProviderType.CUSTOM)
        assert info.name == "test"
        assert info.supports_streaming is False

    def test_provider_type_values(self) -> None:
        """TC-LP03-b: ProviderType enum values."""
        assert ProviderType.OLLAMA == "ollama"
        assert ProviderType.OPENAI == "openai"
        assert ProviderType.ANTHROPIC == "anthropic"
        assert ProviderType.CUSTOM == "custom"


# =============================================================================
# TC-LP04: ProviderRegistry
# =============================================================================


@pytest.mark.unit
class TestProviderRegistry:
    """ProviderRegistry tests."""

    def test_register_and_get(self) -> None:
        """TC-LP04-a: Register and retrieve a provider."""
        registry = ProviderRegistry()
        provider = OllamaProvider()
        registry.register(provider)
        assert registry.get("ollama") is provider
        assert registry.provider_count == 1

    def test_default_is_first_registered(self) -> None:
        """TC-LP04-b: First registered provider becomes default."""
        registry = ProviderRegistry()
        provider = OllamaProvider()
        registry.register(provider)
        assert registry.get_default() is provider

    def test_set_default(self) -> None:
        """TC-LP04-c: set_default changes the default provider."""
        registry = ProviderRegistry()
        registry.register(OllamaProvider())
        registry.register(OpenAIProvider(LLMConfig(provider="openai", api_key="key")))
        registry.set_default("openai")
        default = registry.get_default()
        assert default is not None
        assert default.info.name == "openai"

    def test_set_default_unknown_raises(self) -> None:
        """TC-LP04-d: set_default with unknown name raises KeyError."""
        registry = ProviderRegistry()
        with pytest.raises(KeyError):
            registry.set_default("nonexistent")

    def test_get_unknown_returns_none(self) -> None:
        """TC-LP04-e: get() with unknown name returns None."""
        registry = ProviderRegistry()
        assert registry.get("nonexistent") is None

    def test_provider_names(self) -> None:
        """TC-LP04-f: provider_names lists all registered names."""
        registry = ProviderRegistry()
        registry.register(OllamaProvider())
        registry.register(AnthropicProvider(LLMConfig(provider="anthropic", api_key="k")))
        assert "ollama" in registry.provider_names
        assert "anthropic" in registry.provider_names

    def test_fluent_chaining(self) -> None:
        """TC-LP04-g: register returns self for chaining."""
        registry = ProviderRegistry()
        result = registry.register(OllamaProvider())
        assert result is registry

    def test_clear(self) -> None:
        """TC-LP04-h: clear removes all providers."""
        registry = ProviderRegistry()
        registry.register(OllamaProvider())
        registry.clear()
        assert registry.provider_count == 0
        assert registry.get_default() is None

    def test_failover_chain(self) -> None:
        """TC-LP04-i: get_available walks failover chain."""
        registry = ProviderRegistry()
        # OpenAI without key → not available
        registry.register(OpenAIProvider(LLMConfig(provider="openai", api_key="")))
        # Ollama → available
        registry.register(OllamaProvider())
        registry.set_failover_chain(["openai", "ollama"])
        available = registry.get_available()
        assert available is not None
        assert available.info.name == "ollama"

    def test_empty_registry_returns_none(self) -> None:
        """TC-LP04-j: Empty registry returns None for get_available."""
        registry = ProviderRegistry()
        assert registry.get_available() is None


# =============================================================================
# TC-LP05: Built-in providers
# =============================================================================


@pytest.mark.unit
class TestBuiltinProviders:
    """Built-in provider stub tests."""

    def test_ollama_info(self) -> None:
        """TC-LP05-a: OllamaProvider has correct info."""
        p = OllamaProvider()
        assert p.info.name == "ollama"
        assert p.info.provider_type == ProviderType.OLLAMA
        assert p.info.supports_streaming is True

    def test_ollama_is_available(self) -> None:
        """TC-LP05-b: OllamaProvider is always available (stub)."""
        assert OllamaProvider().is_available() is True

    def test_openai_not_available_without_key(self) -> None:
        """TC-LP05-c: OpenAIProvider not available without API key."""
        p = OpenAIProvider(LLMConfig(provider="openai", api_key=""))
        assert p.is_available() is False

    def test_openai_available_with_key(self) -> None:
        """TC-LP05-d: OpenAIProvider available with API key."""
        p = OpenAIProvider(LLMConfig(provider="openai", api_key="sk-test"))
        assert p.is_available() is True

    def test_anthropic_stub_generate(self) -> None:
        """TC-LP05-e: AnthropicProvider returns stub response."""
        p = AnthropicProvider(LLMConfig(provider="anthropic", api_key="ak-test"))
        resp = p.generate("test prompt")
        assert isinstance(resp, LLMResponse)
        assert resp.provider == "anthropic"

    def test_openai_stub_generate(self) -> None:
        """TC-LP05-f: OpenAIProvider returns stub response."""
        p = OpenAIProvider()
        resp = p.generate("test prompt")
        assert isinstance(resp, LLMResponse)
        assert resp.provider == "openai"


# =============================================================================
# TC-LP06: Protocol compliance
# =============================================================================


@pytest.mark.unit
class TestLLMProviderProtocol:
    """LLMProvider protocol compliance tests."""

    def test_ollama_satisfies_protocol(self) -> None:
        """TC-LP06-a: OllamaProvider satisfies LLMProvider protocol."""
        assert isinstance(OllamaProvider(), LLMProvider)

    def test_openai_satisfies_protocol(self) -> None:
        """TC-LP06-b: OpenAIProvider satisfies LLMProvider protocol."""
        assert isinstance(OpenAIProvider(), LLMProvider)

    def test_anthropic_satisfies_protocol(self) -> None:
        """TC-LP06-c: AnthropicProvider satisfies LLMProvider protocol."""
        p = AnthropicProvider(LLMConfig(provider="anthropic", api_key="k"))
        assert isinstance(p, LLMProvider)
