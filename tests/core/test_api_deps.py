"""Unit tests for core/kg/api/deps.py.

Tests all dependency injection callables without touching real Neo4j.
All tests are ``@pytest.mark.unit``.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kg.config import AppConfig, Neo4jConfig, reset


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset config/driver singletons around each test."""
    reset()
    yield
    reset()


@pytest.fixture
def mock_driver() -> MagicMock:
    """Return a MagicMock that acts as a Neo4j sync driver."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value = session
    return driver


@pytest.fixture
def mock_async_driver() -> MagicMock:
    """Return a MagicMock that acts as a Neo4j async driver."""
    driver = MagicMock()
    session = AsyncMock()
    driver.session.return_value = session
    return driver


@pytest.fixture
def test_config() -> AppConfig:
    """Minimal AppConfig that avoids real Neo4j connection."""
    return AppConfig(neo4j=Neo4jConfig(uri="bolt://mock:7687", database="testdb"))


# ---------------------------------------------------------------------------
# get_neo4j_driver
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetNeo4jDriver:
    """Tests for get_neo4j_driver()."""

    def test_returns_driver_singleton(self, mock_driver: MagicMock, test_config: AppConfig):
        """get_neo4j_driver() should return whatever get_driver() returns."""
        from kg.api.deps import get_neo4j_driver

        with patch("kg.api.deps.get_driver", return_value=mock_driver) as mock_get:
            result = get_neo4j_driver()

        mock_get.assert_called_once()
        assert result is mock_driver

    def test_returns_same_object_on_repeated_calls(self, mock_driver: MagicMock):
        """Repeated calls return the same driver object (singleton)."""
        from kg.api.deps import get_neo4j_driver

        with patch("kg.api.deps.get_driver", return_value=mock_driver):
            r1 = get_neo4j_driver()
            r2 = get_neo4j_driver()

        assert r1 is r2


# ---------------------------------------------------------------------------
# get_neo4j_session
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetNeo4jSession:
    """Tests for get_neo4j_session() generator."""

    def test_yields_session(self, mock_driver: MagicMock, test_config: AppConfig):
        """get_neo4j_session should yield the session returned by driver.session()."""
        from kg.api.deps import get_neo4j_session

        with patch("kg.api.deps.get_driver", return_value=mock_driver), \
             patch("kg.api.deps.get_config", return_value=test_config):
            gen = get_neo4j_session()
            session = next(gen)

        assert session is mock_driver.session.return_value

    def test_session_opened_with_database(self, mock_driver: MagicMock, test_config: AppConfig):
        """driver.session() should be called with the configured database name."""
        from kg.api.deps import get_neo4j_session

        with patch("kg.api.deps.get_driver", return_value=mock_driver), \
             patch("kg.api.deps.get_config", return_value=test_config):
            gen = get_neo4j_session()
            next(gen)
            try:
                next(gen)
            except StopIteration:
                pass

        mock_driver.session.assert_called_once_with(database="testdb")

    def test_session_closed_after_yield(self, mock_driver: MagicMock, test_config: AppConfig):
        """session.close() must be called in the finally block after use."""
        from kg.api.deps import get_neo4j_session

        with patch("kg.api.deps.get_driver", return_value=mock_driver), \
             patch("kg.api.deps.get_config", return_value=test_config):
            gen = get_neo4j_session()
            session = next(gen)
            try:
                next(gen)
            except StopIteration:
                pass

        session.close.assert_called_once()

    def test_session_closed_even_on_exception(self, mock_driver: MagicMock, test_config: AppConfig):
        """session.close() must be called even when consumer raises."""
        from kg.api.deps import get_neo4j_session

        with patch("kg.api.deps.get_driver", return_value=mock_driver), \
             patch("kg.api.deps.get_config", return_value=test_config):
            gen = get_neo4j_session()
            session = next(gen)
            try:
                gen.throw(RuntimeError("boom"))
            except RuntimeError:
                pass

        session.close.assert_called_once()


# ---------------------------------------------------------------------------
# get_async_neo4j_session
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetAsyncNeo4jSession:
    """Tests for get_async_neo4j_session() async generator."""

    @pytest.mark.asyncio
    async def test_yields_async_session(self, mock_async_driver: MagicMock, test_config: AppConfig):
        """get_async_neo4j_session should yield the session returned by driver.session()."""
        from kg.api.deps import get_async_neo4j_session

        async_session = AsyncMock()
        mock_async_driver.session.return_value = async_session

        # Patch get_async_driver where it is *imported inside the function*
        with patch("kg.api.deps.get_config", return_value=test_config), \
             patch("kg.config.get_async_driver", return_value=mock_async_driver):
            gen = get_async_neo4j_session()
            result = None
            async for item in gen:
                result = item
                break

        assert result is async_session

    @pytest.mark.asyncio
    async def test_async_session_closed_after_yield(self, mock_async_driver: MagicMock, test_config: AppConfig):
        """async session.close() must be awaited in the finally block."""
        from kg.api.deps import get_async_neo4j_session

        async_session = AsyncMock()
        mock_async_driver.session.return_value = async_session

        with patch("kg.api.deps.get_config", return_value=test_config), \
             patch("kg.config.get_async_driver", return_value=mock_async_driver):
            gen = get_async_neo4j_session()
            async for _ in gen:
                break
            # Explicitly close generator to trigger finally block
            await gen.aclose()

        async_session.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_app_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetAppConfig:
    """Tests for get_app_config()."""

    def test_returns_app_config_instance(self, test_config: AppConfig):
        """get_app_config() should return whatever get_config() returns."""
        from kg.api.deps import get_app_config

        with patch("kg.api.deps.get_config", return_value=test_config):
            result = get_app_config()

        assert result is test_config

    def test_returns_app_config_type(self, test_config: AppConfig):
        """Return type should be AppConfig."""
        from kg.api.deps import get_app_config

        with patch("kg.api.deps.get_config", return_value=test_config):
            result = get_app_config()

        assert isinstance(result, AppConfig)

    def test_config_values_preserved(self, test_config: AppConfig):
        """The config returned should have the same values as the injected one."""
        from kg.api.deps import get_app_config

        with patch("kg.api.deps.get_config", return_value=test_config):
            result = get_app_config()

        assert result.neo4j.database == "testdb"
        assert result.neo4j.uri == "bolt://mock:7687"


# ---------------------------------------------------------------------------
# Request-state dependencies
# ---------------------------------------------------------------------------


def _make_mock_request(state_attrs: dict[str, Any]) -> MagicMock:
    """Build a mock Starlette Request with app.state populated."""
    request = MagicMock()
    state = MagicMock(spec=[])  # blank spec so getattr falls through to mock
    for k, v in state_attrs.items():
        setattr(state, k, v)
    request.app.state = state
    return request


@pytest.mark.unit
class TestGetWorkflowRepo:
    """Tests for get_workflow_repo()."""

    def test_returns_workflow_repo_from_state(self):
        """Should read workflow_repo directly from app.state."""
        from kg.api.deps import get_workflow_repo

        repo = MagicMock()
        request = _make_mock_request({"workflow_repo": repo})
        assert get_workflow_repo(request) is repo

    def test_returns_none_if_state_is_none(self):
        """If app.state.workflow_repo is None, return None."""
        from kg.api.deps import get_workflow_repo

        request = _make_mock_request({"workflow_repo": None})
        assert get_workflow_repo(request) is None


@pytest.mark.unit
class TestGetDocumentRepo:
    """Tests for get_document_repo()."""

    def test_returns_document_repo_from_state(self):
        """Should read document_repo directly from app.state."""
        from kg.api.deps import get_document_repo

        repo = MagicMock()
        request = _make_mock_request({"document_repo": repo})
        assert get_document_repo(request) is repo


@pytest.mark.unit
class TestGetToolRegistry:
    """Tests for get_tool_registry()."""

    def test_returns_tool_registry_when_present(self):
        """Should return the tool_registry attribute from app.state."""
        from kg.api.deps import get_tool_registry

        registry = MagicMock()
        request = _make_mock_request({"tool_registry": registry})
        assert get_tool_registry(request) is registry

    def test_returns_none_when_attribute_missing(self):
        """Should return None when app.state has no tool_registry attribute."""
        from kg.api.deps import get_tool_registry

        # state has no tool_registry attribute at all
        request = MagicMock()
        # Use a simple object whose __getattr__ raises AttributeError
        request.app.state = object()
        assert get_tool_registry(request) is None


@pytest.mark.unit
class TestGetRagEngine:
    """Tests for get_rag_engine()."""

    def test_returns_rag_engine_when_present(self):
        """Should return the rag_engine attribute from app.state."""
        from kg.api.deps import get_rag_engine

        engine = MagicMock()
        request = _make_mock_request({"rag_engine": engine})
        assert get_rag_engine(request) is engine

    def test_returns_none_when_attribute_missing(self):
        """Should return None when app.state has no rag_engine attribute."""
        from kg.api.deps import get_rag_engine

        request = MagicMock()
        request.app.state = object()
        assert get_rag_engine(request) is None


@pytest.mark.unit
class TestGetDocumentPipeline:
    """Tests for get_document_pipeline()."""

    def test_returns_pipeline_when_present(self):
        """Should return the document_pipeline attribute from app.state."""
        from kg.api.deps import get_document_pipeline

        pipeline = MagicMock()
        request = _make_mock_request({"document_pipeline": pipeline})
        assert get_document_pipeline(request) is pipeline

    def test_returns_none_when_attribute_missing(self):
        """Should return None when app.state has no document_pipeline attribute."""
        from kg.api.deps import get_document_pipeline

        request = MagicMock()
        request.app.state = object()
        assert get_document_pipeline(request) is None
