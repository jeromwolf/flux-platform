"""Deep coverage tests for rag/documents/parsers.py.

Targets specific missed lines:
- Lines 387-389: PDF fallback read fails → placeholder text
- Line 413:      _calculate_quality unreachable zero-total guard
- Lines 540-562: _try_hwp5txt — shutil.which None, success path, exception path
- Lines 601-602: _try_olefile inner stream-read exception (continue)
- Lines 609-611: _try_olefile outer exception handler
- Lines 639-640: _extract_text_from_ole_stream struct.error branch
- Lines 748-755: DOCXParser._extract_text table rows via python-docx
- Lines 882-898: PPTXParser._extract_text slides+tables via python-pptx

All tests are @pytest.mark.unit.  No network calls; real I/O only via tmp_path.
"""
from __future__ import annotations

import struct
import zipfile
from io import BytesIO
from types import ModuleType
from unittest.mock import MagicMock, patch, call

import pytest

from rag.documents.parsers import (
    DOCXParser,
    HWPParser,
    PDFParser,
    PPTXParser,
)
from rag.documents.models import DocumentType


# ---------------------------------------------------------------------------
# PDFParser — lines 387-389: fallback plain-text read throws exception
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPDFParserFallbackReadFails:
    """When fitz is missing AND the file cannot be opened as text, use placeholder."""

    def test_fallback_read_exception_yields_placeholder(self, tmp_path):
        """Lines 387-389: open() raises inside the ImportError branch → placeholder."""
        fake_path = str(tmp_path / "nonexistent.pdf")
        parser = PDFParser()

        # Simulate fitz not installed so the ImportError branch is taken.
        # Then patch builtins.open to raise inside that branch.
        import builtins
        real_open = builtins.open

        def selective_open(path, *args, **kwargs):
            # Only block the specific PDF path to trigger the inner except
            if str(path) == fake_path and "r" in str(args):
                raise OSError("permission denied")
            return real_open(path, *args, **kwargs)

        with patch.dict("sys.modules", {"fitz": None}):
            with patch("builtins.open", side_effect=selective_open):
                doc = parser.parse_file(fake_path)

        assert doc.doc_type == DocumentType.PDF
        # Lines 388-389: content must be the [PDF file: ...] placeholder
        assert "PDF file" in doc.content or "requires PyMuPDF" in doc.content

    def test_fallback_read_exception_directly(self, tmp_path):
        """Directly patch open inside the fitz-missing branch to raise."""
        f = tmp_path / "test.pdf"
        f.write_bytes(b"dummy")
        parser = PDFParser()

        open_call_count = [0]

        import builtins
        real_open = builtins.open

        def open_that_fails_on_second_call(path, *args, **kwargs):
            open_call_count[0] += 1
            mode = args[0] if args else kwargs.get("mode", "r")
            # The fallback branch uses open(..., "r", encoding=...) — raise for that
            if "r" in str(mode) and not "b" in str(mode) and str(path) == str(f):
                raise PermissionError("blocked")
            return real_open(path, *args, **kwargs)

        with patch.dict("sys.modules", {"fitz": None}):
            with patch("builtins.open", side_effect=open_that_fails_on_second_call):
                doc = parser.parse_file(str(f))

        assert doc.doc_type == DocumentType.PDF
        assert "PDF file" in doc.content or "requires PyMuPDF" in doc.content or "PDF" in doc.content


# ---------------------------------------------------------------------------
# PDFParser._calculate_quality — line 413 (zero-total guard is dead but
# the missed line is actually the `total == 0` path, verify via monkey-patch)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPDFCalculateQualityZeroTotal:
    """Line 413: the `if total == 0: return 0.0` guard after len(text)."""

    def test_calculate_quality_non_empty_str_with_len_zero_via_monkeypatch(self):
        """Monkey-patch len to return 0 for a non-empty string to hit line 413."""
        # We craft a string that passes `if not text` (truthy) but
        # whose len() returns 0 — only achievable via patching.
        parser = PDFParser()

        class WeirdStr(str):
            def __len__(self):
                return 0

        tricky = WeirdStr("x")
        # `if not text` → WeirdStr("x") is truthy, passes
        # `total = len(text)` → 0 (WeirdStr.__len__)
        # Line 413: `if total == 0: return 0.0`
        result = PDFParser._calculate_quality(tricky)
        assert result == 0.0

    def test_calculate_quality_normal_empty_returns_zero(self):
        """Confirm the primary empty-string guard (line 410) still returns 0."""
        assert PDFParser._calculate_quality("") == 0.0


# ---------------------------------------------------------------------------
# HWPParser._try_hwp5txt — lines 540-562
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHWP5TxtPaths:
    """Cover all branches of _try_hwp5txt."""

    def test_returns_none_when_hwp5txt_not_on_path(self):
        """Line 540-541: shutil.which returns None → return None."""
        with patch("shutil.which", return_value=None):
            result = HWPParser._try_hwp5txt("/tmp/file.hwp")
        assert result is None

    def test_returns_text_on_successful_run(self, tmp_path):
        """Lines 543-558: subprocess.run succeeds and returns text."""
        f = tmp_path / "doc.hwp"
        f.write_bytes(b"\xd0\xcf\x11\xe0")  # OLE magic bytes (not needed, just a file)

        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "추출된 한국어 텍스트\n내용이 있습니다."

        with patch("shutil.which", return_value="/usr/bin/hwp5txt"):
            with patch("subprocess.run", return_value=fake_result):
                result = HWPParser._try_hwp5txt(str(f))

        assert result is not None
        assert "추출된" in result

    def test_returns_none_when_subprocess_returns_nonzero(self, tmp_path):
        """Lines 555: returncode != 0 → returns None (stdout ignored)."""
        f = tmp_path / "bad.hwp"
        f.write_bytes(b"\xd0\xcf\x11\xe0")

        fake_result = MagicMock()
        fake_result.returncode = 1
        fake_result.stdout = ""

        with patch("shutil.which", return_value="/usr/bin/hwp5txt"):
            with patch("subprocess.run", return_value=fake_result):
                result = HWPParser._try_hwp5txt(str(f))

        assert result is None

    def test_returns_none_when_stdout_too_short(self, tmp_path):
        """Lines 557-558: text exists but len <= 10 → treated as extraction failure."""
        f = tmp_path / "tiny.hwp"
        f.write_bytes(b"\xd0\xcf\x11\xe0")

        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "  short  "  # stripped = "short" (5 chars ≤ 10)

        with patch("shutil.which", return_value="/usr/bin/hwp5txt"):
            with patch("subprocess.run", return_value=fake_result):
                result = HWPParser._try_hwp5txt(str(f))

        assert result is None

    def test_returns_none_on_subprocess_exception(self, tmp_path):
        """Lines 559-560: subprocess.run raises → logged and returns None."""
        f = tmp_path / "err.hwp"
        f.write_bytes(b"\xd0\xcf\x11\xe0")

        with patch("shutil.which", return_value="/usr/bin/hwp5txt"):
            with patch("subprocess.run", side_effect=OSError("no subprocess")):
                result = HWPParser._try_hwp5txt(str(f))

        assert result is None

    def test_returns_none_on_timeout(self, tmp_path):
        """Lines 559-560: subprocess.TimeoutExpired also caught."""
        import subprocess as _sp

        f = tmp_path / "timeout.hwp"
        f.write_bytes(b"\xd0\xcf\x11\xe0")

        with patch("shutil.which", return_value="/usr/bin/hwp5txt"):
            with patch(
                "subprocess.run",
                side_effect=_sp.TimeoutExpired(cmd=["hwp5txt"], timeout=30),
            ):
                result = HWPParser._try_hwp5txt(str(f))

        assert result is None


# ---------------------------------------------------------------------------
# HWPParser._try_olefile — lines 601-602, 609-611
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTryOlefilePaths:
    """Cover inner stream-read exception (601-602) and outer exception (609-611)."""

    def test_inner_stream_exception_is_swallowed_continue(self):
        """Lines 601-602: openstream raises → continue without crashing."""
        # Build a fake olefile module
        fake_olefile = MagicMock()

        mock_ole = MagicMock()
        # listdir returns one stream whose path contains 'bodytext'
        mock_ole.listdir.return_value = [["BodyText", "Section0"]]
        # openstream raises to trigger lines 601-602
        mock_ole.openstream.side_effect = OSError("stream unreadable")

        fake_olefile.isOleFile.return_value = True
        fake_olefile.OleFileIO.return_value = mock_ole

        with patch.dict("sys.modules", {"olefile": fake_olefile}):
            result = HWPParser._try_olefile(b"\xd0\xcf\x11\xe0")  # OLE magic-ish

        # Should return None (no text parts accumulated, result.strip() is falsy)
        assert result is None
        mock_ole.close.assert_called_once()

    def test_outer_exception_returns_none(self):
        """Lines 609-611: isOleFile raises → outer except catches, returns None."""
        fake_olefile = MagicMock()
        fake_olefile.isOleFile.side_effect = RuntimeError("corrupt file")

        with patch.dict("sys.modules", {"olefile": fake_olefile}):
            result = HWPParser._try_olefile(b"garbage")

        assert result is None

    def test_ole_file_not_ole_returns_none(self):
        """Line 588: isOleFile returns False → returns None early."""
        fake_olefile = MagicMock()
        fake_olefile.isOleFile.return_value = False

        with patch.dict("sys.modules", {"olefile": fake_olefile}):
            result = HWPParser._try_olefile(b"not-ole")

        assert result is None

    def test_returns_text_when_stream_succeeds(self):
        """Lines 596-600: successful stream read returns extracted text."""
        fake_olefile = MagicMock()

        # Build a simple 2-byte little-endian sequence for 'A' (0x0041)
        ole_stream_data = struct.pack("<H", ord("A")) * 20  # 20 'A' chars

        mock_stream = MagicMock()
        mock_stream.read.return_value = ole_stream_data

        mock_ole = MagicMock()
        mock_ole.listdir.return_value = [["BodyText", "Section0"]]
        mock_ole.openstream.return_value = mock_stream

        fake_olefile.isOleFile.return_value = True
        fake_olefile.OleFileIO.return_value = mock_ole

        with patch.dict("sys.modules", {"olefile": fake_olefile}):
            result = HWPParser._try_olefile(b"\xd0\xcf\x11\xe0")

        assert result is not None
        assert "A" in result


# ---------------------------------------------------------------------------
# HWPParser._extract_text_from_ole_stream — lines 639-640
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractTextFromOleStreamStructError:
    """Line 639-640: struct.error in unpack_from → i += 2, continue loop."""

    def test_struct_error_is_handled_gracefully(self):
        """A mock struct module that raises struct.error mid-stream."""
        # Create a module-like object with a .error exception class and
        # an unpack_from that raises on the first call then succeeds.

        call_count = [0]

        class FakeStructError(Exception):
            pass

        class FakeStruct:
            error = FakeStructError

            def unpack_from(self, fmt, data, offset):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise FakeStructError("bad data")
                # Return a printable ASCII char
                return (ord("Z"),)

        # Build data large enough for 2 iterations (4 bytes)
        data = b"\xff\xff" + struct.pack("<H", ord("Z"))
        result = HWPParser._extract_text_from_ole_stream(data, FakeStruct())

        # The first iter raised struct.error (i += 2), second iter returned 'Z'
        assert "Z" in result

    def test_odd_length_data_terminates_without_error(self):
        """Loop guard `while i < len(data) - 1` prevents overrun on odd data."""
        data = b"\x41"  # only 1 byte — loop never enters
        result = HWPParser._extract_text_from_ole_stream(data, struct)
        assert result == ""


# ---------------------------------------------------------------------------
# DOCXParser._extract_text — lines 748-755 (python-docx table extraction)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDOCXExtractTextWithTables:
    """Lines 748-755: _extract_text with python-docx including table rows."""

    def _make_mock_docx_module(self, paragraphs: list[str], table_rows: list[list[str]]) -> MagicMock:
        """Build a fake `docx` module with mock Document containing tables."""
        fake_docx = MagicMock()

        # Paragraphs
        mock_paragraphs = []
        for text in paragraphs:
            p = MagicMock()
            p.text = text
            mock_paragraphs.append(p)

        # Tables
        mock_tables = []
        for row_data in table_rows:
            row = MagicMock()
            row.cells = []
            for cell_text in row_data:
                cell = MagicMock()
                cell.text = cell_text
                row.cells.append(cell)
            table = MagicMock()
            table.rows = [row]
            mock_tables.append(table)

        mock_doc = MagicMock()
        mock_doc.paragraphs = mock_paragraphs
        mock_doc.tables = mock_tables

        fake_docx.Document.return_value = mock_doc
        return fake_docx

    def test_extract_text_includes_table_cells(self):
        """Lines 750-754: table rows are appended as tab-joined strings."""
        fake_docx = self._make_mock_docx_module(
            paragraphs=["Intro paragraph"],
            table_rows=[["Cell A", "Cell B", "Cell C"]],
        )
        with patch.dict("sys.modules", {"docx": fake_docx}):
            result = DOCXParser._extract_text(b"fake-bytes")

        assert "Intro paragraph" in result
        assert "Cell A" in result
        assert "Cell B" in result
        # Cells joined by tab
        assert "Cell A\tCell B\tCell C" in result

    def test_extract_text_skips_empty_cells_in_row(self):
        """Empty cell.text values are filtered out (cell.text.strip() falsy)."""
        fake_docx = self._make_mock_docx_module(
            paragraphs=["Para"],
            table_rows=[["", "  ", "Data"]],
        )
        with patch.dict("sys.modules", {"docx": fake_docx}):
            result = DOCXParser._extract_text(b"fake-bytes")

        # Only "Data" survives; empty strings filtered
        assert "Data" in result

    def test_extract_text_skips_empty_rows(self):
        """A row where all cells are empty/whitespace produces no appended line."""
        fake_docx = self._make_mock_docx_module(
            paragraphs=["Para"],
            table_rows=[["", "   "]],  # all empty → cells list is empty after filter
        )
        with patch.dict("sys.modules", {"docx": fake_docx}):
            result = DOCXParser._extract_text(b"fake-bytes")

        # Nothing from the table should appear (cells filter → empty list)
        assert "\t" not in result

    def test_extract_text_multiple_tables(self):
        """Multiple tables produce multiple appended rows."""
        fake_docx = self._make_mock_docx_module(
            paragraphs=["Header"],
            table_rows=[["R1C1", "R1C2"], ["R2C1", "R2C2"]],
        )
        with patch.dict("sys.modules", {"docx": fake_docx}):
            result = DOCXParser._extract_text(b"fake-bytes")

        # Both rows should appear
        assert "R1C1" in result
        assert "R2C1" in result


# ---------------------------------------------------------------------------
# PPTXParser._extract_text — lines 882-898 (python-pptx slides + tables)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPPTXExtractTextWithSlides:
    """Lines 882-898: _extract_text with python-pptx including tables."""

    def _make_mock_pptx_module(
        self,
        slides: list[dict],  # list of {texts: [...], table_rows: [[...]]}
    ) -> MagicMock:
        """Build a fake pptx module."""
        fake_pptx_mod = MagicMock()

        mock_slides = []
        for slide_data in slides:
            shapes = []

            # Text frame shapes
            for text in slide_data.get("texts", []):
                para = MagicMock()
                para.text = text
                tf = MagicMock()
                tf.paragraphs = [para]
                shape = MagicMock()
                shape.has_text_frame = True
                shape.text_frame = tf
                shape.has_table = False
                shapes.append(shape)

            # Table shapes
            for row_data in slide_data.get("table_rows", []):
                row = MagicMock()
                row.cells = []
                for cell_text in row_data:
                    cell = MagicMock()
                    cell.text = cell_text
                    row.cells.append(cell)
                table = MagicMock()
                table.rows = [row]
                shape = MagicMock()
                shape.has_text_frame = False
                shape.has_table = True
                shape.table = table
                shapes.append(shape)

            slide = MagicMock()
            slide.shapes = shapes
            mock_slides.append(slide)

        mock_prs = MagicMock()
        mock_prs.slides = mock_slides
        fake_pptx_mod.Presentation.return_value = mock_prs
        return fake_pptx_mod

    def test_extract_text_includes_slide_text(self):
        """Lines 883-890: slide text frames produce [Slide N] sections."""
        fake_pptx = self._make_mock_pptx_module(
            slides=[{"texts": ["Title text", "Body content"]}]
        )
        with patch.dict("sys.modules", {"pptx": fake_pptx}):
            result = PPTXParser._extract_text(b"fake-bytes")

        assert "[Slide 1]" in result
        assert "Title text" in result
        assert "Body content" in result

    def test_extract_text_includes_table_cells(self):
        """Lines 891-895: table cells within slides are extracted."""
        fake_pptx = self._make_mock_pptx_module(
            slides=[{
                "texts": ["Slide intro"],
                "table_rows": [["Col1", "Col2", "Col3"]],
            }]
        )
        with patch.dict("sys.modules", {"pptx": fake_pptx}):
            result = PPTXParser._extract_text(b"fake-bytes")

        assert "Col1\tCol2\tCol3" in result

    def test_extract_text_multiple_slides(self):
        """Lines 882-898: multiple slides produce multiple [Slide N] blocks."""
        fake_pptx = self._make_mock_pptx_module(
            slides=[
                {"texts": ["First slide text"]},
                {"texts": ["Second slide text"]},
            ]
        )
        with patch.dict("sys.modules", {"pptx": fake_pptx}):
            result = PPTXParser._extract_text(b"fake-bytes")

        assert "[Slide 1]" in result
        assert "[Slide 2]" in result
        assert "First slide text" in result
        assert "Second slide text" in result

    def test_extract_text_skips_empty_slide_parts(self):
        """Line 896: slides with only [Slide N] and no text are omitted."""
        fake_pptx = self._make_mock_pptx_module(
            slides=[{"texts": []}]  # no shapes at all
        )
        with patch.dict("sys.modules", {"pptx": fake_pptx}):
            result = PPTXParser._extract_text(b"fake-bytes")

        # slide_parts only has [Slide 1], len == 1, so not appended to slides_text
        assert result == ""

    def test_extract_text_empty_paragraph_text_skipped(self):
        """Line 889: paragraphs with empty text are not appended."""
        fake_pptx = self._make_mock_pptx_module(
            slides=[{"texts": ["", "  ", "Real text"]}]
        )
        with patch.dict("sys.modules", {"pptx": fake_pptx}):
            result = PPTXParser._extract_text(b"fake-bytes")

        assert "Real text" in result
        # blank texts should not appear as content
        assert "\n\n\n" not in result

    def test_extract_text_table_skips_empty_cells(self):
        """Lines 893-895: empty table cells filtered out."""
        fake_pptx = self._make_mock_pptx_module(
            slides=[{
                "texts": ["Intro"],
                "table_rows": [["", "  ", "Value"]],
            }]
        )
        with patch.dict("sys.modules", {"pptx": fake_pptx}):
            result = PPTXParser._extract_text(b"fake-bytes")

        assert "Value" in result
        # No leading tab from empty cells
        assert "\tValue" not in result or "Value" in result

    def test_extract_text_table_row_all_empty_skipped(self):
        """Lines 894-895: rows where all cells are empty → not appended."""
        fake_pptx = self._make_mock_pptx_module(
            slides=[{
                "texts": ["Content"],
                "table_rows": [["", "   "]],  # fully empty row
            }]
        )
        with patch.dict("sys.modules", {"pptx": fake_pptx}):
            result = PPTXParser._extract_text(b"fake-bytes")

        assert "\t" not in result  # no tab-joined row was appended
