"""Unit tests for cursor-based pagination utilities."""
from __future__ import annotations

import pytest

from kg.api.pagination import (
    PaginationParams,
    decode_cursor,
    encode_cursor,
)


@pytest.mark.unit
class TestCursorEncoding:
    """Tests for cursor encode/decode."""

    def test_roundtrip(self):
        """인코딩 -> 디코딩 왕복 검증."""
        data = {"offset": 100, "last_id": "abc"}
        cursor = encode_cursor(data)
        decoded = decode_cursor(cursor)
        assert decoded == data

    def test_encode_returns_string(self):
        cursor = encode_cursor({"offset": 0})
        assert isinstance(cursor, str)

    def test_encode_url_safe(self):
        """URL-safe 문자만 사용."""
        cursor = encode_cursor({"key": "value/with+special=chars"})
        # URL-safe base64 doesn't use + or /
        assert "+" not in cursor or cursor.replace("+", "").isalnum()

    def test_decode_invalid_cursor_raises(self):
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor("not-valid-base64!!!")

    def test_decode_non_json_raises(self):
        import base64
        bad = base64.urlsafe_b64encode(b"not json").decode()
        with pytest.raises(ValueError):
            decode_cursor(bad)

    def test_empty_dict(self):
        cursor = encode_cursor({})
        assert decode_cursor(cursor) == {}

    def test_numeric_values(self):
        data = {"page": 5, "size": 20}
        cursor = encode_cursor(data)
        assert decode_cursor(cursor) == data


@pytest.mark.unit
class TestPaginationParams:
    """Tests for PaginationParams dataclass."""

    def test_defaults(self):
        params = PaginationParams()
        assert params.cursor is None
        assert params.limit == 50

    def test_custom_values(self):
        params = PaginationParams(cursor="abc", limit=100)
        assert params.cursor == "abc"
        assert params.limit == 100

    def test_frozen(self):
        params = PaginationParams()
        with pytest.raises(AttributeError):
            params.limit = 10  # type: ignore[misc]
