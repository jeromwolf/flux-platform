"""Unit tests for LLM providers.

Covers:
    TC-LP01  StubLLMProvider returns message
    TC-LP02  OllamaLLMProvider initialises with defaults
    TC-LP03  OpenAILLMProvider initialises
    TC-LP04  create_llm_provider returns stub when no server
    TC-LP05  create_llm_provider explicit stub
    TC-LP06  OllamaLLMProvider.generate calls Ollama API
    TC-LP07  OpenAILLMProvider.generate calls OpenAI API
    TC-LP08  AgentLLMBridge integration with providers
    TC-LP09  LLMProvider protocol compliance
"""
from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from agent.llm.providers import (
    AnthropicLLMProvider,
    LLMProvider,
    OllamaLLMProvider,
    OpenAILLMProvider,
    StubLLMProvider,
    create_llm_provider,
)
from agent.llm.bridge import AgentLLMBridge, BridgeConfig, ThinkResult


# ---------------------------------------------------------------------------
# TC-LP01: StubLLMProvider returns message
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStubLLMProvider:
    """TC-LP01: StubLLMProvider works correctly."""

    def test_lp01a_returns_stub_message(self) -> None:
        """TC-LP01-a: generate() returns a message with prompt length."""
        provider = StubLLMProvider()
        result = provider.generate("Hello, world!")
        assert "[Stub LLM]" in result
        assert "13 chars" in result

    def test_lp01b_accepts_all_kwargs(self) -> None:
        """TC-LP01-b: generate() accepts system, temperature, max_tokens."""
        provider = StubLLMProvider()
        result = provider.generate(
            "test",
            system="You are helpful.",
            temperature=0.5,
            max_tokens=1024,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_lp01c_satisfies_protocol(self) -> None:
        """TC-LP01-c: StubLLMProvider satisfies LLMProvider protocol."""
        provider = StubLLMProvider()
        assert isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# TC-LP02: OllamaLLMProvider initialises with defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOllamaLLMProviderInit:
    """TC-LP02: OllamaLLMProvider initialises with correct defaults."""

    def test_lp02a_default_model(self) -> None:
        """TC-LP02-a: Default model is llama3.1:8b."""
        provider = OllamaLLMProvider()
        assert provider.model == "llama3.1:8b"

    def test_lp02b_default_base_url(self) -> None:
        """TC-LP02-b: Default base_url is localhost:11434."""
        provider = OllamaLLMProvider()
        assert provider.base_url == "http://localhost:11434"

    def test_lp02c_custom_params(self) -> None:
        """TC-LP02-c: Custom model and base_url are accepted."""
        provider = OllamaLLMProvider(
            model="mistral:7b",
            base_url="http://gpu-server:11434",
        )
        assert provider.model == "mistral:7b"
        assert provider.base_url == "http://gpu-server:11434"

    def test_lp02d_satisfies_protocol(self) -> None:
        """TC-LP02-d: OllamaLLMProvider satisfies LLMProvider protocol."""
        provider = OllamaLLMProvider()
        assert isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# TC-LP03: OpenAILLMProvider initialises
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAILLMProviderInit:
    """TC-LP03: OpenAILLMProvider initialises correctly."""

    def test_lp03a_default_model(self) -> None:
        """TC-LP03-a: Default model is gpt-4o-mini."""
        provider = OpenAILLMProvider(api_key="test-key")
        assert provider.model == "gpt-4o-mini"

    def test_lp03b_custom_model(self) -> None:
        """TC-LP03-b: Custom model is accepted."""
        provider = OpenAILLMProvider(model="gpt-4o", api_key="test-key")
        assert provider.model == "gpt-4o"

    def test_lp03c_api_key_from_constructor(self) -> None:
        """TC-LP03-c: API key can be set via constructor."""
        provider = OpenAILLMProvider(api_key="sk-test-123")
        assert provider.api_key == "sk-test-123"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env-key"})
    def test_lp03d_api_key_from_env(self) -> None:
        """TC-LP03-d: API key falls back to OPENAI_API_KEY env var."""
        provider = OpenAILLMProvider()
        assert provider.api_key == "sk-env-key"

    def test_lp03e_generate_raises_without_key(self) -> None:
        """TC-LP03-e: generate() raises ValueError without API key."""
        provider = OpenAILLMProvider(api_key="")
        with pytest.raises(ValueError, match="API key not set"):
            provider.generate("test")

    def test_lp03f_satisfies_protocol(self) -> None:
        """TC-LP03-f: OpenAILLMProvider satisfies LLMProvider protocol."""
        provider = OpenAILLMProvider(api_key="test")
        assert isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# TC-LP04: create_llm_provider returns stub when no server
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateLLMProviderAutoFallback:
    """TC-LP04: create_llm_provider auto mode falls back to stub."""

    @patch("agent.llm.providers.urllib.request.urlopen")
    @patch.dict("os.environ", {}, clear=True)
    def test_lp04a_returns_stub_when_no_server(self, mock_urlopen: MagicMock) -> None:
        """TC-LP04-a: auto mode returns StubLLMProvider when no LLM available."""
        mock_urlopen.side_effect = Exception("Connection refused")

        provider = create_llm_provider("auto")
        assert isinstance(provider, StubLLMProvider)

    @patch("agent.llm.providers.urllib.request.urlopen")
    def test_lp04b_returns_ollama_when_server_available(
        self, mock_urlopen: MagicMock
    ) -> None:
        """TC-LP04-b: auto mode returns OllamaLLMProvider when server is up."""
        # Mock a successful health check
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"models":[]}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = create_llm_provider("auto")
        assert isinstance(provider, OllamaLLMProvider)

    @patch("agent.llm.providers.urllib.request.urlopen")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    def test_lp04c_returns_openai_when_ollama_down(
        self, mock_urlopen: MagicMock
    ) -> None:
        """TC-LP04-c: auto mode returns OpenAI when Ollama is down."""
        # Ollama health check fails
        mock_urlopen.side_effect = Exception("Connection refused")

        provider = create_llm_provider("auto")
        assert isinstance(provider, OpenAILLMProvider)


# ---------------------------------------------------------------------------
# TC-LP05: create_llm_provider explicit stub
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateLLMProviderExplicitStub:
    """TC-LP05: create_llm_provider with provider='stub'."""

    def test_lp05a_returns_stub_provider(self) -> None:
        """TC-LP05-a: provider='stub' returns StubLLMProvider."""
        provider = create_llm_provider("stub")
        assert isinstance(provider, StubLLMProvider)

    def test_lp05b_stub_generates_text(self) -> None:
        """TC-LP05-b: Stub provider generates text."""
        provider = create_llm_provider("stub")
        result = provider.generate("Hello")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# TC-LP06: OllamaLLMProvider.generate calls Ollama API
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOllamaLLMProviderGenerate:
    """TC-LP06: OllamaLLMProvider.generate constructs correct HTTP requests."""

    @patch("agent.llm.providers.urllib.request.urlopen")
    def test_lp06a_sends_correct_payload(self, mock_urlopen: MagicMock) -> None:
        """TC-LP06-a: generate() sends correct payload to Ollama."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"response": "Hello from Ollama!"}
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = OllamaLLMProvider(model="test-model")
        result = provider.generate("Hi", system="Be helpful")

        assert result == "Hello from Ollama!"

        # Verify the request
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.full_url == "http://localhost:11434/api/generate"

        body = json.loads(req.data)
        assert body["model"] == "test-model"
        assert body["prompt"] == "Hi"
        assert body["system"] == "Be helpful"
        assert body["stream"] is False


# ---------------------------------------------------------------------------
# TC-LP07: OpenAILLMProvider.generate calls OpenAI API
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAILLMProviderGenerate:
    """TC-LP07: OpenAILLMProvider.generate constructs correct HTTP requests."""

    @patch("agent.llm.providers.urllib.request.urlopen")
    def test_lp07a_sends_correct_payload(self, mock_urlopen: MagicMock) -> None:
        """TC-LP07-a: generate() sends correct payload to OpenAI."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Hello from OpenAI!"}}]
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key="sk-test-key")
        result = provider.generate("Hi", system="Be helpful", temperature=0.5)

        assert result == "Hello from OpenAI!"

        # Verify the request
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.full_url == "https://api.openai.com/v1/chat/completions"
        assert req.headers["Authorization"] == "Bearer sk-test-key"

        body = json.loads(req.data)
        assert body["model"] == "gpt-4o-mini"
        assert body["temperature"] == 0.5
        messages = body["messages"]
        assert messages[0] == {"role": "system", "content": "Be helpful"}
        assert messages[1] == {"role": "user", "content": "Hi"}


# ---------------------------------------------------------------------------
# TC-LP-A01: AnthropicLLMProvider initialises
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnthropicLLMProviderInit:
    """TC-LP-A01: AnthropicLLMProvider initialises correctly."""

    def test_anthropic_provider_init_default_model(self) -> None:
        """AnthropicLLMProvider uses claude-sonnet-4-20250514 by default."""
        provider = AnthropicLLMProvider(api_key="sk-ant-test")
        assert provider.model == "claude-sonnet-4-20250514"

    def test_anthropic_provider_init_custom_model(self) -> None:
        """Custom model is accepted."""
        provider = AnthropicLLMProvider(model="claude-opus-4-20250514", api_key="sk-ant-test")
        assert provider.model == "claude-opus-4-20250514"

    def test_anthropic_provider_init_api_key_from_constructor(self) -> None:
        """API key can be set via constructor."""
        provider = AnthropicLLMProvider(api_key="sk-ant-abc123")
        assert provider.api_key == "sk-ant-abc123"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-env-key"})
    def test_anthropic_provider_init_api_key_from_env(self) -> None:
        """API key falls back to ANTHROPIC_API_KEY env var."""
        provider = AnthropicLLMProvider()
        assert provider.api_key == "sk-ant-env-key"

    def test_anthropic_provider_init_satisfies_protocol(self) -> None:
        """AnthropicLLMProvider satisfies LLMProvider protocol."""
        provider = AnthropicLLMProvider(api_key="sk-ant-test")
        assert isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# TC-LP-A02: AnthropicLLMProvider.generate with mock
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnthropicLLMProviderGenerate:
    """TC-LP-A02: AnthropicLLMProvider.generate constructs correct HTTP requests."""

    @patch("agent.llm.providers.urllib.request.urlopen")
    def test_anthropic_provider_generate_with_mock(self, mock_urlopen: MagicMock) -> None:
        """generate() sends correct payload and parses response correctly."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "content": [{"type": "text", "text": "Hello from Anthropic!"}],
            "role": "assistant",
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = AnthropicLLMProvider(api_key="sk-ant-test-key")
        result = provider.generate("Hello", system="Be helpful")

        assert result == "Hello from Anthropic!"

        # Verify the HTTP request structure
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.full_url == "https://api.anthropic.com/v1/messages"
        assert req.headers["X-api-key"] == "sk-ant-test-key"
        assert req.headers["Anthropic-version"] == "2023-06-01"

        body = json.loads(req.data)
        assert body["model"] == "claude-sonnet-4-20250514"
        assert body["max_tokens"] == 1024
        assert body["messages"] == [{"role": "user", "content": "Hello"}]
        assert body["system"] == "Be helpful"

    @patch("agent.llm.providers.urllib.request.urlopen")
    def test_anthropic_provider_generate_without_system(self, mock_urlopen: MagicMock) -> None:
        """generate() omits system key when system is empty string."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "content": [{"type": "text", "text": "Response"}],
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = AnthropicLLMProvider(api_key="sk-ant-test-key")
        result = provider.generate("No system prompt")

        assert result == "Response"

        body = json.loads(mock_urlopen.call_args[0][0].data)
        assert "system" not in body


# ---------------------------------------------------------------------------
# TC-LP-A03: AnthropicLLMProvider error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnthropicLLMProviderHandlesError:
    """TC-LP-A03: AnthropicLLMProvider handles errors gracefully."""

    @patch("agent.llm.providers.urllib.request.urlopen")
    def test_anthropic_provider_handles_error(self, mock_urlopen: MagicMock) -> None:
        """generate() raises urllib.error.URLError on network failure."""
        mock_urlopen.side_effect = urllib.error.URLError("Network timeout")

        provider = AnthropicLLMProvider(api_key="sk-ant-test-key")
        with pytest.raises(urllib.error.URLError):
            provider.generate("test prompt")

    def test_anthropic_provider_raises_missing_key(self) -> None:
        """generate() raises ValueError when no API key is set."""
        provider = AnthropicLLMProvider(api_key="")
        with pytest.raises(ValueError, match="API key not set"):
            provider.generate("test prompt")


# ---------------------------------------------------------------------------
# TC-LP-A04: create_llm_provider selects Anthropic when key set
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFactorySelectsAnthropic:
    """TC-LP-A04: Factory selects AnthropicLLMProvider when ANTHROPIC_API_KEY is set."""

    @patch("agent.llm.providers.urllib.request.urlopen")
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"})
    def test_factory_selects_anthropic_when_key_set(
        self, mock_urlopen: MagicMock
    ) -> None:
        """auto mode picks Anthropic when Ollama is down and ANTHROPIC_API_KEY is set."""
        # Ollama health check fails so factory moves to Anthropic
        mock_urlopen.side_effect = Exception("Connection refused")

        provider = create_llm_provider("auto")
        assert isinstance(provider, AnthropicLLMProvider)
        assert provider.api_key == "sk-ant-test"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-explicit"})
    def test_factory_explicit_anthropic(self) -> None:
        """provider='anthropic' returns AnthropicLLMProvider when key is set."""
        provider = create_llm_provider("anthropic")
        assert isinstance(provider, AnthropicLLMProvider)
        assert provider.api_key == "sk-ant-explicit"

    @patch.dict("os.environ", {}, clear=True)
    def test_factory_explicit_anthropic_raises_without_key(self) -> None:
        """provider='anthropic' raises ValueError when ANTHROPIC_API_KEY is not set."""
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            create_llm_provider("anthropic")

    @patch("agent.llm.providers.urllib.request.urlopen")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-openai"}, clear=True)
    def test_factory_anthropic_priority_over_openai(
        self, mock_urlopen: MagicMock
    ) -> None:
        """Anthropic takes priority over OpenAI in auto mode when both keys absent."""
        # Ollama fails, no ANTHROPIC key, falls to OpenAI
        mock_urlopen.side_effect = Exception("Connection refused")
        provider = create_llm_provider("auto")
        # ANTHROPIC_API_KEY not set, so OpenAI is selected
        assert isinstance(provider, OpenAILLMProvider)


# ---------------------------------------------------------------------------
# TC-LP08: AgentLLMBridge integration with providers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentLLMBridgeIntegration:
    """TC-LP08: AgentLLMBridge works with new-style providers."""

    def test_lp08a_bridge_with_stub_provider(self) -> None:
        """TC-LP08-a: Bridge works with StubLLMProvider."""
        bridge = AgentLLMBridge()
        bridge.set_provider(StubLLMProvider())
        result = bridge.think("Hello, world!")
        assert result.success is True
        assert "[Stub LLM]" in result.text

    def test_lp08b_bridge_without_provider(self) -> None:
        """TC-LP08-b: Bridge returns error when no provider set."""
        bridge = AgentLLMBridge()
        result = bridge.think("Hello")
        assert result.success is False
        assert "No LLM provider" in result.error

    def test_lp08c_bridge_complete_alias(self) -> None:
        """TC-LP08-c: Bridge.complete() is an alias for think()."""
        bridge = AgentLLMBridge()
        bridge.set_provider(StubLLMProvider())
        result = bridge.complete("test prompt")
        assert result.success is True
        assert "[Stub LLM]" in result.text

    def test_lp08d_bridge_from_auto_returns_bridge(self) -> None:
        """TC-LP08-d: from_auto() returns a configured bridge."""
        bridge = AgentLLMBridge.from_auto(provider_name="stub")
        assert bridge.has_provider is True
        result = bridge.think("test")
        assert result.success is True

    def test_lp08e_bridge_retries_on_failure(self) -> None:
        """TC-LP08-e: Bridge retries on provider failure."""
        failing_provider = MagicMock()
        failing_provider.generate.side_effect = RuntimeError("LLM down")

        config = BridgeConfig(max_retries=1)
        bridge = AgentLLMBridge(config=config)
        bridge.set_provider(failing_provider)

        result = bridge.think("test")
        assert result.success is False
        assert "LLM failed after 2 attempts" in result.error
        # 1 initial + 1 retry = 2 calls
        assert failing_provider.generate.call_count == 2

    def test_lp08f_think_result_is_frozen(self) -> None:
        """TC-LP08-f: ThinkResult is a frozen dataclass."""
        import dataclasses

        result = ThinkResult(text="hello")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            result.text = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-LP09: LLMProvider protocol compliance
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMProviderProtocol:
    """TC-LP09: All providers satisfy the LLMProvider runtime_checkable protocol."""

    def test_lp09a_stub_is_llm_provider(self) -> None:
        assert isinstance(StubLLMProvider(), LLMProvider)

    def test_lp09b_ollama_is_llm_provider(self) -> None:
        assert isinstance(OllamaLLMProvider(), LLMProvider)

    def test_lp09c_openai_is_llm_provider(self) -> None:
        assert isinstance(OpenAILLMProvider(api_key="test"), LLMProvider)

    def test_lp09d_anthropic_is_llm_provider(self) -> None:
        assert isinstance(AnthropicLLMProvider(api_key="test"), LLMProvider)
