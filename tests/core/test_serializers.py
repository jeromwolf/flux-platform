"""Unit tests for kg.api.serializers.

All tests are marked with ``@pytest.mark.unit`` and require no external services.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from kg.api.serializers import serialize_neo4j_value


@pytest.mark.unit
class TestSerializeNeo4jValue:
    """Test serialize_neo4j_value with various types."""

    def test_none_returns_none(self) -> None:
        assert serialize_neo4j_value(None) is None

    def test_primitives_pass_through(self) -> None:
        assert serialize_neo4j_value("hello") == "hello"
        assert serialize_neo4j_value(42) == 42
        assert serialize_neo4j_value(3.14) == 3.14
        assert serialize_neo4j_value(True) is True
        assert serialize_neo4j_value(False) is False

    def test_list_recursion(self) -> None:
        result = serialize_neo4j_value([1, "two", None, [3, 4]])
        assert result == [1, "two", None, [3, 4]]

    def test_dict_recursion(self) -> None:
        result = serialize_neo4j_value({"a": 1, "b": {"c": "d"}})
        assert result == {"a": 1, "b": {"c": "d"}}

    def test_spatial_type(self) -> None:
        """Objects with x and y attributes are serialized as lat/lon."""
        point = MagicMock()
        point.x = 129.0
        point.y = 35.1
        # Remove isoformat to avoid ambiguity
        del point.isoformat
        result = serialize_neo4j_value(point)
        assert result == {"lat": 35.1, "lon": 129.0}

    def test_temporal_type(self) -> None:
        """Objects with isoformat() are serialized via isoformat."""
        dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = serialize_neo4j_value(dt)
        assert result == "2025-01-15T10:30:00+00:00"

    def test_unknown_type_falls_back_to_str(self) -> None:
        """Unrecognized types are converted to string."""

        class CustomObj:
            def __str__(self) -> str:
                return "custom-value"

        result = serialize_neo4j_value(CustomObj())
        assert result == "custom-value"

    def test_nested_spatial_in_list(self) -> None:
        """Spatial types nested in lists are properly serialized."""
        point = MagicMock()
        point.x = 126.9
        point.y = 37.5
        del point.isoformat
        result = serialize_neo4j_value([point, "Seoul"])
        assert result == [{"lat": 37.5, "lon": 126.9}, "Seoul"]
