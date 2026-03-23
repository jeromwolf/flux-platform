"""Unit tests for enhanced PDF and HWP parsers.

Covers:
    TC-PP01: PDFParser with fitz available (mock fitz)
    TC-PP02: PDFParser fallback when fitz not available
    TC-PP03: PDFParser text quality calculation
    TC-PP04: HWPParser with string input (passthrough)
    TC-PP05: HWPParser with bytes via olefile (mock)
    TC-PP06: HWPParser fallback chain
    TC-PP07: ParserRegistry still works with updated parsers

All tests are @pytest.mark.unit and require no optional dependencies.
External libs (fitz, olefile, subprocess) are fully mocked.
PYTHONPATH: .
"""
from __future__ import annotations

import struct
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from rag.documents.models import DocumentType
from rag.documents.parsers import HWPParser, PDFParser, ParserRegistry


# ---------------------------------------------------------------------------
# TC-PP01: PDFParser with fitz available
# ---------------------------------------------------------------------------


class TestPDFParserWithFitz:
    """TC-PP01: PDFParser uses fitz when available."""

    def _make_fitz_mock(self, pages_text: list[str]) -> ModuleType:
        """Build a minimal fitz mock that returns the given per-page texts."""
        fitz_mod = ModuleType("fitz")

        mock_pages = []
        for text in pages_text:
            page = MagicMock()
            page.get_text.return_value = text
            page.get_images.return_value = []
            mock_pages.append(page)

        n = len(mock_pages)

        mock_doc = MagicMock()
        # MagicMock magic-method delegation: must be set via return_value on
        # the pre-existing MagicMock dunder attribute (not reassigned).
        mock_doc.__len__.return_value = n
        mock_doc.__getitem__.side_effect = lambda i: mock_pages[i]
        mock_doc.is_closed = False
        mock_doc.close = MagicMock()

        fitz_mod.open = MagicMock(return_value=mock_doc)
        return fitz_mod

    @pytest.mark.unit
    def test_parse_file_extracts_text_from_pages(self, tmp_path) -> None:
        """TC-PP01-a: parse_file extracts text from each PDF page."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        fitz_mock = self._make_fitz_mock(["Page one text.", "Page two text."])
        with patch.dict(sys.modules, {"fitz": fitz_mock}):
            parser = PDFParser()
            doc = parser.parse_file(str(pdf_file), doc_id="pdf-001")

        assert "Page one text." in doc.content
        assert "Page two text." in doc.content
        assert doc.doc_type == DocumentType.PDF
        assert doc.doc_id == "pdf-001"

    @pytest.mark.unit
    def test_parse_file_sets_needs_ocr_false_for_good_text(self, tmp_path) -> None:
        """TC-PP01-b: needs_ocr is False when text quality is good."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        # High quality text: all printable English
        good_text = "This is a high quality English text with many readable words."
        fitz_mock = self._make_fitz_mock([good_text])
        with patch.dict(sys.modules, {"fitz": fitz_mock}):
            parser = PDFParser()
            doc = parser.parse_file(str(pdf_file), doc_id="pdf-002")

        assert doc.metadata.get("needs_ocr") is False

    @pytest.mark.unit
    def test_parse_file_sets_needs_ocr_true_for_low_quality(self, tmp_path) -> None:
        """TC-PP01-c: needs_ocr is True when text quality < 0.3."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        # Garbage binary-like text has very low quality
        garbage_text = "\x00\x01\x02\x03\x04\x05\x06\x07\x08" * 50
        fitz_mock = self._make_fitz_mock([garbage_text])
        with patch.dict(sys.modules, {"fitz": fitz_mock}):
            parser = PDFParser()
            doc = parser.parse_file(str(pdf_file), doc_id="pdf-003")

        assert doc.metadata.get("needs_ocr") is True

    @pytest.mark.unit
    def test_parse_file_stores_quality_scores_in_metadata(self, tmp_path) -> None:
        """TC-PP01-d: parse_file stores quality_scores list in metadata."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        fitz_mock = self._make_fitz_mock(["Page 1 text.", "Page 2 text."])
        with patch.dict(sys.modules, {"fitz": fitz_mock}):
            parser = PDFParser()
            doc = parser.parse_file(str(pdf_file), doc_id="pdf-004")

        quality_scores = doc.metadata.get("quality_scores")
        assert isinstance(quality_scores, list)
        assert len(quality_scores) == 2
        assert all(0.0 <= s <= 1.0 for s in quality_scores)


# ---------------------------------------------------------------------------
# TC-PP02: PDFParser fallback when fitz not available
# ---------------------------------------------------------------------------


class TestPDFParserFallback:
    """TC-PP02: PDFParser falls back gracefully without fitz."""

    @pytest.mark.unit
    def test_parse_string_content_works_without_fitz(self) -> None:
        """TC-PP02-a: parse() with string content never needs fitz."""
        parser = PDFParser()
        doc = parser.parse("Pre-extracted PDF text", doc_id="pdf-fb-001")
        assert doc.content == "Pre-extracted PDF text"
        assert doc.doc_type == DocumentType.PDF

    @pytest.mark.unit
    def test_parse_file_falls_back_to_text_read_without_fitz(self, tmp_path) -> None:
        """TC-PP02-b: parse_file reads bytes as text when fitz is absent."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("Plain text content in PDF-named file", encoding="utf-8")

        with patch.dict(sys.modules, {"fitz": None}):
            parser = PDFParser()
            doc = parser.parse_file(str(pdf_file), doc_id="pdf-fb-002")

        # Fallback text read should contain the file content
        assert doc.doc_type == DocumentType.PDF
        assert doc.doc_id == "pdf-fb-002"
        assert len(doc.content) > 0


# ---------------------------------------------------------------------------
# TC-PP03: PDFParser text quality calculation
# ---------------------------------------------------------------------------


class TestPDFParserQuality:
    """TC-PP03: _calculate_quality static method."""

    @pytest.mark.unit
    def test_empty_text_returns_zero(self) -> None:
        """TC-PP03-a: Empty string yields 0.0 quality."""
        assert PDFParser._calculate_quality("") == 0.0

    @pytest.mark.unit
    def test_all_english_letters_returns_high_score(self) -> None:
        """TC-PP03-b: Pure English text has quality close to 1.0."""
        score = PDFParser._calculate_quality("Hello World ")
        # All chars are alpha or space — should be 1.0
        assert score == pytest.approx(1.0, abs=0.01)

    @pytest.mark.unit
    def test_korean_text_returns_high_score(self) -> None:
        """TC-PP03-c: Korean Hangul characters yield high quality."""
        score = PDFParser._calculate_quality("안녕하세요 한국어 텍스트")
        assert score > 0.7

    @pytest.mark.unit
    def test_binary_garbage_returns_low_score(self) -> None:
        """TC-PP03-d: Binary garbage yields very low quality."""
        garbage = "".join(chr(i) for i in range(1, 30))  # control chars
        score = PDFParser._calculate_quality(garbage)
        assert score < 0.3

    @pytest.mark.unit
    def test_mixed_content_returns_intermediate_score(self) -> None:
        """TC-PP03-e: Mixed text/garbage yields intermediate score."""
        mixed = "Hello " + "".join(chr(i) for i in range(1, 10))
        score = PDFParser._calculate_quality(mixed)
        assert 0.0 < score < 1.0


# ---------------------------------------------------------------------------
# TC-PP04: HWPParser with string input (passthrough)
# ---------------------------------------------------------------------------


class TestHWPParserStringInput:
    """TC-PP04: HWPParser.parse() with string content."""

    @pytest.mark.unit
    def test_parse_string_returns_document_with_hwp_type(self) -> None:
        """TC-PP04-a: parse() with a string returns HWP Document."""
        parser = HWPParser()
        doc = parser.parse("HWP 문서 내용", doc_id="hwp-001")
        assert doc.content == "HWP 문서 내용"
        assert doc.doc_type == DocumentType.HWP
        assert doc.doc_id == "hwp-001"

    @pytest.mark.unit
    def test_parse_uses_metadata_title(self) -> None:
        """TC-PP04-b: parse() uses 'title' from metadata."""
        parser = HWPParser()
        doc = parser.parse("content", doc_id="hwp-002", metadata={"title": "My HWP"})
        assert doc.title == "My HWP"

    @pytest.mark.unit
    def test_parse_uses_default_title_when_missing(self) -> None:
        """TC-PP04-c: parse() defaults to 'HWP Document' when no title."""
        parser = HWPParser()
        doc = parser.parse("content", doc_id="hwp-003")
        assert doc.title == "HWP Document"


# ---------------------------------------------------------------------------
# TC-PP05: HWPParser with bytes via olefile mock
# ---------------------------------------------------------------------------


class TestHWPParserOlefile:
    """TC-PP05: HWPParser._try_olefile with mocked olefile library."""

    def _make_ole_stream_data(self, text: str) -> bytes:
        """Encode text as little-endian 2-byte code points (OLE stream format)."""
        parts = []
        for ch in text:
            code = ord(ch)
            if 0x20 <= code < 0xFFFF:
                parts.append(struct.pack("<H", code))
        return b"".join(parts)

    @pytest.mark.unit
    def test_try_olefile_extracts_text_from_bodytext_stream(self) -> None:
        """TC-PP05-a: _try_olefile extracts text from BodyText streams."""
        raw_text = "HWP 본문 내용"
        stream_data = self._make_ole_stream_data(raw_text)

        # Build mock olefile
        mock_stream = MagicMock()
        mock_stream.read.return_value = stream_data

        mock_ole = MagicMock()
        mock_ole.listdir.return_value = [["BodyText", "Section0"]]
        mock_ole.openstream.return_value = mock_stream
        mock_ole.close = MagicMock()

        mock_olefile_mod = MagicMock()
        mock_olefile_mod.isOleFile.return_value = True
        mock_olefile_mod.OleFileIO.return_value = mock_ole

        with patch.dict(sys.modules, {"olefile": mock_olefile_mod}):
            result = HWPParser._try_olefile(b"fake ole data")

        assert result is not None
        # The extracted text should contain recognisable characters from raw_text
        assert len(result.strip()) > 0

    @pytest.mark.unit
    def test_try_olefile_returns_none_for_non_ole_file(self) -> None:
        """TC-PP05-b: _try_olefile returns None when not an OLE file."""
        mock_olefile_mod = MagicMock()
        mock_olefile_mod.isOleFile.return_value = False

        with patch.dict(sys.modules, {"olefile": mock_olefile_mod}):
            result = HWPParser._try_olefile(b"not an OLE file")

        assert result is None

    @pytest.mark.unit
    def test_try_olefile_returns_none_when_no_bodytext_streams(self) -> None:
        """TC-PP05-c: _try_olefile returns None when BodyText stream is absent."""
        mock_ole = MagicMock()
        mock_ole.listdir.return_value = [["Metadata", "Summary"]]
        mock_ole.close = MagicMock()

        mock_olefile_mod = MagicMock()
        mock_olefile_mod.isOleFile.return_value = True
        mock_olefile_mod.OleFileIO.return_value = mock_ole

        with patch.dict(sys.modules, {"olefile": mock_olefile_mod}):
            result = HWPParser._try_olefile(b"fake ole data")

        assert result is None


# ---------------------------------------------------------------------------
# TC-PP06: HWPParser fallback chain
# ---------------------------------------------------------------------------


class TestHWPParserFallbackChain:
    """TC-PP06: parse_file falls back correctly through tier chain."""

    @pytest.mark.unit
    def test_parse_file_uses_hwp5txt_when_available(self, tmp_path) -> None:
        """TC-PP06-a: parse_file uses hwp5txt extraction method when CLI available."""
        hwp_file = tmp_path / "doc.hwp"
        hwp_file.write_bytes(b"\xd0\xcf\x11\xe0fake hwp bytes")

        parser = HWPParser()
        expected_text = "hwp5txt로 추출된 텍스트"

        with patch.object(HWPParser, "_try_hwp5txt", return_value=expected_text) as mock_hwp5, \
             patch.object(HWPParser, "_try_olefile", return_value=None) as mock_ole:
            doc = parser.parse_file(str(hwp_file), doc_id="hwp-f01")

        mock_hwp5.assert_called_once()
        mock_ole.assert_not_called()
        assert doc.content == expected_text
        assert doc.metadata.get("extraction_method") == "hwp5txt"

    @pytest.mark.unit
    def test_parse_file_falls_back_to_olefile_when_hwp5txt_fails(self, tmp_path) -> None:
        """TC-PP06-b: parse_file falls back to olefile when hwp5txt returns None."""
        hwp_file = tmp_path / "doc.hwp"
        hwp_file.write_bytes(b"\xd0\xcf\x11\xe0fake hwp bytes")

        parser = HWPParser()
        expected_text = "olefile로 추출된 텍스트"

        with patch.object(HWPParser, "_try_hwp5txt", return_value=None), \
             patch.object(HWPParser, "_try_olefile", return_value=expected_text):
            doc = parser.parse_file(str(hwp_file), doc_id="hwp-f02")

        assert doc.content == expected_text
        assert doc.metadata.get("extraction_method") == "olefile"

    @pytest.mark.unit
    def test_parse_file_returns_error_doc_when_all_methods_fail(self, tmp_path) -> None:
        """TC-PP06-c: parse_file returns a document with error content when all tiers fail."""
        hwp_file = tmp_path / "doc.hwp"
        hwp_file.write_bytes(b"\xd0\xcf\x11\xe0fake hwp bytes")

        parser = HWPParser()

        with patch.object(HWPParser, "_try_hwp5txt", return_value=None), \
             patch.object(HWPParser, "_try_olefile", return_value=None):
            doc = parser.parse_file(str(hwp_file), doc_id="hwp-f03")

        assert doc.doc_type == DocumentType.HWP
        assert "failed" in doc.content.lower() or "HWP" in doc.content
        assert doc.metadata.get("extraction_method") == "failed"


# ---------------------------------------------------------------------------
# TC-PP07: ParserRegistry still works
# ---------------------------------------------------------------------------


class TestParserRegistryWithUpdatedParsers:
    """TC-PP07: ParserRegistry still works correctly after parser updates."""

    @pytest.mark.unit
    def test_registry_parse_pdf_with_string_content(self) -> None:
        """TC-PP07-a: Registry routes PDF content to PDFParser."""
        registry = ParserRegistry()
        doc = registry.parse("PDF text content", DocumentType.PDF, doc_id="reg-pdf-01")
        assert doc.doc_type == DocumentType.PDF
        assert doc.content == "PDF text content"

    @pytest.mark.unit
    def test_registry_parse_hwp_with_string_content(self) -> None:
        """TC-PP07-b: Registry routes HWP content to HWPParser."""
        registry = ParserRegistry()
        doc = registry.parse("HWP text content", DocumentType.HWP, doc_id="reg-hwp-01")
        assert doc.doc_type == DocumentType.HWP
        assert doc.content == "HWP text content"

    @pytest.mark.unit
    def test_registry_has_registered_types(self) -> None:
        """TC-PP07-c: Default registry has all built-in document types."""
        registry = ParserRegistry()
        assert len(registry.supported_types) == 8
        assert DocumentType.PDF in registry.supported_types
        assert DocumentType.HWP in registry.supported_types
