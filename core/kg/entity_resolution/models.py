"""Data models for the Entity Resolution module.

Provides:
- MatchMethod: enumeration of matching strategies
- ERCandidate: a single candidate match between two entity strings
- ERResult: resolved group of aliases mapped to a canonical name
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MatchMethod(str, Enum):
    """Strategy used to determine entity similarity.

    Attributes:
        EXACT: Byte-identical after normalization.
        FUZZY: String-distance based (SequenceMatcher / Jaro-Winkler).
        EMBEDDING: Vector cosine similarity (future).
        LLM: LLM-based semantic judgment (future).
    """

    EXACT = "EXACT"
    FUZZY = "FUZZY"
    EMBEDDING = "EMBEDDING"
    LLM = "LLM"


@dataclass
class ERCandidate:
    """A single candidate match between two entity mentions.

    Attributes:
        entity_a: First entity surface form.
        entity_b: Second entity surface form.
        similarity: Similarity score in [0.0, 1.0].
        method: The matching strategy that produced this score.
        context: Arbitrary metadata (e.g., source dataset, match details).
    """

    entity_a: str
    entity_b: str
    similarity: float
    method: MatchMethod
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ERResult:
    """Resolution result grouping aliases under a canonical name.

    Attributes:
        canonical: The chosen canonical (representative) entity name.
        aliases: Other surface forms that resolve to ``canonical``.
        candidates: The underlying pairwise match evidence.
        merged: Whether the resolver decided to merge these mentions.
    """

    canonical: str
    aliases: list[str] = field(default_factory=list)
    candidates: list[ERCandidate] = field(default_factory=list)
    merged: bool = False
