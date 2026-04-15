"""Unit tests for /docs and /openapi.json endpoint protection.

Verifies that interactive API documentation is disabled in production
and enabled in development / testing environments.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kg.api.app import create_app
from kg.config import AppConfig, Neo4jConfig, reset


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset config singleton before/after each test."""
    reset()
    yield
    reset()


@pytest.fixture
def prod_config() -> AppConfig:
    return AppConfig(
        env="production",
        neo4j=Neo4jConfig(uri="bolt://mock:7687"),
    )


@pytest.fixture
def dev_config() -> AppConfig:
    return AppConfig(
        env="development",
        neo4j=Neo4jConfig(uri="bolt://mock:7687"),
    )


@pytest.fixture
def staging_config() -> AppConfig:
    return AppConfig(
        env="staging",
        neo4j=Neo4jConfig(uri="bolt://mock:7687"),
    )


@pytest.fixture
def testing_config() -> AppConfig:
    return AppConfig(
        env="testing",
        neo4j=Neo4jConfig(uri="bolt://mock:7687"),
    )


# ---------------------------------------------------------------------------
# Core API docs protection tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_docs_disabled_in_production(prod_config: AppConfig) -> None:
    """GET /docs returns 404 in production mode."""
    app = create_app(prod_config)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/docs")
    assert resp.status_code == 404


@pytest.mark.unit
def test_openapi_json_disabled_in_production(prod_config: AppConfig) -> None:
    """GET /openapi.json returns 404 in production mode."""
    app = create_app(prod_config)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/openapi.json")
    assert resp.status_code == 404


@pytest.mark.unit
def test_redoc_disabled_in_production(prod_config: AppConfig) -> None:
    """GET /redoc returns 404 in production mode (redoc is always disabled)."""
    app = create_app(prod_config)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/redoc")
    assert resp.status_code == 404


@pytest.mark.unit
def test_docs_enabled_in_development(dev_config: AppConfig) -> None:
    """GET /docs returns 200 in development mode."""
    app = create_app(dev_config)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.unit
def test_openapi_json_enabled_in_development(dev_config: AppConfig) -> None:
    """GET /openapi.json returns 200 in development mode."""
    app = create_app(dev_config)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200


@pytest.mark.unit
def test_docs_enabled_in_staging(staging_config: AppConfig) -> None:
    """GET /docs returns 200 in staging mode (only production disables docs)."""
    app = create_app(staging_config)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.unit
def test_openapi_json_enabled_in_staging(staging_config: AppConfig) -> None:
    """GET /openapi.json returns 200 in staging mode (only production disables docs)."""
    app = create_app(staging_config)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200


@pytest.mark.unit
def test_docs_enabled_in_testing(testing_config: AppConfig) -> None:
    """GET /docs returns 200 in testing mode."""
    app = create_app(testing_config)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.unit
def test_openapi_json_enabled_in_testing(testing_config: AppConfig) -> None:
    """GET /openapi.json returns 200 in testing mode."""
    app = create_app(testing_config)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Gateway docs protection tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_gateway_docs_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gateway /docs returns 404 when ENV=production."""
    monkeypatch.setenv("ENV", "production")
    from gateway.server import create_server
    from gateway.config import GatewayConfig

    server = create_server(GatewayConfig())
    client = TestClient(server, raise_server_exceptions=False)
    resp = client.get("/docs")
    assert resp.status_code == 404


@pytest.mark.unit
def test_gateway_openapi_json_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gateway /openapi.json returns 404 when ENV=production."""
    monkeypatch.setenv("ENV", "production")
    from gateway.server import create_server
    from gateway.config import GatewayConfig

    server = create_server(GatewayConfig())
    client = TestClient(server, raise_server_exceptions=False)
    resp = client.get("/openapi.json")
    assert resp.status_code == 404


@pytest.mark.unit
def test_gateway_docs_enabled_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gateway /docs returns 200 when ENV=development."""
    monkeypatch.setenv("ENV", "development")
    from gateway.server import create_server
    from gateway.config import GatewayConfig

    server = create_server(GatewayConfig())
    client = TestClient(server, raise_server_exceptions=False)
    resp = client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.unit
def test_gateway_openapi_json_enabled_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gateway /openapi.json returns 200 when ENV=development."""
    monkeypatch.setenv("ENV", "development")
    from gateway.server import create_server
    from gateway.config import GatewayConfig

    server = create_server(GatewayConfig())
    client = TestClient(server, raise_server_exceptions=False)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
