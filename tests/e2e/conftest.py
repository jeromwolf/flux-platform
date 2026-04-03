"""Shared E2E test fixtures.

Provides the ``harness`` fixture that creates a mock-backed FastAPI app
with MockNeo4jSession + httpx.AsyncClient via ASGITransport.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest_asyncio
import httpx
from httpx import ASGITransport

from tests.helpers.mock_neo4j import MockNeo4jSession, MockNeo4jResult


@pytest_asyncio.fixture
async def harness():
    """Async HTTPX client backed by MockNeo4jSession.

    Yields:
        (client, session, app) — 3-tuple where ``client`` is an
        ``httpx.AsyncClient``, ``session`` is the ``MockNeo4jSession``,
        and ``app`` is the FastAPI application (for ``app.state`` manipulation).
    """
    from kg.config import AppConfig, Neo4jConfig, reset
    from kg.api.app import create_app
    from kg.api.deps import get_async_neo4j_session

    config = AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

    with patch("kg.api.app.get_config", return_value=config), \
         patch("kg.api.app.set_config"):
        app = create_app(config=config)

    session = MockNeo4jSession()

    async def _override():
        yield session

    app.dependency_overrides[get_async_neo4j_session] = _override

    # ASGITransport does NOT trigger ASGI lifespan events, so we must
    # manually initialise app.state attributes that the lifespan would set.
    from kg.db.memory_workflow_repo import InMemoryWorkflowRepository
    from kg.db.memory_document_repo import InMemoryDocumentRepository

    app.state.workflow_repo = InMemoryWorkflowRepository()
    app.state.document_repo = InMemoryDocumentRepository()
    app.state.tool_registry = None
    app.state.rag_engine = None
    app.state.document_pipeline = None

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session, app

    reset()


def _reset(session: MockNeo4jSession, side_effects: list[Any]) -> None:
    """Replace session side-effects and reset the call index."""
    session._side_effects = side_effects
    session._call_index = 0
