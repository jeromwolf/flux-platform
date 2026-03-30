"""Unit tests for ImportError fallback branches in core/kg __init__.py files.

Each module exposes maritime-specific names only when the maritime domain package
is installed.  These tests simulate the package being absent by injecting ``None``
into ``sys.modules`` (which causes Python to treat the import as an ImportError
when the module is reloaded) and verify that:

  * the ``except ImportError: pass`` branch is taken, and
  * ``__all__`` does **not** contain the maritime-specific names.

The tests restore ``sys.modules`` to its original state after each run to prevent
cross-test pollution.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Generator

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backup_modules(*names: str) -> dict[str, ModuleType | None]:
    """Snapshot the current state of *names* in sys.modules."""
    return {n: sys.modules.get(n) for n in names}  # type: ignore[misc]


def _restore_modules(snapshot: dict[str, ModuleType | None]) -> None:
    """Restore sys.modules to a previously saved snapshot."""
    for name, value in snapshot.items():
        if value is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = value


# ---------------------------------------------------------------------------
# Tests: core/kg/evaluation/__init__.py
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEvaluationInitImportError:
    """Cover lines 53-54 in core/kg/evaluation/__init__.py."""

    _MARITIME_NAMES = ("EvalQuestion", "EvalDataset", "ReasoningType", "Difficulty")
    _MARITIME_MODULE = "maritime.evaluation.dataset"

    def test_maritime_names_in_all_when_available(self) -> None:
        """When the maritime package is present, __all__ includes maritime names."""
        import kg.evaluation as ev
        for name in self._MARITIME_NAMES:
            assert name in ev.__all__, f"{name!r} should be in __all__ when maritime is available"

    def test_maritime_names_absent_from_all_on_import_error(self) -> None:
        """When maritime.evaluation.dataset raises ImportError, __all__ omits maritime names."""
        affected = [
            "kg.evaluation",
            self._MARITIME_MODULE,
        ]
        snapshot = _backup_modules(*affected)

        try:
            # Inject None → Python raises ImportError when this is imported.
            sys.modules[self._MARITIME_MODULE] = None  # type: ignore[assignment]
            # Remove the parent package so reload re-executes the try/except.
            sys.modules.pop("kg.evaluation", None)

            import kg.evaluation as ev
            importlib.reload(ev)

            for name in self._MARITIME_NAMES:
                assert name not in ev.__all__, (
                    f"{name!r} should NOT be in __all__ when maritime is unavailable"
                )
        finally:
            _restore_modules(snapshot)
            # Force a clean reload so subsequent tests see the real package.
            sys.modules.pop("kg.evaluation", None)
            import kg.evaluation  # noqa: F401  (re-populate cache)

    def test_core_names_always_present(self) -> None:
        """Core evaluation names are always in __all__ regardless of maritime."""
        import kg.evaluation as ev
        for name in ("CypherAccuracy", "QueryRelevancy", "ReasoningTypeMetric",
                     "EvaluationRunner", "EvalReport"):
            assert name in ev.__all__


# ---------------------------------------------------------------------------
# Tests: core/kg/n10s/__init__.py
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestN10sInitImportError:
    """Cover lines 22-23 in core/kg/n10s/__init__.py."""

    _MARITIME_MODULE = "maritime.n10s.owl_exporter"

    def test_owl_exporter_in_all_when_available(self) -> None:
        """When the maritime package is present, __all__ includes OWLExporter."""
        try:
            import maritime.n10s.owl_exporter  # noqa: F401
        except ImportError:
            pytest.skip("maritime.n10s.owl_exporter not installed in this environment")
        import kg.n10s as n10s
        assert "OWLExporter" in n10s.__all__

    def test_owl_exporter_absent_from_all_on_import_error(self) -> None:
        """When maritime.n10s.owl_exporter raises ImportError, OWLExporter not in __all__."""
        affected = [
            "kg.n10s",
            self._MARITIME_MODULE,
            "maritime.n10s",
        ]
        snapshot = _backup_modules(*affected)

        try:
            sys.modules[self._MARITIME_MODULE] = None  # type: ignore[assignment]
            sys.modules.pop("kg.n10s", None)

            import kg.n10s as n10s
            importlib.reload(n10s)

            assert "OWLExporter" not in n10s.__all__
        finally:
            _restore_modules(snapshot)
            sys.modules.pop("kg.n10s", None)
            import kg.n10s  # noqa: F401

    def test_core_names_always_present(self) -> None:
        """N10sConfig and N10sImporter are always in __all__."""
        import kg.n10s as n10s
        assert "N10sConfig" in n10s.__all__
        assert "N10sImporter" in n10s.__all__


# ---------------------------------------------------------------------------
# Tests: core/kg/nlp/__init__.py
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNLPInitImportError:
    """Cover lines 35-36 in core/kg/nlp/__init__.py."""

    _MARITIME_MODULE = "maritime.nlp.maritime_terms"
    _MARITIME_NAMES = (
        "ENTITY_SYNONYMS",
        "RELATIONSHIP_KEYWORDS",
        "PROPERTY_VALUE_MAP",
        "NAMED_ENTITIES",
        "resolve_entity",
        "resolve_property_value",
        "resolve_named_entity",
        "get_term_context_for_llm",
    )

    def test_maritime_names_in_all_when_available(self) -> None:
        """When maritime.nlp.maritime_terms is present, __all__ includes maritime names."""
        import kg.nlp as nlp
        for name in self._MARITIME_NAMES:
            assert name in nlp.__all__, f"{name!r} should be in __all__ when maritime is available"

    def test_maritime_names_absent_from_all_on_import_error(self) -> None:
        """When maritime.nlp.maritime_terms raises ImportError, maritime names absent."""
        affected = [
            "kg.nlp",
            self._MARITIME_MODULE,
            "maritime.nlp",
        ]
        snapshot = _backup_modules(*affected)

        try:
            sys.modules[self._MARITIME_MODULE] = None  # type: ignore[assignment]
            sys.modules.pop("kg.nlp", None)

            import kg.nlp as nlp
            importlib.reload(nlp)

            for name in self._MARITIME_NAMES:
                assert name not in nlp.__all__, (
                    f"{name!r} should NOT be in __all__ when maritime.nlp is unavailable"
                )
        finally:
            _restore_modules(snapshot)
            sys.modules.pop("kg.nlp", None)
            import kg.nlp  # noqa: F401

    def test_core_names_always_present(self) -> None:
        """NLParser, ParseResult, and TermDictionary are always in __all__."""
        import kg.nlp as nlp
        for name in ("NLParser", "ParseResult", "TermDictionary"):
            assert name in nlp.__all__


# ---------------------------------------------------------------------------
# Tests: core/kg/schema/__init__.py
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSchemaInitImportError:
    """Cover lines 3-13 in core/kg/schema/__init__.py (100% coverage target)."""

    _MARITIME_MODULE = "maritime.schema.load_sample_data"

    def test_init_schema_always_present(self) -> None:
        """init_schema is always importable and present in __all__."""
        import kg.schema as schema
        assert "init_schema" in schema.__all__
        from kg.schema import init_schema  # noqa: F401
        assert callable(init_schema)

    def test_load_sample_data_in_all_when_available(self) -> None:
        """When maritime.schema.load_sample_data is present, __all__ includes it."""
        try:
            import maritime.schema.load_sample_data  # noqa: F401
        except ImportError:
            pytest.skip("maritime.schema.load_sample_data not installed in this environment")
        import kg.schema as schema
        assert "load_sample_data" in schema.__all__

    def test_load_sample_data_absent_from_all_on_import_error(self) -> None:
        """When maritime.schema.load_sample_data raises ImportError, it's absent from __all__."""
        affected = [
            "kg.schema",
            self._MARITIME_MODULE,
            "maritime.schema",
        ]
        snapshot = _backup_modules(*affected)

        try:
            sys.modules[self._MARITIME_MODULE] = None  # type: ignore[assignment]
            sys.modules.pop("kg.schema", None)

            import kg.schema as schema
            importlib.reload(schema)

            assert "load_sample_data" not in schema.__all__
            # init_schema must still be present
            assert "init_schema" in schema.__all__
        finally:
            _restore_modules(snapshot)
            sys.modules.pop("kg.schema", None)
            import kg.schema  # noqa: F401

    def test_module_is_importable(self) -> None:
        """The schema __init__ module can be imported cleanly."""
        import kg.schema as schema
        assert isinstance(schema, ModuleType)
