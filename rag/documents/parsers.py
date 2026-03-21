"""Document parsers for various file formats.

Each parser converts a raw file into a Document instance.
Y1 implementations use stdlib only; Y2+ will use specialized
libraries (PyPDF2, python-hwp, etc.).

Usage::

    registry = ParserRegistry()
    doc = registry.parse("report content", DocumentType.PDF, doc_id="doc-001")
"""
from __future__ import annotations

import csv
import html
import io
import logging
import os
import re
from typing import Any, Optional, Protocol, runtime_checkable

from rag.documents.models import Document, DocumentType

logger = logging.getLogger(__name__)


@runtime_checkable
class DocumentParser(Protocol):
    """Protocol for document format parsers."""

    def parse(
        self,
        content: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        """Parse raw content into a Document."""
        ...

    def parse_file(
        self,
        file_path: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        """Parse a file into a Document."""
        ...

    @property
    def supported_type(self) -> DocumentType:
        """Document type this parser handles."""
        ...


class TextParser:
    """Plain text parser (passthrough)."""

    @property
    def supported_type(self) -> DocumentType:
        return DocumentType.TXT

    def parse(
        self,
        content: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        meta = metadata or {}
        return Document(
            doc_id=doc_id or "unknown",
            title=meta.get("title", "Untitled"),
            content=content,
            doc_type=DocumentType.TXT,
            source=meta.get("source", ""),
            metadata=meta,
        )

    def parse_file(
        self,
        file_path: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        meta = dict(metadata or {})
        if "title" not in meta:
            meta["title"] = os.path.basename(file_path)
        if "source" not in meta:
            meta["source"] = file_path
        return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)


class MarkdownParser:
    """Markdown parser — strips markdown syntax to extract plain text."""

    @property
    def supported_type(self) -> DocumentType:
        return DocumentType.MARKDOWN

    def parse(
        self,
        content: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        plain_text = self._strip_markdown(content)
        meta = metadata or {}
        title = self._extract_title(content) or meta.get("title", "Untitled")
        return Document(
            doc_id=doc_id or "unknown",
            title=title,
            content=plain_text,
            doc_type=DocumentType.MARKDOWN,
            source=meta.get("source", ""),
            metadata=meta,
        )

    def parse_file(
        self,
        file_path: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        meta = dict(metadata or {})
        if "source" not in meta:
            meta["source"] = file_path
        return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove common markdown syntax."""
        # Remove fenced code blocks ```...```
        text = re.sub(r'```[^\n]*\n.*?```', '', text, flags=re.DOTALL)
        # Remove headers (# ## ###)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Remove bold/italic (**text** or *text* or __text__ or _text_)
        text = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)
        text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text)
        # Remove inline code `text`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove links [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove images ![alt](url)
        text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
        # Remove blockquotes >
        text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
        # Remove horizontal rules
        text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
        # Collapse excess blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def _extract_title(text: str) -> str:
        """Extract title from first H1 heading."""
        match = re.match(r'^#\s+(.+)$', text, re.MULTILINE)
        return match.group(1).strip() if match else ""


class HTMLParser:
    """HTML parser — strips tags to extract plain text."""

    @property
    def supported_type(self) -> DocumentType:
        return DocumentType.HTML

    def parse(
        self,
        content: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        plain_text = self._strip_html(content)
        meta = metadata or {}
        title = self._extract_title(content) or meta.get("title", "Untitled")
        return Document(
            doc_id=doc_id or "unknown",
            title=title,
            content=plain_text,
            doc_type=DocumentType.HTML,
            source=meta.get("source", ""),
            metadata=meta,
        )

    def parse_file(
        self,
        file_path: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        meta = dict(metadata or {})
        if "source" not in meta:
            meta["source"] = file_path
        return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags and decode entities."""
        # Remove script and style blocks
        text = re.sub(
            r'<(script|style)[^>]*>.*?</\1>',
            '',
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Replace block-level closing tags with newlines
        text = re.sub(
            r'<(?:br|/p|/div|/li|/tr|/h[1-6])[^>]*>',
            '\n',
            text,
            flags=re.IGNORECASE,
        )
        # Remove remaining tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = html.unescape(text)
        # Collapse excess blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def _extract_title(text: str) -> str:
        """Extract title from <title> tag."""
        match = re.search(
            r'<title[^>]*>(.*?)</title>',
            text,
            re.IGNORECASE | re.DOTALL,
        )
        return match.group(1).strip() if match else ""


class CSVParser:
    """CSV parser — converts rows to tab-separated text lines."""

    @property
    def supported_type(self) -> DocumentType:
        return DocumentType.CSV

    def parse(
        self,
        content: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        lines = ["\t".join(row) for row in rows]
        text = "\n".join(lines)
        meta = dict(metadata or {})
        meta["row_count"] = len(rows)
        meta["column_count"] = len(rows[0]) if rows else 0
        return Document(
            doc_id=doc_id or "unknown",
            title=meta.get("title", "CSV Data"),
            content=text,
            doc_type=DocumentType.CSV,
            source=meta.get("source", ""),
            metadata=meta,
        )

    def parse_file(
        self,
        file_path: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        meta = dict(metadata or {})
        if "title" not in meta:
            meta["title"] = os.path.basename(file_path)
        if "source" not in meta:
            meta["source"] = file_path
        return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)


class PDFParser:
    """PDF parser stub — Y2 will use PyPDF2 or pdfplumber.

    In Y1, ``parse`` accepts pre-extracted text directly.
    ``parse_file`` attempts a best-effort text read and logs a
    warning when a proper PDF library is required.
    """

    @property
    def supported_type(self) -> DocumentType:
        return DocumentType.PDF

    def parse(
        self,
        content: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        """Parse raw text content extracted from a PDF."""
        meta = metadata or {}
        return Document(
            doc_id=doc_id or "unknown",
            title=meta.get("title", "PDF Document"),
            content=content,
            doc_type=DocumentType.PDF,
            source=meta.get("source", ""),
            metadata=meta,
        )

    def parse_file(
        self,
        file_path: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        """Stub: reads file as text. Y2 will use a PDF extraction library."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as exc:
            logger.warning("PDF parsing requires PyPDF2 or pdfplumber: %s", exc)
            content = f"[PDF file: {file_path} — requires PyPDF2 for extraction]"
        meta = dict(metadata or {})
        if "title" not in meta:
            meta["title"] = os.path.basename(file_path)
        if "source" not in meta:
            meta["source"] = file_path
        return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)


class HWPParser:
    """HWP parser stub — Y2 will use python-hwp or olefile.

    In Y1, ``parse`` accepts pre-extracted text directly.
    ``parse_file`` logs a warning and returns a placeholder document.
    """

    @property
    def supported_type(self) -> DocumentType:
        return DocumentType.HWP

    def parse(
        self,
        content: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        meta = metadata or {}
        return Document(
            doc_id=doc_id or "unknown",
            title=meta.get("title", "HWP Document"),
            content=content,
            doc_type=DocumentType.HWP,
            source=meta.get("source", ""),
            metadata=meta,
        )

    def parse_file(
        self,
        file_path: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        logger.warning(
            "HWP binary extraction requires python-hwp library; "
            "returning placeholder for %s",
            file_path,
        )
        content = f"[HWP file: {file_path} — requires python-hwp for extraction]"
        meta = dict(metadata or {})
        if "title" not in meta:
            meta["title"] = os.path.basename(file_path)
        if "source" not in meta:
            meta["source"] = file_path
        return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)


class ParserRegistry:
    """Registry mapping DocumentType to its parser.

    Usage::

        registry = ParserRegistry()
        doc = registry.parse(content, DocumentType.MARKDOWN, doc_id="doc-001")

        # Auto-detect type from file extension and parse file
        doc_type = registry.detect_type("report.pdf")
        doc = registry.parse_file("report.pdf", doc_type, doc_id="doc-002")
    """

    def __init__(self) -> None:
        self._parsers: dict[DocumentType, DocumentParser] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register all built-in parsers."""
        for parser in (
            TextParser(),
            MarkdownParser(),
            HTMLParser(),
            CSVParser(),
            PDFParser(),
            HWPParser(),
        ):
            self._parsers[parser.supported_type] = parser

    def register(self, parser: DocumentParser) -> "ParserRegistry":
        """Register a custom parser, replacing any existing one for its type.

        Returns self for chaining.
        """
        self._parsers[parser.supported_type] = parser
        return self

    def get_parser(self, doc_type: DocumentType) -> Optional[DocumentParser]:
        """Return parser for *doc_type*, or None if not registered."""
        return self._parsers.get(doc_type)

    def parse(
        self,
        content: str,
        doc_type: DocumentType,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        """Parse *content* string using the parser registered for *doc_type*.

        Raises:
            ValueError: When no parser is registered for the given type.
        """
        parser = self._parsers.get(doc_type)
        if parser is None:
            raise ValueError(f"No parser registered for {doc_type.value}")
        return parser.parse(content, doc_id=doc_id, metadata=metadata)

    def parse_file(
        self,
        file_path: str,
        doc_type: Optional[DocumentType] = None,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        """Parse a file, auto-detecting its type when *doc_type* is omitted.

        Raises:
            ValueError: When no parser is registered for the detected type.
        """
        resolved_type = doc_type if doc_type is not None else self.detect_type(file_path)
        parser = self._parsers.get(resolved_type)
        if parser is None:
            raise ValueError(f"No parser registered for {resolved_type.value}")
        return parser.parse_file(file_path, doc_id=doc_id, metadata=metadata)

    def detect_type(self, file_path: str) -> DocumentType:
        """Detect DocumentType from file extension.

        Falls back to TXT for unknown extensions.
        """
        ext = os.path.splitext(file_path)[1].lower()
        mapping: dict[str, DocumentType] = {
            ".txt": DocumentType.TXT,
            ".md": DocumentType.MARKDOWN,
            ".markdown": DocumentType.MARKDOWN,
            ".html": DocumentType.HTML,
            ".htm": DocumentType.HTML,
            ".csv": DocumentType.CSV,
            ".pdf": DocumentType.PDF,
            ".hwp": DocumentType.HWP,
        }
        return mapping.get(ext, DocumentType.TXT)

    @property
    def supported_types(self) -> list[DocumentType]:
        """List of DocumentType values with registered parsers."""
        return list(self._parsers.keys())
