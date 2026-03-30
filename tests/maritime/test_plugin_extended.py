"""Extended unit tests for MaritimeDomainPlugin covering uncovered methods.

Covers:
  - get_ontology_loader  (lines 32-34)
  - get_term_dictionary  (lines 37-39)
  - get_entity_groups    (lines 55-65)
  - get_evaluation_dataset (lines 71-73)
  - register_plugin      (line 76-78)
"""

from __future__ import annotations

from types import ModuleType

import pytest

from kg.plugins.registry import PluginRegistry


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def plugin():
    from maritime.plugin import MaritimeDomainPlugin
    return MaritimeDomainPlugin()


# ---------------------------------------------------------------------------
# get_ontology_loader
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetOntologyLoader:
    """Lines 32-34: get_ontology_loader returns load_maritime_ontology callable."""

    def test_returns_callable(self, plugin) -> None:
        loader = plugin.get_ontology_loader()
        assert callable(loader), "get_ontology_loader() must return a callable"

    def test_returns_load_maritime_ontology_function(self, plugin) -> None:
        """The returned object should be the load_maritime_ontology function."""
        from maritime.ontology.maritime_loader import load_maritime_ontology
        loader = plugin.get_ontology_loader()
        assert loader is load_maritime_ontology

    def test_return_type_is_not_none(self, plugin) -> None:
        assert plugin.get_ontology_loader() is not None


# ---------------------------------------------------------------------------
# get_term_dictionary
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetTermDictionary:
    """Lines 37-39: get_term_dictionary returns the maritime_terms module."""

    def test_returns_module(self, plugin) -> None:
        result = plugin.get_term_dictionary()
        assert isinstance(result, ModuleType), (
            f"get_term_dictionary() should return a module, got {type(result)}"
        )

    def test_returns_maritime_terms_module(self, plugin) -> None:
        from maritime.nlp import maritime_terms
        result = plugin.get_term_dictionary()
        assert result is maritime_terms

    def test_module_has_expected_attributes(self, plugin) -> None:
        """The returned module should expose canonical term-dict attributes."""
        result = plugin.get_term_dictionary()
        for attr in ("ENTITY_SYNONYMS", "RELATIONSHIP_KEYWORDS", "resolve_entity"):
            assert hasattr(result, attr), f"maritime_terms module missing {attr!r}"

    def test_return_type_is_not_none(self, plugin) -> None:
        assert plugin.get_term_dictionary() is not None


# ---------------------------------------------------------------------------
# get_entity_groups
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetEntityGroups:
    """Lines 55-65: get_entity_groups returns a dict with label_to_group, get_color, get_group."""

    def test_returns_dict(self, plugin) -> None:
        result = plugin.get_entity_groups()
        assert isinstance(result, dict), "get_entity_groups() must return a dict"

    def test_has_required_keys(self, plugin) -> None:
        result = plugin.get_entity_groups()
        for key in ("label_to_group", "get_color", "get_group"):
            assert key in result, f"Key {key!r} missing from get_entity_groups() result"

    def test_label_to_group_is_dict(self, plugin) -> None:
        result = plugin.get_entity_groups()
        assert isinstance(result["label_to_group"], dict)
        assert len(result["label_to_group"]) > 0, "_LABEL_TO_GROUP should not be empty"

    def test_get_color_is_callable(self, plugin) -> None:
        result = plugin.get_entity_groups()
        assert callable(result["get_color"])

    def test_get_group_is_callable(self, plugin) -> None:
        result = plugin.get_entity_groups()
        assert callable(result["get_group"])

    def test_get_color_returns_string_for_vessel(self, plugin) -> None:
        result = plugin.get_entity_groups()
        color = result["get_color"]("Vessel")
        assert isinstance(color, str)
        assert color  # non-empty

    def test_get_group_returns_string_for_vessel(self, plugin) -> None:
        result = plugin.get_entity_groups()
        group = result["get_group"]("Vessel")
        assert isinstance(group, str)

    def test_get_group_unknown_label_returns_unknown(self, plugin) -> None:
        result = plugin.get_entity_groups()
        group = result["get_group"]("NonExistentLabel_XYZ")
        assert group == "Unknown"

    def test_matches_underlying_module(self, plugin) -> None:
        """Values match what entity_groups module exports directly."""
        from maritime.entity_groups import (
            _LABEL_TO_GROUP,
            get_color_for_label,
            get_group_for_label,
        )
        result = plugin.get_entity_groups()
        assert result["label_to_group"] is _LABEL_TO_GROUP
        assert result["get_color"] is get_color_for_label
        assert result["get_group"] is get_group_for_label


# ---------------------------------------------------------------------------
# get_evaluation_dataset
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetEvaluationDataset:
    """Lines 71-73: get_evaluation_dataset returns the maritime.evaluation.dataset module."""

    def test_returns_module(self, plugin) -> None:
        result = plugin.get_evaluation_dataset()
        assert isinstance(result, ModuleType), (
            f"get_evaluation_dataset() should return a module, got {type(result)}"
        )

    def test_returns_dataset_module(self, plugin) -> None:
        from maritime.evaluation import dataset
        result = plugin.get_evaluation_dataset()
        assert result is dataset

    def test_module_has_eval_dataset_class(self, plugin) -> None:
        result = plugin.get_evaluation_dataset()
        assert hasattr(result, "EvalDataset"), "dataset module should expose EvalDataset"

    def test_module_has_eval_question_class(self, plugin) -> None:
        result = plugin.get_evaluation_dataset()
        assert hasattr(result, "EvalQuestion")

    def test_module_has_reasoning_type_enum(self, plugin) -> None:
        result = plugin.get_evaluation_dataset()
        assert hasattr(result, "ReasoningType")

    def test_return_type_is_not_none(self, plugin) -> None:
        assert plugin.get_evaluation_dataset() is not None


# ---------------------------------------------------------------------------
# register_plugin
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRegisterPlugin:
    """Lines 76-78: register_plugin() adds MaritimeDomainPlugin to the registry."""

    def test_register_adds_to_registry(self) -> None:
        from maritime.plugin import register_plugin
        registry = PluginRegistry()
        register_plugin(registry)
        assert "maritime" in registry

    def test_registered_plugin_is_maritime_instance(self) -> None:
        from maritime.plugin import MaritimeDomainPlugin, register_plugin
        registry = PluginRegistry()
        register_plugin(registry)
        plugin = registry.get("maritime")
        assert isinstance(plugin, MaritimeDomainPlugin)

    def test_register_twice_overwrites(self) -> None:
        """Registering twice should not raise; last registration wins."""
        from maritime.plugin import register_plugin
        registry = PluginRegistry()
        register_plugin(registry)
        register_plugin(registry)
        assert len(registry) == 1
        assert "maritime" in registry

    def test_registry_names_contains_maritime(self) -> None:
        from maritime.plugin import register_plugin
        registry = PluginRegistry()
        register_plugin(registry)
        assert "maritime" in registry.names()
