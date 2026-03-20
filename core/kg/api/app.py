"""FastAPI application factory for the Maritime KG API.

Usage::

    from kg.api import create_app

    app = create_app()

Run with uvicorn::

    uvicorn kg.api.app:app --reload
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kg.api.middleware.auth import get_current_api_key
from kg.config import AppConfig, close_driver, get_config, set_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: setup and teardown Neo4j drivers."""
    # Enable JSON logging in production
    if os.environ.get("LOG_FORMAT") == "json":
        from kg.api.middleware.logging import setup_json_logging

        setup_json_logging(level=os.environ.get("LOG_LEVEL", "INFO"))

    logger.info("Maritime KG API starting up")
    yield
    logger.info("Maritime KG API shutting down -- closing Neo4j drivers")
    close_driver()
    from kg.config import close_async_driver

    await close_async_driver()


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Optional configuration override. When ``None``, the
            configuration is loaded from environment variables via
            :func:`~kg.config.get_config`.

    Returns:
        A fully configured :class:`FastAPI` instance.
    """
    if config is not None:
        set_config(config)
    else:
        # Ensure config singleton is initialized
        get_config()

    app = FastAPI(
        title="Maritime KG API",
        version="0.1.0",
        description="REST API for exploring the KRISO Maritime Knowledge Graph",
        lifespan=_lifespan,
    )

    # CORS -- configurable origins (default: localhost for development)
    cors_origins_str = os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:8080",
    )
    cors_origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "Accept"],
    )

    # Metrics middleware (before CORS so it wraps all requests)
    from kg.api.middleware.metrics import MetricsMiddleware, metrics_endpoint

    app.add_middleware(MetricsMiddleware)

    # Prometheus metrics endpoint (no auth required)
    app.add_route("/metrics", metrics_endpoint)

    # Import and include routers
    from kg.api.routes.etl import router as etl_router
    from kg.api.routes.graph import router as graph_router
    from kg.api.routes.health import router as health_router
    from kg.api.routes.lineage import router as lineage_router
    from kg.api.routes.query import router as query_router
    from kg.api.routes.schema import router as schema_router

    _auth_deps = [Depends(get_current_api_key)]

    app.include_router(health_router)
    app.include_router(graph_router, dependencies=_auth_deps)
    app.include_router(schema_router, dependencies=_auth_deps)
    app.include_router(query_router, dependencies=_auth_deps)
    app.include_router(lineage_router, dependencies=_auth_deps)
    app.include_router(etl_router, dependencies=_auth_deps)

    return app


# Module-level app instance for ``uvicorn kg.api.app:app``
app = create_app()
