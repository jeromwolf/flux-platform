"""Korean PII detection and redaction for document processing.

Detects and optionally redacts the following PII types:

* ``RESIDENT_NUMBER``  — Korean resident registration number (주민등록번호)
* ``PHONE_NUMBER``     — Korean mobile/landline phone numbers (전화번호)
* ``EMAIL``            — Email addresses
* ``BANK_ACCOUNT``     — Korean bank account numbers
* ``PASSPORT``         — Korean passport numbers

Usage::

    detector = PIIDetector()
    result = detector.scan("주민번호: 800101-1234567")
    if result.has_pii:
        clean = detector.redact("주민번호: 800101-1234567")
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class PIIType(str, Enum):
    """Categories of personally identifiable information."""

    RESIDENT_NUMBER = "resident_number"
    PHONE_NUMBER = "phone_number"
    EMAIL = "email"
    BANK_ACCOUNT = "bank_account"
    PASSPORT = "passport"


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_PATTERNS: dict[PIIType, re.Pattern[str]] = {
    # 주민등록번호: 6자리 날짜 + 하이픈 + 생년월일성별코드 1자리(1~4) + 6자리
    PIIType.RESIDENT_NUMBER: re.compile(
        r"\b\d{6}-[1-4]\d{6}\b"
    ),
    # 한국 휴대폰/전화: 01x-NNNN-NNNN (N 3~4자리)
    PIIType.PHONE_NUMBER: re.compile(
        r"\b01[016789]-\d{3,4}-\d{4}\b"
    ),
    # 이메일 주소
    PIIType.EMAIL: re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    # 한국 은행 계좌번호: 10~16자리 숫자 (하이픈 구분자 허용)
    # 예: 110-123-456789 / 1101234567890
    PIIType.BANK_ACCOUNT: re.compile(
        r"\b\d{3,6}-\d{2,6}-\d{5,7}\b"
    ),
    # 한국 여권번호: 영문 2자리 + 숫자 7자리 (예: M12345678 또는 AB1234567)
    PIIType.PASSPORT: re.compile(
        r"\b[A-Z]{1,2}\d{7,8}\b"
    ),
}

_REDACT_PLACEHOLDER = "[REDACTED]"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PIIDetection:
    """A single PII match found within a text.

    Attributes:
        pii_type: Category of PII detected.
        value: The matched substring.
        start: Start character offset in the original text.
        end: End character offset (exclusive) in the original text.
    """

    pii_type: PIIType
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class PIIScanResult:
    """Result of scanning a text for PII.

    Attributes:
        has_pii: True when at least one PII item was detected.
        detections: Tuple of all PIIDetection objects found.
        text_length: Character length of the scanned text.
    """

    has_pii: bool
    detections: tuple[PIIDetection, ...]
    text_length: int

    @property
    def types_found(self) -> set[PIIType]:
        """Set of distinct PII categories present in this result."""
        return {d.pii_type for d in self.detections}


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class PIIDetector:
    """Detects and redacts PII from Korean-language documents.

    Example::

        detector = PIIDetector()
        result = detector.scan("연락처: 010-1234-5678")
        assert result.has_pii
        safe_text = detector.redact("연락처: 010-1234-5678")
        assert "010-1234-5678" not in safe_text
    """

    def scan(self, text: str) -> PIIScanResult:
        """Scan *text* for all supported PII patterns.

        Searches every registered pattern and collects all non-overlapping
        matches.  Results are sorted by start position.

        Args:
            text: The raw text to scan.

        Returns:
            PIIScanResult with all detections.
        """
        detections: list[PIIDetection] = []
        for pii_type, pattern in _PATTERNS.items():
            for m in pattern.finditer(text):
                detections.append(
                    PIIDetection(
                        pii_type=pii_type,
                        value=m.group(),
                        start=m.start(),
                        end=m.end(),
                    )
                )

        detections.sort(key=lambda d: d.start)

        return PIIScanResult(
            has_pii=len(detections) > 0,
            detections=tuple(detections),
            text_length=len(text),
        )

    def redact(self, text: str, placeholder: str = _REDACT_PLACEHOLDER) -> str:
        """Replace all detected PII in *text* with *placeholder*.

        Handles overlapping matches by processing replacements from right
        to left so that character offsets remain valid.

        Args:
            text: The raw text to redact.
            placeholder: Replacement string (default ``[REDACTED]``).

        Returns:
            Text with all PII replaced by *placeholder*.
        """
        result = self.scan(text)
        if not result.has_pii:
            return text

        # Process right-to-left so offsets stay valid
        chars = list(text)
        for det in sorted(result.detections, key=lambda d: d.start, reverse=True):
            chars[det.start : det.end] = list(placeholder)

        return "".join(chars)
