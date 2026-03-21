"""Unit tests for document parsers.

Covers:
    TC-DP01: TextParser
    TC-DP02: MarkdownParser
    TC-DP03: HTMLParser
    TC-DP04: CSVParser
    TC-DP05: PDFParser / HWPParser
    TC-DP06: ParserRegistry
    TC-DP07: DocumentParser protocol

All tests are marked @pytest.mark.unit and require no external dependencies.
No file I/O — parse() is called with string content only.
PYTHONPATH: .
"""
from __future__ import annotations

import pytest

from rag.documents.models import DocumentType
from rag.documents.parsers import (
    CSVParser,
    DocumentParser,
    HTMLParser,
    HWPParser,
    MarkdownParser,
    PDFParser,
    ParserRegistry,
    TextParser,
)


# ---------------------------------------------------------------------------
# TC-DP01: TextParser
# ---------------------------------------------------------------------------


class TestTextParser:
    """TC-DP01: Plain text passthrough parser."""

    def setup_method(self) -> None:
        self.parser = TextParser()

    @pytest.mark.unit
    def test_parse_returns_document_with_txt_type(self) -> None:
        """TC-DP01-a: parse() returns a Document whose doc_type is TXT."""
        doc = self.parser.parse("hello world", doc_id="d1")
        assert doc.doc_type == DocumentType.TXT

    @pytest.mark.unit
    def test_parse_uses_metadata_title(self) -> None:
        """TC-DP01-b: parse() uses the 'title' key from metadata."""
        doc = self.parser.parse("content", doc_id="d1", metadata={"title": "My Title"})
        assert doc.title == "My Title"

    @pytest.mark.unit
    def test_supported_type_is_txt(self) -> None:
        """TC-DP01-c: supported_type property returns TXT."""
        assert self.parser.supported_type == DocumentType.TXT


# ---------------------------------------------------------------------------
# TC-DP02: MarkdownParser
# ---------------------------------------------------------------------------


class TestMarkdownParser:
    """TC-DP02: Markdown stripping and title extraction."""

    def setup_method(self) -> None:
        self.parser = MarkdownParser()

    @pytest.mark.unit
    def test_strip_markdown_removes_headers(self) -> None:
        """TC-DP02-a: _strip_markdown removes # heading markers."""
        result = MarkdownParser._strip_markdown("# Heading One\n## Heading Two\ntext")
        assert "# " not in result
        assert "Heading One" in result
        assert "Heading Two" in result

    @pytest.mark.unit
    def test_strip_markdown_removes_bold_and_italic(self) -> None:
        """TC-DP02-b: _strip_markdown strips **bold** and *italic* markers."""
        result = MarkdownParser._strip_markdown("**bold** and *italic* text")
        assert "**" not in result
        assert "*" not in result
        assert "bold" in result
        assert "italic" in result

    @pytest.mark.unit
    def test_strip_markdown_removes_links(self) -> None:
        """TC-DP02-c: _strip_markdown converts [text](url) to text only."""
        result = MarkdownParser._strip_markdown("[click here](https://example.com)")
        assert "https://example.com" not in result
        assert "click here" in result

    @pytest.mark.unit
    def test_extract_title_finds_h1(self) -> None:
        """TC-DP02-d: _extract_title returns the text of the first H1."""
        title = MarkdownParser._extract_title("# My Document\nsome content")
        assert title == "My Document"

    @pytest.mark.unit
    def test_parse_extracts_title_from_h1(self) -> None:
        """TC-DP02-e: parse() sets Document.title from the H1 heading."""
        content = "# Report Title\nBody text here."
        doc = self.parser.parse(content, doc_id="d2")
        assert doc.title == "Report Title"

    @pytest.mark.unit
    def test_supported_type_is_markdown(self) -> None:
        """TC-DP02-f: supported_type property returns MARKDOWN."""
        assert self.parser.supported_type == DocumentType.MARKDOWN


# ---------------------------------------------------------------------------
# TC-DP03: HTMLParser
# ---------------------------------------------------------------------------


class TestHTMLParser:
    """TC-DP03: HTML tag stripping, entity decoding, script removal."""

    def setup_method(self) -> None:
        self.parser = HTMLParser()

    @pytest.mark.unit
    def test_strip_html_removes_tags(self) -> None:
        """TC-DP03-a: _strip_html removes all HTML tags."""
        result = HTMLParser._strip_html("<p>Hello <b>world</b></p>")
        assert "<" not in result
        assert "Hello" in result
        assert "world" in result

    @pytest.mark.unit
    def test_strip_html_decodes_entities(self) -> None:
        """TC-DP03-b: _strip_html decodes &amp; &lt; &gt; &quot; etc."""
        result = HTMLParser._strip_html("&amp; &lt;tag&gt; &quot;quoted&quot;")
        assert "&amp;" not in result
        assert "&" in result
        assert "<tag>" in result
        assert '"quoted"' in result

    @pytest.mark.unit
    def test_strip_html_removes_script_and_style_blocks(self) -> None:
        """TC-DP03-c: _strip_html strips <script> and <style> blocks entirely."""
        html_content = (
            "<html><head><style>body{color:red}</style></head>"
            "<body><script>alert(1)</script><p>visible</p></body></html>"
        )
        result = HTMLParser._strip_html(html_content)
        assert "color:red" not in result
        assert "alert(1)" not in result
        assert "visible" in result

    @pytest.mark.unit
    def test_extract_title_finds_title_tag(self) -> None:
        """TC-DP03-d: _extract_title returns content of <title> tag."""
        title = HTMLParser._extract_title("<html><head><title>Page Title</title></head></html>")
        assert title == "Page Title"

    @pytest.mark.unit
    def test_parse_returns_html_type(self) -> None:
        """TC-DP03-e: parse() returns a Document with doc_type HTML."""
        doc = self.parser.parse("<p>content</p>", doc_id="d3")
        assert doc.doc_type == DocumentType.HTML

    @pytest.mark.unit
    def test_supported_type_is_html(self) -> None:
        """TC-DP03-f: supported_type property returns HTML."""
        assert self.parser.supported_type == DocumentType.HTML


# ---------------------------------------------------------------------------
# TC-DP04: CSVParser
# ---------------------------------------------------------------------------


class TestCSVParser:
    """TC-DP04: CSV to tab-separated text conversion."""

    def setup_method(self) -> None:
        self.parser = CSVParser()

    @pytest.mark.unit
    def test_parse_converts_csv_to_tab_separated(self) -> None:
        """TC-DP04-a: parse() joins CSV fields with tabs in output content."""
        csv_content = "name,age,city\nAlice,30,Seoul\nBob,25,Busan"
        doc = self.parser.parse(csv_content, doc_id="d4")
        lines = doc.content.splitlines()
        assert lines[0] == "name\tage\tcity"
        assert lines[1] == "Alice\t30\tSeoul"
        assert lines[2] == "Bob\t25\tBusan"

    @pytest.mark.unit
    def test_parse_sets_row_and_column_count_metadata(self) -> None:
        """TC-DP04-b: parse() stores row_count and column_count in metadata."""
        csv_content = "a,b,c\n1,2,3\n4,5,6"
        doc = self.parser.parse(csv_content, doc_id="d4")
        assert doc.metadata["row_count"] == 3
        assert doc.metadata["column_count"] == 3

    @pytest.mark.unit
    def test_supported_type_is_csv(self) -> None:
        """TC-DP04-c: supported_type property returns CSV."""
        assert self.parser.supported_type == DocumentType.CSV


# ---------------------------------------------------------------------------
# TC-DP05: PDFParser / HWPParser
# ---------------------------------------------------------------------------


class TestPDFParser:
    """TC-DP05: PDFParser stub."""

    def setup_method(self) -> None:
        self.parser = PDFParser()

    @pytest.mark.unit
    def test_parse_accepts_raw_text_content(self) -> None:
        """TC-DP05-a: PDFParser.parse() accepts pre-extracted text and returns Document."""
        raw_text = "Extracted PDF text paragraph one.\nParagraph two."
        doc = self.parser.parse(raw_text, doc_id="pdf-001")
        assert doc.content == raw_text
        assert doc.doc_type == DocumentType.PDF

    @pytest.mark.unit
    def test_supported_type_is_pdf(self) -> None:
        """TC-DP05-c (PDF half): supported_type is PDF."""
        assert self.parser.supported_type == DocumentType.PDF


class TestHWPParser:
    """TC-DP05: HWPParser stub."""

    def setup_method(self) -> None:
        self.parser = HWPParser()

    @pytest.mark.unit
    def test_parse_accepts_raw_text_content(self) -> None:
        """TC-DP05-b: HWPParser.parse() accepts pre-extracted text and returns Document."""
        raw_text = "Extracted HWP text content."
        doc = self.parser.parse(raw_text, doc_id="hwp-001")
        assert doc.content == raw_text
        assert doc.doc_type == DocumentType.HWP

    @pytest.mark.unit
    def test_supported_type_is_hwp(self) -> None:
        """TC-DP05-c (HWP half): supported_type is HWP."""
        assert self.parser.supported_type == DocumentType.HWP


# ---------------------------------------------------------------------------
# TC-DP06: ParserRegistry
# ---------------------------------------------------------------------------


class TestParserRegistry:
    """TC-DP06: ParserRegistry functionality."""

    def setup_method(self) -> None:
        self.registry = ParserRegistry()

    @pytest.mark.unit
    def test_default_registry_has_all_six_types(self) -> None:
        """TC-DP06-a: Default registry registers all 6 DocumentType values."""
        registered = set(self.registry.supported_types)
        expected = {
            DocumentType.TXT,
            DocumentType.MARKDOWN,
            DocumentType.HTML,
            DocumentType.CSV,
            DocumentType.PDF,
            DocumentType.HWP,
        }
        assert registered == expected

    @pytest.mark.unit
    def test_detect_type_maps_txt_extension(self) -> None:
        """TC-DP06-b: detect_type maps .txt -> TXT."""
        assert self.registry.detect_type("report.txt") == DocumentType.TXT

    @pytest.mark.unit
    def test_detect_type_maps_md_extension(self) -> None:
        """TC-DP06-b: detect_type maps .md -> MARKDOWN."""
        assert self.registry.detect_type("readme.md") == DocumentType.MARKDOWN

    @pytest.mark.unit
    def test_detect_type_maps_html_extension(self) -> None:
        """TC-DP06-b: detect_type maps .html -> HTML."""
        assert self.registry.detect_type("page.html") == DocumentType.HTML

    @pytest.mark.unit
    def test_detect_type_maps_csv_extension(self) -> None:
        """TC-DP06-b: detect_type maps .csv -> CSV."""
        assert self.registry.detect_type("data.csv") == DocumentType.CSV

    @pytest.mark.unit
    def test_detect_type_maps_pdf_extension(self) -> None:
        """TC-DP06-b: detect_type maps .pdf -> PDF."""
        assert self.registry.detect_type("doc.pdf") == DocumentType.PDF

    @pytest.mark.unit
    def test_detect_type_maps_hwp_extension(self) -> None:
        """TC-DP06-b: detect_type maps .hwp -> HWP."""
        assert self.registry.detect_type("document.hwp") == DocumentType.HWP

    @pytest.mark.unit
    def test_detect_type_returns_txt_for_unknown_extension(self) -> None:
        """TC-DP06-c: detect_type falls back to TXT for unrecognised extensions."""
        assert self.registry.detect_type("archive.xyz") == DocumentType.TXT

    @pytest.mark.unit
    def test_parse_delegates_to_correct_parser(self) -> None:
        """TC-DP06-d: parse() routes to the right parser based on doc_type."""
        doc = self.registry.parse("# Title\nBody.", DocumentType.MARKDOWN, doc_id="r1")
        assert doc.doc_type == DocumentType.MARKDOWN
        assert doc.title == "Title"

    @pytest.mark.unit
    def test_parse_raises_value_error_for_unregistered_type(self) -> None:
        """TC-DP06-e: parse() raises ValueError when type has no registered parser."""
        # Remove a parser from the internal dict to simulate missing registration.
        del self.registry._parsers[DocumentType.CSV]
        with pytest.raises(ValueError, match="csv"):
            self.registry.parse("a,b", DocumentType.CSV, doc_id="r2")

    @pytest.mark.unit
    def test_register_allows_custom_parser(self) -> None:
        """TC-DP06-f: register() replaces the parser for a given type and returns self."""

        class AlwaysUpperTextParser(TextParser):
            def parse(self, content, doc_id="", metadata=None):
                doc = super().parse(content, doc_id=doc_id, metadata=metadata)
                # Return a new Document with uppercased content
                import dataclasses
                return dataclasses.replace(doc, content=content.upper())

        custom = AlwaysUpperTextParser()
        result = self.registry.register(custom)
        # register() returns self for chaining
        assert result is self.registry
        doc = self.registry.parse("hello", DocumentType.TXT, doc_id="r3")
        assert doc.content == "HELLO"

    @pytest.mark.unit
    def test_supported_types_property(self) -> None:
        """TC-DP06-g: supported_types returns a list of registered DocumentType values."""
        types = self.registry.supported_types
        assert isinstance(types, list)
        assert len(types) == 6
        assert DocumentType.PDF in types


# ---------------------------------------------------------------------------
# TC-DP07: DocumentParser protocol
# ---------------------------------------------------------------------------


class TestDocumentParserProtocol:
    """TC-DP07: All concrete parsers satisfy the DocumentParser protocol."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "parser_cls",
        [TextParser, MarkdownParser, HTMLParser, CSVParser, PDFParser, HWPParser],
    )
    def test_all_parsers_satisfy_protocol(self, parser_cls) -> None:
        """TC-DP07-a: isinstance(parser, DocumentParser) is True for every parser."""
        parser = parser_cls()
        assert isinstance(parser, DocumentParser)
