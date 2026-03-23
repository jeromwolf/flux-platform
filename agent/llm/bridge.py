"""LLM bridge for agent runtime.

Adapts the LLM provider abstraction for use within the agent execution
engines. Provides prompt formatting, token counting, and provider failover.

Usage::

    from agent.llm.bridge import AgentLLMBridge

    bridge = AgentLLMBridge()
    bridge.set_provider(my_ollama_provider)
    response = bridge.think("What tools should I use?")

    # Or auto-detect a provider:
    bridge = AgentLLMBridge.from_auto()
    response = bridge.think("Summarise the vessel registry.")
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

    Wraps LLMProvider instances with agent-specific prompt formatting
    and error handling.

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

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_auto(
        cls,
        config: Optional[BridgeConfig] = None,
        provider_name: str = "auto",
    ) -> AgentLLMBridge:
        """Create a bridge with an auto-detected LLM provider.

        Uses :func:`agent.llm.providers.create_llm_provider` to select
        the best available backend (Ollama -> OpenAI -> Stub).

        Args:
            config: Optional bridge configuration override.
            provider_name: Provider selection hint passed to the factory.

        Returns:
            A fully configured AgentLLMBridge.
        """
        try:
            from agent.llm.providers import create_llm_provider

            provider = create_llm_provider(provider_name)
        except Exception as exc:
            logger.warning("LLM provider auto-detection failed: %s", exc)
            provider = None

        bridge = cls(config=config)
        if provider is not None:
            bridge.set_provider(provider)
        return bridge

    # ------------------------------------------------------------------
    # Provider management
    # ------------------------------------------------------------------

    def set_provider(self, provider: Any) -> AgentLLMBridge:
        """Set the LLM provider.

        Args:
            provider: Any object that exposes a
                ``generate(prompt, system, temperature, max_tokens)`` method
                returning a ``str``, or a legacy provider whose ``generate()``
                returns an object with a ``.text`` attribute.

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

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

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

        sys = system_prompt or self._config.system_prompt
        provider_name = getattr(
            self._provider, "name", type(self._provider).__name__
        )

        last_error = ""
        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._call_provider(prompt, sys)
                logger.debug(
                    "LLM response received (provider=%s)",
                    provider_name,
                )
                return ThinkResult(
                    text=response,
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

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> ThinkResult:
        """Alias for :meth:`think` -- provided for API symmetry.

        Args:
            prompt: User-facing instruction or question.
            system_prompt: Optional system context override.

        Returns:
            :class:`ThinkResult` with generated text and metadata.
        """
        return self.think(prompt, system_prompt=system_prompt)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_provider(self, prompt: str, system: str) -> str:
        """Call the underlying provider with proper argument handling.

        Supports two interfaces:
          1. New-style: ``generate(prompt, system=, temperature=, max_tokens=)`` -> str
          2. Legacy: ``generate(formatted_prompt)`` -> object with ``.text``

        Also tracks token usage when the response carries a ``token_count``
        attribute (legacy providers).

        Args:
            prompt: User prompt text.
            system: System instruction text.

        Returns:
            Generated text string.
        """
        # Try new-style provider (returns str directly)
        try:
            result = self._provider.generate(
                prompt,
                system=system,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
            # Track token usage from legacy response objects
            if not isinstance(result, str):
                tokens = getattr(result, "token_count", 0)
                self._total_tokens += tokens
                return result.text
            return result
        except TypeError:
            # Fallback: provider may only accept positional prompt
            full_prompt = self._format_prompt(prompt, system)
            result = self._provider.generate(full_prompt)
            if not isinstance(result, str):
                tokens = getattr(result, "token_count", 0)
                self._total_tokens += tokens
                return result.text
            return result

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
