"""Maritime domain plugin registration.

Provides the ``MaritimeDomainPlugin`` class and the ``register_plugin()``
function called by the plugin discovery system.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from kg.plugins.base import BaseDomainPlugin
from kg.plugins.registry import PluginInfo, PluginRegistry


class MaritimeDomainPlugin(BaseDomainPlugin):
    """Maritime domain plugin providing Korean maritime-specific extensions.

    Registers crawlers, ontology loader, NLP terms, entity groups, and
    schema files from the ``maritime`` package.
    """

    @classmethod
    def info(cls) -> PluginInfo:
        return PluginInfo(
            name="maritime",
            display_name="해사 도메인",
            version="0.1.0",
            description="Korean maritime domain: ontology, crawlers, NLP terms",
        )

    def get_ontology_loader(self) -> Any:
        from maritime.ontology.maritime_loader import load_maritime_ontology

        return load_maritime_ontology

    def get_term_dictionary(self) -> Any:
        from maritime.nlp import maritime_terms

        return maritime_terms

    def get_crawler_classes(self) -> list[type]:
        from maritime.crawlers.kma_marine import KMAMarineCrawler
        from maritime.crawlers.kriso_facilities import KRISOFacilitiesCrawler
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler
        from maritime.crawlers.maritime_accidents import MaritimeAccidentsCrawler

        return [
            KRISOPapersCrawler,
            KRISOFacilitiesCrawler,
            KMAMarineCrawler,
            MaritimeAccidentsCrawler,
        ]

    def get_entity_groups(self) -> dict[str, Any]:
        from maritime.entity_groups import (
            _LABEL_TO_GROUP,
            get_color_for_label,
            get_group_for_label,
        )

        return {
            "label_to_group": _LABEL_TO_GROUP,
            "get_color": get_color_for_label,
            "get_group": get_group_for_label,
        }

    def get_schema_dir(self) -> Path:
        return Path(__file__).resolve().parent / "schema"

    def get_evaluation_dataset(self) -> Any:
        from maritime.evaluation import dataset

        return dataset


def register_plugin(registry: PluginRegistry) -> None:
    """Called by PluginRegistry.discover_plugins() during auto-discovery."""
    registry.register(MaritimeDomainPlugin())
