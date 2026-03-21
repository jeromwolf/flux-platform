"""Temporal models for TemporalCypherBuilder.

Defines TemporalMode enum and TemporalRange dataclass used to configure
time-based filtering in Cypher queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TemporalMode(str, Enum):
    """Mode for temporal filtering in Cypher queries.

    Each mode determines how validFrom/validTo properties are evaluated:

    - POINT_IN_TIME: records valid at a single instant
    - RANGE: records overlapping a time window
    - CURRENT: records still valid now (validTo IS NULL or in the future)
    - HISTORY: no temporal filter — return all versions
    - AS_OF: semantically versioned snapshot at a given instant
    """

    POINT_IN_TIME = "POINT_IN_TIME"
    RANGE = "RANGE"
    CURRENT = "CURRENT"
    HISTORY = "HISTORY"
    AS_OF = "AS_OF"


@dataclass(frozen=True)
class TemporalRange:
    """Configuration for temporal filtering on a graph node.

    Describes which temporal window or instant to query, and which
    Neo4j properties hold the validity interval.

    Attributes:
        start: Start of the temporal window (required for RANGE and POINT_IN_TIME).
        end: End of the temporal window (required for RANGE).
        mode: How the temporal filter is applied.
        valid_from_property: Neo4j property name for the validity start timestamp.
        valid_to_property: Neo4j property name for the validity end timestamp.

    Raises:
        ValueError: If mode is RANGE but start or end is missing.
        ValueError: If mode is POINT_IN_TIME but start is missing.

    Examples:
        >>> from datetime import datetime
        >>> r = TemporalRange(
        ...     start=datetime(2024, 1, 1),
        ...     end=datetime(2024, 6, 30),
        ...     mode=TemporalMode.RANGE,
        ... )
    """

    start: datetime | None = None
    end: datetime | None = None
    mode: TemporalMode = TemporalMode.CURRENT
    valid_from_property: str = "validFrom"
    valid_to_property: str = "validTo"

    def __post_init__(self) -> None:
        """Validate field combinations against the selected mode.

        Raises:
            ValueError: For invalid start/end combinations per mode.
        """
        if self.mode == TemporalMode.RANGE:
            if self.start is None or self.end is None:
                raise ValueError(
                    "TemporalRange with mode=RANGE requires both 'start' and 'end' to be set."
                )
        elif self.mode == TemporalMode.POINT_IN_TIME:
            if self.start is None:
                raise ValueError(
                    "TemporalRange with mode=POINT_IN_TIME requires 'start' to be set."
                )
        elif self.mode == TemporalMode.AS_OF:
            if self.start is None:
                raise ValueError(
                    "TemporalRange with mode=AS_OF requires 'start' to be set."
                )
