"""Extended unit tests for rag/documents/parsers.py.

Covers the branches not exercised by test_parsers.py:
- TextParser.parse_file / default title/source metadata
- MarkdownParser.parse_file / edge cases (code block, image, blockquote)
- HTMLParser.parse_file / edge cases
- CSVParser.parse / empty CSV
- PDFParser._calculate_quality / parse_file fallback paths
- HWPParser._extract_text_from_ole_stream / _try_hwp5txt unsafe path
- DOCXParser.parse(bytes) / parse_file / _extract_text zipfile fallback
- PPTXParser.parse(bytes) / parse_file / _extract_text zipfile fallback
- ParserRegistry.detect_type edge cases (.htm, .doc, .markdown)
- ParserRegistry.get_parser / parse_file auto-detect / parse_file no-parser

All tests are @pytest.mark.unit.  No real file I/O unless tmpfiles are used
via the tmp_path fixture; no network calls; no optional heavy dependencies
(fitz, olefile, docx, pptx) are required.
"""
from __future__ import annotations

import os
import struct
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from rag.documents.models import DocumentType
from rag.documents.parsers import (
    CSVParser,
    DOCXParser,
    HTMLParser,
    HWPParser,
    MarkdownParser,
    PDFParser,
    PPTXParser,
    ParserRegistry,
    TextParser,
)


# ---------------------------------------------------------------------------
# TextParser — parse_file
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTextParserParseFile:
    """TextParser.parse_file reads a file and auto-fills title/source."""

    def test_parse_file_reads_content(self, tmp_path):
        """parse_file returns a Document whose content matches the file."""
        f = tmp_path / "hello.txt"
        f.write_text("hello world", encoding="utf-8")
        parser = TextParser()
        doc = parser.parse_file(str(f))
        assert doc.content == "hello world"
        assert doc.doc_type == DocumentType.TXT

    def test_parse_file_auto_title_from_filename(self, tmp_path):
        """parse_file uses the filename as title when metadata has no title."""
        f = tmp_path / "my_report.txt"
        f.write_text("data", encoding="utf-8")
        parser = TextParser()
        doc = parser.parse_file(str(f))
        assert doc.title == "my_report.txt"

    def test_parse_file_auto_source_from_path(self, tmp_path):
        """parse_file sets source to the full file path."""
        f = tmp_path / "report.txt"
        f.write_text("content", encoding="utf-8")
        parser = TextParser()
        doc = parser.parse_file(str(f))
        assert doc.source == str(f)

    def test_parse_file_explicit_doc_id(self, tmp_path):
        """parse_file uses the caller-supplied doc_id."""
        f = tmp_path / "doc.txt"
        f.write_text("x", encoding="utf-8")
        parser = TextParser()
        doc = parser.parse_file(str(f), doc_id="explicit-id")
        assert doc.doc_id == "explicit-id"

    def test_parse_file_metadata_overrides_title(self, tmp_path):
        """parse_file respects caller-supplied title in metadata."""
        f = tmp_path / "doc.txt"
        f.write_text("x", encoding="utf-8")
        parser = TextParser()
        doc = parser.parse_file(str(f), metadata={"title": "Custom Title"})
        assert doc.title == "Custom Title"


# ---------------------------------------------------------------------------
# MarkdownParser — parse_file and additional strip_markdown paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMarkdownParserExtended:
    """Additional MarkdownParser coverage."""

    def test_strip_markdown_removes_fenced_code_blocks(self):
        """_strip_markdown removes ```...``` code blocks."""
        md = "Before\n```python\nprint('hello')\n```\nAfter"
        result = MarkdownParser._strip_markdown(md)
        assert "print" not in result
        assert "Before" in result
        assert "After" in result

    def test_strip_markdown_removes_images(self):
        """_strip_markdown turns ![alt](url) into alt text only."""
        result = MarkdownParser._strip_markdown("![logo](https://example.com/img.png)")
        assert "https://example.com/img.png" not in result

    def test_strip_markdown_removes_blockquotes(self):
        """_strip_markdown strips leading > from blockquotes."""
        result = MarkdownParser._strip_markdown("> This is a quote")
        assert result.strip() == "This is a quote"

    def test_strip_markdown_removes_horizontal_rules(self):
        """_strip_markdown removes --- / *** horizontal rule lines."""
        result = MarkdownParser._strip_markdown("paragraph\n\n---\n\nanother")
        assert "---" not in result
        assert "paragraph" in result

    def test_strip_markdown_removes_inline_code(self):
        """_strip_markdown strips `backtick` inline code markers."""
        result = MarkdownParser._strip_markdown("Use `func()` here")
        assert "`" not in result
        assert "func()" in result

    def test_extract_title_returns_empty_when_no_h1(self):
        """_extract_title returns an empty string when no H1 is present."""
        title = MarkdownParser._extract_title("## Not H1\nsome text")
        assert title == ""

    def test_parse_file_reads_markdown(self, tmp_path):
        """parse_file parses markdown from a .md file."""
        f = tmp_path / "readme.md"
        f.write_text("# My Title\nBody text", encoding="utf-8")
        parser = MarkdownParser()
        doc = parser.parse_file(str(f))
        assert doc.title == "My Title"
        assert doc.doc_type == DocumentType.MARKDOWN
        assert doc.source == str(f)


# ---------------------------------------------------------------------------
# HTMLParser — edge cases and parse_file
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHTMLParserExtended:
    """Additional HTMLParser coverage."""

    def test_strip_html_handles_br_tags(self):
        """<br> produces a newline in the output."""
        result = HTMLParser._strip_html("line1<br>line2")
        assert "line1" in result
        assert "line2" in result

    def test_extract_title_returns_empty_when_no_title_tag(self):
        """_extract_title returns empty string when no <title> tag exists."""
        title = HTMLParser._extract_title("<html><body><p>text</p></body></html>")
        assert title == ""

    def test_parse_file_reads_html(self, tmp_path):
        """parse_file loads an HTML file and strips tags."""
        f = tmp_path / "page.html"
        f.write_text(
            "<html><head><title>Page</title></head><body><p>Hello</p></body></html>",
            encoding="utf-8",
        )
        parser = HTMLParser()
        doc = parser.parse_file(str(f))
        assert doc.title == "Page"
        assert "Hello" in doc.content
        assert doc.doc_type == DocumentType.HTML


# ---------------------------------------------------------------------------
# CSVParser — empty CSV edge case
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCSVParserExtended:
    """Additional CSVParser edge cases."""

    def test_parse_empty_csv_sets_zero_counts(self):
        """parse() on empty content results in row_count=0, column_count=0."""
        parser = CSVParser()
        doc = parser.parse("", doc_id="empty-csv")
        assert doc.metadata["row_count"] == 0
        assert doc.metadata["column_count"] == 0

    def test_parse_csv_default_title(self):
        """parse() uses 'CSV Data' as default title when metadata has no title."""
        parser = CSVParser()
        doc = parser.parse("a,b\n1,2", doc_id="d")
        assert doc.title == "CSV Data"

    def test_parse_file_csv_sets_title_from_filename(self, tmp_path):
        """parse_file uses filename as title for CSV files."""
        f = tmp_path / "data.csv"
        f.write_text("x,y\n1,2", encoding="utf-8")
        parser = CSVParser()
        doc = parser.parse_file(str(f))
        assert doc.title == "data.csv"


# ---------------------------------------------------------------------------
# PDFParser — _calculate_quality and parse_file fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPDFParserExtended:
    """PDFParser._calculate_quality and parse_file fallback behavior."""

    def test_calculate_quality_empty_text_returns_zero(self):
        """_calculate_quality returns 0.0 for empty string."""
        score = PDFParser._calculate_quality("")
        assert score == 0.0

    def test_calculate_quality_high_for_clean_text(self):
        """_calculate_quality returns a high score for normal English text."""
        score = PDFParser._calculate_quality("Hello world, this is a clean PDF page.")
        assert score > 0.9

    def test_calculate_quality_includes_korean(self):
        """_calculate_quality treats Hangul syllables as meaningful characters."""
        score = PDFParser._calculate_quality("안녕하세요 Hello")
        assert score > 0.9

    def test_calculate_quality_low_for_garbage(self):
        """Binary-like garbage text yields a quality score close to 0."""
        # Use control characters and symbols that are NOT alphabetic
        garbage = "".join(chr(c) for c in range(0x2500, 0x2580))  # Box drawing chars
        score = PDFParser._calculate_quality(garbage)
        assert score < 0.5

    def test_parse_file_falls_back_when_fitz_missing(self, tmp_path):
        """parse_file reads the file as plain text when fitz is not installed."""
        f = tmp_path / "report.pdf"
        f.write_text("plain text content", encoding="utf-8")
        parser = PDFParser()
        with patch.dict("sys.modules", {"fitz": None}):
            doc = parser.parse_file(str(f))
        assert doc.doc_type == DocumentType.PDF
        assert "plain text content" in doc.content

    def test_parse_file_handles_fitz_exception(self, tmp_path):
        """parse_file returns an error Document when fitz.open raises."""
        f = tmp_path / "bad.pdf"
        f.write_bytes(b"not a real pdf")
        parser = PDFParser()

        fake_fitz = MagicMock()
        fake_fitz.open.side_effect = RuntimeError("corrupt pdf")
        with patch.dict("sys.modules", {"fitz": fake_fitz}):
            doc = parser.parse_file(str(f))
        assert doc.doc_type == DocumentType.PDF
        assert "parsing failed" in doc.content.lower() or "corrupt" in doc.content.lower()

    def test_parse_sets_default_title(self):
        """parse() uses 'PDF Document' as default title."""
        parser = PDFParser()
        doc = parser.parse("some pdf text", doc_id="pdf-1")
        assert doc.title == "PDF Document"


# ---------------------------------------------------------------------------
# HWPParser — _extract_text_from_ole_stream and unsafe path guard
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHWPParserExtended:
    """HWPParser low-level helpers."""

    def test_extract_text_from_ole_stream_ascii_chars(self):
        """_extract_text_from_ole_stream extracts printable ASCII characters."""
        # Build little-endian encoded bytes for 'A', 'B', 'C'
        data = struct.pack("<HHH", ord("A"), ord("B"), ord("C"))
        result = HWPParser._extract_text_from_ole_stream(data, struct)
        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_extract_text_from_ole_stream_newline_codes(self):
        """Code 0x0A (LF) is converted to a newline character."""
        data = struct.pack("<H", 0x0A)
        result = HWPParser._extract_text_from_ole_stream(data, struct)
        assert "\n" in result

    def test_extract_text_from_ole_stream_filters_bom(self):
        """BOM code points (0xFEFF, 0xFFFE) are skipped."""
        data = struct.pack("<HH", 0xFEFF, ord("X"))
        result = HWPParser._extract_text_from_ole_stream(data, struct)
        assert chr(0xFEFF) not in result

    def test_try_hwp5txt_skips_unsafe_path(self):
        """_try_hwp5txt returns None for paths with shell metacharacters."""
        result = HWPParser._try_hwp5txt("/tmp/file;rm -rf /")
        assert result is None

    def test_try_olefile_returns_none_when_not_installed(self):
        """_try_olefile returns None when the olefile package is not available."""
        with patch.dict("sys.modules", {"olefile": None}):
            result = HWPParser._try_olefile(b"not an ole file")
        assert result is None

    def test_parse_returns_hwp_type(self):
        """parse() returns Document with HWP doc_type."""
        parser = HWPParser()
        doc = parser.parse("some hwp text", doc_id="hwp-1")
        assert doc.doc_type == DocumentType.HWP
        assert doc.title == "HWP Document"

    def test_parse_file_unreadable_file(self, tmp_path):
        """parse_file returns an error Document when the file cannot be read."""
        missing = str(tmp_path / "missing.hwp")
        parser = HWPParser()
        doc = parser.parse_file(missing)
        assert doc.doc_type == DocumentType.HWP
        assert "failed" in doc.content.lower() or "HWP" in doc.content


# ---------------------------------------------------------------------------
# DOCXParser — bytes input, parse_file, zipfile fallback, file-read failure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDOCXParserExtended:
    """DOCXParser with mocked python-docx and zipfile fallback."""

    def _make_minimal_docx_bytes(self) -> bytes:
        """Build a minimal valid DOCX (zip) with word/document.xml."""
        buf = BytesIO()
        xml = (
            '<?xml version="1.0"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Hello DOCX</w:t></w:r></w:p></w:body>"
            "</w:document>"
        )
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("word/document.xml", xml)
        return buf.getvalue()

    def test_parse_bytes_uses_zipfile_fallback(self):
        """parse(bytes) falls back to zipfile XML extraction when docx not installed."""
        data = self._make_minimal_docx_bytes()
        parser = DOCXParser()
        # Force docx import to fail
        with patch.dict("sys.modules", {"docx": None}):
            doc = parser.parse(data, doc_id="docx-1")
        assert doc.doc_type == DocumentType.DOCX
        assert "Hello DOCX" in doc.content or doc.content != ""

    def test_parse_string_passthrough(self):
        """parse(str) uses the string content directly without extraction."""
        parser = DOCXParser()
        doc = parser.parse("pre-extracted text", doc_id="docx-str")
        assert doc.content == "pre-extracted text"
        assert doc.doc_type == DocumentType.DOCX

    def test_parse_file_reads_and_delegates(self, tmp_path):
        """parse_file reads bytes and delegates to parse()."""
        data = self._make_minimal_docx_bytes()
        f = tmp_path / "report.docx"
        f.write_bytes(data)
        parser = DOCXParser()
        with patch.dict("sys.modules", {"docx": None}):
            doc = parser.parse_file(str(f))
        assert doc.doc_type == DocumentType.DOCX
        assert doc.title == "report.docx"

    def test_parse_file_unreadable_returns_error_document(self, tmp_path):
        """parse_file returns an error Document when the file does not exist."""
        parser = DOCXParser()
        doc = parser.parse_file(str(tmp_path / "missing.docx"))
        assert doc.doc_type == DocumentType.DOCX
        assert "failed" in doc.content.lower()

    def test_extract_text_empty_zip_returns_empty(self):
        """_extract_text returns empty string for a zip with no document.xml."""
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("other/file.xml", "<x/>")
        data = buf.getvalue()
        with patch.dict("sys.modules", {"docx": None}):
            result = DOCXParser._extract_text(data)
        assert result == ""

    def test_parse_default_title(self):
        """parse() uses 'DOCX Document' as default title."""
        parser = DOCXParser()
        doc = parser.parse("text", doc_id="d")
        assert doc.title == "DOCX Document"


# ---------------------------------------------------------------------------
# PPTXParser — bytes input, parse_file, zipfile fallback, file-read failure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPPTXParserExtended:
    """PPTXParser with mocked python-pptx and zipfile fallback."""

    def _make_minimal_pptx_bytes(self) -> bytes:
        """Build a minimal valid PPTX (zip) with a single slide."""
        buf = BytesIO()
        xml = (
            '<?xml version="1.0"?>'
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
            ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            "<p:cSld><p:spTree/></p:cSld>"
            "</p:sld>"
        )
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("ppt/slides/slide1.xml", xml)
        return buf.getvalue()

    def test_parse_bytes_uses_zipfile_fallback(self):
        """parse(bytes) falls back to zipfile XML extraction when pptx not installed."""
        data = self._make_minimal_pptx_bytes()
        parser = PPTXParser()
        with patch.dict("sys.modules", {"pptx": None}):
            doc = parser.parse(data, doc_id="pptx-1")
        assert doc.doc_type == DocumentType.PPTX

    def test_parse_string_passthrough(self):
        """parse(str) uses the string content directly."""
        parser = PPTXParser()
        doc = parser.parse("slide text", doc_id="pptx-str")
        assert doc.content == "slide text"
        assert doc.doc_type == DocumentType.PPTX

    def test_parse_file_reads_and_delegates(self, tmp_path):
        """parse_file reads bytes and calls parse()."""
        data = self._make_minimal_pptx_bytes()
        f = tmp_path / "deck.pptx"
        f.write_bytes(data)
        parser = PPTXParser()
        with patch.dict("sys.modules", {"pptx": None}):
            doc = parser.parse_file(str(f))
        assert doc.doc_type == DocumentType.PPTX
        assert doc.title == "deck.pptx"

    def test_parse_file_unreadable_returns_error_document(self, tmp_path):
        """parse_file returns an error Document when the file is missing."""
        parser = PPTXParser()
        doc = parser.parse_file(str(tmp_path / "missing.pptx"))
        assert doc.doc_type == DocumentType.PPTX
        assert "failed" in doc.content.lower()

    def test_extract_text_no_slide_files_returns_empty(self):
        """_extract_text returns empty string when zip has no slide XML files."""
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("ppt/other.xml", "<x/>")
        data = buf.getvalue()
        with patch.dict("sys.modules", {"pptx": None}):
            result = PPTXParser._extract_text(data)
        assert result == ""

    def test_parse_default_title(self):
        """parse() uses 'PPTX Document' as default title."""
        parser = PPTXParser()
        doc = parser.parse("text", doc_id="p")
        assert doc.title == "PPTX Document"


# ---------------------------------------------------------------------------
# ParserRegistry — additional detect_type variants and get_parser
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParserRegistryExtended:
    """ParserRegistry.detect_type edge cases and get_parser."""

    def setup_method(self):
        self.registry = ParserRegistry()

    def test_detect_type_htm_extension(self):
        """detect_type maps .htm -> HTML."""
        assert self.registry.detect_type("file.htm") == DocumentType.HTML

    def test_detect_type_markdown_extension(self):
        """detect_type maps .markdown -> MARKDOWN."""
        assert self.registry.detect_type("notes.markdown") == DocumentType.MARKDOWN

    def test_detect_type_doc_extension(self):
        """detect_type maps .doc -> DOCX."""
        assert self.registry.detect_type("legacy.doc") == DocumentType.DOCX

    def test_detect_type_pptx_extension(self):
        """detect_type maps .pptx -> PPTX."""
        assert self.registry.detect_type("slides.pptx") == DocumentType.PPTX

    def test_detect_type_is_case_insensitive(self):
        """detect_type handles uppercase extensions."""
        assert self.registry.detect_type("report.PDF") == DocumentType.PDF

    def test_get_parser_returns_correct_instance(self):
        """get_parser returns the registered parser instance for a known type."""
        parser = self.registry.get_parser(DocumentType.MARKDOWN)
        assert parser is not None
        assert parser.supported_type == DocumentType.MARKDOWN

    def test_get_parser_returns_none_for_unregistered(self):
        """get_parser returns None when type has no registered parser."""
        del self.registry._parsers[DocumentType.HWP]
        result = self.registry.get_parser(DocumentType.HWP)
        assert result is None

    def test_parse_file_auto_detect_type(self, tmp_path):
        """parse_file auto-detects DocumentType from extension when type omitted."""
        f = tmp_path / "doc.txt"
        f.write_text("auto detect test", encoding="utf-8")
        doc = self.registry.parse_file(str(f))
        assert doc.doc_type == DocumentType.TXT
        assert doc.content == "auto detect test"

    def test_parse_file_raises_for_unregistered_type(self, tmp_path):
        """parse_file raises ValueError when no parser handles the detected type."""
        f = tmp_path / "doc.txt"
        f.write_text("x", encoding="utf-8")
        del self.registry._parsers[DocumentType.TXT]
        with pytest.raises(ValueError, match="txt"):
            self.registry.parse_file(str(f))
