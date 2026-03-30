"""FastAPI dependency injection functions.

Provides ``Depends``-compatible callables for Neo4j driver, session,
and application configuration.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

from starlette.requests import Request

from kg.config import AppConfig, get_config, get_driver
from kg.project import KGProjectContext, PROJECT_HEADER


def get_neo4j_driver() -> Any:
    """Return the shared Neo4j driver singleton.

    Returns:
        The Neo4j driver instance.
    """
    return get_driver()


def get_neo4j_session() -> Generator[Any, None, None]:
    """Yield a Neo4j session scoped to a single request.

    The session is automatically closed when the request finishes.

    Yields:
        A Neo4j session bound to the configured database.
    """
    driver = get_driver()
    cfg = get_config()
    session = driver.session(database=cfg.neo4j.database)
    try:
        yield session
    finally:
        session.close()


async def get_async_neo4j_session() -> AsyncGenerator[Any, None]:
    """Yield an async Neo4j session scoped to a single request.

    The session is automatically closed when the request finishes.

    Yields:
        An async Neo4j session bound to the configured database.
    """
    from kg.config import get_async_driver

    driver = get_async_driver()
    cfg = get_config()
    session = driver.session(database=cfg.neo4j.database)
    try:
        yield session
    finally:
        await session.close()


def get_app_config() -> AppConfig:
    """Return the current application configuration.

    Returns:
        The active :class:`~kg.config.AppConfig` singleton.
    """
    return get_config()


def get_workflow_repo(request: Request):
    """Get the workflow repository from app state."""
    return request.app.state.workflow_repo


def get_document_repo(request: Request):
    """Get the document repository from app state."""
    return request.app.state.document_repo


def get_tool_registry(request: Request):
    """Get the shared tool registry from app state."""
    return getattr(request.app.state, "tool_registry", None)


def get_rag_engine(request: Request):
    """Get the shared RAG engine from app state."""
    return getattr(request.app.state, "rag_engine", None)


def get_document_pipeline(request: Request):
    """Get the shared document pipeline from app state."""
    return getattr(request.app.state, "document_pipeline", None)


def get_project_context(request: Request) -> KGProjectContext:
    """Extract KG project context from the X-KG-Project request header.

    Returns KGProjectContext with project="default" when header is absent.
    Raises HTTPException(400) for invalid project names.
    """
    header_value = request.headers.get(PROJECT_HEADER)
    try:
        return KGProjectContext.from_header(header_value)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc
