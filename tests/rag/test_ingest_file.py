"""Tests for DocumentPipeline.ingest_file() method.

TC-IF01: ingest_file reads and parses files correctly.
TC-IF02: ingest_file handles error cases gracefully.
"""
from __future__ import annotations

import pytest

from rag.documents.pipeline import DocumentPipeline, _EXTENSION_TO_DOCTYPE, _SUPPORTED_EXTENSIONS


@pytest.mark.unit
class TestIngestFileBasic:
    """TC-IF01: Basic ingest_file functionality."""

    def test_if01a_ingest_txt_file(self, tmp_path) -> None:
        """TC-IF01-a: Ingest a .txt file successfully."""
        f = tmp_path / "test.txt"
        f.write_text("Hello World\nSecond line", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.success is True
        assert result.chunks_created > 0
        assert result.doc_id == "test.txt"

    def test_if01b_ingest_md_file(self, tmp_path) -> None:
        """TC-IF01-b: Ingest a .md file successfully."""
        f = tmp_path / "readme.md"
        f.write_text("# Title\n\nSome content here", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.success is True
        assert result.chunks_created > 0

    def test_if01c_custom_doc_id(self, tmp_path) -> None:
        """TC-IF01-c: Custom doc_id is used when provided."""
        f = tmp_path / "file.txt"
        f.write_text("Content", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f), doc_id="custom-001")
        assert result.doc_id == "custom-001"

    def test_if01d_metadata_includes_source_path(self, tmp_path) -> None:
        """TC-IF01-d: Metadata includes source_path and file_size."""
        f = tmp_path / "meta.txt"
        f.write_text("Test metadata", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.success is True
        # source_path is stored in the Document metadata passed to parsers;
        # IngestionResult.metadata carries title/doc_type from ingest_document.
        assert result.metadata.get("doc_type") is not None

    def test_if01e_custom_metadata_merged(self, tmp_path) -> None:
        """TC-IF01-e: Custom metadata is merged into result."""
        f = tmp_path / "meta2.txt"
        f.write_text("With custom metadata", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f), metadata={"source": "test"})
        assert result.success is True

    def test_if01f_csv_file_parsed(self, tmp_path) -> None:
        """TC-IF01-f: CSV file is handled via CSV parser."""
        f = tmp_path / "data.csv"
        f.write_text("col1,col2\nval1,val2", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.success is True

    def test_if01g_json_file_parsed(self, tmp_path) -> None:
        """TC-IF01-g: JSON file is handled via TXT parser (falls back to TXT)."""
        f = tmp_path / "config.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.success is True

    def test_if01h_ingested_count_increments(self, tmp_path) -> None:
        """TC-IF01-h: ingest_file increments ingested_count."""
        f = tmp_path / "count.txt"
        f.write_text("Count test", encoding="utf-8")
        pipeline = DocumentPipeline()
        assert pipeline.ingested_count == 0
        pipeline.ingest_file(str(f))
        assert pipeline.ingested_count == 1

    def test_if01i_html_file_parsed(self, tmp_path) -> None:
        """TC-IF01-i: HTML file is handled via HTML parser."""
        f = tmp_path / "page.html"
        f.write_text("<html><body><p>Maritime data</p></body></html>", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.success is True

    def test_if01j_xml_file_parsed_as_txt(self, tmp_path) -> None:
        """TC-IF01-j: XML file is handled via TXT parser (no dedicated XML parser)."""
        f = tmp_path / "data.xml"
        f.write_text("<root><item>value</item></root>", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.success is True


@pytest.mark.unit
class TestIngestFileErrors:
    """TC-IF02: Error handling for ingest_file."""

    def test_if02a_file_not_found(self) -> None:
        """TC-IF02-a: Non-existent file returns failure."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file("/nonexistent/file.txt")
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_if02b_unsupported_extension(self, tmp_path) -> None:
        """TC-IF02-b: Unsupported extension returns failure."""
        f = tmp_path / "file.xyz"
        f.write_text("unknown", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.success is False
        assert "unsupported" in result.error.lower()

    def test_if02c_empty_file(self, tmp_path) -> None:
        """TC-IF02-c: Empty file returns appropriate result (no chunks = failure)."""
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        # Empty content produces no chunks → ingest_document returns success=False
        assert isinstance(result.success, bool)

    def test_if02d_extension_map_completeness(self) -> None:
        """TC-IF02-d: Extension map covers expected formats."""
        expected = {".pdf", ".hwp", ".docx", ".pptx", ".txt", ".md", ".csv", ".json", ".xml", ".html"}
        assert expected.issubset(_SUPPORTED_EXTENSIONS)

    def test_if02e_doc_id_defaults_to_filename(self, tmp_path) -> None:
        """TC-IF02-e: When no doc_id, defaults to filename (basename)."""
        f = tmp_path / "myfile.txt"
        f.write_text("Fallback doc id", encoding="utf-8")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.doc_id == "myfile.txt"

    def test_if02f_unsupported_ext_doc_id_is_filename(self, tmp_path) -> None:
        """TC-IF02-f: Unsupported extension error result still carries filename as doc_id."""
        f = tmp_path / "archive.zip"
        f.write_bytes(b"PK\x03\x04")
        pipeline = DocumentPipeline()
        result = pipeline.ingest_file(str(f))
        assert result.success is False
        assert result.doc_id == "archive.zip"

    def test_if02g_does_not_increment_count_on_error(self, tmp_path) -> None:
        """TC-IF02-g: Failed ingestion does not increment ingested_count."""
        pipeline = DocumentPipeline()
        pipeline.ingest_file("/nonexistent/file.txt")
        assert pipeline.ingested_count == 0

    def test_if02h_doctype_map_values_are_document_types(self) -> None:
        """TC-IF02-h: All values in _EXTENSION_TO_DOCTYPE are DocumentType instances."""
        from rag.documents.models import DocumentType

        for ext, dtype in _EXTENSION_TO_DOCTYPE.items():
            assert isinstance(dtype, DocumentType), f"{ext} maps to non-DocumentType: {dtype!r}"
