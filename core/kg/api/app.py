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

from kg.api.middleware.auth import get_current_api_key, get_current_user, require_role
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

    # PostgreSQL repositories (graceful fallback to in-memory)
    try:
        from kg.db.connection import get_pg_pool
        pool = await get_pg_pool()
        if pool is not None:
            from kg.db.pg_workflow_repo import PgWorkflowRepository
            from kg.db.pg_document_repo import PgDocumentRepository
            app.state.workflow_repo = PgWorkflowRepository(pool)
            app.state.document_repo = PgDocumentRepository(pool)
            logger.info("Using PostgreSQL repositories")
        else:
            raise ImportError("No pool")
    except Exception:
        from kg.db.memory_workflow_repo import InMemoryWorkflowRepository
        from kg.db.memory_document_repo import InMemoryDocumentRepository
        app.state.workflow_repo = InMemoryWorkflowRepository()
        app.state.document_repo = InMemoryDocumentRepository()
        logger.warning("Using in-memory repositories — data will NOT persist across restarts. Configure PostgreSQL for production.", exc_info=True)

    # Agent tool registry (graceful fallback)
    try:
        from agent.tools.builtins import create_builtin_registry
        app.state.tool_registry = create_builtin_registry()
        logger.info("Agent tool registry initialized (%d tools)", len(app.state.tool_registry.list_tools()))
    except Exception:
        app.state.tool_registry = None
        logger.warning("Agent tool registry unavailable — agent chat/tool endpoints will return 503", exc_info=True)

    # RAG engine (graceful fallback)
    try:
        from rag.engines.models import RAGConfig
        from rag.engines.orchestrator import HybridRAGEngine
        app.state.rag_engine = HybridRAGEngine(config=RAGConfig())
        logger.info("RAG engine initialized")
    except Exception:
        app.state.rag_engine = None
        logger.warning("RAG engine unavailable — document search endpoints will return empty results", exc_info=True)

    # Document pipeline (graceful fallback)
    try:
        from rag.documents.pipeline import DocumentPipeline
        app.state.document_pipeline = DocumentPipeline()
        logger.info("Document pipeline initialized")
    except Exception:
        app.state.document_pipeline = None
        logger.warning("Document pipeline unavailable — file upload/parsing will not work", exc_info=True)

    yield
    logger.info("Maritime KG API shutting down -- closing Neo4j drivers")
    close_driver()
    from kg.config import close_async_driver

    await close_async_driver()

    try:
        from kg.db.connection import close_pg_pool
        await close_pg_pool()
    except Exception:
        logger.debug("PostgreSQL pool close failed", exc_info=True)

    try:
        from kg.db.redis_client import close_redis_client

        close_redis_client()
    except Exception:
        logger.debug("Redis client close failed", exc_info=True)


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
        cfg = config
    else:
        # Ensure config singleton is initialized
        cfg = get_config()

    # Disable interactive docs in production (security: prevent schema exposure)
    _is_production = cfg.env == "production"
    docs_url = None if _is_production else "/docs"
    openapi_url = None if _is_production else "/openapi.json"

    app = FastAPI(
        title="Maritime KG API",
        version="0.1.0",
        description="REST API for exploring the KRISO Maritime Knowledge Graph",
        lifespan=_lifespan,
        docs_url=docs_url,
        openapi_url=openapi_url,
        redoc_url=None,
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

    # Rate limiting (production only) — prefer Redis backend when available
    cfg = config if config is not None else get_config()
    if cfg.env != "development":
        from kg.api.middleware.rate_limit import RateLimitMiddleware, RedisRateLimitBackend

        redis_backend = None
        try:
            from kg.db.redis_client import get_redis_client

            client = get_redis_client()
            if client is not None:
                redis_backend = RedisRateLimitBackend(redis_client=client)
                logger.info("Rate limiting: Redis backend")
        except Exception:
            logger.debug("Redis rate-limit backend unavailable", exc_info=True)

        app.add_middleware(RateLimitMiddleware, backend=redis_backend)

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
    from kg.api.routes.mcp_endpoint import router as mcp_router
    from kg.api.routes.nodes import router as nodes_router
    from kg.api.routes.query import router as query_router
    from kg.api.routes.rag import router as rag_router
    from kg.api.routes.relationships import router as relationships_router
    from kg.api.routes.schema import router as schema_router
    from kg.api.routes.workflows import router as workflows_router

    # --- RBAC dependency tiers ---
    # Base: authenticated user (viewer+)
    _auth_deps = [Depends(get_current_user)]
    # Writer: data modification (researcher, developer, admin)
    _write_deps = [Depends(require_role("researcher", "developer", "admin"))]
    # Admin: dangerous operations (admin only)
    _admin_deps = [Depends(require_role("admin"))]

    # No auth required
    app.include_router(health_router, prefix="/api/v1")

    # Read-only routes (viewer+)
    app.include_router(graph_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(schema_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(query_router, prefix="/api/v1", dependencies=_auth_deps)
    app.include_router(lineage_router, prefix="/api/v1", dependencies=_auth_deps)

    # Write routes (researcher/developer/admin)
    app.include_router(nodes_router, prefix="/api/v1", dependencies=_write_deps)
    app.include_router(relationships_router, prefix="/api/v1", dependencies=_write_deps)
    app.include_router(embeddings_router, prefix="/api/v1", dependencies=_write_deps)
    app.include_router(rag_router, prefix="/api/v1", dependencies=_write_deps)
    app.include_router(agent_router, prefix="/api/v1", dependencies=_write_deps)
    app.include_router(documents_router, prefix="/api/v1", dependencies=_write_deps)
    app.include_router(workflows_router, prefix="/api/v1", dependencies=_write_deps)
    app.include_router(algorithms_router, prefix="/api/v1", dependencies=_write_deps)

    # Admin routes (admin only)
    app.include_router(cypher_router, prefix="/api/v1", dependencies=_admin_deps)
    app.include_router(etl_router, prefix="/api/v1", dependencies=_admin_deps)
    app.include_router(mcp_router, prefix="/api/v1", dependencies=_admin_deps)

    return app


# Module-level app instance for ``uvicorn kg.api.app:app``
app = create_app()
