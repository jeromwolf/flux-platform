"""Data models for the LLM provider layer.

All models are frozen dataclasses for immutability.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class ProviderType(str, Enum):
    """Supported LLM provider types."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ProviderInfo:
    """Metadata about an LLM provider."""
    name: str
    provider_type: ProviderType
    description: str = ""
    version: str = "0.1.0"
    supports_streaming: bool = False
    supports_embeddings: bool = False
    max_context_length: int = 4096


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for an LLM provider instance.

    Load from environment variables via ``from_env()``.
    """
    provider: str = "ollama"
    model: str = "mistral"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    timeout: float = 30.0
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 1.0

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Load LLM configuration from environment variables.

        Environment variables:
            LLM_PROVIDER: Provider name (default: "ollama")
            LLM_MODEL: Model name (default: "mistral")
            LLM_BASE_URL: API base URL (default: "http://localhost:11434")
            LLM_API_KEY: API key for authenticated providers
            LLM_TIMEOUT: Request timeout in seconds (default: 30.0)
            LLM_MAX_TOKENS: Maximum output tokens (default: 2048)
            LLM_TEMPERATURE: Sampling temperature (default: 0.7)
        """
        return cls(
            provider=os.getenv("LLM_PROVIDER", cls.provider),
            model=os.getenv("LLM_MODEL", cls.model),
            base_url=os.getenv("LLM_BASE_URL", cls.base_url),
            api_key=os.getenv("LLM_API_KEY", cls.api_key),
            timeout=float(os.getenv("LLM_TIMEOUT", str(cls.timeout))),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", str(cls.max_tokens))),
            temperature=float(os.getenv("LLM_TEMPERATURE", str(cls.temperature))),
        )

    def validate(self) -> list[str]:
        """Validate configuration and return list of error messages.

        Returns:
            List of validation error strings. Empty list means valid.
        """
        errors: list[str] = []
        if not self.provider:
            errors.append("provider must not be empty")
        if not self.model:
            errors.append("model must not be empty")
        if self.timeout <= 0:
            errors.append("timeout must be positive")
        if self.max_tokens <= 0:
            errors.append("max_tokens must be positive")
        if not (0.0 <= self.temperature <= 2.0):
            errors.append("temperature must be between 0.0 and 2.0")
        if not (0.0 <= self.top_p <= 1.0):
            errors.append("top_p must be between 0.0 and 1.0")
        if self.provider in ("openai", "anthropic") and not self.api_key:
            errors.append(f"{self.provider} provider requires api_key")
        return errors


@dataclass(frozen=True)
class LLMResponse:
    """Immutable response from an LLM provider."""
    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        """Total tokens used (prompt + completion)."""
        return self.total_tokens or (self.prompt_tokens + self.completion_tokens)
