"""Coverage gap tests for several files with small uncovered branches.

Targets:
- core/kg/api/pagination.py  line 65  : get_pagination_params()
- core/kg/plugins/base.py    line 39  : BaseDomainPlugin.get_ontology_loader default return None
- core/kg/cache/models.py    line 40  : CacheConfig.validate max_size <= 0 branch
- core/kg/embeddings/ollama_embedder.py lines 82-84: lazy _get_embedder init path
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# Pagination — get_pagination_params (line 65)
# ===========================================================================


@pytest.mark.unit
class TestGetPaginationParams:
    """Direct calls to the get_pagination_params FastAPI dependency function."""

    def test_defaults(self) -> None:
        """Calling with explicit None/50 returns PaginationParams with defaults."""
        from kg.api.pagination import PaginationParams, get_pagination_params

        # When called directly (not via FastAPI DI) the Query sentinels are
        # forwarded as-is, so we pass explicit values to exercise the line.
        result = get_pagination_params(cursor=None, limit=50)
        assert isinstance(result, PaginationParams)
        assert result.cursor is None
        assert result.limit == 50

    def test_custom_cursor_and_limit(self) -> None:
        """Cursor and limit are forwarded to PaginationParams."""
        from kg.api.pagination import PaginationParams, get_pagination_params

        result = get_pagination_params(cursor="abc123", limit=25)
        assert isinstance(result, PaginationParams)
        assert result.cursor == "abc123"
        assert result.limit == 25

    def test_none_cursor_explicit(self) -> None:
        """Explicit None cursor is stored as-is."""
        from kg.api.pagination import get_pagination_params

        result = get_pagination_params(cursor=None, limit=100)
        assert result.cursor is None
        assert result.limit == 100


# ===========================================================================
# BaseDomainPlugin — default no-op implementations (line 39)
# ===========================================================================


@pytest.mark.unit
class TestBaseDomainPluginDefaults:
    """BaseDomainPlugin default methods return None (line 39 and siblings)."""

    def test_get_ontology_loader_returns_none(self) -> None:
        """The default get_ontology_loader implementation returns None."""
        from kg.plugins.base import BaseDomainPlugin

        class _MinimalPlugin(BaseDomainPlugin):
            """Does not override any optional methods."""

            @classmethod
            def info(cls):
                from kg.plugins.registry import PluginInfo
                return PluginInfo(name="minimal", display_name="Minimal")

        plugin = _MinimalPlugin()
        # Directly exercises the base-class `return None` on line 39
        assert plugin.get_ontology_loader() is None

    def test_get_term_dictionary_returns_none(self) -> None:
        """Default get_term_dictionary returns None."""
        from kg.plugins.base import BaseDomainPlugin

        class _MinimalPlugin(BaseDomainPlugin):
            @classmethod
            def info(cls):
                from kg.plugins.registry import PluginInfo
                return PluginInfo(name="m2", display_name="M2")

        plugin = _MinimalPlugin()
        assert plugin.get_term_dictionary() is None

    def test_get_crawler_classes_returns_none(self) -> None:
        from kg.plugins.base import BaseDomainPlugin

        class _MinimalPlugin(BaseDomainPlugin):
            @classmethod
            def info(cls):
                from kg.plugins.registry import PluginInfo
                return PluginInfo(name="m3", display_name="M3")

        assert _MinimalPlugin().get_crawler_classes() is None

    def test_get_entity_groups_returns_none(self) -> None:
        from kg.plugins.base import BaseDomainPlugin

        class _MinimalPlugin(BaseDomainPlugin):
            @classmethod
            def info(cls):
                from kg.plugins.registry import PluginInfo
                return PluginInfo(name="m4", display_name="M4")

        assert _MinimalPlugin().get_entity_groups() is None

    def test_get_schema_dir_returns_none(self) -> None:
        from kg.plugins.base import BaseDomainPlugin

        class _MinimalPlugin(BaseDomainPlugin):
            @classmethod
            def info(cls):
                from kg.plugins.registry import PluginInfo
                return PluginInfo(name="m5", display_name="M5")

        assert _MinimalPlugin().get_schema_dir() is None

    def test_get_evaluation_dataset_returns_none(self) -> None:
        from kg.plugins.base import BaseDomainPlugin

        class _MinimalPlugin(BaseDomainPlugin):
            @classmethod
            def info(cls):
                from kg.plugins.registry import PluginInfo
                return PluginInfo(name="m6", display_name="M6")

        assert _MinimalPlugin().get_evaluation_dataset() is None

    def test_get_api_routes_returns_none(self) -> None:
        from kg.plugins.base import BaseDomainPlugin

        class _MinimalPlugin(BaseDomainPlugin):
            @classmethod
            def info(cls):
                from kg.plugins.registry import PluginInfo
                return PluginInfo(name="m7", display_name="M7")

        assert _MinimalPlugin().get_api_routes() is None

    def test_info_raises_not_implemented_on_base(self) -> None:
        """Calling info() on BaseDomainPlugin itself raises NotImplementedError."""
        from kg.plugins.base import BaseDomainPlugin

        with pytest.raises(NotImplementedError):
            BaseDomainPlugin.info()


# ===========================================================================
# CacheConfig.validate — max_size <= 0 branch (line 40)
# ===========================================================================


@pytest.mark.unit
class TestCacheConfigValidateMaxSize:
    """CacheConfig.validate covers the max_size <= 0 error path (line 40)."""

    def test_validate_zero_max_size(self) -> None:
        """max_size = 0 triggers the 'max_size must be positive' error."""
        from kg.cache.models import CacheConfig

        cfg = CacheConfig(max_size=0)
        errors = cfg.validate()
        assert any("max_size" in e for e in errors)

    def test_validate_negative_max_size(self) -> None:
        """Negative max_size also triggers the error."""
        from kg.cache.models import CacheConfig

        cfg = CacheConfig(max_size=-5)
        errors = cfg.validate()
        assert any("max_size" in e for e in errors)

    def test_validate_positive_max_size_no_error(self) -> None:
        """A positive max_size produces no error for that field."""
        from kg.cache.models import CacheConfig

        cfg = CacheConfig(max_size=1)
        errors = cfg.validate()
        assert not any("max_size" in e for e in errors)


# ===========================================================================
# OllamaEmbedder._get_embedder — lazy init path (lines 82-84)
# ===========================================================================


@pytest.mark.unit
class TestOllamaEmbedderLazyInit:
    """_get_embedder initializes OllamaEmbeddings on first call (lines 82-84)."""

    def test_get_embedder_lazy_init(self) -> None:
        """_embedder is None before first call; becomes non-None after."""
        from kg.embeddings.ollama_embedder import OllamaEmbedder

        mock_embeddings_cls = MagicMock()
        mock_embeddings_instance = MagicMock()
        mock_embeddings_cls.return_value = mock_embeddings_instance

        fake_ollama_module = MagicMock()
        fake_ollama_module.OllamaEmbeddings = mock_embeddings_cls

        with patch.dict(
            "sys.modules",
            {"neo4j_graphrag.embeddings.ollama": fake_ollama_module},
        ):
            embedder = OllamaEmbedder(
                model="nomic-embed-text", base_url="http://localhost:11434"
            )
            assert embedder._embedder is None

            # First call triggers the lazy init code at lines 82-84
            result = embedder._get_embedder()

        assert result is mock_embeddings_instance
        mock_embeddings_cls.assert_called_once_with(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        )

    def test_get_embedder_cached_on_second_call(self) -> None:
        """_get_embedder returns the same instance on subsequent calls."""
        from kg.embeddings.ollama_embedder import OllamaEmbedder

        mock_embeddings_cls = MagicMock()
        mock_instance = MagicMock()
        mock_embeddings_cls.return_value = mock_instance

        fake_module = MagicMock()
        fake_module.OllamaEmbeddings = mock_embeddings_cls

        with patch.dict(
            "sys.modules",
            {"neo4j_graphrag.embeddings.ollama": fake_module},
        ):
            embedder = OllamaEmbedder()
            first = embedder._get_embedder()
            second = embedder._get_embedder()

        assert first is second
        # OllamaEmbeddings constructor called only once
        assert mock_embeddings_cls.call_count == 1

    def test_get_embedder_passes_model_and_url(self) -> None:
        """Constructor args are forwarded to OllamaEmbeddings."""
        from kg.embeddings.ollama_embedder import OllamaEmbedder

        mock_cls = MagicMock()
        fake_module = MagicMock()
        fake_module.OllamaEmbeddings = mock_cls

        with patch.dict(
            "sys.modules",
            {"neo4j_graphrag.embeddings.ollama": fake_module},
        ):
            embedder = OllamaEmbedder(
                model="bge-m3", base_url="http://custom-host:11434"
            )
            embedder._get_embedder()

        mock_cls.assert_called_once_with(
            model="bge-m3",
            base_url="http://custom-host:11434",
        )
