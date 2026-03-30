"""Extended unit tests for core/kg/api/routes/graph.py.

Covers the ImportError fallback for maritime.entity_groups (lines 13-20):
- get_color_for_label returns "#999999" when maritime is unavailable
- get_group_for_label returns "unknown" when maritime is unavailable
- _LABEL_TO_GROUP is empty dict when maritime is unavailable

Pattern mirrors TestSchemaImportErrorFallback in test_api_schema_routes.py.
All tests are @pytest.mark.unit.
"""
from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# TestGraphImportErrorFallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGraphImportErrorFallback:
    """Tests for the ImportError fallback in graph.py (lines 13-20).

    The fallback code runs at module import time when
    ``maritime.entity_groups`` is unavailable. We simulate that by
    reloading the module with the import blocked via sys.modules.
    """

    def _reload_graph_without_maritime(self) -> object:
        """Remove graph module and maritime.entity_groups, then reload."""
        saved: dict[str, object] = {}

        # Remove maritime-related modules
        for key in list(sys.modules.keys()):
            if "maritime.entity_groups" in key or key == "maritime.entity_groups":
                saved[key] = sys.modules.pop(key)

        # Remove the graph route module so it re-executes the top-level try/except
        for key in list(sys.modules.keys()):
            if "kg.api.routes.graph" in key:
                saved[key] = sys.modules.pop(key)

        return saved

    def _restore_modules(self, saved: dict[str, object]) -> None:
        """Restore previously saved modules."""
        for key, mod in saved.items():
            sys.modules[key] = mod  # type: ignore[assignment]

    def test_fallback_color_function_returns_grey(self) -> None:
        """When maritime.entity_groups is missing, get_color_for_label returns '#999999'."""
        saved = self._reload_graph_without_maritime()
        try:
            with patch.dict(sys.modules, {"maritime.entity_groups": None}):
                import kg.api.routes.graph as graph_module
                importlib.reload(graph_module)

                result = graph_module.get_color_for_label("Vessel")
                assert result == "#999999"
        finally:
            self._restore_modules(saved)

    def test_fallback_color_function_returns_grey_for_any_label(self) -> None:
        """The fallback get_color_for_label returns '#999999' regardless of label."""
        saved = self._reload_graph_without_maritime()
        try:
            with patch.dict(sys.modules, {"maritime.entity_groups": None}):
                import kg.api.routes.graph as graph_module
                importlib.reload(graph_module)

                assert graph_module.get_color_for_label("Port") == "#999999"
                assert graph_module.get_color_for_label("AnchorageArea") == "#999999"
                assert graph_module.get_color_for_label("") == "#999999"
        finally:
            self._restore_modules(saved)

    def test_fallback_group_function_returns_unknown(self) -> None:
        """When maritime.entity_groups is missing, get_group_for_label returns 'unknown'."""
        saved = self._reload_graph_without_maritime()
        try:
            with patch.dict(sys.modules, {"maritime.entity_groups": None}):
                import kg.api.routes.graph as graph_module
                importlib.reload(graph_module)

                result = graph_module.get_group_for_label("Vessel")
                assert result == "unknown"
        finally:
            self._restore_modules(saved)

    def test_fallback_group_function_returns_unknown_for_any_label(self) -> None:
        """The fallback get_group_for_label returns 'unknown' regardless of label."""
        saved = self._reload_graph_without_maritime()
        try:
            with patch.dict(sys.modules, {"maritime.entity_groups": None}):
                import kg.api.routes.graph as graph_module
                importlib.reload(graph_module)

                assert graph_module.get_group_for_label("Port") == "unknown"
                assert graph_module.get_group_for_label("SomeOtherLabel") == "unknown"
                assert graph_module.get_group_for_label("") == "unknown"
        finally:
            self._restore_modules(saved)

    def test_fallback_label_to_group_is_empty_dict(self) -> None:
        """When maritime.entity_groups is missing, _LABEL_TO_GROUP is an empty dict."""
        saved = self._reload_graph_without_maritime()
        try:
            with patch.dict(sys.modules, {"maritime.entity_groups": None}):
                import kg.api.routes.graph as graph_module
                importlib.reload(graph_module)

                assert graph_module._LABEL_TO_GROUP == {}
                assert isinstance(graph_module._LABEL_TO_GROUP, dict)
        finally:
            self._restore_modules(saved)

    def test_fallback_functions_are_callable(self) -> None:
        """The fallback stubs are proper callables, not None."""
        saved = self._reload_graph_without_maritime()
        try:
            with patch.dict(sys.modules, {"maritime.entity_groups": None}):
                import kg.api.routes.graph as graph_module
                importlib.reload(graph_module)

                assert callable(graph_module.get_color_for_label)
                assert callable(graph_module.get_group_for_label)
        finally:
            self._restore_modules(saved)
