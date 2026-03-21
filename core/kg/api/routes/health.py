"""Health check endpoint with optional deep diagnostics.

Standard health check returns basic connectivity status. With ``?deep=true``,
returns component-level diagnostics including Neo4j, disk, and memory checks.
"""

from __future__ import annotations

import logging
import platform
import shutil
import time
from typing import Any, Optional, Union

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from kg.api.deps import get_app_config, get_async_neo4j_session
from kg.api.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthComponent(BaseModel):
    """Individual component health status."""

    name: str
    status: str  # "ok", "degraded", "down"
    latency_ms: Optional[float] = None
    details: Optional[dict[str, Any]] = None


class DeepHealthResponse(BaseModel):
    """Extended health response with component-level diagnostics."""

    status: str
    version: str
    neo4j_connected: bool
    components: list[HealthComponent]
    system: Optional[dict[str, Any]] = None


async def _check_neo4j(session: Any) -> HealthComponent:
    """Check Neo4j connectivity and measure latency."""
    start = time.monotonic()
    try:
        result = await session.run("RETURN 1 AS n")
        record = await result.single()
        latency = (time.monotonic() - start) * 1000
        ok = record is not None and record["n"] == 1
        return HealthComponent(
            name="neo4j",
            status="ok" if ok else "degraded",
            latency_ms=round(latency, 2),
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        logger.warning("Neo4j health check failed", exc_info=True)
        return HealthComponent(
            name="neo4j",
            status="down",
            latency_ms=round(latency, 2),
            details={"error": str(exc)},
        )


def _check_disk() -> HealthComponent:
    """Check available disk space."""
    try:
        usage = shutil.disk_usage("/")
        free_pct = (usage.free / usage.total) * 100
        status = "ok" if free_pct > 10 else ("degraded" if free_pct > 5 else "down")
        return HealthComponent(
            name="disk",
            status=status,
            details={
                "total_gb": round(usage.total / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "free_pct": round(free_pct, 1),
            },
        )
    except Exception as exc:
        return HealthComponent(
            name="disk",
            status="degraded",
            details={"error": str(exc)},
        )


def _check_memory() -> HealthComponent:
    """Check available system memory."""
    if not _HAS_PSUTIL:
        return HealthComponent(
            name="memory",
            status="ok",
            details={"note": "psutil not installed, memory check skipped"},
        )
    try:
        mem = psutil.virtual_memory()
        status = "ok" if mem.percent < 85 else ("degraded" if mem.percent < 95 else "down")
        return HealthComponent(
            name="memory",
            status=status,
            details={
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_pct": round(mem.percent, 1),
            },
        )
    except Exception as exc:
        return HealthComponent(
            name="memory",
            status="degraded",
            details={"error": str(exc)},
        )


def _get_system_info() -> dict[str, Any]:
    """Gather basic system information."""
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "hostname": platform.node(),
    }


@router.get("/health", response_model=Union[HealthResponse, DeepHealthResponse])
async def health(
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    config: Any = Depends(get_app_config),  # noqa: B008
    deep: bool = Query(False, description="Enable deep health diagnostics"),
) -> Union[HealthResponse, DeepHealthResponse]:
    """Check API and Neo4j connectivity.

    Returns ``"ok"`` when Neo4j is reachable, ``"degraded"`` otherwise.

    With ``?deep=true``, returns component-level diagnostics including
    Neo4j latency, disk space, and memory usage.
    """
    neo4j_component = await _check_neo4j(session)
    neo4j_ok = neo4j_component.status == "ok"

    if not deep:
        return HealthResponse(
            status="ok" if neo4j_ok else "degraded",
            version="0.1.0",
            neo4j_connected=neo4j_ok,
        )

    # Deep health check
    components = [neo4j_component, _check_disk(), _check_memory()]

    # Overall status: worst component status wins
    statuses = [c.status for c in components]
    if "down" in statuses:
        overall = "down"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "ok"

    return DeepHealthResponse(
        status=overall,
        version="0.1.0",
        neo4j_connected=neo4j_ok,
        components=components,
        system=_get_system_info(),
    )
