"""Config validation unit tests.

TC-CV01 ~ TC-CV05: ConfigValidator behavior tests.
All tests run without external dependencies.
"""

from __future__ import annotations

import pytest

from kg.config import AppConfig, Neo4jConfig
from kg.config_validator import (
    ConfigValidationError,
    ValidationIssue,
    ValidationSeverity,
    validate_config,
    validate_env_completeness,
)


# =============================================================================
# TC-CV01: ValidationIssue
# =============================================================================


@pytest.mark.unit
class TestValidationIssue:
    """ValidationIssue tests."""

    def test_creation(self) -> None:
        """TC-CV01-a: Basic creation."""
        issue = ValidationIssue(field="test", message="test error")
        assert issue.field == "test"
        assert issue.severity == ValidationSeverity.ERROR

    def test_str_format(self) -> None:
        """TC-CV01-b: String format includes severity and field."""
        issue = ValidationIssue(
            field="env", message="bad value",
            severity=ValidationSeverity.WARNING,
        )
        s = str(issue)
        assert "[WARNING]" in s
        assert "env" in s

    def test_str_with_suggestion(self) -> None:
        """TC-CV01-c: String includes suggestion when present."""
        issue = ValidationIssue(
            field="f", message="m", suggestion="do this",
        )
        assert "Suggestion" in str(issue)

    def test_frozen(self) -> None:
        """TC-CV01-d: ValidationIssue is frozen."""
        issue = ValidationIssue(field="f", message="m")
        with pytest.raises(AttributeError):
            issue.field = "new"  # type: ignore[misc]


# =============================================================================
# TC-CV02: Valid config
# =============================================================================


@pytest.mark.unit
class TestValidConfig:
    """Tests with valid configurations."""

    def test_default_config_valid(self) -> None:
        """TC-CV02-a: Default AppConfig passes validation (may have warnings)."""
        config = AppConfig()
        issues = validate_config(config)
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0

    def test_production_config_valid(self) -> None:
        """TC-CV02-b: Well-formed production config has no errors."""
        config = AppConfig(
            env="production",
            log_level="INFO",
            neo4j=Neo4jConfig(
                uri="bolt://neo4j:7687",
                password="secure-password",
            ),
        )
        issues = validate_config(config)
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0


# =============================================================================
# TC-CV03: Invalid configs
# =============================================================================


@pytest.mark.unit
class TestInvalidConfig:
    """Tests with invalid configurations."""

    def test_invalid_neo4j_uri(self) -> None:
        """TC-CV03-a: Invalid URI scheme produces ERROR."""
        config = AppConfig(
            neo4j=Neo4jConfig(uri="http://localhost:7687"),
        )
        issues = validate_config(config)
        assert any(
            i.field == "neo4j.uri" and i.severity == ValidationSeverity.ERROR
            for i in issues
        )

    def test_invalid_log_level(self) -> None:
        """TC-CV03-b: Unknown log level produces ERROR."""
        config = AppConfig(log_level="VERBOSE")
        issues = validate_config(config)
        assert any(
            i.field == "log_level" and i.severity == ValidationSeverity.ERROR
            for i in issues
        )

    def test_zero_pool_size(self) -> None:
        """TC-CV03-c: Zero pool size produces ERROR."""
        config = AppConfig(
            neo4j=Neo4jConfig(max_connection_pool_size=0),
        )
        issues = validate_config(config)
        assert any(
            i.field == "neo4j.max_connection_pool_size"
            and i.severity == ValidationSeverity.ERROR
            for i in issues
        )

    def test_negative_timeout(self) -> None:
        """TC-CV03-d: Negative timeout produces ERROR."""
        config = AppConfig(
            neo4j=Neo4jConfig(connection_timeout=-1),
        )
        issues = validate_config(config)
        assert any(
            i.field == "neo4j.connection_timeout"
            and i.severity == ValidationSeverity.ERROR
            for i in issues
        )


# =============================================================================
# TC-CV04: Strict mode
# =============================================================================


@pytest.mark.unit
class TestStrictMode:
    """Strict validation mode tests."""

    def test_strict_raises_on_error(self) -> None:
        """TC-CV04-a: Strict mode raises ConfigValidationError on errors."""
        config = AppConfig(log_level="INVALID")
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(config, strict=True)
        assert len(exc_info.value.issues) > 0

    def test_strict_passes_with_warnings_only(self) -> None:
        """TC-CV04-b: Strict mode doesn't raise on warnings-only."""
        config = AppConfig(env="custom_env")  # unknown env → WARNING only
        # Should not raise (no errors, only warnings)
        issues = validate_config(config, strict=True)
        assert all(i.severity != ValidationSeverity.ERROR for i in issues)


# =============================================================================
# TC-CV05: Warnings
# =============================================================================


@pytest.mark.unit
class TestWarnings:
    """Warning-level validation tests."""

    def test_unknown_env_warning(self) -> None:
        """TC-CV05-a: Unknown environment produces WARNING."""
        config = AppConfig(env="custom")
        issues = validate_config(config)
        assert any(
            i.field == "env" and i.severity == ValidationSeverity.WARNING
            for i in issues
        )

    def test_debug_in_production_warning(self) -> None:
        """TC-CV05-b: DEBUG log level in production produces WARNING."""
        config = AppConfig(env="production", log_level="DEBUG")
        issues = validate_config(config)
        assert any(
            i.field == "log_level" and i.severity == ValidationSeverity.WARNING
            for i in issues
        )

    def test_empty_password_warning(self) -> None:
        """TC-CV05-c: Empty Neo4j password produces WARNING."""
        config = AppConfig(neo4j=Neo4jConfig(password=""))
        issues = validate_config(config)
        assert any(
            i.field == "neo4j.password" and i.severity == ValidationSeverity.WARNING
            for i in issues
        )

    def test_large_pool_warning(self) -> None:
        """TC-CV05-d: Very large pool size produces WARNING."""
        config = AppConfig(
            neo4j=Neo4jConfig(max_connection_pool_size=500),
        )
        issues = validate_config(config)
        assert any(
            i.field == "neo4j.max_connection_pool_size"
            and i.severity == ValidationSeverity.WARNING
            for i in issues
        )


# =============================================================================
# TC-CV06: Environment completeness
# =============================================================================


@pytest.mark.unit
class TestEnvCompleteness:
    """validate_env_completeness tests."""

    def test_missing_neo4j_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-CV06-a: Missing NEO4J vars produce warnings."""
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        issues = validate_env_completeness()
        assert any("NEO4J_URI" in i.field for i in issues)
        assert any("NEO4J_PASSWORD" in i.field for i in issues)

    def test_severity_levels(self) -> None:
        """TC-CV06-b: Enum has correct values."""
        assert ValidationSeverity.ERROR == "error"
        assert ValidationSeverity.WARNING == "warning"
        assert ValidationSeverity.INFO == "info"
