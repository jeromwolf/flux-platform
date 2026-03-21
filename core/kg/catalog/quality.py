"""Quality scoring logic for KG catalog entries.

Provides heuristic scoring across four dimensions:

- **Completeness** — fraction of optional metadata fields that are populated.
- **Accuracy** — placeholder (1.0) until live data validation is available (Y2).
- **Freshness** — time-decay based on ``updated_at``; full score for < 30 days.
- **Consistency** — structural invariants: valid ``entry_type`` and non-empty name.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from kg.catalog.models import CatalogEntry, QualityDimension, QualityScore

logger = logging.getLogger(__name__)

# Valid entry_type values
_VALID_ENTRY_TYPES: frozenset[str] = frozenset(
    {"NODE_LABEL", "RELATIONSHIP_TYPE", "INDEX", "CONSTRAINT"}
)

# Freshness decay: full score up to this many days, then linear decrease to 0
_FRESHNESS_FULL_DAYS: int = 30
_FRESHNESS_ZERO_DAYS: int = 365


def _score_completeness(entry: CatalogEntry) -> QualityScore:
    """Score how thoroughly optional metadata fields are populated.

    Checks three optional fields: ``description``, ``owner``, ``tags``.
    Each populated field contributes equally to the score.

    Args:
        entry: The catalog entry to evaluate.

    Returns:
        QualityScore for COMPLETENESS with a score in [0.0, 1.0].
    """
    checks: list[tuple[str, bool]] = [
        ("description", bool(entry.description.strip())),
        ("owner", bool(entry.owner.strip())),
        ("tags", len(entry.tags) > 0),
    ]
    filled = sum(1 for _, ok in checks if ok)
    score = filled / len(checks)
    missing = [name for name, ok in checks if not ok]
    if missing:
        details = f"{filled}/{len(checks)} optional fields populated; missing: {', '.join(missing)}"
    else:
        details = "All optional metadata fields are populated."
    return QualityScore(
        dimension=QualityDimension.COMPLETENESS,
        score=score,
        details=details,
    )


def _score_accuracy(_entry: CatalogEntry, _stats: dict | None) -> QualityScore:
    """Placeholder accuracy score — requires live data validation (Y2).

    Args:
        _entry: The catalog entry (unused until Y2 implementation).
        _stats: Optional statistics dict (unused until Y2 implementation).

    Returns:
        QualityScore for ACCURACY fixed at 1.0.
    """
    return QualityScore(
        dimension=QualityDimension.ACCURACY,
        score=1.0,
        details="Accuracy validation not yet implemented (planned for Year 2). Score defaulted to 1.0.",
    )


def _score_freshness(entry: CatalogEntry) -> QualityScore:
    """Score how recently the entry was updated.

    Scoring rules:
    - ``updated_at`` absent → 0.0 (unknown age).
    - Age ≤ ``_FRESHNESS_FULL_DAYS`` → 1.0.
    - ``_FRESHNESS_FULL_DAYS`` < age < ``_FRESHNESS_ZERO_DAYS`` → linear decay.
    - Age ≥ ``_FRESHNESS_ZERO_DAYS`` → 0.0.

    Args:
        entry: The catalog entry to evaluate.

    Returns:
        QualityScore for FRESHNESS with a score in [0.0, 1.0].
    """
    if not entry.updated_at:
        return QualityScore(
            dimension=QualityDimension.FRESHNESS,
            score=0.0,
            details="updated_at is not set; freshness cannot be determined.",
        )

    try:
        updated = datetime.fromisoformat(entry.updated_at)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        age_days = (now - updated).days
    except ValueError:
        logger.warning("Cannot parse updated_at=%r for entry %s", entry.updated_at, entry.id)
        return QualityScore(
            dimension=QualityDimension.FRESHNESS,
            score=0.0,
            details=f"updated_at value {entry.updated_at!r} is not a valid ISO 8601 datetime.",
        )

    if age_days <= _FRESHNESS_FULL_DAYS:
        score = 1.0
        details = f"Updated {age_days} day(s) ago — within the {_FRESHNESS_FULL_DAYS}-day full-score window."
    elif age_days >= _FRESHNESS_ZERO_DAYS:
        score = 0.0
        details = f"Updated {age_days} day(s) ago — exceeds {_FRESHNESS_ZERO_DAYS}-day staleness threshold."
    else:
        decay_range = _FRESHNESS_ZERO_DAYS - _FRESHNESS_FULL_DAYS
        elapsed = age_days - _FRESHNESS_FULL_DAYS
        score = round(1.0 - elapsed / decay_range, 4)
        details = (
            f"Updated {age_days} day(s) ago — linear decay applied "
            f"(score={score:.4f})."
        )

    return QualityScore(
        dimension=QualityDimension.FRESHNESS,
        score=score,
        details=details,
    )


def _score_consistency(entry: CatalogEntry) -> QualityScore:
    """Check structural invariants of the entry.

    Checks:
    1. ``entry_type`` is one of the four valid values.
    2. ``name`` is non-empty.

    Args:
        entry: The catalog entry to evaluate.

    Returns:
        QualityScore for CONSISTENCY; 1.0 if all checks pass, 0.0 otherwise.
    """
    issues: list[str] = []

    if entry.entry_type not in _VALID_ENTRY_TYPES:
        issues.append(
            f"entry_type={entry.entry_type!r} is not valid "
            f"(expected one of {sorted(_VALID_ENTRY_TYPES)})"
        )

    if not entry.name.strip():
        issues.append("name is empty or whitespace-only")

    if issues:
        return QualityScore(
            dimension=QualityDimension.CONSISTENCY,
            score=0.0,
            details="Consistency violations: " + "; ".join(issues),
        )

    return QualityScore(
        dimension=QualityDimension.CONSISTENCY,
        score=1.0,
        details="All consistency checks passed (valid entry_type and non-empty name).",
    )


def calculate_quality_score(
    entry: CatalogEntry,
    stats: dict | None = None,
) -> list[QualityScore]:
    """Calculate quality scores across all four dimensions for a catalog entry.

    Args:
        entry: The CatalogEntry to evaluate.
        stats: Optional live statistics dictionary (reserved for future use
            in accuracy scoring during Year 2 implementation).

    Returns:
        A list of four QualityScore instances — one per QualityDimension —
        in the order [COMPLETENESS, ACCURACY, FRESHNESS, CONSISTENCY].
    """
    return [
        _score_completeness(entry),
        _score_accuracy(entry, stats),
        _score_freshness(entry),
        _score_consistency(entry),
    ]
