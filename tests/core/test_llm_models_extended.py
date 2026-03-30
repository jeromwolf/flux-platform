"""Extended unit tests for core/kg/llm/models.py — validate() branch coverage.

Covers the three previously uncovered validation branches (lines 78, 80, 88):
- line 78: empty provider → "provider must not be empty"
- line 80: empty model   → "model must not be empty"
- line 88: top_p > 1.0  → "top_p must be between 0.0 and 1.0"

LLMConfig is a frozen dataclass so we use keyword-only construction.
All tests are @pytest.mark.unit.
"""
from __future__ import annotations

import pytest

from kg.llm.models import LLMConfig


# ---------------------------------------------------------------------------
# TestLLMConfigValidateEmptyProvider
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMConfigValidateEmptyProvider:
    """Tests for the empty provider validation branch (line 78)."""

    def test_empty_provider_string_produces_error(self) -> None:
        """provider='' → errors contains 'provider must not be empty'."""
        cfg = LLMConfig(provider="", model="mistral")
        errors = cfg.validate()
        assert "provider must not be empty" in errors

    def test_empty_provider_only_that_error_for_otherwise_valid_config(self) -> None:
        """Only the provider error is present when everything else is valid."""
        cfg = LLMConfig(
            provider="",
            model="mistral",
            base_url="http://localhost:11434",
            api_key="",
            timeout=30.0,
            max_tokens=2048,
            temperature=0.7,
            top_p=1.0,
        )
        errors = cfg.validate()
        assert "provider must not be empty" in errors
        # model is set, so no model error
        assert "model must not be empty" not in errors

    def test_non_empty_provider_does_not_trigger_error(self) -> None:
        """A non-empty provider string does not add the provider error."""
        cfg = LLMConfig(provider="ollama", model="mistral")
        errors = cfg.validate()
        assert "provider must not be empty" not in errors


# ---------------------------------------------------------------------------
# TestLLMConfigValidateEmptyModel
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMConfigValidateEmptyModel:
    """Tests for the empty model validation branch (line 80)."""

    def test_empty_model_string_produces_error(self) -> None:
        """model='' → errors contains 'model must not be empty'."""
        cfg = LLMConfig(provider="ollama", model="")
        errors = cfg.validate()
        assert "model must not be empty" in errors

    def test_empty_model_only_that_error_for_otherwise_valid_config(self) -> None:
        """Only the model error is present when everything else is valid."""
        cfg = LLMConfig(
            provider="ollama",
            model="",
            base_url="http://localhost:11434",
            api_key="",
            timeout=30.0,
            max_tokens=2048,
            temperature=0.7,
            top_p=1.0,
        )
        errors = cfg.validate()
        assert "model must not be empty" in errors
        assert "provider must not be empty" not in errors

    def test_non_empty_model_does_not_trigger_error(self) -> None:
        """A non-empty model string does not add the model error."""
        cfg = LLMConfig(provider="ollama", model="llama3")
        errors = cfg.validate()
        assert "model must not be empty" not in errors

    def test_empty_provider_and_empty_model_both_reported(self) -> None:
        """Both provider and model errors are returned when both are empty."""
        cfg = LLMConfig(provider="", model="")
        errors = cfg.validate()
        assert "provider must not be empty" in errors
        assert "model must not be empty" in errors


# ---------------------------------------------------------------------------
# TestLLMConfigValidateTopP
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMConfigValidateTopP:
    """Tests for the top_p out-of-range validation branch (line 88)."""

    def test_top_p_above_one_produces_error(self) -> None:
        """top_p=1.5 → errors contains 'top_p must be between 0.0 and 1.0'."""
        cfg = LLMConfig(provider="ollama", model="mistral", top_p=1.5)
        errors = cfg.validate()
        assert "top_p must be between 0.0 and 1.0" in errors

    def test_top_p_below_zero_produces_error(self) -> None:
        """top_p=-0.1 → errors contains 'top_p must be between 0.0 and 1.0'."""
        cfg = LLMConfig(provider="ollama", model="mistral", top_p=-0.1)
        errors = cfg.validate()
        assert "top_p must be between 0.0 and 1.0" in errors

    def test_top_p_at_boundary_zero_is_valid(self) -> None:
        """top_p=0.0 is a valid boundary value."""
        cfg = LLMConfig(provider="ollama", model="mistral", top_p=0.0)
        errors = cfg.validate()
        assert "top_p must be between 0.0 and 1.0" not in errors

    def test_top_p_at_boundary_one_is_valid(self) -> None:
        """top_p=1.0 is the maximum valid value."""
        cfg = LLMConfig(provider="ollama", model="mistral", top_p=1.0)
        errors = cfg.validate()
        assert "top_p must be between 0.0 and 1.0" not in errors

    def test_top_p_in_range_is_valid(self) -> None:
        """top_p=0.9 is within range and produces no error."""
        cfg = LLMConfig(provider="ollama", model="mistral", top_p=0.9)
        errors = cfg.validate()
        assert "top_p must be between 0.0 and 1.0" not in errors

    def test_top_p_exactly_two_is_invalid(self) -> None:
        """top_p=2.0 exceeds 1.0 and produces an error."""
        cfg = LLMConfig(provider="ollama", model="mistral", top_p=2.0)
        errors = cfg.validate()
        assert "top_p must be between 0.0 and 1.0" in errors

    def test_valid_config_produces_no_errors(self) -> None:
        """A fully valid config produces an empty errors list."""
        cfg = LLMConfig(
            provider="ollama",
            model="mistral",
            base_url="http://localhost:11434",
            api_key="",
            timeout=30.0,
            max_tokens=2048,
            temperature=0.7,
            top_p=0.95,
        )
        errors = cfg.validate()
        assert errors == []
