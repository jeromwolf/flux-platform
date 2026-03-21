"""LLM Provider registry.

Manages registration and lookup of LLM providers. Supports
provider discovery and failover configuration.
"""
from __future__ import annotations

import logging
from typing import Any

from kg.llm.models import LLMConfig, ProviderInfo
from kg.llm.protocol import LLMProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for LLM provider instances.

    Manages provider registration, lookup, and optional failover chains.

    Example::

        registry = ProviderRegistry()
        registry.register(my_ollama_provider)
        provider = registry.get("ollama")
        response = provider.generate("Hello")
    """

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._default: str | None = None
        self._failover_chain: list[str] = []

    def register(self, provider: LLMProvider) -> ProviderRegistry:
        """Register a provider instance.

        Args:
            provider: An LLMProvider implementation.

        Returns:
            Self for chaining.
        """
        name = provider.info.name
        self._providers[name] = provider
        logger.info("Registered LLM provider: %s", name)
        if self._default is None:
            self._default = name
        return self

    def get(self, name: str) -> LLMProvider | None:
        """Look up a provider by name.

        Args:
            name: Provider name.

        Returns:
            The provider instance, or None if not found.
        """
        return self._providers.get(name)

    def get_default(self) -> LLMProvider | None:
        """Return the default provider (first registered).

        Returns:
            The default provider, or None if registry is empty.
        """
        if self._default is None:
            return None
        return self._providers.get(self._default)

    def set_default(self, name: str) -> ProviderRegistry:
        """Set the default provider by name.

        Args:
            name: Provider name (must already be registered).

        Returns:
            Self for chaining.

        Raises:
            KeyError: If provider name is not registered.
        """
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not registered")
        self._default = name
        return self

    def set_failover_chain(self, names: list[str]) -> ProviderRegistry:
        """Configure failover order for provider selection.

        Args:
            names: Ordered list of provider names to try.

        Returns:
            Self for chaining.
        """
        self._failover_chain = list(names)
        return self

    def get_available(self) -> LLMProvider | None:
        """Return the first available provider from failover chain.

        Falls back to default if no failover chain is configured,
        or returns None if nothing is available.

        Returns:
            An available LLMProvider, or None.
        """
        chain = self._failover_chain or (
            [self._default] if self._default else []
        )
        for name in chain:
            provider = self._providers.get(name)
            if provider is not None and provider.is_available():
                return provider
        return None

    @property
    def provider_names(self) -> list[str]:
        """Names of all registered providers."""
        return list(self._providers.keys())

    @property
    def provider_count(self) -> int:
        """Number of registered providers."""
        return len(self._providers)

    def clear(self) -> None:
        """Remove all registered providers."""
        self._providers.clear()
        self._default = None
        self._failover_chain.clear()
