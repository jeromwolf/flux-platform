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
    """PDF parser using PyMuPDF (fitz).

    Falls back to basic text extraction if fitz is not available.
    Includes text quality scoring for OCR detection.

    ``parse()`` accepts pre-extracted text (string) directly.
    ``parse_file()`` uses fitz for real PDF extraction with quality metrics.
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
        """Parse raw text content extracted from a PDF.

        Args:
            content: Pre-extracted text string from a PDF.
            doc_id: Unique identifier for this document.
            metadata: Optional metadata dict; 'title' and 'source' are used.

        Returns:
            Document with PDF type.
        """
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
        """Extract text from a PDF file using PyMuPDF (fitz).

        Performs page-level extraction, computes per-page text quality scores,
        and sets ``needs_ocr=True`` when the overall quality is below 0.3.

        Falls back to a best-effort text read when fitz is not installed.

        Args:
            file_path: Absolute path to the PDF file.
            doc_id: Unique identifier for this document.
            metadata: Optional metadata dict merged with extracted metadata.

        Returns:
            Document with extracted text and quality metadata.
        """
        meta = dict(metadata or {})
        if "title" not in meta:
            meta["title"] = os.path.basename(file_path)
        if "source" not in meta:
            meta["source"] = file_path

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            pages_text: list[str] = []
            quality_scores: list[float] = []
            image_count = 0

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                images = page.get_images()
                image_count += len(images)

                if text.strip():
                    quality = self._calculate_quality(text)
                    quality_scores.append(quality)
                    pages_text.append(text.strip())

            total_pages = len(doc)
            doc.close()

            full_text = "\n\n".join(pages_text)
            overall_quality = (
                sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            )
            needs_ocr = (not pages_text and image_count > 0) or overall_quality < 0.3

            meta["page_count"] = total_pages
            meta["quality_scores"] = quality_scores
            meta["needs_ocr"] = needs_ocr
            meta["image_count"] = image_count

        except ImportError:
            logger.debug("fitz (PyMuPDF) not installed; falling back to text read for %s", file_path)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    full_text = f.read()
            except Exception as exc:
                logger.warning("PDF text fallback read failed: %s", exc)
                full_text = f"[PDF file: {file_path} — requires PyMuPDF for extraction]"
        except Exception as exc:
            logger.warning("PDF parsing with fitz failed: %s", exc)
            full_text = f"[PDF parsing failed: {exc}]"

        return self.parse(full_text, doc_id=doc_id or os.path.basename(file_path), metadata=meta)

    @staticmethod
    def _calculate_quality(text: str) -> float:
        """Compute text quality score as the ratio of meaningful characters.

        Meaningful characters are Korean syllables (AC00–D7A3), English alpha,
        digits, and common punctuation/whitespace.

        Args:
            text: Raw text extracted from a PDF page.

        Returns:
            Float in [0, 1]; higher means better quality text.
        """
        if not text:
            return 0.0
        total = len(text)
        if total == 0:
            return 0.0
        meaningful = 0
        for ch in text:
            if (
                "\uac00" <= ch <= "\ud7a3"  # Korean Hangul syllables
                or ch.isalpha()             # English and other alphabetics
                or ch.isdigit()             # Digits
                or ch in " .,!?;:()\n\t-"  # Common punctuation / whitespace
            ):
                meaningful += 1
        return meaningful / total


class HWPParser:
    """HWP (Hangul Word Processor) parser.

    Uses a 3-tier fallback strategy for binary HWP files:

    1. ``hwp5txt`` CLI (best quality, requires pyhwp installed)
    2. ``olefile`` binary OLE extraction (no external CLI needed)
    3. Error message when neither is available

    ``parse()`` accepts pre-extracted text (string) directly.
    ``parse_file()`` reads bytes and runs the fallback chain.
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
        """Parse pre-extracted HWP text content.

        Args:
            content: Pre-extracted text string.
            doc_id: Unique identifier.
            metadata: Optional metadata dict.

        Returns:
            Document with HWP type.
        """
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
        """Extract text from an HWP binary file.

        Tries hwp5txt CLI first, then olefile binary extraction.
        Returns an error message document when all methods fail.

        Args:
            file_path: Absolute path to the HWP file.
            doc_id: Unique identifier.
            metadata: Optional metadata dict merged with extracted metadata.

        Returns:
            Document with extracted text and extraction_method in metadata.
        """
        meta = dict(metadata or {})
        if "title" not in meta:
            meta["title"] = os.path.basename(file_path)
        if "source" not in meta:
            meta["source"] = file_path

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as exc:
            logger.warning("Could not read HWP file %s: %s", file_path, exc)
            content = f"[HWP file read failed: {exc}]"
            return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)

        # Tier 1: hwp5txt CLI
        content = self._try_hwp5txt(file_path)
        if content is not None:
            meta["extraction_method"] = "hwp5txt"
            return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)

        # Tier 2: olefile binary extraction
        content = self._try_olefile(data)
        if content is not None:
            meta["extraction_method"] = "olefile"
            return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)

        # Tier 3: extraction failed
        logger.warning("All HWP extraction methods failed for %s", file_path)
        meta["extraction_method"] = "failed"
        content = f"[HWP extraction failed: {file_path}]"
        return self.parse(content, doc_id=doc_id or os.path.basename(file_path), metadata=meta)

    @staticmethod
    def _try_hwp5txt(file_path: str) -> Optional[str]:
        """Extract HWP text using the hwp5txt CLI tool.

        Args:
            file_path: Path to the HWP file (must not contain shell metacharacters).

        Returns:
            Extracted text string, or None if unavailable/failed.
        """
        import subprocess
        import shutil
        import tempfile

        # Shell injection protection
        _unsafe = re.compile(r'[;&|`$(){}!<>\x00]')
        if _unsafe.search(file_path):
            logger.warning("Unsafe characters in HWP file path; skipping hwp5txt")
            return None

        if shutil.which("hwp5txt") is None:
            return None

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                import shutil as _shutil
                tmp_path = os.path.join(tmp_dir, os.path.basename(file_path))
                _shutil.copy2(file_path, tmp_path)
                result = subprocess.run(
                    ["hwp5txt", tmp_path],
                    capture_output=True,
                    text=True,
                    cwd=tmp_dir,
                    timeout=30,
                )
            if result.returncode == 0 and result.stdout.strip():
                text = result.stdout.strip()
                if len(text) > 10:
                    return text
        except Exception as exc:
            logger.debug("hwp5txt failed: %s", exc)

        return None

    @staticmethod
    def _try_olefile(data: bytes) -> Optional[str]:
        """Extract text from HWP bytes using the olefile library.

        HWP files are OLE2 compound documents. Text is stored in
        BodyText/Section* streams as compressed binary records.

        Args:
            data: Raw bytes of the HWP file.

        Returns:
            Extracted text string, or None if olefile is unavailable/failed.
        """
        import struct
        import io as _io

        try:
            import olefile
        except ImportError:
            logger.debug("olefile not installed; skipping OLE extraction")
            return None

        try:
            if not olefile.isOleFile(_io.BytesIO(data)):
                return None

            ole = olefile.OleFileIO(_io.BytesIO(data))
            text_parts: list[str] = []

            for stream_name in ole.listdir():
                stream_path = "/".join(stream_name)
                if "bodytext" in stream_path.lower():
                    try:
                        raw = ole.openstream(stream_name).read()
                        text = HWPParser._extract_text_from_ole_stream(raw, struct)
                        if text.strip():
                            text_parts.append(text.strip())
                    except Exception:
                        continue

            ole.close()

            result = "\n\n".join(text_parts)
            return result if result.strip() else None

        except Exception as exc:
            logger.debug("olefile extraction failed: %s", exc)
            return None

    @staticmethod
    def _extract_text_from_ole_stream(data: bytes, struct_mod: Any) -> str:
        """Extract readable Unicode text from a HWP BodyText binary stream.

        Iterates through 2-byte little-endian code points and collects
        printable characters.

        Args:
            data: Raw bytes from an OLE BodyText stream.
            struct_mod: The ``struct`` module (passed to avoid repeated imports).

        Returns:
            Reconstructed text string.
        """
        text_parts: list[str] = []
        i = 0
        while i < len(data) - 1:
            try:
                char_code = struct_mod.unpack_from("<H", data, i)[0]
                if 0x20 <= char_code < 0xFFFF and char_code not in (0xFEFF, 0xFFFE):
                    ch = chr(char_code)
                    if ch.isprintable() or ch in ("\n", "\r", "\t"):
                        text_parts.append(ch)
                elif char_code in (0x0A, 0x0D, 0x02):
                    text_parts.append("\n")
                i += 2
            except (struct_mod.error, ValueError):
                i += 2
        return "".join(text_parts)


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
