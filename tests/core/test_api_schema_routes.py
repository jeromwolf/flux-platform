"""Unit tests for core/kg/api/routes/schema.py.

Tests the schema introspection endpoint covering:
- Non-identifier label gets count=0 (lines 66-67)
- Count query exception returns 0 (lines 72-73)
- Normal schema endpoint path
- ImportError fallback for maritime.entity_groups (lines 18-26)
All tests are ``@pytest.mark.unit``.
"""
from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from kg.config import AppConfig, Neo4jConfig, reset

from tests.helpers.mock_neo4j import (
    MockNeo4jResult,
    MockNeo4jSession,
    make_test_app,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config():
    reset()
    yield
    reset()


@pytest.fixture
def dev_config() -> AppConfig:
    return AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))


# ---------------------------------------------------------------------------
# Session helpers for schema endpoint
# ---------------------------------------------------------------------------


def _label_record(label: str) -> dict[str, Any]:
    """Build a record dict for CALL db.labels()."""
    return {"label": label}


def _rel_type_record(rel_type: str) -> dict[str, Any]:
    """Build a record dict for CALL db.relationshipTypes()."""
    return {"relationshipType": rel_type}


def _count_record(cnt: int) -> dict[str, Any]:
    """Build a record dict for MATCH (n:Label) RETURN count(n) AS cnt."""
    return {"cnt": cnt}


# ---------------------------------------------------------------------------
# TestSchemaNonIdentifierLabel
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaNonIdentifierLabel:
    """Tests for the non-identifier label bypass (lines 66-67)."""

    def test_non_identifier_label_gets_zero_count(self, dev_config: AppConfig):
        """A label that fails .isidentifier() (e.g. contains spaces) gets count=0."""
        # Label with a space is not a valid Python identifier
        bad_label = "Bad Label"
        good_label = "Vessel"

        # Session calls:
        # 1. CALL db.labels() -> [bad_label, good_label]
        # 2. CALL db.relationshipTypes() -> []
        # 3. MATCH (n:Vessel) RETURN count(n) -> 5
        # (bad_label is skipped via continue, so no session.run for it)
        session = MockNeo4jSession(
            side_effects=[
                MockNeo4jResult([_label_record(bad_label), _label_record(good_label)]),
                MockNeo4jResult([]),  # relationship types
                MockNeo4jResult([_count_record(5)]),  # count for Vessel
            ]
        )
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.schema.ENTITY_GROUPS", {}), patch(
            "kg.api.routes.schema.GROUP_COLORS", {}
        ):
            resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        body = resp.json()
        labels = {lbl["label"]: lbl for lbl in body["labels"]}

        assert bad_label in labels
        assert labels[bad_label]["count"] == 0

        assert good_label in labels
        assert labels[good_label]["count"] == 5

    def test_label_with_hyphen_is_not_identifier(self, dev_config: AppConfig):
        """A label with a hyphen is not a valid identifier and gets count=0."""
        bad_label = "My-Label"

        session = MockNeo4jSession(
            side_effects=[
                MockNeo4jResult([_label_record(bad_label)]),
                MockNeo4jResult([]),  # relationship types
                # No count query for bad_label
            ]
        )
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.schema.ENTITY_GROUPS", {}), patch(
            "kg.api.routes.schema.GROUP_COLORS", {}
        ):
            resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        body = resp.json()
        labels = {lbl["label"]: lbl for lbl in body["labels"]}
        assert labels[bad_label]["count"] == 0

    def test_label_starting_with_digit_is_not_identifier(self, dev_config: AppConfig):
        """A label starting with a digit is not a valid identifier and gets count=0."""
        bad_label = "1stLabel"

        session = MockNeo4jSession(
            side_effects=[
                MockNeo4jResult([_label_record(bad_label)]),
                MockNeo4jResult([]),
            ]
        )
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.schema.ENTITY_GROUPS", {}), patch(
            "kg.api.routes.schema.GROUP_COLORS", {}
        ):
            resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        body = resp.json()
        labels = {lbl["label"]: lbl for lbl in body["labels"]}
        assert labels[bad_label]["count"] == 0


# ---------------------------------------------------------------------------
# TestSchemaCountException
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaCountException:
    """Tests for the count query exception path (lines 72-73)."""

    def test_count_exception_returns_zero(self, dev_config: AppConfig):
        """When the count query raises, label count defaults to 0."""

        class ExceptionOnCountSession:
            """Session that raises on the third call (count query)."""

            _call_count = 0

            async def run(self, cypher: str, params: dict | None = None):
                self._call_count += 1
                if self._call_count == 1:
                    # db.labels()
                    return MockNeo4jResult([_label_record("Vessel")])
                elif self._call_count == 2:
                    # db.relationshipTypes()
                    return MockNeo4jResult([])
                else:
                    # count query — raise an exception
                    raise RuntimeError("Neo4j count failed")

            async def close(self) -> None:
                pass

        from kg.api.app import create_app
        from kg.api.deps import get_async_neo4j_session

        with patch("kg.api.app.get_config", return_value=dev_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=dev_config)

        async def _override_session():
            yield ExceptionOnCountSession()

        app.dependency_overrides[get_async_neo4j_session] = _override_session

        from fastapi.testclient import TestClient

        client = TestClient(app)

        with patch("kg.api.routes.schema.ENTITY_GROUPS", {}), patch(
            "kg.api.routes.schema.GROUP_COLORS", {}
        ):
            resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        body = resp.json()
        labels = {lbl["label"]: lbl for lbl in body["labels"]}
        assert labels["Vessel"]["count"] == 0

    def test_multiple_labels_count_exception_only_affects_that_label(self, dev_config: AppConfig):
        """When count fails for one label, other labels still get their counts."""

        call_count = [0]

        class PartialExceptionSession:
            async def run(self, cypher: str, params: dict | None = None):
                call_count[0] += 1
                if call_count[0] == 1:
                    # db.labels()
                    return MockNeo4jResult([
                        _label_record("Vessel"),
                        _label_record("Port"),
                    ])
                elif call_count[0] == 2:
                    # db.relationshipTypes()
                    return MockNeo4jResult([])
                elif call_count[0] == 3:
                    # count for Vessel — success
                    result = MockNeo4jResult([_count_record(42)])
                    return result
                else:
                    # count for Port — raise
                    raise RuntimeError("Port count failed")

            async def close(self) -> None:
                pass

        from kg.api.app import create_app
        from kg.api.deps import get_async_neo4j_session

        with patch("kg.api.app.get_config", return_value=dev_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=dev_config)

        async def _override_session():
            yield PartialExceptionSession()

        app.dependency_overrides[get_async_neo4j_session] = _override_session

        from fastapi.testclient import TestClient

        client = TestClient(app)

        with patch("kg.api.routes.schema.ENTITY_GROUPS", {}), patch(
            "kg.api.routes.schema.GROUP_COLORS", {}
        ):
            resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        body = resp.json()
        labels = {lbl["label"]: lbl for lbl in body["labels"]}
        assert labels["Vessel"]["count"] == 42
        assert labels["Port"]["count"] == 0


# ---------------------------------------------------------------------------
# TestSchemaEndpointNormalPath
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaEndpointNormalPath:
    """Tests for the normal schema endpoint execution path."""

    def test_schema_returns_labels_and_relationship_types(self, dev_config: AppConfig):
        """Normal path returns labels and relationship types from Neo4j."""
        session = MockNeo4jSession(
            side_effects=[
                MockNeo4jResult([_label_record("Vessel"), _label_record("Port")]),
                MockNeo4jResult([_rel_type_record("DOCKED_AT"), _rel_type_record("BELONGS_TO")]),
                MockNeo4jResult([_count_record(10)]),  # Vessel count
                MockNeo4jResult([_count_record(5)]),   # Port count
            ]
        )
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.schema.ENTITY_GROUPS", {}), patch(
            "kg.api.routes.schema.GROUP_COLORS", {}
        ):
            resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        body = resp.json()
        assert body["totalLabels"] == 2
        assert body["totalRelationshipTypes"] == 2
        label_names = [lbl["label"] for lbl in body["labels"]]
        assert "Vessel" in label_names
        assert "Port" in label_names
        assert "DOCKED_AT" in body["relationshipTypes"]
        assert "BELONGS_TO" in body["relationshipTypes"]

    def test_schema_includes_entity_groups_when_available(self, dev_config: AppConfig):
        """When ENTITY_GROUPS and GROUP_COLORS are set, entityGroups is populated."""
        session = MockNeo4jSession(
            side_effects=[
                MockNeo4jResult([_label_record("Vessel")]),
                MockNeo4jResult([]),
                MockNeo4jResult([_count_record(7)]),
            ]
        )
        client = make_test_app(session, dev_config)

        entity_groups = {"PhysicalEntity": ["Vessel"]}
        group_colors = {"PhysicalEntity": "#FF5500"}

        with patch("kg.api.routes.schema.ENTITY_GROUPS", entity_groups), patch(
            "kg.api.routes.schema.GROUP_COLORS", group_colors
        ):
            resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        body = resp.json()
        assert "PhysicalEntity" in body["entityGroups"]
        assert body["entityGroups"]["PhysicalEntity"]["color"] == "#FF5500"
        assert "Vessel" in body["entityGroups"]["PhysicalEntity"]["labels"]

    def test_schema_empty_graph_returns_empty_collections(self, dev_config: AppConfig):
        """When no labels or relationships exist, empty collections are returned."""
        session = MockNeo4jSession(
            side_effects=[
                MockNeo4jResult([]),  # no labels
                MockNeo4jResult([]),  # no rel types
            ]
        )
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.schema.ENTITY_GROUPS", {}), patch(
            "kg.api.routes.schema.GROUP_COLORS", {}
        ):
            resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        body = resp.json()
        assert body["labels"] == []
        assert body["relationshipTypes"] == []
        assert body["totalLabels"] == 0
        assert body["totalRelationshipTypes"] == 0

    def test_schema_label_info_has_group_and_color_fields(self, dev_config: AppConfig):
        """Each label entry in the response contains group, color, count fields."""
        session = MockNeo4jSession(
            side_effects=[
                MockNeo4jResult([_label_record("Vessel")]),
                MockNeo4jResult([]),
                MockNeo4jResult([_count_record(3)]),
            ]
        )
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.schema.ENTITY_GROUPS", {}), patch(
            "kg.api.routes.schema.GROUP_COLORS", {}
        ), patch(
            "kg.api.routes.schema.get_group_for_label",
            return_value="PhysicalEntity",
        ), patch(
            "kg.api.routes.schema.get_color_for_label",
            return_value="#FF0000",
        ):
            resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        body = resp.json()
        vessel = body["labels"][0]
        assert vessel["label"] == "Vessel"
        assert vessel["group"] == "PhysicalEntity"
        assert vessel["color"] == "#FF0000"
        assert vessel["count"] == 3


# ---------------------------------------------------------------------------
# TestSchemaImportErrorFallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaImportErrorFallback:
    """Tests for the ImportError fallback (lines 18-26).

    The fallback code is executed at module import time when
    ``maritime.entity_groups`` is unavailable. We test this by reloading
    the module with the import blocked.
    """

    def test_fallback_functions_return_default_values(self):
        """When maritime.entity_groups is unavailable, fallback functions return defaults."""
        import importlib

        # Save and remove maritime.entity_groups from sys.modules to force re-import
        saved_modules = {}
        keys_to_remove = [k for k in sys.modules if "maritime.entity_groups" in k or k == "maritime.entity_groups"]
        for k in keys_to_remove:
            saved_modules[k] = sys.modules.pop(k)

        # Also remove the schema module so it re-imports
        schema_key = None
        for k in list(sys.modules.keys()):
            if "kg.api.routes.schema" in k:
                schema_key = k
                saved_modules[k] = sys.modules.pop(k)

        try:
            # Block maritime.entity_groups import
            with patch.dict(sys.modules, {"maritime.entity_groups": None}):
                # Re-import the schema module — the try/except ImportError block runs
                import kg.api.routes.schema as schema_module
                importlib.reload(schema_module)

                # Fallback get_color_for_label should return "#999999"
                assert schema_module.get_color_for_label("AnyLabel") == "#999999"
                # Fallback get_group_for_label should return "unknown"
                assert schema_module.get_group_for_label("AnyLabel") == "unknown"
                # Fallback dicts should be empty
                assert schema_module.ENTITY_GROUPS == {}
                assert schema_module.GROUP_COLORS == {}
        finally:
            # Restore original modules
            for k, v in saved_modules.items():
                sys.modules[k] = v

    def test_fallback_color_is_grey(self):
        """The fallback color #999999 is a neutral grey."""
        import importlib

        saved_modules = {}
        for k in list(sys.modules.keys()):
            if "maritime.entity_groups" in k:
                saved_modules[k] = sys.modules.pop(k)
            if "kg.api.routes.schema" in k:
                saved_modules[k] = sys.modules.pop(k)

        try:
            with patch.dict(sys.modules, {"maritime.entity_groups": None}):
                import kg.api.routes.schema as schema_module
                importlib.reload(schema_module)

                color = schema_module.get_color_for_label("VesselType")
                assert color == "#999999"
        finally:
            for k, v in saved_modules.items():
                sys.modules[k] = v

    def test_fallback_group_is_unknown(self):
        """The fallback group name is 'unknown'."""
        import importlib

        saved_modules = {}
        for k in list(sys.modules.keys()):
            if "maritime.entity_groups" in k:
                saved_modules[k] = sys.modules.pop(k)
            if "kg.api.routes.schema" in k:
                saved_modules[k] = sys.modules.pop(k)

        try:
            with patch.dict(sys.modules, {"maritime.entity_groups": None}):
                import kg.api.routes.schema as schema_module
                importlib.reload(schema_module)

                group = schema_module.get_group_for_label("SomeLabel")
                assert group == "unknown"
        finally:
            for k, v in saved_modules.items():
                sys.modules[k] = v
