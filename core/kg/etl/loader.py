"""Neo4j batch loader for ETL pipeline output.

Provides:
- Neo4jBatchLoader: generates parameterized MERGE cypher and loads
  record batches into Neo4j via a supplied session.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Neo4jBatchLoader:
    """Batch loader that MERGEs records into Neo4j by a unique identifier.

    The loader builds parameterized Cypher MERGE statements and executes
    them against a caller-supplied Neo4j session, making it easy to mock
    in tests.

    Args:
        label: The Neo4j node label to merge (e.g. ``"Vessel"``).
        id_field: The property used as the merge key (e.g. ``"vesselId"``).
        batch_size: Number of records per UNWIND batch.
        project: Optional project scoping context.  Accepts either a plain
            string (used as both the label suffix and property value) or an
            object with ``.label`` and ``.property_value`` attributes (e.g.
            a ``KGProjectContext`` instance).  When set, the generated MERGE
            pattern gains an extra label (``KG_<name>``) and each merged node
            gets a ``_kg_project`` property.  Defaults to ``None`` for full
            backward compatibility.
    """

    def __init__(
        self,
        label: str,
        id_field: str,
        batch_size: int = 500,
        project: Any | None = None,
    ) -> None:
        self._label = label
        self._id_field = id_field
        self._batch_size = batch_size
        self._project = project

    @property
    def label(self) -> str:
        """The Neo4j node label for this loader."""
        return self._label

    @property
    def id_field(self) -> str:
        """The property used as the MERGE key."""
        return self._id_field

    @property
    def batch_size(self) -> int:
        """Number of records per batch."""
        return self._batch_size

    def _build_merge_cypher(self) -> str:
        """Generate a parameterized MERGE + SET Cypher statement.

        Uses UNWIND to process a batch of records in a single transaction.
        The merge key is the ``id_field`` property; all other properties
        are set via ``SET n += row``.

        When ``project`` was supplied at construction time, the MERGE pattern
        gains an additional project label (``KG_<name>``) and the SET clause
        writes ``n._kg_project = '<name>'``.

        Returns:
            Cypher query string with a ``$batch`` parameter.
        """
        if self._project is not None:
            # Support both plain strings and objects with .label / .property_value
            if isinstance(self._project, str):
                proj_label = f"KG_{self._project}"
                proj_value = self._project
            else:
                proj_label = getattr(self._project, "label", f"KG_{self._project}")
                proj_value = getattr(
                    self._project, "property_value", str(self._project)
                )
            return (
                "UNWIND $batch AS row "
                f"MERGE (n:{self._label}:{proj_label} {{{self._id_field}: row.{self._id_field}}}) "
                f"SET n += row, n._kg_project = '{proj_value}'"
            )

        return (
            "UNWIND $batch AS row "
            f"MERGE (n:{self._label} {{{self._id_field}: row.{self._id_field}}}) "
            "SET n += row"
        )

    def load(self, records: list[dict[str, Any]], session: Any) -> int:
        """Load *records* into Neo4j using the supplied session.

        Records are split into batches of ``batch_size`` and executed
        as UNWIND MERGE statements.

        Args:
            records: List of property dicts to merge.
            session: A Neo4j session (or mock) supporting ``session.run(query, params)``.

        Returns:
            Number of records processed.
        """
        if not records:
            return 0

        cypher = self._build_merge_cypher()
        total = 0

        for i in range(0, len(records), self._batch_size):
            batch = records[i : i + self._batch_size]
            session.run(cypher, {"batch": batch})
            total += len(batch)
            logger.debug(
                "Loaded batch %d-%d (%d records) for label %s",
                i,
                i + len(batch),
                len(batch),
                self._label,
            )

        logger.info("Loaded %d total records for label %s", total, self._label)
        return total
