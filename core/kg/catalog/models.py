"""Frozen dataclass models for the KG metadata catalog.

Defines the core data structures used to track KG assets, their quality
scores, and schema evolution history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QualityDimension(str, Enum):
    """Dimensions along which a CatalogEntry is evaluated.

    Attributes:
        COMPLETENESS: How thoroughly metadata fields are populated.
        ACCURACY: How correct the data is relative to ground truth.
        FRESHNESS: How recently the entry was updated.
        CONSISTENCY: Whether structural invariants hold.
    """

    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    FRESHNESS = "freshness"
    CONSISTENCY = "consistency"


@dataclass(frozen=True)
class QualityScore:
    """A single quality measurement for one dimension.

    Attributes:
        dimension: The quality dimension being measured.
        score: Normalised score in [0.0, 1.0].
        details: Human-readable explanation of how the score was computed.
    """

    dimension: QualityDimension
    score: float
    details: str = ""


@dataclass(frozen=True)
class SchemaChange:
    """Records a single schema evolution event for a catalog entry.

    Attributes:
        version: Semantic version string (e.g., "1.2.0").
        timestamp: ISO 8601 datetime string of when the change occurred.
        change_type: One of "ADD_LABEL", "ADD_PROPERTY", "MODIFY_PROPERTY",
            "REMOVE_LABEL", "REMOVE_PROPERTY".
        target: Label or property path affected (e.g., "Vessel.mmsi").
        description: Optional prose description of the change.
        author: Optional identifier of the person/service that made the change.
    """

    version: str
    timestamp: str
    change_type: str
    target: str
    description: str = ""
    author: str = ""


@dataclass(frozen=True)
class CatalogEntry:
    """An immutable record describing a KG asset (node label, relationship type, etc.).

    Attributes:
        id: Unique identifier for this entry (e.g., "node.Vessel").
        name: Human-readable asset name (e.g., "Vessel").
        entry_type: One of "NODE_LABEL", "RELATIONSHIP_TYPE", "INDEX", "CONSTRAINT".
        description: Optional prose description of the asset.
        created_at: ISO 8601 creation timestamp.
        updated_at: ISO 8601 last-updated timestamp.
        owner: Identifier of the owning team or person.
        tags: Immutable sequence of classification tags.
        quality_scores: Immutable sequence of QualityScore measurements.
        schema_history: Immutable sequence of SchemaChange records.
        properties: Immutable sequence of (key, value) metadata pairs.
    """

    id: str
    name: str
    entry_type: str
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    owner: str = ""
    tags: tuple[str, ...] = ()
    quality_scores: tuple[QualityScore, ...] = ()
    schema_history: tuple[SchemaChange, ...] = ()
    properties: tuple[tuple[str, str], ...] = ()

    @property
    def overall_quality(self) -> float:
        """Average of all quality_scores, or 0.0 when no scores are present.

        Returns:
            Float in [0.0, 1.0] representing mean quality across all dimensions.
        """
        if not self.quality_scores:
            return 0.0
        return sum(qs.score for qs in self.quality_scores) / len(self.quality_scores)
