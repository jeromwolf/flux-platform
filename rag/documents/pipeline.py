"""Document ingestion pipeline.

End-to-end pipeline: parse → chunk → embed → index.

Usage::

    pipeline = DocumentPipeline(
        chunker=TextChunker(ChunkingConfig(chunk_size=256)),
        embedder=StubEmbeddingProvider(),
        retriever=SimpleRetriever(),
    )
    result = pipeline.ingest_text("My document content", doc_id="doc-001")
    result = pipeline.ingest_document(document)
    result = pipeline.ingest_file("report.pdf")
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from rag.documents.chunker import TextChunker
from rag.documents.models import Document, DocumentChunk, DocumentType

logger = logging.getLogger(__name__)

# Maps file extension to the parser name used in ParserRegistry / parser classes.
_EXTENSION_TO_DOCTYPE: dict[str, DocumentType] = {
    ".pdf": DocumentType.PDF,
    ".hwp": DocumentType.HWP,
    ".docx": DocumentType.DOCX,
    ".pptx": DocumentType.PPTX,
    ".txt": DocumentType.TXT,
    ".md": DocumentType.MARKDOWN,
    ".markdown": DocumentType.MARKDOWN,
    ".csv": DocumentType.CSV,
    ".json": DocumentType.TXT,
    ".xml": DocumentType.TXT,
    ".html": DocumentType.HTML,
    ".htm": DocumentType.HTML,
}

# Subset of extensions that map to a parseable format via ParserRegistry.
_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_EXTENSION_TO_DOCTYPE.keys())


@dataclass(frozen=True)
class IngestionResult:
    """Result of document ingestion."""

    doc_id: str
    chunks_created: int = 0
    chunks_embedded: int = 0
    chunks_indexed: int = 0
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentPipeline:
    """End-to-end document ingestion pipeline.

    Steps:
    1. Parse: Convert raw content into Document (via parsers if available)
    2. Chunk: Split document into overlapping chunks
    3. Embed: Generate vector embeddings for each chunk
    4. Index: Add embedded chunks to retriever
    """

    def __init__(
        self,
        chunker: Optional[TextChunker] = None,
        embedder: Any = None,  # EmbeddingProvider protocol
        retriever: Any = None,  # SimpleRetriever
    ) -> None:
        self._chunker = chunker or TextChunker()
        self._embedder = embedder
        self._retriever = retriever
        self._ingested_count = 0

    @property
    def ingested_count(self) -> int:
        return self._ingested_count

    def ingest_text(
        self,
        text: str,
        doc_id: str = "",
        title: str = "Untitled",
        metadata: Optional[dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest raw text through the full pipeline."""
        doc = Document(
            doc_id=doc_id or f"doc-{self._ingested_count}",
            title=title,
            content=text,
            metadata=metadata or {},
        )
        return self.ingest_document(doc)

    def ingest_document(self, document: Document) -> IngestionResult:
        """Ingest a Document through chunk -> embed -> index."""
        start = time.monotonic()

        try:
            # 1. Chunk
            chunks = self._chunker.chunk_document(document)
            if not chunks:
                return IngestionResult(
                    doc_id=document.doc_id,
                    duration_ms=round((time.monotonic() - start) * 1000, 2),
                    error="No chunks produced",
                    success=False,
                )

            # 2. Embed
            embedded_chunks = chunks
            embedded_count = 0
            if self._embedder is not None:
                embedded_chunks, embedded_count = self._embed_chunks(chunks)

            # 3. Index
            indexed_count = 0
            if self._retriever is not None and embedded_count > 0:
                indexed_count = self._retriever.add_chunks(embedded_chunks)

            self._ingested_count += 1
            duration = (time.monotonic() - start) * 1000

            return IngestionResult(
                doc_id=document.doc_id,
                chunks_created=len(chunks),
                chunks_embedded=embedded_count,
                chunks_indexed=indexed_count,
                duration_ms=round(duration, 2),
                success=True,
                metadata={
                    "title": document.title,
                    "doc_type": document.doc_type.value,
                },
            )

        except Exception as exc:
            logger.error("Document ingestion failed: %s", exc)
            return IngestionResult(
                doc_id=document.doc_id,
                duration_ms=round((time.monotonic() - start) * 1000, 2),
                success=False,
                error=str(exc),
            )

    def ingest_file(
        self,
        file_path: str,
        doc_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest a file from disk through the full pipeline.

        Reads the file, detects its format from the extension, parses it using
        the appropriate parser via :class:`~rag.documents.parsers.ParserRegistry`,
        then delegates to :meth:`ingest_document`.

        Args:
            file_path: Path to the file to ingest.
            doc_id: Optional document ID. Defaults to the filename (basename).
            metadata: Optional extra metadata merged into the document.

        Returns:
            IngestionResult with ingestion outcome.
        """
        path = Path(file_path)
        effective_id = doc_id or path.name

        if not path.exists():
            return IngestionResult(
                doc_id=effective_id,
                success=False,
                error=f"File not found: {file_path}",
            )

        ext = path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            return IngestionResult(
                doc_id=effective_id,
                success=False,
                error=f"Unsupported file extension: {ext}",
            )

        try:
            file_size = path.stat().st_size
        except OSError as exc:
            return IngestionResult(
                doc_id=effective_id,
                success=False,
                error=f"Failed to read file: {exc}",
            )

        # Parse using the registry (handles all format-specific logic + fallbacks)
        try:
            from rag.documents.parsers import ParserRegistry

            registry = ParserRegistry()
            doc_type = _EXTENSION_TO_DOCTYPE[ext]
            extra_meta = {**(metadata or {}), "source_path": str(path), "file_size": file_size}
            parsed_doc = registry.parse_file(
                str(path),
                doc_type=doc_type,
                doc_id=effective_id,
                metadata=extra_meta,
            )
        except Exception as exc:
            logger.error("File parsing failed for %s: %s", file_path, exc)
            return IngestionResult(
                doc_id=effective_id,
                success=False,
                error=f"Parse error: {exc}",
            )

        # Override doc_id/title with our computed values (registry may set its own)
        doc = Document(
            doc_id=effective_id,
            title=parsed_doc.title or path.stem,
            content=parsed_doc.content,
            doc_type=parsed_doc.doc_type,
            source=str(path),
            metadata=parsed_doc.metadata,
        )
        return self.ingest_document(doc)

    def _embed_chunks(
        self, chunks: list[DocumentChunk]
    ) -> tuple[list[DocumentChunk], int]:
        """Generate embeddings for chunks, return new chunks with embeddings."""
        texts = [c.content for c in chunks]

        try:
            result = self._embedder.embed_texts(texts)
            embedded: list[DocumentChunk] = []
            count = 0
            for chunk, vector in zip(chunks, result.vectors):
                # Create new chunk with embedding (frozen dataclass)
                new_chunk = DocumentChunk(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    metadata=chunk.metadata,
                    embedding=vector,
                )
                embedded.append(new_chunk)
                count += 1
            return embedded, count
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)
            return chunks, 0

    def reset(self) -> None:
        """Reset ingestion counter."""
        self._ingested_count = 0
