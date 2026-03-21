"""Document data models for the RAG pipeline."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocumentType(str, Enum):
    """Supported document source formats."""

    PDF = "pdf"
    HWP = "hwp"
    TXT = "txt"
    HTML = "html"
    MARKDOWN = "markdown"
    CSV = "csv"


@dataclass(frozen=True)
class Document:
    """Immutable representation of a source document.

    Attributes:
        doc_id: Unique document identifier.
        title: Human-readable document title.
        content: Full text content of the document.
        doc_type: Source format of the document.
        source: Origin path or URL.
        metadata: Arbitrary key-value pairs (author, lang, etc.).
        created_at: Unix timestamp of document ingestion.
    """

    doc_id: str
    title: str
    content: str
    doc_type: DocumentType = DocumentType.TXT
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @property
    def word_count(self) -> int:
        """Number of whitespace-delimited words in content."""
        return len(self.content.split())

    @property
    def char_count(self) -> int:
        """Number of characters in content."""
        return len(self.content)


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration for the text chunker.

    Attributes:
        chunk_size: Maximum number of characters per chunk.
        chunk_overlap: Number of characters to overlap between adjacent chunks.
        separator: Preferred split boundary (e.g., paragraph break).
    """

    chunk_size: int = 512
    chunk_overlap: int = 50
    separator: str = "\n\n"

    def validate(self) -> list[str]:
        """Return a list of validation error messages (empty = valid).

        Checks:
            - chunk_size must be positive.
            - chunk_overlap must be less than chunk_size.
        """
        errors: list[str] = []
        if self.chunk_size <= 0:
            errors.append(f"chunk_size must be > 0, got {self.chunk_size}")
        if self.chunk_overlap >= self.chunk_size:
            errors.append(
                f"chunk_overlap ({self.chunk_overlap}) must be < chunk_size ({self.chunk_size})"
            )
        return errors


@dataclass(frozen=True)
class DocumentChunk:
    """A single chunk derived from a parent document.

    Attributes:
        chunk_id: Unique identifier for this chunk.
        doc_id: Parent document identifier.
        content: Text content of the chunk.
        chunk_index: Zero-based position within the document.
        start_char: Start character offset in the original document.
        end_char: End character offset in the original document.
        metadata: Inherited or chunk-specific metadata.
        embedding: Dense vector representation (empty tuple = not yet embedded).
    """

    chunk_id: str
    doc_id: str
    content: str
    chunk_index: int
    start_char: int = 0
    end_char: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: tuple[float, ...] = ()

    @property
    def has_embedding(self) -> bool:
        """True when the chunk carries a non-empty embedding vector."""
        return len(self.embedding) > 0
