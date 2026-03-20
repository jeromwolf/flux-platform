"""Unit tests for crawler registry system.

Tests for CrawlerInfo dataclass, BaseCrawler.info() default implementation,
CrawlerRegistry register/get/list_all/names, discover_builtins(),
get_registry() singleton, and each built-in crawler's info() metadata.

Total: 17 tests
"""

from __future__ import annotations

import pytest

from kg.crawlers.base import BaseCrawler, CrawlerInfo
from kg.crawlers.registry import CrawlerRegistry, discover_builtins, get_registry

# ==============================================================================
# CrawlerInfo Tests
# ==============================================================================


@pytest.mark.unit
class TestCrawlerInfo:
    """Tests for CrawlerInfo dataclass."""

    def test_creation_with_all_fields(self):
        """CrawlerInfo can be created with all fields."""
        info = CrawlerInfo(
            name="test-crawler",
            display_name="Test Crawler",
            description="A test crawler",
            version="2.0.0",
        )
        assert info.name == "test-crawler"
        assert info.display_name == "Test Crawler"
        assert info.description == "A test crawler"
        assert info.version == "2.0.0"

    def test_default_version(self):
        """CrawlerInfo defaults version to '1.0.0'."""
        info = CrawlerInfo(
            name="test",
            display_name="Test",
            description="desc",
        )
        assert info.version == "1.0.0"

    def test_frozen_immutability(self):
        """CrawlerInfo is frozen (immutable)."""
        info = CrawlerInfo(name="test", display_name="Test", description="desc")
        with pytest.raises(AttributeError):
            info.name = "changed"  # type: ignore[misc]


# ==============================================================================
# BaseCrawler.info() Default Implementation Tests
# ==============================================================================


@pytest.mark.unit
class TestBaseCrawlerInfoDefault:
    """Tests for BaseCrawler.info() default implementation."""

    def test_default_info_derives_name_from_class(self):
        """Default info() derives kebab-case name from class name."""

        # Test with a fresh subclass (built-in crawlers override info())
        class SampleTestCrawler(BaseCrawler):
            """Sample test crawler for unit testing."""

            def save_to_neo4j(self, records):
                return 0

        info = SampleTestCrawler.info()
        # SampleTestCrawler -> "sample-test-crawler"
        assert info.name == "sample-test-crawler"
        assert info.display_name == "SampleTestCrawler"

    def test_default_info_uses_docstring_first_line(self):
        """Default info() uses first line of docstring as description."""

        class DocTestCrawler(BaseCrawler):
            """First line of docstring.

            More details here.
            """

            def save_to_neo4j(self, records):
                return 0

        info = DocTestCrawler.info()
        assert info.description == "First line of docstring."


# ==============================================================================
# CrawlerRegistry Tests
# ==============================================================================


@pytest.mark.unit
class TestCrawlerRegistry:
    """Tests for CrawlerRegistry class."""

    def test_register_and_get(self):
        """register() stores and get() retrieves a crawler class."""
        from kg.crawlers.kma_marine import KMAMarineCrawler

        registry = CrawlerRegistry()
        registry.register(KMAMarineCrawler)
        assert registry.get("kma-marine") is KMAMarineCrawler

    def test_get_returns_none_for_unknown(self):
        """get() returns None for unregistered name."""
        registry = CrawlerRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all_returns_sorted_classes(self):
        """list_all() returns crawler classes sorted by name."""
        from kg.crawlers.kma_marine import KMAMarineCrawler
        from kg.crawlers.kriso_papers import KRISOPapersCrawler

        registry = CrawlerRegistry()
        registry.register(KRISOPapersCrawler)
        registry.register(KMAMarineCrawler)

        classes = registry.list_all()
        assert len(classes) == 2
        # "kma-marine" < "kriso-papers" alphabetically
        assert classes[0] is KMAMarineCrawler
        assert classes[1] is KRISOPapersCrawler

    def test_names_returns_sorted_names(self):
        """names() returns sorted list of registered names."""
        from kg.crawlers.kma_marine import KMAMarineCrawler
        from kg.crawlers.kriso_papers import KRISOPapersCrawler

        registry = CrawlerRegistry()
        registry.register(KRISOPapersCrawler)
        registry.register(KMAMarineCrawler)

        names = registry.names()
        assert names == ["kma-marine", "kriso-papers"]

    def test_len(self):
        """len(registry) returns count of registered crawlers."""
        from kg.crawlers.kma_marine import KMAMarineCrawler

        registry = CrawlerRegistry()
        assert len(registry) == 0
        registry.register(KMAMarineCrawler)
        assert len(registry) == 1

    def test_contains(self):
        """'name' in registry works correctly."""
        from kg.crawlers.kma_marine import KMAMarineCrawler

        registry = CrawlerRegistry()
        registry.register(KMAMarineCrawler)
        assert "kma-marine" in registry
        assert "nonexistent" not in registry


# ==============================================================================
# discover_builtins() Tests
# ==============================================================================


@pytest.mark.unit
class TestDiscoverBuiltins:
    """Tests for discover_builtins() function."""

    def test_discovers_all_four_crawlers(self):
        """discover_builtins() registers all 4 built-in crawlers."""
        registry = discover_builtins()
        assert len(registry) == 4

    def test_discovered_names(self):
        """discover_builtins() registers the correct names."""
        registry = discover_builtins()
        expected = {"kma-marine", "kriso-facilities", "kriso-papers", "maritime-accidents"}
        assert set(registry.names()) == expected

    def test_discover_returns_new_registry_each_time(self):
        """discover_builtins() returns a fresh registry each call."""
        r1 = discover_builtins()
        r2 = discover_builtins()
        assert r1 is not r2


# ==============================================================================
# get_registry() Singleton Tests
# ==============================================================================


@pytest.mark.unit
class TestGetRegistry:
    """Tests for get_registry() singleton."""

    def test_returns_registry_instance(self):
        """get_registry() returns a CrawlerRegistry."""
        registry = get_registry()
        assert isinstance(registry, CrawlerRegistry)

    def test_singleton_returns_same_instance(self):
        """get_registry() returns the same instance on repeated calls."""
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2


# ==============================================================================
# Per-Crawler info() Tests
# ==============================================================================


@pytest.mark.unit
class TestCrawlerInfoValues:
    """Tests that each built-in crawler returns correct info()."""

    def test_kriso_papers_info(self):
        """KRISOPapersCrawler.info() returns correct metadata."""
        from kg.crawlers.kriso_papers import KRISOPapersCrawler

        info = KRISOPapersCrawler.info()
        assert info.name == "kriso-papers"
        assert info.display_name == "KRISO ScholarWorks"
        assert info.description == "KRISO 학술논문 크롤러"

    def test_kriso_facilities_info(self):
        """KRISOFacilitiesCrawler.info() returns correct metadata."""
        from kg.crawlers.kriso_facilities import KRISOFacilitiesCrawler

        info = KRISOFacilitiesCrawler.info()
        assert info.name == "kriso-facilities"
        assert info.display_name == "KRISO 시험시설"
        assert info.description == "KRISO 시험시설 데이터 크롤러"

    def test_kma_marine_info(self):
        """KMAMarineCrawler.info() returns correct metadata."""
        from kg.crawlers.kma_marine import KMAMarineCrawler

        info = KMAMarineCrawler.info()
        assert info.name == "kma-marine"
        assert info.display_name == "기상청 해양기상"
        assert info.description == "기상청 해양기상 데이터 크롤러"

    def test_maritime_accidents_info(self):
        """MaritimeAccidentsCrawler.info() returns correct metadata."""
        from kg.crawlers.maritime_accidents import MaritimeAccidentsCrawler

        info = MaritimeAccidentsCrawler.info()
        assert info.name == "maritime-accidents"
        assert info.display_name == "해양사고"
        assert info.description == "해양사고 데이터 크롤러"
