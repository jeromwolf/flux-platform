"""LLM provider implementations for the agent runtime.

Provides concrete LLM providers (Ollama, OpenAI, Anthropic, Stub) that conform
to the :class:`LLMProvider` protocol, plus a factory for auto-detection.

All HTTP calls use ``urllib.request`` (stdlib) to avoid external dependencies.

Usage::

    from agent.llm.providers import create_llm_provider

    provider = create_llm_provider("auto")  # tries Ollama -> Anthropic -> OpenAI -> Stub
    text = provider.generate("Hello, world!")
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that all LLM providers must satisfy."""

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text from a prompt.

        Args:
            prompt: User-facing prompt text.
            system: Optional system instruction.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            Generated text string.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------


@dataclass
class OllamaLLMProvider:
    """LLM provider backed by a local Ollama server.

    Uses the ``/api/generate`` endpoint via ``urllib.request``.

    Args:
        model: Ollama model name (e.g. ``"llama3.1:8b"``).
        base_url: Ollama server URL.
        timeout: HTTP request timeout in seconds.
    """

    model: str = "llama3.1:8b"
    base_url: str = "http://localhost:11434"
    timeout: int = 60

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text using Ollama API.

        Args:
            prompt: User prompt.
            system: System instruction.
            temperature: Sampling temperature.
            max_tokens: Max tokens to predict.

        Returns:
            Generated text.

        Raises:
            urllib.error.URLError: If Ollama server is unreachable.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "")


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


@dataclass
class OpenAILLMProvider:
    """LLM provider backed by the OpenAI Chat Completions API.

    Uses ``urllib.request`` for zero external dependencies.

    Args:
        model: OpenAI model name.
        api_key: API key (falls back to ``OPENAI_API_KEY`` env var).
        timeout: HTTP request timeout in seconds.
    """

    model: str = "gpt-4o-mini"
    api_key: str = ""
    timeout: int = 60

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("OPENAI_API_KEY", "")

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text using OpenAI Chat Completions API.

        Args:
            prompt: User prompt.
            system: System instruction.
            temperature: Sampling temperature.
            max_tokens: Max tokens to generate.

        Returns:
            Generated text.

        Raises:
            ValueError: If no API key is available.
            urllib.error.URLError: If the API is unreachable.
        """
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not set. Provide via constructor or "
                "OPENAI_API_KEY environment variable."
            )

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------


@dataclass
class AnthropicLLMProvider:
    """LLM provider backed by the Anthropic Messages API.

    Uses ``urllib.request`` for zero external dependencies — no ``anthropic``
    SDK required.

    Args:
        model: Anthropic model name.
        api_key: API key (falls back to ``ANTHROPIC_API_KEY`` env var).
        timeout: HTTP request timeout in seconds.
    """

    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    timeout: int = 60

    _ENDPOINT = "https://api.anthropic.com/v1/messages"
    _API_VERSION = "2023-06-01"

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using Anthropic Messages API.

        Args:
            prompt: User prompt.
            system: System instruction.
            temperature: Sampling temperature.
            max_tokens: Max tokens to generate.

        Returns:
            Generated text, or an error message string on failure.
        """
        if not self.api_key:
            logger.warning(
                "Anthropic API key not set. Provide via constructor or "
                "ANTHROPIC_API_KEY environment variable."
            )
            return "[AnthropicLLMProvider] Error: API key not set."

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._ENDPOINT,
            data=data,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self._API_VERSION,
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["content"][0]["text"]
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("AnthropicLLMProvider request failed: %s", exc)
            return f"[AnthropicLLMProvider] Error: {exc}"


# ---------------------------------------------------------------------------
# Stub provider (for testing without a real LLM)
# ---------------------------------------------------------------------------


@dataclass
class StubLLMProvider:
    """Stub LLM provider that returns a fixed message.

    Useful for testing and local development without a real LLM backend.
    """

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Return a stub response indicating no real LLM is configured.

        Args:
            prompt: User prompt (used for length reporting).
            system: Ignored.
            temperature: Ignored.
            max_tokens: Ignored.

        Returns:
            Stub message string.
        """
        return (
            f"[Stub LLM] Received prompt ({len(prompt)} chars). "
            "No real LLM configured."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_llm_provider(provider: str = "auto") -> LLMProvider:
    """Create an LLM provider by name with auto-detection.

    Resolution order for ``"auto"``:
      1. Ollama (health-check ``/api/tags``)
      2. Anthropic (if ``ANTHROPIC_API_KEY`` is set)
      3. OpenAI (if ``OPENAI_API_KEY`` is set)
      4. StubLLMProvider (always available)

    Args:
        provider: Provider name: ``"ollama"``, ``"anthropic"``, ``"openai"``,
            ``"stub"``, or ``"auto"`` (default).

    Returns:
        An :class:`LLMProvider`-compatible instance.

    Raises:
        ValueError: If an explicit provider name is given but cannot be
            initialised (e.g. ``"ollama"`` when server is down).
    """
    if provider == "stub":
        return StubLLMProvider()

    if provider in ("ollama", "auto"):
        try:
            p = OllamaLLMProvider()
            # Quick health check -- just verify the server is reachable
            urllib.request.urlopen(f"{p.base_url}/api/tags", timeout=3)
            logger.info("Ollama LLM provider connected at %s", p.base_url)
            return p
        except Exception as exc:
            if provider == "ollama":
                raise ValueError(
                    f"Ollama server not reachable: {exc}"
                ) from exc
            logger.debug("Ollama not available, trying next provider: %s", exc)

    if provider in ("anthropic", "auto"):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            logger.info(
                "Anthropic LLM provider selected (model: claude-sonnet-4-20250514)"
            )
            return AnthropicLLMProvider(api_key=api_key)
        elif provider == "anthropic":
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        else:
            logger.debug("Anthropic API key not found, trying next provider")

    if provider in ("openai", "auto"):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            logger.info("OpenAI LLM provider selected (model: gpt-4o-mini)")
            return OpenAILLMProvider(api_key=api_key)
        elif provider == "openai":
            raise ValueError("OPENAI_API_KEY environment variable not set")
        else:
            logger.debug("OpenAI API key not found, falling back to stub")

    logger.info("Using StubLLMProvider (no real LLM available)")
    return StubLLMProvider()
