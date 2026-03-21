"""LLM Provider protocol definition.

Defines the interface that all LLM providers must implement.
Uses ``@runtime_checkable`` Protocol for structural typing.
"""
from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

from kg.llm.models import LLMConfig, LLMResponse, ProviderInfo


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM provider implementations.

    Providers must implement at minimum ``generate()`` and ``info()``.
    Streaming and embedding support are optional capabilities declared
    in ``ProviderInfo``.
    """

    @property
    def info(self) -> ProviderInfo:
        """Return provider metadata."""
        ...

    def generate(self, prompt: str, **kwargs: object) -> LLMResponse:
        """Generate a completion for the given prompt.

        Args:
            prompt: The input text prompt.
            **kwargs: Provider-specific parameters.

        Returns:
            An LLMResponse containing the generated text.
        """
        ...

    def is_available(self) -> bool:
        """Check if the provider is currently available.

        Returns:
            True if the provider can accept requests.
        """
        ...
