"""Cursor-based pagination utilities.

Provides cursor encoding/decoding and a FastAPI dependency for
extracting pagination parameters from query strings.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from fastapi import Query


@dataclass(frozen=True)
class PaginationParams:
    """Parsed pagination parameters from query string."""

    cursor: str | None = None
    limit: int = 50


def encode_cursor(data: dict) -> str:
    """Encode pagination state as a URL-safe cursor string.

    Args:
        data: Dict with cursor state (e.g. {"offset": 100} or {"last_id": "abc"}).

    Returns:
        URL-safe base64-encoded cursor string.
    """
    return base64.urlsafe_b64encode(json.dumps(data, sort_keys=True).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """Decode a cursor string back to pagination state.

    Args:
        cursor: URL-safe base64-encoded cursor string.

    Returns:
        Dict with cursor state.

    Raises:
        ValueError: If the cursor is malformed.
    """
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {cursor}") from exc


def get_pagination_params(
    cursor: str | None = Query(None, description="Pagination cursor"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
) -> PaginationParams:
    """FastAPI dependency for pagination parameters.

    Usage::

        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends(get_pagination_params)):
            ...
    """
    return PaginationParams(cursor=cursor, limit=limit)
