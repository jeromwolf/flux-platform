"""Tests for core.kg.project -- Multi-project KG namespace management.

Verifies KGProjectContext dataclass, from_header() factory, project_label() helper,
and module-level constants. All tests run without Neo4j.
"""
from __future__ import annotations

import pytest

from kg.project import (
    DEFAULT_PROJECT,
    PROJECT_HEADER,
    PROJECT_LABEL_PREFIX,
    KGProjectContext,
    project_label,
)


# ---------------------------------------------------------------------------
# KGProjectContext dataclass
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestKGProjectContext:
    """KGProjectContext dataclass tests."""

    def test_default_values(self) -> None:
        ctx = KGProjectContext(name="default")
        assert ctx.name == "default"
        assert ctx.label == "KG_default"
        assert ctx.property_value == "default"

    def test_custom_name(self) -> None:
        ctx = KGProjectContext(name="DevKG")
        assert ctx.name == "DevKG"
        assert ctx.label == "KG_DevKG"
        assert ctx.property_value == "DevKG"

    def test_frozen(self) -> None:
        ctx = KGProjectContext(name="test")
        with pytest.raises(AttributeError):
            ctx.name = "other"  # type: ignore[misc]

    def test_label_prefix(self) -> None:
        ctx = KGProjectContext(name="Prod")
        assert ctx.label.startswith(PROJECT_LABEL_PREFIX)

    def test_property_value_equals_name(self) -> None:
        ctx = KGProjectContext(name="MyProject")
        assert ctx.property_value == ctx.name

    def test_label_concatenation(self) -> None:
        ctx = KGProjectContext(name="Alpha")
        assert ctx.label == f"{PROJECT_LABEL_PREFIX}Alpha"


# ---------------------------------------------------------------------------
# from_header() factory
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFromHeader:
    """KGProjectContext.from_header() factory tests."""

    def test_none_returns_default(self) -> None:
        ctx = KGProjectContext.from_header(None)
        assert ctx.name == DEFAULT_PROJECT

    def test_empty_returns_default(self) -> None:
        ctx = KGProjectContext.from_header("")
        assert ctx.name == DEFAULT_PROJECT

    def test_whitespace_only_returns_default(self) -> None:
        ctx = KGProjectContext.from_header("   ")
        assert ctx.name == DEFAULT_PROJECT

    def test_valid_name(self) -> None:
        ctx = KGProjectContext.from_header("DevKG")
        assert ctx.name == "DevKG"

    def test_valid_with_underscore(self) -> None:
        ctx = KGProjectContext.from_header("coast_guard_patrol")
        assert ctx.name == "coast_guard_patrol"

    def test_valid_with_numbers(self) -> None:
        ctx = KGProjectContext.from_header("Project2026")
        assert ctx.name == "Project2026"

    def test_invalid_starts_with_number(self) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            KGProjectContext.from_header("123abc")

    def test_invalid_special_chars_dash(self) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            KGProjectContext.from_header("dev-kg")

    def test_invalid_special_chars_dot(self) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            KGProjectContext.from_header("dev.kg")

    def test_invalid_spaces(self) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            KGProjectContext.from_header("dev kg")

    def test_invalid_too_long(self) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            KGProjectContext.from_header("A" * 65)

    def test_max_length_valid(self) -> None:
        name = "A" + "b" * 63  # 64 chars total
        ctx = KGProjectContext.from_header(name)
        assert ctx.name == name

    def test_single_char_valid(self) -> None:
        ctx = KGProjectContext.from_header("X")
        assert ctx.name == "X"

    def test_strips_whitespace(self) -> None:
        ctx = KGProjectContext.from_header("  DevKG  ")
        assert ctx.name == "DevKG"


# ---------------------------------------------------------------------------
# project_label() helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectLabel:
    """project_label() helper function tests."""

    def test_simple(self) -> None:
        assert project_label("DevKG") == "KG_DevKG"

    def test_default(self) -> None:
        assert project_label(DEFAULT_PROJECT) == "KG_default"

    def test_underscore_name(self) -> None:
        assert project_label("my_project") == "KG_my_project"


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConstants:
    """Module-level constant tests."""

    def test_default_project(self) -> None:
        assert DEFAULT_PROJECT == "default"

    def test_prefix(self) -> None:
        assert PROJECT_LABEL_PREFIX == "KG_"

    def test_header_name(self) -> None:
        assert PROJECT_HEADER == "X-KG-Project"
