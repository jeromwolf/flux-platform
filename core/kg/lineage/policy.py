"""Lineage recording policy engine.

Controls which lineage events are recorded based on entity type and
data classification level. Integrates with the RBAC
:class:`~kg.rbac.models.DataClassification` model (5 levels).

Recording levels determine the granularity of lineage tracking:

- **NONE**: No lineage recorded.
- **MINIMAL**: Only creation and deletion events.
- **STANDARD**: Creation, transformation, deletion, and merge events.
- **DETAILED**: All events except export.
- **FULL**: Every event is recorded, including snapshots.

Usage::

    from kg.lineage.policy import LineagePolicy, RecordingLevel
    from kg.lineage.models import LineageEventType

    policy = LineagePolicy(default_level=RecordingLevel.STANDARD)
    policy.set_level("ExperimentalDataset", RecordingLevel.FULL)

    if policy.should_record("Vessel", LineageEventType.TRANSFORMATION):
        # record the event
        ...
"""

from __future__ import annotations

from enum import Enum

from kg.lineage.models import LineageEventType

# =========================================================================
# Enums
# =========================================================================


class RecordingLevel(str, Enum):
    """Lineage recording granularity levels.

    Higher levels capture more event types and enable snapshots.
    """

    NONE = "NONE"
    MINIMAL = "MINIMAL"
    STANDARD = "STANDARD"
    DETAILED = "DETAILED"
    FULL = "FULL"


# =========================================================================
# Event type sets per recording level
# =========================================================================

_MINIMAL_EVENTS: frozenset[LineageEventType] = frozenset({
    LineageEventType.CREATION,
    LineageEventType.DELETION,
})

_STANDARD_EVENTS: frozenset[LineageEventType] = frozenset({
    LineageEventType.CREATION,
    LineageEventType.TRANSFORMATION,
    LineageEventType.DELETION,
    LineageEventType.MERGE,
})

_DETAILED_EVENTS: frozenset[LineageEventType] = frozenset({
    LineageEventType.CREATION,
    LineageEventType.TRANSFORMATION,
    LineageEventType.DERIVATION,
    LineageEventType.INGESTION,
    LineageEventType.DELETION,
    LineageEventType.MERGE,
    LineageEventType.SPLIT,
})

_FULL_EVENTS: frozenset[LineageEventType] = frozenset(LineageEventType)

_LEVEL_EVENT_MAP: dict[RecordingLevel, frozenset[LineageEventType]] = {
    RecordingLevel.NONE: frozenset(),
    RecordingLevel.MINIMAL: _MINIMAL_EVENTS,
    RecordingLevel.STANDARD: _STANDARD_EVENTS,
    RecordingLevel.DETAILED: _DETAILED_EVENTS,
    RecordingLevel.FULL: _FULL_EVENTS,
}

# Recording levels that enable snapshots
_SNAPSHOT_LEVELS: frozenset[RecordingLevel] = frozenset({
    RecordingLevel.DETAILED,
    RecordingLevel.FULL,
})

# DataClassification level -> RecordingLevel mapping
_CLASSIFICATION_MAP: dict[int, RecordingLevel] = {
    1: RecordingLevel.MINIMAL,     # PUBLIC
    2: RecordingLevel.STANDARD,    # INTERNAL
    3: RecordingLevel.STANDARD,    # CONFIDENTIAL
    4: RecordingLevel.DETAILED,    # SECRET
    5: RecordingLevel.FULL,        # TOP_SECRET
}


# =========================================================================
# Policy
# =========================================================================


class LineagePolicy:
    """Determines which lineage events should be recorded per entity type.

    The policy maintains a default recording level and per-entity-type
    overrides. It integrates with the RBAC DataClassification system
    to auto-derive recording levels from data sensitivity.

    Args:
        default_level: The recording level applied when no entity-specific
            rule exists. Defaults to ``RecordingLevel.STANDARD``.
    """

    def __init__(
        self, default_level: RecordingLevel = RecordingLevel.STANDARD
    ) -> None:
        self._default_level = default_level
        self._rules: dict[str, RecordingLevel] = {}

    @property
    def default_level(self) -> RecordingLevel:
        """The default recording level for entity types without explicit rules."""
        return self._default_level

    def set_level(self, entity_type: str, level: RecordingLevel) -> None:
        """Set the recording level for a specific entity type.

        Args:
            entity_type: Neo4j label (e.g., "Vessel", "ExperimentalDataset").
            level: The desired recording level.
        """
        self._rules[entity_type] = level

    def get_level(self, entity_type: str) -> RecordingLevel:
        """Get the effective recording level for an entity type.

        Returns the entity-specific level if set, otherwise the default.

        Args:
            entity_type: Neo4j label.

        Returns:
            The effective RecordingLevel.
        """
        return self._rules.get(entity_type, self._default_level)

    def should_record(
        self, entity_type: str, event_type: LineageEventType
    ) -> bool:
        """Check whether a lineage event should be recorded.

        Args:
            entity_type: Neo4j label of the entity.
            event_type: The lineage event type.

        Returns:
            True if the event should be recorded under the current policy.
        """
        level = self.get_level(entity_type)
        allowed_events = _LEVEL_EVENT_MAP.get(level, frozenset())
        return event_type in allowed_events

    def should_snapshot(self, entity_type: str) -> bool:
        """Check whether snapshots should be captured for an entity type.

        Snapshots are enabled at DETAILED and FULL recording levels.

        Args:
            entity_type: Neo4j label.

        Returns:
            True if snapshots should be captured.
        """
        level = self.get_level(entity_type)
        return level in _SNAPSHOT_LEVELS

    @classmethod
    def from_data_classification(cls, level: int) -> RecordingLevel:
        """Map a DataClassification numeric level to a RecordingLevel.

        Integration point with :class:`~kg.rbac.models.DataClassification`.

        Args:
            level: Data classification level (1-5).
                1 = PUBLIC, 2 = INTERNAL, 3 = CONFIDENTIAL,
                4 = SECRET, 5 = TOP_SECRET.

        Returns:
            The corresponding RecordingLevel.

        Raises:
            ValueError: If level is outside the valid range (1-5).
        """
        if level not in _CLASSIFICATION_MAP:
            raise ValueError(
                f"Invalid data classification level: {level}. "
                f"Expected 1-5."
            )
        return _CLASSIFICATION_MAP[level]
