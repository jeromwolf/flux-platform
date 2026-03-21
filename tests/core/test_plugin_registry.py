"""Unit tests for the domain plugin registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from kg.plugins.base import BaseDomainPlugin
from kg.plugins.registry import DomainPlugin, PluginInfo, PluginRegistry


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

class _TestPlugin(BaseDomainPlugin):
    """테스트용 더미 플러그인."""

    @classmethod
    def info(cls) -> PluginInfo:
        return PluginInfo(
            name="test-domain",
            display_name="Test Domain",
            version="1.0.0",
            description="A test plugin",
        )

    def get_ontology_loader(self) -> str:
        return "mock_loader"


class _AnotherPlugin(BaseDomainPlugin):
    """두 번째 테스트 플러그인."""

    @classmethod
    def info(cls) -> PluginInfo:
        return PluginInfo(name="another", display_name="Another Domain")


# ---------------------------------------------------------------------------
# PluginInfo tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPluginInfo:
    """Tests for PluginInfo frozen dataclass."""

    def test_creation(self):
        info = PluginInfo(name="test", display_name="Test")
        assert info.name == "test"
        assert info.display_name == "Test"
        assert info.version == "0.1.0"  # default
        assert info.description == ""  # default

    def test_frozen(self):
        info = PluginInfo(name="test", display_name="Test")
        with pytest.raises(AttributeError):
            info.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BaseDomainPlugin tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBaseDomainPlugin:
    """Tests for BaseDomainPlugin default implementations."""

    def test_info_not_implemented(self):
        """info()를 구현하지 않으면 NotImplementedError."""
        plugin = BaseDomainPlugin()
        with pytest.raises(NotImplementedError):
            plugin.info()

    def test_all_defaults_return_none(self):
        """모든 get_* 메서드 기본값은 None."""
        plugin = _TestPlugin()
        assert plugin.get_term_dictionary() is None
        assert plugin.get_crawler_classes() is None
        assert plugin.get_entity_groups() is None
        assert plugin.get_schema_dir() is None
        assert plugin.get_evaluation_dataset() is None
        assert plugin.get_api_routes() is None

    def test_overridden_method(self):
        """오버라이드된 메서드는 값을 반환."""
        plugin = _TestPlugin()
        assert plugin.get_ontology_loader() == "mock_loader"


# ---------------------------------------------------------------------------
# PluginRegistry tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPluginRegistry:
    """Tests for PluginRegistry."""

    def test_register_and_get(self):
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry.register(plugin)
        assert registry.get("test-domain") is plugin

    def test_get_unknown_returns_none(self):
        registry = PluginRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all_sorted(self):
        registry = PluginRegistry()
        registry.register(_TestPlugin())
        registry.register(_AnotherPlugin())
        plugins = registry.list_all()
        assert len(plugins) == 2
        # Sorted by name: "another" < "test-domain"
        assert plugins[0].info().name == "another"
        assert plugins[1].info().name == "test-domain"

    def test_names(self):
        registry = PluginRegistry()
        registry.register(_TestPlugin())
        registry.register(_AnotherPlugin())
        assert registry.names() == ["another", "test-domain"]

    def test_len(self):
        registry = PluginRegistry()
        assert len(registry) == 0
        registry.register(_TestPlugin())
        assert len(registry) == 1

    def test_contains(self):
        registry = PluginRegistry()
        registry.register(_TestPlugin())
        assert "test-domain" in registry
        assert "unknown" not in registry

    def test_repr(self):
        registry = PluginRegistry()
        registry.register(_TestPlugin())
        assert "test-domain" in repr(registry)

    def test_overwrite_warns(self):
        """같은 이름 재등록 시 경고."""
        import logging
        registry = PluginRegistry()
        registry.register(_TestPlugin())
        with pytest.warns(None):  # Just ensure no crash
            registry.register(_TestPlugin())
        # The second registration should succeed (overwrite)
        assert len(registry) == 1


# ---------------------------------------------------------------------------
# DomainPlugin Protocol tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDomainPluginProtocol:
    """Tests for DomainPlugin Protocol conformance."""

    def test_test_plugin_satisfies_protocol(self):
        """_TestPlugin은 DomainPlugin Protocol을 만족."""
        plugin = _TestPlugin()
        assert isinstance(plugin, DomainPlugin)

    def test_base_plugin_satisfies_protocol(self):
        """BaseDomainPlugin 서브클래스는 Protocol을 만족."""
        plugin = _AnotherPlugin()
        assert isinstance(plugin, DomainPlugin)

    def test_non_plugin_fails_protocol(self):
        """Protocol을 구현하지 않는 객체는 isinstance 실패."""
        assert not isinstance("not a plugin", DomainPlugin)
        assert not isinstance(42, DomainPlugin)


# ---------------------------------------------------------------------------
# Maritime plugin tests (if importable)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMaritimePlugin:
    """Tests for the Maritime domain plugin."""

    def test_maritime_plugin_info(self):
        """해사 플러그인 메타데이터."""
        try:
            from maritime.plugin import MaritimeDomainPlugin
        except ImportError:
            pytest.skip("maritime.plugin not importable")

        plugin = MaritimeDomainPlugin()
        info = plugin.info()
        assert info.name == "maritime"
        assert "해사" in info.display_name

    def test_maritime_plugin_satisfies_protocol(self):
        """해사 플러그인은 DomainPlugin 프로토콜을 만족."""
        try:
            from maritime.plugin import MaritimeDomainPlugin
        except ImportError:
            pytest.skip("maritime.plugin not importable")

        plugin = MaritimeDomainPlugin()
        assert isinstance(plugin, DomainPlugin)

    def test_maritime_schema_dir_exists(self):
        """해사 플러그인의 schema 디렉토리가 존재."""
        try:
            from maritime.plugin import MaritimeDomainPlugin
        except ImportError:
            pytest.skip("maritime.plugin not importable")

        plugin = MaritimeDomainPlugin()
        schema_dir = plugin.get_schema_dir()
        assert schema_dir is not None
        assert schema_dir.exists()

    def test_maritime_crawler_classes(self):
        """해사 플러그인이 4개 크롤러 클래스를 제공."""
        try:
            from maritime.plugin import MaritimeDomainPlugin
        except ImportError:
            pytest.skip("maritime.plugin not importable")

        plugin = MaritimeDomainPlugin()
        crawlers = plugin.get_crawler_classes()
        assert crawlers is not None
        assert len(crawlers) == 4

    def test_register_plugin_function(self):
        """register_plugin() 함수가 레지스트리에 등록."""
        try:
            from maritime.plugin import register_plugin
        except ImportError:
            pytest.skip("maritime.plugin not importable")

        registry = PluginRegistry()
        register_plugin(registry)
        assert "maritime" in registry
