"""Crawler registry for discovery and management of crawlers.

Provides a ``CrawlerRegistry`` that maps crawler names to their classes,
and a ``discover_builtins()`` helper that auto-registers crawlers from
registered domain plugins.

Usage::

    from kg.crawlers.registry import get_registry

    registry = get_registry()
    for name in registry.names():
        crawler_cls = registry.get(name)
        print(crawler_cls.info())
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kg.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)

# Module-level singleton instance (lazily initialised)
_registry: CrawlerRegistry | None = None


class CrawlerRegistry:
    """Registry mapping crawler names to their classes.

    Crawlers are registered by their ``info().name`` value and can be
    looked up by name.
    """

    def __init__(self) -> None:
        self._crawlers: dict[str, type[BaseCrawler]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, crawler_cls: type[BaseCrawler]) -> None:
        """Register a crawler class.

        The crawler is keyed by its ``info().name``.  Registering the
        same name twice overwrites the previous entry and logs a warning.

        Parameters
        ----------
        crawler_cls : type[BaseCrawler]
            A concrete ``BaseCrawler`` subclass.
        """
        name = crawler_cls.info().name
        if name in self._crawlers:
            logger.warning(
                "Overwriting crawler %r (was %s, now %s)",
                name,
                self._crawlers[name].__name__,
                crawler_cls.__name__,
            )
        self._crawlers[name] = crawler_cls

    def get(self, name: str) -> type[BaseCrawler] | None:
        """Return the crawler class registered under *name*, or ``None``."""
        return self._crawlers.get(name)

    def list_all(self) -> list[type[BaseCrawler]]:
        """Return all registered crawler classes (sorted by name)."""
        return [self._crawlers[k] for k in sorted(self._crawlers)]

    def names(self) -> list[str]:
        """Return sorted list of all registered crawler names."""
        return sorted(self._crawlers)

    def __len__(self) -> int:
        return len(self._crawlers)

    def __contains__(self, name: str) -> bool:
        return name in self._crawlers

    def __repr__(self) -> str:
        return f"CrawlerRegistry({list(self._crawlers.keys())})"


def discover_builtins() -> CrawlerRegistry:
    """Create a registry populated from registered domain plugins.

    Queries the plugin registry for all domain plugins and registers
    their crawler classes.

    Returns
    -------
    CrawlerRegistry
        A registry containing crawlers from all registered plugins.
    """
    from kg.plugins.registry import get_plugin_registry

    registry = CrawlerRegistry()
    for plugin in get_plugin_registry().list_all():
        crawler_classes = plugin.get_crawler_classes()
        if crawler_classes:
            for cls in crawler_classes:
                registry.register(cls)

    logger.debug("Discovered %d crawlers from plugins", len(registry))
    return registry


def get_registry() -> CrawlerRegistry:
    """Return the module-level singleton registry.

    On first call the built-in crawlers are discovered and registered.
    Subsequent calls return the same instance.
    """
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = discover_builtins()
    return _registry
