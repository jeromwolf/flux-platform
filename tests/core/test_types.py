"""Unit tests for kg.types – FilterOperator enum.

Covers canonical values, short-form alias resolution, case-insensitive
aliases, unknown values, string behaviour, and enum iteration.
"""

from __future__ import annotations

import pytest

from kg.types import FilterOperator


@pytest.mark.unit
class TestFilterOperatorCanonicalValues:
    """All canonical enum members exist with expected string values."""

    _EXPECTED = {
        "EQUALS": "equals",
        "NOT_EQUALS": "not_equals",
        "CONTAINS": "contains",
        "STARTS_WITH": "starts_with",
        "ENDS_WITH": "ends_with",
        "GREATER_THAN": "greater_than",
        "GREATER_THAN_OR_EQUALS": "greater_than_or_equals",
        "LESS_THAN": "less_than",
        "LESS_THAN_OR_EQUALS": "less_than_or_equals",
        "IN": "in",
        "NOT_IN": "not_in",
        "IS_NULL": "is_null",
        "IS_NOT_NULL": "is_not_null",
        "MATCHES_REGEX": "matches_regex",
    }

    def test_all_members_present(self) -> None:
        """Every expected member name exists on FilterOperator."""
        for name in self._EXPECTED:
            assert hasattr(FilterOperator, name), f"Missing member: {name}"

    def test_member_values(self) -> None:
        """Each member's .value matches the expected lowercase string."""
        for name, expected_value in self._EXPECTED.items():
            member = FilterOperator[name]
            assert member.value == expected_value

    def test_total_member_count(self) -> None:
        """Enum has exactly 14 canonical members."""
        assert len(FilterOperator) == 14


@pytest.mark.unit
class TestFilterOperatorAliases:
    """_missing_() resolves short-form aliases to canonical members."""

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("eq", FilterOperator.EQUALS),
            ("neq", FilterOperator.NOT_EQUALS),
            ("gt", FilterOperator.GREATER_THAN),
            ("gte", FilterOperator.GREATER_THAN_OR_EQUALS),
            ("lt", FilterOperator.LESS_THAN),
            ("lte", FilterOperator.LESS_THAN_OR_EQUALS),
            ("in_list", FilterOperator.IN),
            ("not_in_list", FilterOperator.NOT_IN),
            ("regex", FilterOperator.MATCHES_REGEX),
        ],
    )
    def test_alias_resolution(self, alias: str, expected: FilterOperator) -> None:
        """Short-form alias resolves to the correct canonical member."""
        assert FilterOperator(alias) is expected

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("GT", FilterOperator.GREATER_THAN),
            ("Gt", FilterOperator.GREATER_THAN),
            ("gT", FilterOperator.GREATER_THAN),
            ("LTE", FilterOperator.LESS_THAN_OR_EQUALS),
            ("Eq", FilterOperator.EQUALS),
            ("REGEX", FilterOperator.MATCHES_REGEX),
        ],
    )
    def test_alias_case_insensitive(self, alias: str, expected: FilterOperator) -> None:
        """Aliases are resolved case-insensitively."""
        assert FilterOperator(alias) is expected


@pytest.mark.unit
class TestFilterOperatorInvalidValues:
    """Unknown or non-string values raise ValueError."""

    def test_unknown_alias_raises(self) -> None:
        with pytest.raises(ValueError):
            FilterOperator("nonexistent")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            FilterOperator("")

    def test_numeric_value_raises(self) -> None:
        with pytest.raises(ValueError):
            FilterOperator(42)  # type: ignore[arg-type]

    def test_none_value_raises(self) -> None:
        with pytest.raises(ValueError):
            FilterOperator(None)  # type: ignore[arg-type]


@pytest.mark.unit
class TestFilterOperatorStringBehaviour:
    """FilterOperator inherits from str so it behaves as a string."""

    def test_value_access(self) -> None:
        assert FilterOperator.EQUALS.value == "equals"
        assert FilterOperator.GREATER_THAN.value == "greater_than"

    def test_str_returns_value(self) -> None:
        """str(member) should include the value (str enum)."""
        result = str(FilterOperator.EQUALS)
        assert "equals" in result.lower()

    def test_string_equality(self) -> None:
        """As a str enum, members compare equal to their string value."""
        assert FilterOperator.EQUALS == "equals"
        assert FilterOperator.IN == "in"

    def test_string_concatenation(self) -> None:
        """str enum members can be concatenated with strings."""
        result = "op=" + FilterOperator.EQUALS
        assert result == "op=equals"

    def test_iteration(self) -> None:
        """Iterating over FilterOperator yields all members."""
        members = list(FilterOperator)
        assert len(members) == 14
        assert FilterOperator.EQUALS in members
        assert FilterOperator.MATCHES_REGEX in members

    def test_membership_by_name(self) -> None:
        """Member names are accessible via __members__."""
        assert "EQUALS" in FilterOperator.__members__
        assert "GREATER_THAN" in FilterOperator.__members__
        assert "NONEXISTENT" not in FilterOperator.__members__

    def test_canonical_value_construction(self) -> None:
        """Constructing from the canonical value returns the same member."""
        assert FilterOperator("equals") is FilterOperator.EQUALS
        assert FilterOperator("greater_than") is FilterOperator.GREATER_THAN
