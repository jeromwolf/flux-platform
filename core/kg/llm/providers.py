"""Built-in LLM provider stubs.

Provides stub implementations for Ollama, OpenAI, and Anthropic that
can be used for testing and development. Production implementations
will use actual API clients.
"""
from __future__ import annotations

import logging
from typing import Any

from kg.llm.models import LLMConfig, LLMResponse, ProviderInfo, ProviderType

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Ollama LLM provider (local inference).

    Satisfies the LLMProvider protocol via duck typing.
    Uses langchain-ollama under the hood when available.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or LLMConfig()
        self._available = True

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="ollama",
            provider_type=ProviderType.OLLAMA,
            description="Local Ollama inference server",
            supports_streaming=True,
            supports_embeddings=True,
            max_context_length=8192,
        )

    def generate(self, prompt: str, **kwargs: object) -> LLMResponse:
        """Generate completion via Ollama API.

        In stub mode, returns a placeholder response. Production
        implementation connects to the Ollama server.
        """
        try:
            from langchain_ollama import ChatOllama  # noqa: PLC0415
        except ImportError:
            logger.warning("langchain-ollama not installed, returning stub response")
            return LLMResponse(
                text="[Ollama stub response]",
                model=self._config.model,
                provider="ollama",
            )

        llm = ChatOllama(
            model=self._config.model,
            base_url=self._config.base_url,
            temperature=self._config.temperature,
        )
        try:
            result = llm.invoke(prompt)
            content = result.content if hasattr(result, "content") else str(result)
            usage = getattr(result, "usage_metadata", None)
            return LLMResponse(
                text=str(content),
                model=self._config.model,
                provider="ollama",
                prompt_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
                completion_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
                total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
            )
        except Exception as exc:
            logger.error("Ollama generation failed: %s", exc)
            raise

    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        return self._available


class OpenAIProvider:
    """OpenAI LLM provider stub.

    Satisfies the LLMProvider protocol via duck typing.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        cfg = config or LLMConfig(provider="openai", model="gpt-4")
        self._config = cfg
        self._available = bool(cfg.api_key)

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="openai",
            provider_type=ProviderType.OPENAI,
            description="OpenAI API (GPT models)",
            supports_streaming=True,
            supports_embeddings=True,
            max_context_length=128000,
        )

    def generate(self, prompt: str, **kwargs: object) -> LLMResponse:
        """Generate completion via OpenAI API."""
        return LLMResponse(
            text="[OpenAI stub — configure API key for production use]",
            model=self._config.model,
            provider="openai",
        )

    def is_available(self) -> bool:
        return self._available


class AnthropicProvider:
    """Anthropic LLM provider stub.

    Satisfies the LLMProvider protocol via duck typing.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        cfg = config or LLMConfig(provider="anthropic", model="claude-sonnet-4-20250514")
        self._config = cfg
        self._available = bool(cfg.api_key)

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="anthropic",
            provider_type=ProviderType.ANTHROPIC,
            description="Anthropic API (Claude models)",
            supports_streaming=True,
            supports_embeddings=False,
            max_context_length=200000,
        )

    def generate(self, prompt: str, **kwargs: object) -> LLMResponse:
        """Generate completion via Anthropic API."""
        return LLMResponse(
            text="[Anthropic stub — configure API key for production use]",
            model=self._config.model,
            provider="anthropic",
        )

    def is_available(self) -> bool:
        return self._available
