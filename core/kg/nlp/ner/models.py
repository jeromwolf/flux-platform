"""Data models for Named Entity Recognition results.

Defines immutable, frozen dataclasses for NER tags and results.
All data structures are hashable and safe for use in sets and as dict keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NERTagType(str, Enum):
    """Enumeration of supported named entity types in the maritime domain.

    Inherits from str so values can be compared directly with string literals.
    """

    VESSEL = "VESSEL"
    PORT = "PORT"
    BERTH = "BERTH"
    ORG = "ORG"
    SEA_AREA = "SEA_AREA"
    FACILITY = "FACILITY"
    REGULATION = "REGULATION"
    MODEL_SHIP = "MODEL_SHIP"
    EXPERIMENT = "EXPERIMENT"
    WEATHER = "WEATHER"
    DATE = "DATE"
    MMSI = "MMSI"


@dataclass(frozen=True)
class NERTag:
    """A single named entity span extracted from text.

    Attributes:
        text: The matched text span as it appears in the source.
        tag_type: The semantic entity type of this span.
        start: Character offset (inclusive) where the span begins.
        end: Character offset (exclusive) where the span ends.
        confidence: Confidence score in [0.0, 1.0]; default 1.0.
        source: Identifier of the tagger that produced this tag
            (e.g. "dictionary", "regex", "ml").
        normalized: Canonical / normalized form of the entity
            (e.g. "부산항" → "BUSAN").
    """

    text: str
    tag_type: NERTagType
    start: int
    end: int
    confidence: float = 1.0
    source: str = ""
    normalized: str = ""

    def __post_init__(self) -> None:
        """Validate field constraints."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0.0, 1.0], got {self.confidence}"
            )
        if self.start < 0:
            raise ValueError(f"start must be >= 0, got {self.start}")
        if self.end < self.start:
            raise ValueError(
                f"end ({self.end}) must be >= start ({self.start})"
            )


@dataclass(frozen=True)
class NERResult:
    """The complete NER output for a single input text.

    Attributes:
        text: The original input text that was processed.
        tags: Immutable sequence of extracted named entity tags.
        processing_time_ms: Wall-clock time taken to produce this result
            in milliseconds.
    """

    text: str
    tags: tuple[NERTag, ...] = field(default_factory=tuple)
    processing_time_ms: float = 0.0

    @property
    def entities_by_type(self) -> dict[NERTagType, list[NERTag]]:
        """Group tags by their entity type.

        Returns:
            Mapping from NERTagType to the list of tags of that type.
            Types with no tags are omitted.
        """
        result: dict[NERTagType, list[NERTag]] = {}
        for tag in self.tags:
            result.setdefault(tag.tag_type, []).append(tag)
        return result

    @property
    def has_entities(self) -> bool:
        """Return True when at least one entity tag was extracted."""
        return len(self.tags) > 0
