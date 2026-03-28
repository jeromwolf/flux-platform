"""Transform steps for the ETL pipeline.

Provides:
- TransformStep: abstract base class for record transformations
- DateTimeNormalizer: parse and normalize date/time strings to ISO 8601
- TextNormalizer: strip, collapse whitespace, normalize Korean text
- IdentifierNormalizer: ensure identifiers match expected patterns
- ChainTransform: compose multiple transforms sequentially
"""

from __future__ import annotations

import abc
import re
from datetime import datetime

from kg.etl.models import RecordEnvelope


class TransformStep(abc.ABC):
    """Abstract base for a single transformation applied to a RecordEnvelope."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable name for this transform step."""
        ...

    @abc.abstractmethod
    def transform(self, record: RecordEnvelope) -> RecordEnvelope:
        """Apply the transformation to *record* and return the (possibly mutated) envelope.

        Args:
            record: The record envelope to transform.

        Returns:
            The transformed record envelope.
        """
        ...


class DateTimeNormalizer(TransformStep):
    """Parse various date/time formats and normalize to ISO 8601 strings.

    Handles ISO format, Korean date formats (``2024년 3월 15일``),
    and common date-only patterns (``YYYY-MM-DD``, ``YYYY/MM/DD``).

    Args:
        fields: Data fields to normalize. Each field value is replaced
            with its ISO 8601 representation if parsing succeeds.
    """

    # Korean date pattern: 2024년 3월 15일 (with optional time)
    _KO_DATE_RE = re.compile(
        r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일"
        r"(?:\s+(\d{1,2})시\s*(\d{1,2})분(?:\s*(\d{1,2})초)?)?"
    )

    # Common date-only: YYYY-MM-DD or YYYY/MM/DD
    _DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")

    def __init__(self, fields: list[str]) -> None:
        self._fields = fields

    @property
    def name(self) -> str:
        return "DateTimeNormalizer"

    def transform(self, record: RecordEnvelope) -> RecordEnvelope:
        """Normalize date/time fields in *record.data* to ISO 8601."""
        for field_name in self._fields:
            value = record.data.get(field_name)
            if not isinstance(value, str):
                continue
            normalized = self._normalize(value)
            if normalized is not None:
                record.data[field_name] = normalized
        return record

    def _normalize(self, value: str) -> str | None:
        """Attempt to parse *value* into an ISO 8601 string.

        Returns:
            ISO 8601 string on success, or ``None`` if unparseable.
        """
        # Try ISO format first
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(value, fmt).isoformat()
            except ValueError:  # noqa: S112
                continue

        # Korean date format
        match = self._KO_DATE_RE.search(value)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            hour = int(match.group(4)) if match.group(4) else 0
            minute = int(match.group(5)) if match.group(5) else 0
            second = int(match.group(6)) if match.group(6) else 0
            return datetime(year, month, day, hour, minute, second).isoformat()

        # Common date-only
        match = self._DATE_RE.search(value)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return datetime(year, month, day).isoformat()

        return None


class TextNormalizer(TransformStep):
    """Strip leading/trailing whitespace and collapse internal runs of whitespace.

    Also normalizes common Korean text issues such as mixed-width spaces.

    Args:
        fields: Data fields to normalize.
    """

    # Matches any sequence of whitespace (including full-width spaces)
    _WHITESPACE_RE = re.compile(r"[\s\u3000]+")

    def __init__(self, fields: list[str]) -> None:
        self._fields = fields

    @property
    def name(self) -> str:
        return "TextNormalizer"

    def transform(self, record: RecordEnvelope) -> RecordEnvelope:
        """Strip and collapse whitespace in specified text fields."""
        for field_name in self._fields:
            value = record.data.get(field_name)
            if not isinstance(value, str):
                continue
            cleaned = self._WHITESPACE_RE.sub(" ", value).strip()
            record.data[field_name] = cleaned
        return record


class IdentifierNormalizer(TransformStep):
    """Ensure identifier fields match expected prefix patterns.

    Args:
        field: The data field containing the identifier.
        prefix: Expected prefix string (e.g. ``"KRPUS"``).
    """

    def __init__(self, field: str, prefix: str) -> None:
        self._field = field
        self._prefix = prefix

    @property
    def name(self) -> str:
        return "IdentifierNormalizer"

    def transform(self, record: RecordEnvelope) -> RecordEnvelope:
        """Ensure the identifier field starts with the expected prefix.

        If the field value does not start with *prefix*, the prefix is
        prepended with a hyphen separator.
        """
        value = record.data.get(self._field)
        if not isinstance(value, str):
            return record
        value = value.strip()
        if not value.startswith(self._prefix):
            value = f"{self._prefix}-{value}"
        record.data[self._field] = value
        return record


class ChainTransform(TransformStep):
    """Compose multiple transform steps into a single sequential chain.

    Args:
        steps: Ordered list of transforms to apply.
    """

    def __init__(self, steps: list[TransformStep]) -> None:
        self._steps = list(steps)

    @property
    def name(self) -> str:
        names = ", ".join(s.name for s in self._steps)
        return f"Chain[{names}]"

    def transform(self, record: RecordEnvelope) -> RecordEnvelope:
        """Apply each step in order, passing the result forward."""
        for step in self._steps:
            record = step.transform(record)
        return record
