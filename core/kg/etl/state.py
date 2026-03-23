"""ETL run state persistence using SQLite.

Provides a lightweight SQLite-backed store for tracking ETL pipeline
run records across server restarts.  Uses only the Python standard
library (no external dependencies).

Example::

    store = ETLStateStore()
    record = ETLRunRecord(
        run_id="abc-123",
        pipeline_name="papers",
        status="running",
        started_at=time.time(),
    )
    store.save_run(record)
    store.update_status("abc-123", "completed", record_count=42)
    run = store.get_run("abc-123")
    assert run.status == "completed"
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default database directory (relative to working directory)
_DEFAULT_DB_DIR = ".imsp"
_DEFAULT_DB_NAME = "etl_state.db"


@dataclass(frozen=True)
class ETLRunRecord:
    """Immutable record of a single ETL pipeline run.

    Attributes:
        run_id: Unique run identifier (UUID string).
        pipeline_name: Name of the ETL pipeline (e.g., "papers").
        status: Lifecycle status — "pending", "running", "completed", "failed".
        started_at: Unix timestamp when the run started.
        completed_at: Unix timestamp when the run finished.  0.0 if still running.
        record_count: Number of records processed. 0 until completed.
        error: Error message string if status is "failed".
        metadata: Arbitrary extra data stored as JSON.
    """

    run_id: str
    pipeline_name: str
    status: str
    started_at: float
    completed_at: float = 0.0
    record_count: int = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ETLStateStore:
    """SQLite-backed ETL run state store.

    Creates a ``etl_runs`` table in a SQLite database file and provides
    CRUD operations for :class:`ETLRunRecord` objects.

    The database file is created at ``db_path``.  If ``db_path`` is an
    empty string the default location ``.imsp/etl_state.db`` (relative
    to the current working directory) is used.

    Args:
        db_path: Absolute or relative path to the SQLite database file.
            Defaults to ``".imsp/etl_state.db"``.

    Example::

        store = ETLStateStore()
        record = ETLRunRecord(
            run_id="abc-123",
            pipeline_name="papers",
            status="running",
            started_at=time.time(),
        )
        store.save_run(record)
    """

    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS etl_runs (
            run_id       TEXT    PRIMARY KEY,
            pipeline_name TEXT   NOT NULL,
            status        TEXT   NOT NULL,
            started_at    REAL   NOT NULL,
            completed_at  REAL   NOT NULL DEFAULT 0.0,
            record_count  INTEGER NOT NULL DEFAULT 0,
            error         TEXT   NOT NULL DEFAULT '',
            metadata_json TEXT   NOT NULL DEFAULT '{}'
        )
    """

    def __init__(self, db_path: str = "") -> None:
        if not db_path:
            db_dir = os.path.join(os.getcwd(), _DEFAULT_DB_DIR)
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, _DEFAULT_DB_NAME)

        self._db_path = db_path
        self._init_db()
        logger.debug("ETLStateStore initialised: db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with row_factory set.

        Returns:
            A connected :class:`sqlite3.Connection` with
            ``row_factory = sqlite3.Row``.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create the ``etl_runs`` table if it does not exist."""
        with self._connect() as conn:
            conn.execute(self._CREATE_TABLE_SQL)
            conn.commit()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ETLRunRecord:
        """Convert a SQLite row to an :class:`ETLRunRecord`.

        Args:
            row: A ``sqlite3.Row`` from the ``etl_runs`` table.

        Returns:
            Corresponding :class:`ETLRunRecord` (frozen dataclass).
        """
        metadata: dict[str, Any] = {}
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            metadata = {}

        return ETLRunRecord(
            run_id=row["run_id"],
            pipeline_name=row["pipeline_name"],
            status=row["status"],
            started_at=float(row["started_at"]),
            completed_at=float(row["completed_at"]),
            record_count=int(row["record_count"]),
            error=row["error"] or "",
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_run(self, record: ETLRunRecord) -> None:
        """Insert or replace an :class:`ETLRunRecord` in the store.

        Uses ``INSERT OR REPLACE`` semantics — if a record with the same
        ``run_id`` exists it is fully replaced.

        Args:
            record: The run record to persist.
        """
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO etl_runs
                    (run_id, pipeline_name, status, started_at, completed_at,
                     record_count, error, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.pipeline_name,
                    record.status,
                    record.started_at,
                    record.completed_at,
                    record.record_count,
                    record.error,
                    json.dumps(record.metadata),
                ),
            )
            conn.commit()
        logger.debug("Saved ETL run: run_id=%s status=%s", record.run_id, record.status)

    def get_run(self, run_id: str) -> ETLRunRecord | None:
        """Retrieve a single run record by ID.

        Args:
            run_id: Unique run identifier.

        Returns:
            The matching :class:`ETLRunRecord`, or ``None`` if not found.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM etl_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_runs(self, limit: int = 20, pipeline: str = "") -> list[ETLRunRecord]:
        """List run records ordered by ``started_at`` descending (most recent first).

        Args:
            limit: Maximum number of records to return. Defaults to 20.
            pipeline: Optional pipeline name filter. Empty string returns all.

        Returns:
            Sorted list of :class:`ETLRunRecord` objects.
        """
        if pipeline:
            sql = """
                SELECT * FROM etl_runs
                WHERE pipeline_name = ?
                ORDER BY started_at DESC
                LIMIT ?
            """
            args: tuple[Any, ...] = (pipeline, limit)
        else:
            sql = "SELECT * FROM etl_runs ORDER BY started_at DESC LIMIT ?"
            args = (limit,)

        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()

        return [self._row_to_record(row) for row in rows]

    def update_status(
        self,
        run_id: str,
        status: str,
        **kwargs: Any,
    ) -> None:
        """Update the status (and optional fields) of an existing run record.

        Supported keyword arguments (all optional):

        - ``completed_at`` (float): completion Unix timestamp
        - ``record_count`` (int): number of processed records
        - ``error`` (str): error message

        If the run does not exist this method is a no-op.

        Args:
            run_id: Unique run identifier.
            status: New lifecycle status.
            **kwargs: Optional field updates (see above).
        """
        set_clauses: list[str] = ["status = ?"]
        values: list[Any] = [status]

        if "completed_at" in kwargs:
            set_clauses.append("completed_at = ?")
            values.append(float(kwargs["completed_at"]))
        if "record_count" in kwargs:
            set_clauses.append("record_count = ?")
            values.append(int(kwargs["record_count"]))
        if "error" in kwargs:
            set_clauses.append("error = ?")
            values.append(str(kwargs["error"]))

        values.append(run_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE etl_runs SET {', '.join(set_clauses)} WHERE run_id = ?",  # noqa: S608
                values,
            )
            conn.commit()
        logger.debug("Updated ETL run status: run_id=%s status=%s", run_id, status)
