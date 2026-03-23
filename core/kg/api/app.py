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
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "Accept", "X-Request-ID", "Idempotency-Key"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-Request-ID", "traceparent"],
    )

    # Metrics middleware (before CORS so it wraps all requests)
    from kg.api.middleware.metrics import MetricsMiddleware, metrics_endpoint

    app.add_middleware(MetricsMiddleware)

    # Prometheus metrics endpoint (no auth required)
    app.add_route("/metrics", metrics_endpoint)

    # Security headers (OWASP recommended)
    from kg.api.middleware.security_headers import SecurityHeadersMiddleware

    app.add_middleware(SecurityHeadersMiddleware)

    # Distributed tracing (W3C Traceparent)
    from kg.api.middleware.tracing import TracingMiddleware

    app.add_middleware(TracingMiddleware)

    # Request ID middleware
    from kg.api.middleware.request_id import RequestIdMiddleware

    app.add_middleware(RequestIdMiddleware)

    # Audit logging for state-changing operations
    from kg.api.middleware.audit import AuditMiddleware

    app.add_middleware(AuditMiddleware)

    # Error handlers (RFC 7807 Problem Details)
    from kg.api.middleware.error_handler import register_error_handlers

    register_error_handlers(app)

    # Rate limiting (production only)
    cfg = config if config is not None else get_config()
    if cfg.env != "development":
        from kg.api.middleware.rate_limit import RateLimitMiddleware

        app.add_middleware(RateLimitMiddleware)

    # Import and include routers
    from kg.api.routes.agent import router as agent_router
    from kg.api.routes.algorithms import router as algorithms_router
    from kg.api.routes.cypher import router as cypher_router
    from kg.api.routes.documents import router as documents_router
    from kg.api.routes.embeddings import router as embeddings_router
    from kg.api.routes.etl import router as etl_router
    from kg.api.routes.graph import router as graph_router
    from kg.api.routes.health import router as health_router
    from kg.api.routes.lineage import router as lineage_router
    from kg.api.routes.nodes import router as nodes_router
    from kg.api.routes.query import router as query_router
    from kg.api.routes.rag import router as rag_router
    from kg.api.routes.relationships import router as relationships_router
    from kg.api.routes.schema import router as schema_router
    from kg.api.routes.workflows import router as workflows_router

    _auth_deps = [Depends(get_current_api_key)]

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(graph_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(schema_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(query_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(lineage_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(etl_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(nodes_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(relationships_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(cypher_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(embeddings_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(algorithms_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(rag_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(agent_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(documents_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(workflows_router, prefix="/api/v1", dependencies=_auth_deps)

    return app


# Module-level app instance for ``uvicorn kg.api.app:app``
app = create_app()
