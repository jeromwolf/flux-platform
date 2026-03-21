"""Skill data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillDefinition:
    """Definition of an agent skill (higher-level than a tool).

    A skill composes multiple tool calls and LLM interactions into a
    named, reusable capability.

    Example::

        skill = SkillDefinition(
            name="summarise_voyage",
            description="Summarises a vessel voyage from KG data.",
            category="kg",
            required_tools=("kg_query", "format_output"),
        )
        errors = skill.validate()
    """

    name: str
    description: str
    category: str = "general"  # general | kg | nlp | etl | analysis
    version: str = "0.1.0"
    required_tools: tuple[str, ...] = ()  # tools this skill needs
    parameters: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate skill definition fields.

        Returns:
            List of validation error messages. Empty list means valid.
        """
        errors: list[str] = []
        if not self.name:
            errors.append("Skill name is required")
        if not self.description:
            errors.append("Skill description is required")
        return errors


@dataclass(frozen=True)
class SkillResult:
    """Result of skill execution."""

    skill_name: str
    output: str
    success: bool = True
    error: str = ""
    steps_taken: int = 0
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
