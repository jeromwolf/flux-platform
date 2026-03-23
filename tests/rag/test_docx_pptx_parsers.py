"""Tests for DOCX and PPTX parsers.

Covers:
    TC-DP08: DOCXParser (bytes extraction + fallback via zipfile)
    TC-DP09: PPTXParser (bytes extraction + fallback via zipfile)
    TC-DP10: ParserRegistry DOCX/PPTX registration and detect_type

All tests are marked @pytest.mark.unit and require no external dependencies.
The fallback (zipfile-based) extraction path must work without python-docx or
python-pptx installed.
"""
from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from rag.documents.models import DocumentType
from rag.documents.parsers import DOCXParser, PPTXParser, ParserRegistry


# ---------------------------------------------------------------------------
# Minimal synthetic file helpers (stdlib only — no python-docx / python-pptx)
# ---------------------------------------------------------------------------


def _make_minimal_docx(text: str = "Hello World") -> bytes:
    """Create a minimal well-formed DOCX zip containing word/document.xml."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>"
            "</w:document>"
        )
        zf.writestr("word/document.xml", xml)
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
    return buf.getvalue()


def _make_minimal_pptx(text: str = "Slide Content") -> bytes:
    """Create a minimal well-formed PPTX zip containing ppt/slides/slide1.xml."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
            '       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            "<p:cSld><p:spTree><p:sp><p:txBody>"
            f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
            "</p:txBody></p:sp></p:spTree></p:cSld>"
            "</p:sld>"
        )
        zf.writestr("ppt/slides/slide1.xml", xml)
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# TC-DP08: DOCXParser
# ---------------------------------------------------------------------------


class TestDOCXParser:
    """TC-DP08: DOCXParser text extraction using the zipfile fallback."""

    def setup_method(self) -> None:
        self.parser = DOCXParser()

    @pytest.mark.unit
    def test_parse_bytes_minimal_docx_returns_text(self) -> None:
        """TC-DP08-a: parse() with bytes from a minimal DOCX extracts embedded text."""
        content = _make_minimal_docx("테스트 문서")
        doc = self.parser.parse(content, doc_id="d-docx-01")
        assert "테스트 문서" in doc.content

    @pytest.mark.unit
    def test_parse_bytes_empty_text_returns_document(self) -> None:
        """TC-DP08-b: parse() with an empty-text DOCX returns a Document with string content."""
        content = _make_minimal_docx("")
        doc = self.parser.parse(content, doc_id="d-docx-02")
        assert isinstance(doc.content, str)

    @pytest.mark.unit
    def test_parse_bytes_invalid_content_returns_empty(self) -> None:
        """TC-DP08-c: parse() with non-zip bytes returns a Document with empty content."""
        doc = self.parser.parse(b"not a zip file", doc_id="d-docx-03")
        assert doc.content == ""

    @pytest.mark.unit
    def test_parse_string_passthrough(self) -> None:
        """TC-DP08-d: parse() with a plain string uses it as-is (pre-extracted path)."""
        doc = self.parser.parse("pre-extracted text", doc_id="d-docx-04")
        assert doc.content == "pre-extracted text"

    @pytest.mark.unit
    def test_parse_doc_type_is_docx(self) -> None:
        """TC-DP08-e: parse() always returns a Document with doc_type DOCX."""
        doc = self.parser.parse(b"", doc_id="d-docx-05")
        assert doc.doc_type == DocumentType.DOCX

    @pytest.mark.unit
    def test_supported_type_is_docx(self) -> None:
        """TC-DP08-f: supported_type property returns DOCX."""
        assert self.parser.supported_type == DocumentType.DOCX

    @pytest.mark.unit
    def test_korean_content_preserved(self) -> None:
        """TC-DP08-g: Korean text in DOCX is correctly extracted."""
        content = _make_minimal_docx("해사 안전 규정 문서")
        doc = self.parser.parse(content, doc_id="d-docx-06")
        assert "해사" in doc.content

    @pytest.mark.unit
    def test_parse_uses_metadata_title(self) -> None:
        """TC-DP08-h: parse() uses 'title' from metadata when provided."""
        content = _make_minimal_docx("some text")
        doc = self.parser.parse(content, doc_id="d-docx-07", metadata={"title": "My Report"})
        assert doc.title == "My Report"


# ---------------------------------------------------------------------------
# TC-DP09: PPTXParser
# ---------------------------------------------------------------------------


class TestPPTXParser:
    """TC-DP09: PPTXParser text extraction using the zipfile fallback."""

    def setup_method(self) -> None:
        self.parser = PPTXParser()

    @pytest.mark.unit
    def test_parse_bytes_minimal_pptx_returns_text(self) -> None:
        """TC-DP09-a: parse() with bytes from a minimal PPTX extracts slide text."""
        content = _make_minimal_pptx("발표 자료")
        doc = self.parser.parse(content, doc_id="d-pptx-01")
        # The XML fallback strips tags; text content must appear somewhere
        assert "발표" in doc.content or "발표 자료" in doc.content

    @pytest.mark.unit
    def test_parse_bytes_empty_text_returns_document(self) -> None:
        """TC-DP09-b: parse() with an empty-text PPTX returns a Document with string content."""
        content = _make_minimal_pptx("")
        doc = self.parser.parse(content, doc_id="d-pptx-02")
        assert isinstance(doc.content, str)

    @pytest.mark.unit
    def test_parse_bytes_invalid_content_returns_empty(self) -> None:
        """TC-DP09-c: parse() with non-zip bytes returns a Document with empty content."""
        doc = self.parser.parse(b"not a zip file", doc_id="d-pptx-03")
        assert doc.content == ""

    @pytest.mark.unit
    def test_parse_string_passthrough(self) -> None:
        """TC-DP09-d: parse() with a plain string uses it as-is."""
        doc = self.parser.parse("pre-extracted slides text", doc_id="d-pptx-04")
        assert doc.content == "pre-extracted slides text"

    @pytest.mark.unit
    def test_parse_doc_type_is_pptx(self) -> None:
        """TC-DP09-e: parse() always returns a Document with doc_type PPTX."""
        doc = self.parser.parse(b"", doc_id="d-pptx-05")
        assert doc.doc_type == DocumentType.PPTX

    @pytest.mark.unit
    def test_supported_type_is_pptx(self) -> None:
        """TC-DP09-f: supported_type property returns PPTX."""
        assert self.parser.supported_type == DocumentType.PPTX

    @pytest.mark.unit
    def test_parse_uses_metadata_title(self) -> None:
        """TC-DP09-g: parse() uses 'title' from metadata when provided."""
        content = _make_minimal_pptx("slide text")
        doc = self.parser.parse(content, doc_id="d-pptx-06", metadata={"title": "My Deck"})
        assert doc.title == "My Deck"


# ---------------------------------------------------------------------------
# TC-DP10: ParserRegistry DOCX/PPTX registration and detect_type
# ---------------------------------------------------------------------------


class TestParserRegistryDocxPptx:
    """TC-DP10: Registry has DOCX/PPTX parsers and detects them by extension."""

    def setup_method(self) -> None:
        self.registry = ParserRegistry()

    @pytest.mark.unit
    def test_registry_has_docx_parser(self) -> None:
        """TC-DP10-a: get_parser(DocumentType.DOCX) returns a DOCXParser."""
        parser = self.registry.get_parser(DocumentType.DOCX)
        assert parser is not None
        assert isinstance(parser, DOCXParser)

    @pytest.mark.unit
    def test_registry_has_pptx_parser(self) -> None:
        """TC-DP10-b: get_parser(DocumentType.PPTX) returns a PPTXParser."""
        parser = self.registry.get_parser(DocumentType.PPTX)
        assert parser is not None
        assert isinstance(parser, PPTXParser)

    @pytest.mark.unit
    def test_detect_type_maps_docx_extension(self) -> None:
        """TC-DP10-c: detect_type maps .docx -> DOCX."""
        assert self.registry.detect_type("report.docx") == DocumentType.DOCX

    @pytest.mark.unit
    def test_detect_type_maps_doc_extension(self) -> None:
        """TC-DP10-d: detect_type maps .doc -> DOCX (best-effort)."""
        assert self.registry.detect_type("legacy.doc") == DocumentType.DOCX

    @pytest.mark.unit
    def test_detect_type_maps_pptx_extension(self) -> None:
        """TC-DP10-e: detect_type maps .pptx -> PPTX."""
        assert self.registry.detect_type("presentation.pptx") == DocumentType.PPTX

    @pytest.mark.unit
    def test_parse_docx_bytes_via_registry(self) -> None:
        """TC-DP10-f: registry.parse() with DOCX type extracts text from bytes."""
        content = _make_minimal_docx("auto detect test")
        doc = self.registry.parse(content, DocumentType.DOCX, doc_id="reg-01")
        assert "auto detect test" in doc.content

    @pytest.mark.unit
    def test_parse_pptx_bytes_via_registry(self) -> None:
        """TC-DP10-g: registry.parse() with PPTX type returns a valid Document."""
        content = _make_minimal_pptx("slides test")
        doc = self.registry.parse(content, DocumentType.PPTX, doc_id="reg-02")
        assert isinstance(doc.content, str)
        assert doc.doc_type == DocumentType.PPTX

    @pytest.mark.unit
    def test_docx_in_supported_types(self) -> None:
        """TC-DP10-h: DOCX and PPTX appear in supported_types."""
        assert DocumentType.DOCX in self.registry.supported_types
        assert DocumentType.PPTX in self.registry.supported_types
