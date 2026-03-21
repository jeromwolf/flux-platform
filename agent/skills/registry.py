"""Skill registry for agent runtime."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, Optional

from agent.skills.models import SkillDefinition, SkillResult

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Registry for agent skills.

    Skills are higher-level capabilities composed of multiple
    tool calls and LLM interactions.

    Example::

        registry = SkillRegistry()
        registry.register(
            SkillDefinition(
                name="summarise_voyage",
                description="Summarises a vessel voyage from KG data.",
                category="kg",
            ),
            handler=summarise_voyage_handler,
        )
        result = registry.execute("summarise_voyage", {"vessel_id": "IMO1234567"})
    """

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(
        self,
        definition: SkillDefinition,
        handler: Callable[..., Any],
    ) -> SkillRegistry:
        """Register a skill with its handler function.

        Args:
            definition: Skill metadata, category, and required tools.
            handler: Callable that executes the skill logic.

        Returns:
            Self for chaining.

        Raises:
            ValueError: If the skill definition is invalid.
        """
        errors = definition.validate()
        if errors:
            raise ValueError(f"Invalid skill definition: {'; '.join(errors)}")
        self._skills[definition.name] = definition
        self._handlers[definition.name] = handler
        logger.info("Registered skill: %s (category=%s)", definition.name, definition.category)
        return self

    def get(self, name: str) -> Optional[SkillDefinition]:
        """Look up a skill definition by name.

        Args:
            name: Skill name.

        Returns:
            :class:`SkillDefinition` or ``None`` if not found.
        """
        return self._skills.get(name)

    def execute(
        self,
        name: str,
        inputs: Optional[dict[str, Any]] = None,
    ) -> SkillResult:
        """Execute a registered skill.

        Args:
            name: Skill name.
            inputs: Keyword arguments forwarded to the skill handler.

        Returns:
            :class:`SkillResult` with output or error details.
        """
        defn = self._skills.get(name)
        if defn is None:
            return SkillResult(
                skill_name=name,
                output="",
                success=False,
                error=f"Unknown skill: {name}",
            )

        inputs = inputs or {}
        handler = self._handlers[name]
        start = time.monotonic()
        steps = 0
        try:
            raw = handler(**inputs)
            duration = (time.monotonic() - start) * 1000
            # Allow handlers to return a SkillResult directly or a plain value.
            if isinstance(raw, SkillResult):
                return raw
            steps = getattr(raw, "steps_taken", 0)
            return SkillResult(
                skill_name=name,
                output=str(raw),
                success=True,
                steps_taken=steps,
                duration_ms=round(duration, 2),
            )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            logger.error("Skill '%s' failed: %s", name, exc)
            return SkillResult(
                skill_name=name,
                output="",
                success=False,
                error=str(exc),
                steps_taken=steps,
                duration_ms=round(duration, 2),
            )

    @property
    def skill_names(self) -> list[str]:
        """Names of all registered skills."""
        return list(self._skills.keys())

    @property
    def skill_count(self) -> int:
        """Number of registered skills."""
        return len(self._skills)

    def list_skills(self) -> list[SkillDefinition]:
        """Return all registered skill definitions."""
        return list(self._skills.values())

    def list_by_category(self, category: str) -> list[SkillDefinition]:
        """Return skill definitions filtered by category.

        Args:
            category: Category string (e.g. ``"kg"``, ``"nlp"``).

        Returns:
            List of matching :class:`SkillDefinition` instances.
        """
        return [s for s in self._skills.values() if s.category == category]

    def clear(self) -> None:
        """Remove all registered skills and handlers."""
        self._skills.clear()
        self._handlers.clear()
