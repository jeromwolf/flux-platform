"""Unit tests for Korean PII detector.

Covers:
    TC-PII01: Detect Korean resident registration number
    TC-PII02: Detect phone numbers
    TC-PII03: Detect email addresses
    TC-PII04: No PII in clean text
    TC-PII05: Redact replaces PII correctly

All tests are @pytest.mark.unit and require no external dependencies.
PYTHONPATH: .
"""
from __future__ import annotations

import pytest

from rag.documents.pii_detector import PIIDetection, PIIDetector, PIIScanResult, PIIType


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def detector() -> PIIDetector:
    return PIIDetector()


# ---------------------------------------------------------------------------
# TC-PII01: Korean resident registration number
# ---------------------------------------------------------------------------


class TestResidentNumberDetection:
    """TC-PII01: 주민등록번호 detection."""

    @pytest.mark.unit
    def test_detects_resident_number_in_plain_text(self, detector: PIIDetector) -> None:
        """TC-PII01-a: Standard resident number is detected."""
        text = "주민번호: 800101-1234567 입니다."
        result = detector.scan(text)
        assert result.has_pii
        assert any(d.pii_type == PIIType.RESIDENT_NUMBER for d in result.detections)

    @pytest.mark.unit
    def test_detects_all_valid_resident_number_prefixes(self, detector: PIIDetector) -> None:
        """TC-PII01-b: Gender codes 1, 2, 3, 4 are all detected."""
        for code in ("1", "2", "3", "4"):
            text = f"번호: 900101-{code}234567"
            result = detector.scan(text)
            assert result.has_pii, f"gender code {code} not detected"

    @pytest.mark.unit
    def test_resident_number_detection_captures_correct_value(self, detector: PIIDetector) -> None:
        """TC-PII01-c: Detection value matches the actual number substring."""
        text = "800101-1234567"
        result = detector.scan(text)
        assert any(d.value == "800101-1234567" for d in result.detections)

    @pytest.mark.unit
    def test_invalid_resident_number_not_detected(self, detector: PIIDetector) -> None:
        """TC-PII01-d: Invalid gender code (0) is NOT detected as resident number."""
        text = "not-a-resident-number: 800101-0234567"
        result = detector.scan(text)
        resident_hits = [d for d in result.detections if d.pii_type == PIIType.RESIDENT_NUMBER]
        assert len(resident_hits) == 0


# ---------------------------------------------------------------------------
# TC-PII02: Phone numbers
# ---------------------------------------------------------------------------


class TestPhoneNumberDetection:
    """TC-PII02: Korean phone number detection."""

    @pytest.mark.unit
    def test_detects_mobile_010_number(self, detector: PIIDetector) -> None:
        """TC-PII02-a: 010-XXXX-XXXX format is detected."""
        text = "연락처: 010-1234-5678"
        result = detector.scan(text)
        assert result.has_pii
        phone_hits = [d for d in result.detections if d.pii_type == PIIType.PHONE_NUMBER]
        assert len(phone_hits) >= 1

    @pytest.mark.unit
    def test_detects_various_carrier_prefixes(self, detector: PIIDetector) -> None:
        """TC-PII02-b: 011, 016, 017, 018, 019 prefixes are detected."""
        for prefix in ("011", "016", "017", "018", "019"):
            text = f"전화: {prefix}-123-4567"
            result = detector.scan(text)
            phone_hits = [d for d in result.detections if d.pii_type == PIIType.PHONE_NUMBER]
            assert len(phone_hits) >= 1, f"prefix {prefix} not detected"

    @pytest.mark.unit
    def test_phone_detection_captures_position(self, detector: PIIDetector) -> None:
        """TC-PII02-c: Detection records correct start/end offsets."""
        text = "call: 010-9876-5432 please"
        result = detector.scan(text)
        phone_hits = [d for d in result.detections if d.pii_type == PIIType.PHONE_NUMBER]
        assert len(phone_hits) == 1
        det = phone_hits[0]
        assert text[det.start : det.end] == det.value


# ---------------------------------------------------------------------------
# TC-PII03: Email addresses
# ---------------------------------------------------------------------------


class TestEmailDetection:
    """TC-PII03: Email address detection."""

    @pytest.mark.unit
    def test_detects_simple_email(self, detector: PIIDetector) -> None:
        """TC-PII03-a: user@example.com is detected."""
        text = "이메일: user@example.com 로 보내주세요."
        result = detector.scan(text)
        email_hits = [d for d in result.detections if d.pii_type == PIIType.EMAIL]
        assert len(email_hits) == 1
        assert email_hits[0].value == "user@example.com"

    @pytest.mark.unit
    def test_detects_subdomain_email(self, detector: PIIDetector) -> None:
        """TC-PII03-b: name@mail.company.co.kr is detected."""
        text = "Contact: name@mail.company.co.kr"
        result = detector.scan(text)
        assert result.has_pii
        email_hits = [d for d in result.detections if d.pii_type == PIIType.EMAIL]
        assert any("name@mail.company.co.kr" in d.value for d in email_hits)

    @pytest.mark.unit
    def test_multiple_emails_all_detected(self, detector: PIIDetector) -> None:
        """TC-PII03-c: Multiple email addresses in one text are all detected."""
        text = "From: a@x.com To: b@y.org CC: c@z.net"
        result = detector.scan(text)
        email_hits = [d for d in result.detections if d.pii_type == PIIType.EMAIL]
        assert len(email_hits) == 3


# ---------------------------------------------------------------------------
# TC-PII04: No PII in clean text
# ---------------------------------------------------------------------------


class TestNoPIIInCleanText:
    """TC-PII04: Negative tests — clean text must not trigger false positives."""

    @pytest.mark.unit
    def test_clean_korean_text_has_no_pii(self, detector: PIIDetector) -> None:
        """TC-PII04-a: Regular Korean text without PII returns has_pii=False."""
        text = "오늘은 날씨가 매우 맑습니다. 해양 연구소에서 발표한 자료입니다."
        result = detector.scan(text)
        assert not result.has_pii

    @pytest.mark.unit
    def test_empty_string_has_no_pii(self, detector: PIIDetector) -> None:
        """TC-PII04-b: Empty string returns has_pii=False."""
        result = detector.scan("")
        assert not result.has_pii
        assert len(result.detections) == 0

    @pytest.mark.unit
    def test_random_numbers_do_not_trigger_resident_detection(self, detector: PIIDetector) -> None:
        """TC-PII04-c: Generic date-like numbers without the hyphen-gender pattern are clean."""
        text = "참고번호: 20240101 및 20241231"
        result = detector.scan(text)
        resident_hits = [d for d in result.detections if d.pii_type == PIIType.RESIDENT_NUMBER]
        assert len(resident_hits) == 0

    @pytest.mark.unit
    def test_scan_result_text_length_matches_input(self, detector: PIIDetector) -> None:
        """TC-PII04-d: PIIScanResult.text_length equals len(input)."""
        text = "clean text without pii"
        result = detector.scan(text)
        assert result.text_length == len(text)


# ---------------------------------------------------------------------------
# TC-PII05: Redact replaces PII correctly
# ---------------------------------------------------------------------------


class TestRedact:
    """TC-PII05: PIIDetector.redact() replaces PII with [REDACTED]."""

    @pytest.mark.unit
    def test_redact_removes_resident_number(self, detector: PIIDetector) -> None:
        """TC-PII05-a: Resident number is replaced in output."""
        text = "주민번호: 800101-1234567 입니다."
        redacted = detector.redact(text)
        assert "800101-1234567" not in redacted
        assert "[REDACTED]" in redacted

    @pytest.mark.unit
    def test_redact_removes_phone_number(self, detector: PIIDetector) -> None:
        """TC-PII05-b: Phone number is replaced in output."""
        text = "연락처: 010-9876-5432"
        redacted = detector.redact(text)
        assert "010-9876-5432" not in redacted
        assert "[REDACTED]" in redacted

    @pytest.mark.unit
    def test_redact_removes_email(self, detector: PIIDetector) -> None:
        """TC-PII05-c: Email address is replaced in output."""
        text = "이메일: user@example.com"
        redacted = detector.redact(text)
        assert "user@example.com" not in redacted
        assert "[REDACTED]" in redacted

    @pytest.mark.unit
    def test_redact_preserves_non_pii_text(self, detector: PIIDetector) -> None:
        """TC-PII05-d: Non-PII portions of the text are preserved."""
        text = "연락처: 010-1234-5678 (해양연구소 담당자)"
        redacted = detector.redact(text)
        assert "해양연구소 담당자" in redacted

    @pytest.mark.unit
    def test_redact_clean_text_unchanged(self, detector: PIIDetector) -> None:
        """TC-PII05-e: Text without PII is returned unchanged."""
        text = "no pii here at all"
        redacted = detector.redact(text)
        assert redacted == text

    @pytest.mark.unit
    def test_redact_multiple_pii_items(self, detector: PIIDetector) -> None:
        """TC-PII05-f: Multiple PII items in one string are all redacted."""
        text = "이름: 홍길동, 전화: 010-1111-2222, 이메일: gd@test.com"
        redacted = detector.redact(text)
        assert "010-1111-2222" not in redacted
        assert "gd@test.com" not in redacted
        assert redacted.count("[REDACTED]") >= 2

    @pytest.mark.unit
    def test_redact_custom_placeholder(self, detector: PIIDetector) -> None:
        """TC-PII05-g: Custom placeholder is used when specified."""
        text = "email: admin@site.org"
        redacted = detector.redact(text, placeholder="***")
        assert "admin@site.org" not in redacted
        assert "***" in redacted
