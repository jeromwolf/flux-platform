"""Standard API response envelope models.

These are opt-in models for new routes. Existing routes continue to
return raw Pydantic models without wrapping.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

#: Hard upper bound for all paginated list endpoints.
MAX_PAGE_LIMIT: int = 1000


class PaginationParams(BaseModel):
    """Reusable pagination query parameters with a hard upper bound.

    Use as a dependency in route functions::

        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            ...

    The ``limit`` field is capped at :data:`MAX_PAGE_LIMIT` (1 000) to prevent
    runaway queries that could destabilise the database.
    """

    offset: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(
        default=50,
        ge=1,
        le=MAX_PAGE_LIMIT,
        description=f"Maximum items to return (1–{MAX_PAGE_LIMIT})",
    )


class ResponseMeta(BaseModel):
    """Metadata included in every standard response."""

    requestId: str = ""
    timestamp: str = ""


class StandardResponse(BaseModel):
    """Standard single-item response envelope.

    Usage in routes::

        @router.get("/items/{id}", response_model=StandardResponse)
        async def get_item(id: str):
            item = fetch_item(id)
            return StandardResponse(data=item, meta=ResponseMeta(...))
    """

    data: Any = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class PaginationInfo(BaseModel):
    """Cursor-based pagination metadata."""

    cursor: str | None = None
    hasNext: bool = False
    hasPrev: bool = False
    total: int | None = None


class PaginatedResponse(BaseModel):
    """Standard paginated list response envelope."""

    data: list[Any] = Field(default_factory=list)
    pagination: PaginationInfo = Field(default_factory=PaginationInfo)
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
