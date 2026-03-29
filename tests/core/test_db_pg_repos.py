"""Tests for PostgreSQL repository implementations and connection utilities.

Covers:
- PgWorkflowRepository: create, get, list_all, update, delete, _row_to_dict
- PgDocumentRepository: create, list, delete, _row_to_dict
- connection.py: get_pg_pool singleton, failure fallback, reset, close
- redis_client.py: get_redis_client singleton, failure fallback, reset, close
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kg.db.pg_workflow_repo import PgWorkflowRepository
from kg.db.pg_document_repo import PgDocumentRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(coro: Any) -> Any:
    """Run a coroutine synchronously for test purposes."""
    return asyncio.run(coro)


def _make_pool(conn: MagicMock) -> MagicMock:
    """Build a minimal asyncpg pool mock that yields *conn* on acquire()."""
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return pool


def _dt_row(dt: datetime) -> datetime:
    """Return a datetime object (simulates asyncpg returning datetime)."""
    return dt


# ---------------------------------------------------------------------------
# PgWorkflowRepository
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPgWorkflowRepository:
    """Unit tests for PgWorkflowRepository (all DB calls mocked)."""

    # ------------------------------------------------------------------
    # create()
    # ------------------------------------------------------------------

    def test_create_returns_dict_with_all_fields(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgWorkflowRepository(_make_pool(conn))

        nodes = [{"id": "n1", "type": "vessel"}]
        edges = [{"id": "e1", "source": "n1", "target": "n2"}]
        viewport = {"x": 0, "y": 0, "zoom": 1}

        result = run(repo.create("wf1", "My Flow", "desc", nodes, edges, viewport))

        assert result["id"] == "wf1"
        assert result["name"] == "My Flow"
        assert result["description"] == "desc"
        assert result["nodes"] == nodes
        assert result["edges"] == edges
        assert result["viewport"] == viewport
        assert "created_at" in result
        assert "updated_at" in result

    def test_create_calls_execute_once(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgWorkflowRepository(_make_pool(conn))

        run(repo.create("wf1", "Flow", "", [], [], {}))

        conn.execute.assert_awaited_once()

    def test_create_passes_json_dumps_to_execute(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgWorkflowRepository(_make_pool(conn))

        nodes = [{"id": "n1"}]
        run(repo.create("wf1", "Flow", "", nodes, [], {}))

        call_args = conn.execute.await_args[0]
        # positional: sql(0), wf_id(1), name(2), desc(3), nodes(4), edges(5), viewport(6), now(7), now(8)
        assert call_args[4] == json.dumps(nodes)
        assert call_args[5] == json.dumps([])
        assert call_args[6] == json.dumps({})

    def test_create_timestamps_are_iso_strings(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.create("wf1", "Flow", "", [], [], {}))

        # Should be parseable ISO 8601 strings
        datetime.fromisoformat(result["created_at"])
        datetime.fromisoformat(result["updated_at"])

    def test_create_with_empty_nodes_and_edges(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.create("wf_empty", "Empty", "", [], [], {}))

        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["viewport"] == {}

    # ------------------------------------------------------------------
    # get()
    # ------------------------------------------------------------------

    def test_get_returns_dict_when_row_found(self) -> None:
        now = datetime.now(timezone.utc)
        row = {
            "id": "wf1",
            "name": "My Flow",
            "description": "desc",
            "nodes": [{"id": "n1"}],
            "edges": [],
            "viewport": {"zoom": 1},
            "created_at": now,
            "updated_at": now,
        }
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=row)
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.get("wf1"))

        assert result is not None
        assert result["id"] == "wf1"
        assert result["name"] == "My Flow"

    def test_get_returns_none_when_not_found(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.get("nope"))

        assert result is None

    def test_get_calls_fetchrow_with_correct_id(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        repo = PgWorkflowRepository(_make_pool(conn))

        run(repo.get("target_id"))

        call_args = conn.fetchrow.await_args[0]
        assert "target_id" in call_args

    # ------------------------------------------------------------------
    # list_all()
    # ------------------------------------------------------------------

    def test_list_all_returns_list_of_dicts(self) -> None:
        now = datetime.now(timezone.utc)
        rows = [
            {
                "id": "w1",
                "name": "Flow 1",
                "description": "",
                "nodes": [],
                "edges": [],
                "viewport": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "w2",
                "name": "Flow 2",
                "description": "",
                "nodes": [],
                "edges": [],
                "viewport": {},
                "created_at": now,
                "updated_at": now,
            },
        ]
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=rows)
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.list_all())

        assert len(result) == 2
        assert result[0]["id"] == "w1"
        assert result[1]["id"] == "w2"

    def test_list_all_returns_empty_list_when_no_rows(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.list_all())

        assert result == []

    def test_list_all_calls_fetch_once(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        repo = PgWorkflowRepository(_make_pool(conn))

        run(repo.list_all())

        conn.fetch.assert_awaited_once()

    # ------------------------------------------------------------------
    # update()
    # ------------------------------------------------------------------

    def test_update_returns_dict_when_found(self) -> None:
        now = datetime.now(timezone.utc)
        row = {
            "id": "wf1",
            "name": "Updated",
            "description": "new desc",
            "nodes": [{"id": "n2"}],
            "edges": [],
            "viewport": {},
            "created_at": now,
            "updated_at": now,
        }
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=row)
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.update("wf1", "Updated", "new desc", [{"id": "n2"}], [], {}))

        assert result is not None
        assert result["name"] == "Updated"
        assert result["description"] == "new desc"
        assert result["nodes"] == [{"id": "n2"}]

    def test_update_returns_none_when_not_found(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.update("nope", "N", "", [], [], {}))

        assert result is None

    def test_update_calls_fetchrow_with_correct_id(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        repo = PgWorkflowRepository(_make_pool(conn))

        run(repo.update("target_wf", "N", "", [], [], {}))

        call_args = conn.fetchrow.await_args[0]
        assert "target_wf" in call_args

    def test_update_passes_json_dumps(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        repo = PgWorkflowRepository(_make_pool(conn))

        nodes = [{"id": "x"}]
        run(repo.update("wf1", "N", "", nodes, [], {}))

        call_args = conn.fetchrow.await_args[0]
        assert json.dumps(nodes) in call_args

    # ------------------------------------------------------------------
    # delete()
    # ------------------------------------------------------------------

    def test_delete_returns_true_when_found(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"id": "wf1"})
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.delete("wf1"))

        assert result is True

    def test_delete_returns_false_when_not_found(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        repo = PgWorkflowRepository(_make_pool(conn))

        result = run(repo.delete("nope"))

        assert result is False

    def test_delete_calls_fetchrow_with_correct_id(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        repo = PgWorkflowRepository(_make_pool(conn))

        run(repo.delete("target_id"))

        call_args = conn.fetchrow.await_args[0]
        assert "target_id" in call_args

    # ------------------------------------------------------------------
    # _row_to_dict() — static method, no DB needed
    # ------------------------------------------------------------------

    def test_row_to_dict_with_datetime_objects(self) -> None:
        now = datetime.now(timezone.utc)
        row = {
            "id": "w1",
            "name": "Flow",
            "description": "desc",
            "nodes": [{"id": "n1"}],
            "edges": [],
            "viewport": {"zoom": 1},
            "created_at": now,
            "updated_at": now,
        }

        result = PgWorkflowRepository._row_to_dict(row)

        assert result["id"] == "w1"
        assert result["name"] == "Flow"
        assert result["created_at"] == now.isoformat()
        assert result["updated_at"] == now.isoformat()

    def test_row_to_dict_with_json_string_nodes(self) -> None:
        """JSONB columns arriving as raw JSON strings (e.g. from mock drivers)."""
        now = datetime.now(timezone.utc)
        nodes = [{"id": "n1"}]
        edges = [{"id": "e1"}]
        viewport = {"zoom": 2}
        row = {
            "id": "w1",
            "name": "Flow",
            "description": "",
            "nodes": json.dumps(nodes),
            "edges": json.dumps(edges),
            "viewport": json.dumps(viewport),
            "created_at": now,
            "updated_at": now,
        }

        result = PgWorkflowRepository._row_to_dict(row)

        assert result["nodes"] == nodes
        assert result["edges"] == edges
        assert result["viewport"] == viewport

    def test_row_to_dict_with_dict_nodes(self) -> None:
        """JSONB columns already parsed as Python objects (normal asyncpg)."""
        now = datetime.now(timezone.utc)
        nodes = [{"id": "n1"}]
        row = {
            "id": "w1",
            "name": "Flow",
            "description": "",
            "nodes": nodes,
            "edges": [],
            "viewport": {},
            "created_at": now,
            "updated_at": now,
        }

        result = PgWorkflowRepository._row_to_dict(row)

        assert result["nodes"] == nodes

    def test_row_to_dict_with_string_timestamps(self) -> None:
        """Timestamps arriving as ISO strings (not datetime objects)."""
        iso = "2026-03-26T12:00:00+00:00"
        row = {
            "id": "w1",
            "name": "Flow",
            "description": "",
            "nodes": [],
            "edges": [],
            "viewport": {},
            "created_at": iso,
            "updated_at": iso,
        }

        result = PgWorkflowRepository._row_to_dict(row)

        # Should pass through as-is when no isoformat() method
        assert result["created_at"] == iso
        assert result["updated_at"] == iso

    def test_row_to_dict_strips_no_extra_fields(self) -> None:
        """Only expected keys are present."""
        now = datetime.now(timezone.utc)
        row = {
            "id": "w1",
            "name": "Flow",
            "description": "",
            "nodes": [],
            "edges": [],
            "viewport": {},
            "created_at": now,
            "updated_at": now,
        }

        result = PgWorkflowRepository._row_to_dict(row)

        expected_keys = {"id", "name", "description", "nodes", "edges", "viewport", "created_at", "updated_at"}
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# PgDocumentRepository
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPgDocumentRepository:
    """Unit tests for PgDocumentRepository (all DB calls mocked)."""

    # ------------------------------------------------------------------
    # create()
    # ------------------------------------------------------------------

    def test_create_returns_dict_with_all_fields(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgDocumentRepository(_make_pool(conn))

        result = run(repo.create("doc1", "report.pdf", 2048, "application/pdf", "Annual report", "uploaded", 5))

        assert result["id"] == "doc1"
        assert result["filename"] == "report.pdf"
        assert result["size"] == 2048
        assert result["content_type"] == "application/pdf"
        assert result["description"] == "Annual report"
        assert result["status"] == "uploaded"
        assert result["chunks"] == 5
        assert "created_at" in result

    def test_create_calls_execute_once(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgDocumentRepository(_make_pool(conn))

        run(repo.create("doc1", "file.txt", 100, "text/plain", "", "uploaded", 0))

        conn.execute.assert_awaited_once()

    def test_create_timestamp_is_iso_string(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgDocumentRepository(_make_pool(conn))

        result = run(repo.create("doc1", "file.txt", 100, "text/plain", "", "uploaded", 0))

        datetime.fromisoformat(result["created_at"])

    def test_create_passes_all_args_to_execute(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgDocumentRepository(_make_pool(conn))

        run(repo.create("doc1", "report.pdf", 1024, "application/pdf", "desc", "ingested", 10))

        call_args = conn.execute.await_args[0]
        assert "doc1" in call_args
        assert "report.pdf" in call_args
        assert 1024 in call_args
        assert "application/pdf" in call_args
        assert "desc" in call_args
        assert "ingested" in call_args
        assert 10 in call_args

    def test_create_with_zero_chunks(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock()
        repo = PgDocumentRepository(_make_pool(conn))

        result = run(repo.create("doc_zero", "empty.txt", 0, "text/plain", "", "uploaded", 0))

        assert result["chunks"] == 0
        assert result["size"] == 0

    # ------------------------------------------------------------------
    # list()
    # ------------------------------------------------------------------

    def test_list_returns_docs_and_total(self) -> None:
        now = datetime.now(timezone.utc)
        rows = [
            {
                "id": "d1",
                "filename": "a.pdf",
                "size": 100,
                "content_type": "application/pdf",
                "description": "",
                "status": "uploaded",
                "chunks": 3,
                "created_at": now,
                "total_count": 2,
            },
            {
                "id": "d2",
                "filename": "b.pdf",
                "size": 200,
                "content_type": "application/pdf",
                "description": "",
                "status": "ingested",
                "chunks": 5,
                "created_at": now,
                "total_count": 2,
            },
        ]
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=rows)
        repo = PgDocumentRepository(_make_pool(conn))

        docs, total = run(repo.list())

        assert total == 2
        assert len(docs) == 2
        assert docs[0]["id"] == "d1"
        assert docs[1]["id"] == "d2"

    def test_list_returns_empty_when_no_rows(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        repo = PgDocumentRepository(_make_pool(conn))

        docs, total = run(repo.list())

        assert docs == []
        assert total == 0

    def test_list_uses_default_limit_and_offset(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        repo = PgDocumentRepository(_make_pool(conn))

        run(repo.list())

        call_args = conn.fetch.await_args[0]
        assert 50 in call_args  # default limit
        assert 0 in call_args   # default offset

    def test_list_passes_custom_limit_and_offset(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        repo = PgDocumentRepository(_make_pool(conn))

        run(repo.list(limit=10, offset=20))

        call_args = conn.fetch.await_args[0]
        assert 10 in call_args
        assert 20 in call_args

    def test_list_strips_total_count_from_docs(self) -> None:
        now = datetime.now(timezone.utc)
        rows = [
            {
                "id": "d1",
                "filename": "a.pdf",
                "size": 100,
                "content_type": "application/pdf",
                "description": "",
                "status": "uploaded",
                "chunks": 0,
                "created_at": now,
                "total_count": 1,
            }
        ]
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=rows)
        repo = PgDocumentRepository(_make_pool(conn))

        docs, _total = run(repo.list())

        assert "total_count" not in docs[0]

    def test_list_single_row_total_is_one(self) -> None:
        now = datetime.now(timezone.utc)
        rows = [
            {
                "id": "d1",
                "filename": "a.pdf",
                "size": 100,
                "content_type": "application/pdf",
                "description": "",
                "status": "uploaded",
                "chunks": 0,
                "created_at": now,
                "total_count": 1,
            }
        ]
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=rows)
        repo = PgDocumentRepository(_make_pool(conn))

        docs, total = run(repo.list())

        assert total == 1
        assert len(docs) == 1

    # ------------------------------------------------------------------
    # delete()
    # ------------------------------------------------------------------

    def test_delete_returns_true_when_found(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"id": "doc1"})
        repo = PgDocumentRepository(_make_pool(conn))

        result = run(repo.delete("doc1"))

        assert result is True

    def test_delete_returns_false_when_not_found(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        repo = PgDocumentRepository(_make_pool(conn))

        result = run(repo.delete("nope"))

        assert result is False

    def test_delete_calls_fetchrow_with_correct_id(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        repo = PgDocumentRepository(_make_pool(conn))

        run(repo.delete("target_doc"))

        call_args = conn.fetchrow.await_args[0]
        assert "target_doc" in call_args

    # ------------------------------------------------------------------
    # _row_to_dict() — static method
    # ------------------------------------------------------------------

    def test_row_to_dict_with_datetime_created_at(self) -> None:
        now = datetime.now(timezone.utc)
        row = {
            "id": "d1",
            "filename": "report.pdf",
            "size": 1024,
            "content_type": "application/pdf",
            "description": "A report",
            "status": "ingested",
            "chunks": 7,
            "created_at": now,
            "total_count": 5,
        }

        result = PgDocumentRepository._row_to_dict(row)

        assert result["id"] == "d1"
        assert result["created_at"] == now.isoformat()
        assert "total_count" not in result

    def test_row_to_dict_with_string_created_at(self) -> None:
        """created_at arriving as ISO string passes through unchanged."""
        iso = "2026-03-26T12:00:00+00:00"
        row = {
            "id": "d1",
            "filename": "f.txt",
            "size": 0,
            "content_type": "text/plain",
            "description": "",
            "status": "uploaded",
            "chunks": 0,
            "created_at": iso,
            "total_count": 1,
        }

        result = PgDocumentRepository._row_to_dict(row)

        assert result["created_at"] == iso

    def test_row_to_dict_strips_total_count(self) -> None:
        now = datetime.now(timezone.utc)
        row = {
            "id": "d1",
            "filename": "f.txt",
            "size": 0,
            "content_type": "text/plain",
            "description": "",
            "status": "uploaded",
            "chunks": 0,
            "created_at": now,
            "total_count": 99,
        }

        result = PgDocumentRepository._row_to_dict(row)

        assert "total_count" not in result

    def test_row_to_dict_contains_expected_keys(self) -> None:
        now = datetime.now(timezone.utc)
        row = {
            "id": "d1",
            "filename": "f.txt",
            "size": 0,
            "content_type": "text/plain",
            "description": "",
            "status": "uploaded",
            "chunks": 0,
            "created_at": now,
            "total_count": 1,
        }

        result = PgDocumentRepository._row_to_dict(row)

        expected_keys = {"id", "filename", "size", "content_type", "description", "status", "chunks", "created_at"}
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# connection.py — get_pg_pool / close_pg_pool / reset_pg_pool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetPgPool:
    """Unit tests for the asyncpg connection pool singleton."""

    def setup_method(self) -> None:
        """Reset singleton state before each test."""
        import kg.db.connection as conn_mod
        conn_mod.reset_pg_pool()

    def teardown_method(self) -> None:
        """Clean up singleton after each test."""
        import kg.db.connection as conn_mod
        conn_mod.reset_pg_pool()

    def test_returns_pool_on_success(self) -> None:
        """When asyncpg and config are available, get_pg_pool returns a pool."""
        fake_pool = MagicMock()
        mock_config = MagicMock()
        mock_config.postgres.host = "localhost"
        mock_config.postgres.port = 5432
        mock_config.postgres.user = "pg"
        mock_config.postgres.password = "pw"
        mock_config.postgres.database = "imsp"
        mock_config.postgres.min_pool_size = 2
        mock_config.postgres.max_pool_size = 10
        mock_config.postgres.command_timeout = 30.0

        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=fake_pool)

        import kg.db.connection as conn_mod

        async def _run() -> Any:
            return await conn_mod.get_pg_pool()

        with (
            patch.dict(sys.modules, {"asyncpg": mock_asyncpg}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            conn_mod.reset_pg_pool()
            pool = asyncio.run(_run())

        assert pool is fake_pool

    def test_returns_none_on_import_error(self) -> None:
        """When asyncpg is not installed, get_pg_pool returns None."""
        import kg.db.connection as conn_mod

        original = sys.modules.get("asyncpg")
        sys.modules["asyncpg"] = None  # type: ignore[assignment]
        conn_mod.reset_pg_pool()

        try:
            pool = run(conn_mod.get_pg_pool())
            assert pool is None
        finally:
            if original is None:
                sys.modules.pop("asyncpg", None)
            else:
                sys.modules["asyncpg"] = original
            conn_mod.reset_pg_pool()

    def test_returns_none_on_connection_failure(self) -> None:
        """When asyncpg.create_pool raises, get_pg_pool returns None."""
        import kg.db.connection as conn_mod

        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(side_effect=OSError("connection refused"))
        mock_config = MagicMock()

        with (
            patch.dict(sys.modules, {"asyncpg": mock_asyncpg}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            conn_mod.reset_pg_pool()
            pool = run(conn_mod.get_pg_pool())

        assert pool is None

    def test_singleton_returns_same_pool(self) -> None:
        """Second call returns the cached pool without re-creating."""
        fake_pool = MagicMock()
        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=fake_pool)
        mock_config = MagicMock()

        import kg.db.connection as conn_mod

        with (
            patch.dict(sys.modules, {"asyncpg": mock_asyncpg}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            conn_mod.reset_pg_pool()
            pool1 = run(conn_mod.get_pg_pool())
            pool2 = run(conn_mod.get_pg_pool())

        assert pool1 is pool2
        mock_asyncpg.create_pool.assert_awaited_once()

    def test_reset_clears_pool(self) -> None:
        """reset_pg_pool() causes next call to re-create the pool."""
        fake_pool = MagicMock()
        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=fake_pool)
        mock_config = MagicMock()

        import kg.db.connection as conn_mod

        with (
            patch.dict(sys.modules, {"asyncpg": mock_asyncpg}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            conn_mod.reset_pg_pool()
            run(conn_mod.get_pg_pool())
            conn_mod.reset_pg_pool()
            run(conn_mod.get_pg_pool())

        assert mock_asyncpg.create_pool.await_count == 2

    def test_close_pg_pool_calls_pool_close(self) -> None:
        """close_pg_pool() awaits pool.close()."""
        fake_pool = MagicMock()
        fake_pool.close = AsyncMock()
        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=fake_pool)
        mock_config = MagicMock()

        import kg.db.connection as conn_mod

        with (
            patch.dict(sys.modules, {"asyncpg": mock_asyncpg}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            conn_mod.reset_pg_pool()
            run(conn_mod.get_pg_pool())
            run(conn_mod.close_pg_pool())

        fake_pool.close.assert_awaited_once()

    def test_close_pg_pool_is_idempotent(self) -> None:
        """close_pg_pool() can be called multiple times without error."""
        import kg.db.connection as conn_mod

        conn_mod.reset_pg_pool()
        # No pool set, just call close — should not raise
        run(conn_mod.close_pg_pool())
        run(conn_mod.close_pg_pool())

    def test_close_pg_pool_resets_reference(self) -> None:
        """After close, singleton reference is set to None."""
        fake_pool = MagicMock()
        fake_pool.close = AsyncMock()
        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=fake_pool)
        mock_config = MagicMock()

        import kg.db.connection as conn_mod

        with (
            patch.dict(sys.modules, {"asyncpg": mock_asyncpg}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            conn_mod.reset_pg_pool()
            run(conn_mod.get_pg_pool())
            run(conn_mod.close_pg_pool())

        assert conn_mod._pool is None

    def test_reset_pg_pool_sets_none_without_closing(self) -> None:
        """reset_pg_pool() clears the reference but does NOT close the pool."""
        fake_pool = MagicMock()
        fake_pool.close = AsyncMock()
        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=fake_pool)
        mock_config = MagicMock()

        import kg.db.connection as conn_mod

        with (
            patch.dict(sys.modules, {"asyncpg": mock_asyncpg}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            conn_mod.reset_pg_pool()
            run(conn_mod.get_pg_pool())
            conn_mod.reset_pg_pool()

        fake_pool.close.assert_not_awaited()
        assert conn_mod._pool is None


# ---------------------------------------------------------------------------
# redis_client.py — get_redis_client / close_redis_client / reset_redis_client
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetRedisClient:
    """Unit tests for the Redis client singleton."""

    def setup_method(self) -> None:
        """Reset singleton state before each test."""
        import kg.db.redis_client as rc_mod
        rc_mod.reset_redis_client()

    def teardown_method(self) -> None:
        """Clean up singleton after each test."""
        import kg.db.redis_client as rc_mod
        rc_mod.reset_redis_client()

    def test_returns_client_on_success(self) -> None:
        import kg.db.redis_client as rc_mod

        fake_client = MagicMock()
        fake_client.ping = MagicMock(return_value=True)
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url = MagicMock(return_value=fake_client)
        mock_config = MagicMock()
        mock_config.redis.url = "redis://localhost:6379/1"

        with (
            patch.dict(sys.modules, {"redis": mock_redis_mod}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            rc_mod.reset_redis_client()
            client = rc_mod.get_redis_client()

        assert client is fake_client

    def test_returns_none_on_import_error(self) -> None:
        """When redis package is not installed, returns None."""
        import kg.db.redis_client as rc_mod

        original = sys.modules.get("redis")
        sys.modules["redis"] = None  # type: ignore[assignment]
        rc_mod.reset_redis_client()

        try:
            client = rc_mod.get_redis_client()
            assert client is None
        finally:
            if original is None:
                sys.modules.pop("redis", None)
            else:
                sys.modules["redis"] = original
            rc_mod.reset_redis_client()

    def test_returns_none_on_ping_failure(self) -> None:
        """When ping() raises, get_redis_client returns None."""
        import kg.db.redis_client as rc_mod

        fake_client = MagicMock()
        fake_client.ping = MagicMock(side_effect=Exception("connection refused"))
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url = MagicMock(return_value=fake_client)
        mock_config = MagicMock()
        mock_config.redis.url = "redis://localhost:6379/1"

        with (
            patch.dict(sys.modules, {"redis": mock_redis_mod}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            rc_mod.reset_redis_client()
            client = rc_mod.get_redis_client()

        assert client is None

    def test_returns_none_on_from_url_failure(self) -> None:
        """When redis.from_url() raises, returns None."""
        import kg.db.redis_client as rc_mod

        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url = MagicMock(side_effect=Exception("bad url"))
        mock_config = MagicMock()
        mock_config.redis.url = "redis://badhost"

        with (
            patch.dict(sys.modules, {"redis": mock_redis_mod}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            rc_mod.reset_redis_client()
            client = rc_mod.get_redis_client()

        assert client is None

    def test_singleton_returns_same_client(self) -> None:
        """Second call returns cached client without re-connecting."""
        import kg.db.redis_client as rc_mod

        fake_client = MagicMock()
        fake_client.ping = MagicMock(return_value=True)
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url = MagicMock(return_value=fake_client)
        mock_config = MagicMock()
        mock_config.redis.url = "redis://localhost:6379/1"

        with (
            patch.dict(sys.modules, {"redis": mock_redis_mod}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            rc_mod.reset_redis_client()
            c1 = rc_mod.get_redis_client()
            c2 = rc_mod.get_redis_client()

        assert c1 is c2
        mock_redis_mod.from_url.assert_called_once()

    def test_reset_clears_client(self) -> None:
        """reset_redis_client() causes next call to re-create client."""
        import kg.db.redis_client as rc_mod

        fake_client = MagicMock()
        fake_client.ping = MagicMock(return_value=True)
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url = MagicMock(return_value=fake_client)
        mock_config = MagicMock()
        mock_config.redis.url = "redis://localhost:6379/1"

        with (
            patch.dict(sys.modules, {"redis": mock_redis_mod}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            rc_mod.reset_redis_client()
            rc_mod.get_redis_client()
            rc_mod.reset_redis_client()
            rc_mod.get_redis_client()

        assert mock_redis_mod.from_url.call_count == 2

    def test_close_redis_client_calls_close(self) -> None:
        """close_redis_client() calls client.close()."""
        import kg.db.redis_client as rc_mod

        fake_client = MagicMock()
        fake_client.ping = MagicMock(return_value=True)
        fake_client.close = MagicMock()
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url = MagicMock(return_value=fake_client)
        mock_config = MagicMock()
        mock_config.redis.url = "redis://localhost:6379/1"

        with (
            patch.dict(sys.modules, {"redis": mock_redis_mod}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            rc_mod.reset_redis_client()
            rc_mod.get_redis_client()
            rc_mod.close_redis_client()

        fake_client.close.assert_called_once()

    def test_close_redis_client_is_idempotent(self) -> None:
        """close_redis_client() can be called multiple times without error."""
        import kg.db.redis_client as rc_mod

        rc_mod.reset_redis_client()
        rc_mod.close_redis_client()
        rc_mod.close_redis_client()

    def test_close_redis_client_resets_reference(self) -> None:
        """After close, singleton reference is set to None."""
        import kg.db.redis_client as rc_mod

        fake_client = MagicMock()
        fake_client.ping = MagicMock(return_value=True)
        fake_client.close = MagicMock()
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url = MagicMock(return_value=fake_client)
        mock_config = MagicMock()
        mock_config.redis.url = "redis://localhost:6379/1"

        with (
            patch.dict(sys.modules, {"redis": mock_redis_mod}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            rc_mod.reset_redis_client()
            rc_mod.get_redis_client()
            rc_mod.close_redis_client()

        assert rc_mod._redis_client is None

    def test_reset_redis_client_sets_none_without_closing(self) -> None:
        """reset_redis_client() clears reference but does NOT close the client."""
        import kg.db.redis_client as rc_mod

        fake_client = MagicMock()
        fake_client.ping = MagicMock(return_value=True)
        fake_client.close = MagicMock()
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url = MagicMock(return_value=fake_client)
        mock_config = MagicMock()
        mock_config.redis.url = "redis://localhost:6379/1"

        with (
            patch.dict(sys.modules, {"redis": mock_redis_mod}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            rc_mod.reset_redis_client()
            rc_mod.get_redis_client()
            rc_mod.reset_redis_client()

        fake_client.close.assert_not_called()
        assert rc_mod._redis_client is None

    def test_from_url_called_with_correct_url(self) -> None:
        """redis.from_url is called with the URL from config."""
        import kg.db.redis_client as rc_mod

        fake_client = MagicMock()
        fake_client.ping = MagicMock(return_value=True)
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url = MagicMock(return_value=fake_client)
        mock_config = MagicMock()
        mock_config.redis.url = "redis://myredis:6379/1"

        with (
            patch.dict(sys.modules, {"redis": mock_redis_mod}),
            patch("kg.config.get_config", return_value=mock_config),
        ):
            rc_mod.reset_redis_client()
            rc_mod.get_redis_client()

        mock_redis_mod.from_url.assert_called_once_with(
            "redis://myredis:6379/1", decode_responses=True
        )
