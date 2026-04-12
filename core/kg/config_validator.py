"""Configuration validation utilities.

Validates AppConfig and its nested configurations against
expected constraints. Reports all validation issues at once
rather than failing on the first error.

Usage::

    from kg.config_validator import validate_config, ConfigValidationError

    config = get_config()
    try:
        validate_config(config)
    except ConfigValidationError as e:
        for issue in e.issues:
            print(f"  - {issue}")
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kg.config import AppConfig, Environment, Neo4jConfig

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""
    ERROR = "error"      # Must fix before proceeding
    WARNING = "warning"  # Should fix but won't block startup
    INFO = "info"        # Informational, no action required


@dataclass(frozen=True)
class ValidationIssue:
    """A single configuration validation issue."""
    field: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    suggestion: str = ""

    def __str__(self) -> str:
        parts = [f"[{self.severity.value.upper()}] {self.field}: {self.message}"]
        if self.suggestion:
            parts.append(f"  Suggestion: {self.suggestion}")
        return "\n".join(parts)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails.

    Attributes:
        issues: List of all validation issues found.
    """

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        error_count = sum(1 for i in issues if i.severity == ValidationSeverity.ERROR)
        super().__init__(
            f"Configuration validation failed: {error_count} error(s), "
            f"{len(issues)} total issue(s)"
        )


def validate_config(
    config: AppConfig,
    *,
    strict: bool = False,
) -> list[ValidationIssue]:
    """Validate an AppConfig instance.

    Checks all nested configurations and returns issues found.
    In strict mode, raises ConfigValidationError on any ERROR-level issues.

    Args:
        config: The AppConfig to validate.
        strict: If True, raise ConfigValidationError on errors.

    Returns:
        List of ValidationIssue objects.

    Raises:
        ConfigValidationError: In strict mode when errors are found.
    """
    issues: list[ValidationIssue] = []

    issues.extend(_validate_app_config(config))
    issues.extend(_validate_neo4j_config(config.neo4j))

    if strict:
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        if errors:
            raise ConfigValidationError(issues)

    for issue in issues:
        log_fn = {
            ValidationSeverity.ERROR: logger.error,
            ValidationSeverity.WARNING: logger.warning,
            ValidationSeverity.INFO: logger.info,
        }[issue.severity]
        log_fn("Config validation: %s", issue)

    return issues


def _validate_app_config(config: AppConfig) -> list[ValidationIssue]:
    """Validate top-level AppConfig fields."""
    issues: list[ValidationIssue] = []

    # Environment — AppConfig.env is now an Environment enum; validate() at from_env()
    # already rejects unknown values, but direct AppConfig(..., env="custom") paths
    # still use the dataclass constructor with a raw string.  Accept both.
    valid_envs = {e.value for e in Environment}
    env_val = config.env.value if isinstance(config.env, Environment) else str(config.env)
    if env_val not in valid_envs:
        issues.append(ValidationIssue(
            field="env",
            message=f"Unknown environment '{env_val}'",
            severity=ValidationSeverity.WARNING,
            suggestion=f"Use one of: {', '.join(sorted(valid_envs))}",
        ))

    # Log level
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if config.log_level.upper() not in valid_levels:
        issues.append(ValidationIssue(
            field="log_level",
            message=f"Unknown log level '{config.log_level}'",
            severity=ValidationSeverity.ERROR,
            suggestion=f"Use one of: {', '.join(sorted(valid_levels))}",
        ))

    # Project name
    if not config.project_name:
        issues.append(ValidationIssue(
            field="project_name",
            message="Project name is empty",
            severity=ValidationSeverity.WARNING,
        ))

    # Production warnings
    if config.env == Environment.PRODUCTION or env_val == "production":
        if config.log_level.upper() == "DEBUG":
            issues.append(ValidationIssue(
                field="log_level",
                message="DEBUG logging in production may impact performance",
                severity=ValidationSeverity.WARNING,
                suggestion="Use INFO or WARNING in production",
            ))

    return issues


def _validate_neo4j_config(config: Neo4jConfig) -> list[ValidationIssue]:
    """Validate Neo4j connection configuration."""
    issues: list[ValidationIssue] = []

    # URI format
    valid_schemes = {"bolt://", "neo4j://", "bolt+s://", "neo4j+s://"}
    if not any(config.uri.startswith(s) for s in valid_schemes):
        issues.append(ValidationIssue(
            field="neo4j.uri",
            message=f"Invalid Neo4j URI scheme: '{config.uri}'",
            severity=ValidationSeverity.ERROR,
            suggestion="URI should start with bolt:// or neo4j://",
        ))

    # Password
    if not config.password:
        issues.append(ValidationIssue(
            field="neo4j.password",
            message="Neo4j password is empty",
            severity=ValidationSeverity.WARNING,
            suggestion="Set NEO4J_PASSWORD environment variable",
        ))

    # Connection pool
    if config.max_connection_pool_size < 1:
        issues.append(ValidationIssue(
            field="neo4j.max_connection_pool_size",
            message=f"Pool size {config.max_connection_pool_size} is too small",
            severity=ValidationSeverity.ERROR,
        ))
    elif config.max_connection_pool_size > 200:
        issues.append(ValidationIssue(
            field="neo4j.max_connection_pool_size",
            message=f"Pool size {config.max_connection_pool_size} is unusually large",
            severity=ValidationSeverity.WARNING,
            suggestion="Typical values are 25-100",
        ))

    # Connection timeout
    if config.connection_timeout <= 0:
        issues.append(ValidationIssue(
            field="neo4j.connection_timeout",
            message="Connection timeout must be positive",
            severity=ValidationSeverity.ERROR,
        ))
    elif config.connection_timeout < 5:
        issues.append(ValidationIssue(
            field="neo4j.connection_timeout",
            message=f"Timeout {config.connection_timeout}s is very short",
            severity=ValidationSeverity.WARNING,
        ))

    return issues


def validate_env_completeness() -> list[ValidationIssue]:
    """Check if expected environment variables are set.

    Returns issues for missing or empty critical env vars.

    Returns:
        List of ValidationIssue objects.
    """
    import os

    issues: list[ValidationIssue] = []

    required_vars = {
        "NEO4J_URI": "Neo4j connection URI",
        "NEO4J_PASSWORD": "Neo4j password",
    }

    recommended_vars = {
        "ENV": "Application environment (development/staging/production)",
        "LOG_LEVEL": "Logging level",
    }

    for var, desc in required_vars.items():
        if not os.getenv(var):
            issues.append(ValidationIssue(
                field=f"env.{var}",
                message=f"Required environment variable {var} is not set ({desc})",
                severity=ValidationSeverity.WARNING,
                suggestion=f"Set {var} in .env or environment",
            ))

    for var, desc in recommended_vars.items():
        if not os.getenv(var):
            issues.append(ValidationIssue(
                field=f"env.{var}",
                message=f"Recommended environment variable {var} is not set ({desc})",
                severity=ValidationSeverity.INFO,
            ))

    return issues
