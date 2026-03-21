"""LLM bridge for agent runtime.

Adapts the core kg.llm provider abstraction for use within
the agent execution engines. Provides prompt formatting,
token counting, and provider failover.

Usage::

    from agent.llm.bridge import AgentLLMBridge

    bridge = AgentLLMBridge()
    bridge.set_provider(my_ollama_provider)
    response = bridge.think("What tools should I use?")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BridgeConfig:
    """Configuration for the LLM bridge."""

    system_prompt: str = "You are a helpful AI assistant with access to tools."
    max_retries: int = 2
    temperature: float = 0.7
    max_tokens: int = 2048


@dataclass(frozen=True)
class ThinkResult:
    """Result of a thinking/generation step."""

    text: str
    tokens_used: int = 0
    provider_name: str = ""
    success: bool = True
    error: str = ""


class AgentLLMBridge:
    """Bridge between agent runtime and LLM providers.

    Wraps LLMProvider instances (from kg.llm) with agent-specific
    prompt formatting and error handling.

    Example::

        bridge = AgentLLMBridge()
        bridge.set_provider(ollama_provider)
        result = bridge.think("Summarise the vessel registry.")
        if result.success:
            print(result.text)
    """

    def __init__(self, config: Optional[BridgeConfig] = None) -> None:
        self._config = config or BridgeConfig()
        self._provider: Any = None  # LLMProvider protocol (duck-typed)
        self._total_tokens: int = 0

    def set_provider(self, provider: Any) -> AgentLLMBridge:
        """Set the LLM provider.

        Args:
            provider: Any object that exposes a ``generate(prompt)`` method
                returning an object with a ``text`` attribute.

        Returns:
            Self for chaining.
        """
        self._provider = provider
        logger.info(
            "LLM provider set: %s",
            getattr(provider, "name", type(provider).__name__),
        )
        return self

    @property
    def has_provider(self) -> bool:
        """True when a provider has been configured."""
        return self._provider is not None

    @property
    def total_tokens_used(self) -> int:
        """Cumulative tokens consumed across all ``think`` calls."""
        return self._total_tokens

    def think(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> ThinkResult:
        """Generate a thinking response.

        Formats the prompt with system context, calls the provider,
        handles errors with retries.

        Args:
            prompt: User-facing instruction or question.
            system_prompt: Optional override for the system context.
                Defaults to ``BridgeConfig.system_prompt``.

        Returns:
            :class:`ThinkResult` with generated text and metadata.
        """
        if self._provider is None:
            return ThinkResult(
                text="[No LLM provider configured]",
                success=False,
                error="No LLM provider set",
            )

        full_prompt = self._format_prompt(prompt, system_prompt)

        last_error = ""
        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._provider.generate(full_prompt)
                tokens = getattr(response, "token_count", 0)
                self._total_tokens += tokens
                provider_name = getattr(response, "provider", "") or getattr(
                    self._provider, "name", ""
                )
                logger.debug(
                    "LLM response received (tokens=%d, provider=%s)",
                    tokens,
                    provider_name,
                )
                return ThinkResult(
                    text=response.text,
                    tokens_used=tokens,
                    provider_name=provider_name,
                    success=True,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning("LLM attempt %d failed: %s", attempt + 1, exc)

        return ThinkResult(
            text="",
            success=False,
            error=(
                f"LLM failed after {self._config.max_retries + 1} attempts: {last_error}"
            ),
        )

    def _format_prompt(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Format prompt with system context.

        Args:
            prompt: Raw user prompt.
            system_prompt: Optional system context override.

        Returns:
            Formatted prompt string.
        """
        sys = system_prompt or self._config.system_prompt
        return f"[System] {sys}\n\n[User] {prompt}"

    def reset_token_count(self) -> None:
        """Reset the total token counter to zero."""
        self._total_tokens = 0
