"""Deep health check endpoint unit tests.

TC-DH01 ~ TC-DH06: Health endpoint with ?deep=true parameter.
All tests run without Neo4j — uses mocked session.
"""

from __future__ import annotations

import shutil

import pytest

from kg.api.routes.health import (
    DeepHealthResponse,
    HealthComponent,
    _check_disk,
    _get_system_info,
)


# =============================================================================
# TC-DH01: HealthComponent model
# =============================================================================


@pytest.mark.unit
class TestHealthComponent:
    """HealthComponent model tests."""

    def test_basic_creation(self) -> None:
        """TC-DH01-a: HealthComponent can be created with minimal fields."""
        c = HealthComponent(name="test", status="ok")
        assert c.name == "test"
        assert c.status == "ok"
        assert c.latency_ms is None
        assert c.details is None

    def test_with_details(self) -> None:
        """TC-DH01-b: HealthComponent supports details dict."""
        c = HealthComponent(
            name="neo4j",
            status="ok",
            latency_ms=5.2,
            details={"version": "5.x"},
        )
        assert c.latency_ms == 5.2
        assert c.details["version"] == "5.x"


# =============================================================================
# TC-DH02: DeepHealthResponse model
# =============================================================================


@pytest.mark.unit
class TestDeepHealthResponse:
    """DeepHealthResponse model tests."""

    def test_creation_with_components(self) -> None:
        """TC-DH02-a: DeepHealthResponse holds component list."""
        resp = DeepHealthResponse(
            status="ok",
            version="0.1.0",
            neo4j_connected=True,
            components=[
                HealthComponent(name="neo4j", status="ok"),
                HealthComponent(name="disk", status="ok"),
            ],
        )
        assert len(resp.components) == 2
        assert resp.status == "ok"

    def test_with_system_info(self) -> None:
        """TC-DH02-b: DeepHealthResponse supports system info."""
        resp = DeepHealthResponse(
            status="ok",
            version="0.1.0",
            neo4j_connected=True,
            components=[],
            system={"python_version": "3.10.0"},
        )
        assert resp.system is not None
        assert "python_version" in resp.system


# =============================================================================
# TC-DH03: Disk check
# =============================================================================


@pytest.mark.unit
class TestDiskCheck:
    """Disk space check tests."""

    def test_disk_check_returns_component(self) -> None:
        """TC-DH03-a: _check_disk returns HealthComponent with disk info."""
        result = _check_disk()
        assert isinstance(result, HealthComponent)
        assert result.name == "disk"
        assert result.status in ("ok", "degraded", "down")
        assert result.details is not None
        assert "total_gb" in result.details
        assert "free_gb" in result.details
        assert "free_pct" in result.details


# =============================================================================
# TC-DH04: Memory check
# =============================================================================


@pytest.mark.unit
class TestMemoryCheck:
    """Memory check tests."""

    def test_memory_check_returns_component(self) -> None:
        """TC-DH04-a: _check_memory returns a HealthComponent."""
        from kg.api.routes.health import _check_memory

        result = _check_memory()
        assert isinstance(result, HealthComponent)
        assert result.name == "memory"
        assert result.status in ("ok", "degraded", "down")
        assert result.details is not None


# =============================================================================
# TC-DH05: System info
# =============================================================================


@pytest.mark.unit
class TestSystemInfo:
    """System information gathering tests."""

    def test_system_info_contains_keys(self) -> None:
        """TC-DH05-a: _get_system_info returns expected keys."""
        info = _get_system_info()
        assert "python_version" in info
        assert "platform" in info
        assert "hostname" in info

    def test_python_version_format(self) -> None:
        """TC-DH05-b: Python version is a valid version string."""
        info = _get_system_info()
        parts = info["python_version"].split(".")
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts[:2])
