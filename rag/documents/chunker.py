"""Text chunking implementation for the document pipeline."""
from __future__ import annotations

from rag.documents.models import ChunkingConfig, Document, DocumentChunk


class TextChunker:
    """Splits documents into overlapping text chunks.

    Uses separator-based splitting with configurable chunk size and overlap.
    Segments smaller than ``chunk_size`` are merged greedily before overflow
    forces a new chunk boundary.

    Example::

        config = ChunkingConfig(chunk_size=256, chunk_overlap=32)
        chunker = TextChunker(config)
        chunks = chunker.chunk_document(doc)
    """

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self._config: ChunkingConfig = config or ChunkingConfig()
        errors = self._config.validate()
        if errors:
            raise ValueError("Invalid ChunkingConfig: " + "; ".join(errors))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_document(self, document: Document) -> list[DocumentChunk]:
        """Split a document into chunks.

        Args:
            document: Source document to split.

        Returns:
            Ordered list of ``DocumentChunk`` objects covering the full
            document content.
        """
        return self.chunk_text(document.content, doc_id=document.doc_id)

    def chunk_text(self, text: str, doc_id: str = "") -> list[DocumentChunk]:
        """Split raw text into chunks.

        Args:
            text: Arbitrary text string to split.
            doc_id: Identifier to attach to every generated chunk.

        Returns:
            Ordered list of ``DocumentChunk`` objects.
        """
        if not text:
            return []

        segments = self._split_by_separator(text)
        merged = self._merge_segments(segments)
        return self._build_chunks(merged, doc_id, text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_by_separator(self, text: str) -> list[str]:
        """Split *text* on the configured separator, keeping non-empty parts."""
        sep = self._config.separator
        parts = text.split(sep)
        return [p for p in parts if p.strip()]

    def _merge_segments(self, segments: list[str]) -> list[str]:
        """Merge short adjacent segments up to ``chunk_size`` characters.

        When a segment itself exceeds ``chunk_size`` it is kept as-is so that
        callers can still produce a chunk from it.
        """
        if not segments:
            return []

        sep = self._config.separator
        chunk_size = self._config.chunk_size
        merged: list[str] = []
        current = segments[0]

        for seg in segments[1:]:
            # +len(sep) accounts for the separator we would re-insert
            candidate = current + sep + seg
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                merged.append(current)
                current = seg

        merged.append(current)
        return merged

    def _build_chunks(
        self, merged: list[str], doc_id: str, original_text: str
    ) -> list[DocumentChunk]:
        """Convert merged text blocks into ``DocumentChunk`` instances.

        Applies overlap by prepending a tail from the previous chunk when the
        resulting text still fits within ``chunk_size``.
        """
        chunk_size = self._config.chunk_size
        chunk_overlap = self._config.chunk_overlap

        # Running overlap tail from the previous chunk (starts empty)
        prev_overlap: str = ""

        chunks: list[DocumentChunk] = []
        search_start = 0  # sliding window to locate offsets in original text

        for index, block in enumerate(merged):
            # Prepend overlap text from the previous chunk when it fits
            if prev_overlap and len(prev_overlap) + len(block) <= chunk_size:
                content = prev_overlap + block
            else:
                content = block

            # Locate character offsets in the original document
            start_char = original_text.find(block, search_start)
            if start_char == -1:
                # Fallback: use end of previous chunk
                start_char = chunks[-1].end_char if chunks else 0
            end_char = start_char + len(block)
            # Next search begins just before the overlap region so offsets stay accurate
            search_start = max(0, end_char - chunk_overlap)

            chunk = DocumentChunk(
                chunk_id=f"{doc_id}_{index}" if doc_id else str(index),
                doc_id=doc_id,
                content=content,
                chunk_index=index,
                start_char=start_char,
                end_char=end_char,
            )
            chunks.append(chunk)

            # Capture tail of the *content* (including any prepended overlap) for next iteration
            prev_overlap = content[-chunk_overlap:] if chunk_overlap else ""

        return chunks
