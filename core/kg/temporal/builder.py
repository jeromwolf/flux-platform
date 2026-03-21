"""TemporalCypherBuilder — temporal query extension for CypherBuilder.

Adds fluent methods for time-based filtering using validFrom / validTo
node properties, following bitemporal and slowly-changing-dimension patterns
common in maritime knowledge graphs.

Usage::

    from datetime import datetime
    from kg.temporal.builder import TemporalCypherBuilder

    # Records valid at a specific point in time
    query, params = (
        TemporalCypherBuilder()
        .match("(v:Vessel)")
        .for_node("v")
        .at_time(datetime(2025, 6, 1))
        .return_("v.name AS name")
        .build()
    )

    # Records whose validity interval overlaps a date range
    query, params = (
        TemporalCypherBuilder()
        .match("(r:Route)")
        .for_node("r")
        .between(datetime(2025, 1, 1), datetime(2025, 12, 31))
        .return_("r")
        .build()
    )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kg.cypher_builder import CypherBuilder
from kg.temporal.models import TemporalMode, TemporalRange


class TemporalCypherBuilder(CypherBuilder):
    """CypherBuilder extended with temporal filtering capabilities.

    Provides fluent methods to constrain graph queries by node validity
    intervals stored in ``validFrom`` / ``validTo`` properties (configurable).
    Temporal WHERE clauses are injected at ``build()`` time using
    ``_next_param()`` so they never collide with user-supplied parameters.

    Inherits all methods from :class:`~kg.cypher_builder.CypherBuilder`.

    Attributes:
        _temporal_range: Current temporal filter configuration, or ``None``
            if no temporal filter has been applied.
        _temporal_alias: Alias of the node to which temporal filters apply.
    """

    def __init__(self) -> None:
        super().__init__()
        self._temporal_range: TemporalRange | None = None
        self._temporal_alias: str = "n"

    # =========================================================================
    # Configuration helpers
    # =========================================================================

    def for_node(self, alias: str) -> TemporalCypherBuilder:
        """Set which node alias receives temporal WHERE filters.

        Call this before any of the temporal filter methods if the target
        node alias differs from the default ``"n"``.

        Args:
            alias: Node alias used in the MATCH clause (e.g., ``"v"``, ``"r"``).

        Returns:
            Self for chaining.

        Examples:
            >>> builder = TemporalCypherBuilder().match("(v:Vessel)").for_node("v")
        """
        self._temporal_alias = alias
        return self

    def with_temporal_properties(
        self,
        valid_from: str = "validFrom",
        valid_to: str = "validTo",
    ) -> TemporalCypherBuilder:
        """Override the Neo4j property names used for the validity interval.

        Useful when the graph schema uses non-standard names such as
        ``"startDate"`` / ``"endDate"`` or ``"from"`` / ``"to"``.

        Args:
            valid_from: Property name for the validity start timestamp.
            valid_to: Property name for the validity end timestamp.

        Returns:
            Self for chaining.

        Examples:
            >>> builder = (
            ...     TemporalCypherBuilder()
            ...     .match("(e:Event)")
            ...     .for_node("e")
            ...     .with_temporal_properties("startDate", "endDate")
            ...     .current()
            ... )
        """
        # Preserve any existing range config, replacing only property names.
        # TemporalRange is frozen so we create a new instance via dataclasses.replace.
        if self._temporal_range is not None:
            from dataclasses import replace as _dc_replace

            self._temporal_range = _dc_replace(
                self._temporal_range,
                valid_from_property=valid_from,
                valid_to_property=valid_to,
            )
        else:
            # Store a neutral HISTORY range so the property names are remembered
            # and picked up by _current_valid_from/to_property() when the caller
            # chains a temporal filter method afterwards.
            self._temporal_range = TemporalRange(
                mode=TemporalMode.HISTORY,  # no WHERE clauses emitted
                valid_from_property=valid_from,
                valid_to_property=valid_to,
            )
        return self

    # =========================================================================
    # Temporal filter methods
    # =========================================================================

    def at_time(self, dt: datetime) -> TemporalCypherBuilder:
        """Filter to records valid at a specific instant.

        Generates::

            WHERE n.validFrom <= $p1
              AND (n.validTo IS NULL OR n.validTo >= $p1)

        Args:
            dt: The instant to query. Timezone-naive values are treated as UTC.

        Returns:
            Self for chaining.
        """
        vfp = self._current_valid_from_property()
        vtp = self._current_valid_to_property()
        self._temporal_range = TemporalRange(
            start=dt,
            mode=TemporalMode.POINT_IN_TIME,
            valid_from_property=vfp,
            valid_to_property=vtp,
        )
        return self

    def between(self, start: datetime, end: datetime) -> TemporalCypherBuilder:
        """Filter to records whose validity overlaps [start, end].

        Uses an Allen-interval overlap test::

            WHERE n.validFrom <= $p_end
              AND (n.validTo IS NULL OR n.validTo >= $p_start)

        Args:
            start: Start of the query window (inclusive).
            end: End of the query window (inclusive).

        Returns:
            Self for chaining.
        """
        vfp = self._current_valid_from_property()
        vtp = self._current_valid_to_property()
        self._temporal_range = TemporalRange(
            start=start,
            end=end,
            mode=TemporalMode.RANGE,
            valid_from_property=vfp,
            valid_to_property=vtp,
        )
        return self

    def current(self) -> TemporalCypherBuilder:
        """Filter to records still valid at the time the query is built.

        ``datetime.now(tz=timezone.utc)`` is captured when ``current()`` is
        called and frozen into the query parameters.

        Generates::

            WHERE (n.validTo IS NULL OR n.validTo >= $p_now)

        Returns:
            Self for chaining.
        """
        vfp = self._current_valid_from_property()
        vtp = self._current_valid_to_property()
        self._temporal_range = TemporalRange(
            start=datetime.now(tz=timezone.utc),
            mode=TemporalMode.CURRENT,
            valid_from_property=vfp,
            valid_to_property=vtp,
        )
        return self

    def with_history(self) -> TemporalCypherBuilder:
        """Disable temporal filtering — return all versions of records.

        No WHERE clauses are added for temporal properties. Use this to
        inspect full history or audit trails.

        Returns:
            Self for chaining.
        """
        vfp = self._current_valid_from_property()
        vtp = self._current_valid_to_property()
        self._temporal_range = TemporalRange(
            mode=TemporalMode.HISTORY,
            valid_from_property=vfp,
            valid_to_property=vtp,
        )
        return self

    def as_of(self, dt: datetime) -> TemporalCypherBuilder:
        """Filter to the versioned state of records as of a given instant.

        Semantically equivalent to :meth:`at_time` but signals intent to query
        a versioned / slowly-changing dataset rather than an event stream.

        Generates::

            WHERE n.validFrom <= $p_asof
              AND (n.validTo IS NULL OR n.validTo >= $p_asof)

        Args:
            dt: The snapshot instant.

        Returns:
            Self for chaining.
        """
        vfp = self._current_valid_from_property()
        vtp = self._current_valid_to_property()
        self._temporal_range = TemporalRange(
            start=dt,
            mode=TemporalMode.AS_OF,
            valid_from_property=vfp,
            valid_to_property=vtp,
        )
        return self

    # =========================================================================
    # Build override
    # =========================================================================

    def build(self) -> tuple[str, dict[str, Any]]:
        """Build the Cypher query, injecting temporal WHERE clauses first.

        Temporal conditions are appended to ``_where_clauses`` using
        ``_next_param()`` for collision-safe parameter names, then the
        parent ``build()`` assembles the full query string.

        Returns:
            Tuple of ``(query_string, parameters_dict)``.
        """
        if self._temporal_range is not None:
            self._inject_temporal_where(self._temporal_range)
        return super().build()

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _current_valid_from_property(self) -> str:
        """Return the valid_from_property from existing range or default."""
        if self._temporal_range is not None:
            return self._temporal_range.valid_from_property
        return "validFrom"

    def _current_valid_to_property(self) -> str:
        """Return the valid_to_property from existing range or default."""
        if self._temporal_range is not None:
            return self._temporal_range.valid_to_property
        return "validTo"

    def _inject_temporal_where(self, tr: TemporalRange) -> None:
        """Append temporal WHERE conditions for the given TemporalRange.

        Parameters are allocated via ``_next_param()`` to guarantee uniqueness
        across all clauses already present in the builder.

        Args:
            tr: The TemporalRange configuration to translate into WHERE clauses.
        """
        alias = self._temporal_alias
        vf = tr.valid_from_property
        vt = tr.valid_to_property

        if tr.mode == TemporalMode.POINT_IN_TIME:
            # Records valid at a single instant: validFrom <= t <= validTo
            p_at = self._next_param()
            self._parameters[p_at] = tr.start
            self._where_clauses.append(f"{alias}.{vf} <= ${p_at}")
            self._where_clauses.append(
                f"({alias}.{vt} IS NULL OR {alias}.{vt} >= ${p_at})"
            )

        elif tr.mode == TemporalMode.RANGE:
            # Allen-interval overlap: validFrom <= end AND validTo >= start
            p_start = self._next_param()
            p_end = self._next_param()
            self._parameters[p_start] = tr.start
            self._parameters[p_end] = tr.end
            self._where_clauses.append(f"{alias}.{vf} <= ${p_end}")
            self._where_clauses.append(
                f"({alias}.{vt} IS NULL OR {alias}.{vt} >= ${p_start})"
            )

        elif tr.mode == TemporalMode.CURRENT:
            # Still valid now: validTo IS NULL or in the future
            p_now = self._next_param()
            self._parameters[p_now] = tr.start  # captured at current() call time
            self._where_clauses.append(
                f"({alias}.{vt} IS NULL OR {alias}.{vt} >= ${p_now})"
            )

        elif tr.mode == TemporalMode.AS_OF:
            # Versioned snapshot — same logic as POINT_IN_TIME
            p_asof = self._next_param()
            self._parameters[p_asof] = tr.start
            self._where_clauses.append(f"{alias}.{vf} <= ${p_asof}")
            self._where_clauses.append(
                f"({alias}.{vt} IS NULL OR {alias}.{vt} >= ${p_asof})"
            )

        # HISTORY: no clauses added — all versions returned
