"""Health check endpoint."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from kg.api.deps import get_app_config, get_async_neo4j_session
from kg.api.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health(
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    config: Any = Depends(get_app_config),  # noqa: B008
) -> HealthResponse:
    """Check API and Neo4j connectivity.

    Returns ``"ok"`` when Neo4j is reachable, ``"degraded"`` otherwise.
    """
    neo4j_ok = False
    try:
        result = await session.run("RETURN 1 AS n")
        record = await result.single()
        neo4j_ok = record is not None and record["n"] == 1
    except Exception:
        logger.warning("Neo4j health check failed", exc_info=True)

    return HealthResponse(
        status="ok" if neo4j_ok else "degraded",
        version="0.1.0",
        neo4j_connected=neo4j_ok,
    )
