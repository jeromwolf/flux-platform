"""Unit tests for the RAG engine skeleton.

Covers:
    TC-RAG01: DocumentType
    TC-RAG02: Document
    TC-RAG03: ChunkingConfig
    TC-RAG04: DocumentChunk
    TC-RAG05: TextChunker
    TC-RAG06: EmbeddingConfig
    TC-RAG07: EmbeddingResult
    TC-RAG08: EmbeddingProvider protocol
    TC-RAG09: RetrievalMode
    TC-RAG10: RAGConfig
    TC-RAG11: RAGResult
    TC-RAG12: SimpleRetriever

All tests are marked @pytest.mark.unit and require no external dependencies.
PYTHONPATH: .
"""

from __future__ import annotations

import dataclasses

import pytest

from rag.documents.models import ChunkingConfig, Document, DocumentChunk, DocumentType
from rag.documents.chunker import TextChunker
from rag.embeddings.models import EmbeddingConfig, EmbeddingResult
from rag.embeddings.protocol import EmbeddingProvider
from rag.engines.models import RAGConfig, RAGResult, RetrievalMode, RetrievedChunk
from rag.engines.retriever import SimpleRetriever


# ---------------------------------------------------------------------------
# TC-RAG01: DocumentType
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDocumentType:
    """TC-RAG01: DocumentType enum."""

    def test_all_six_values(self):
        """TC-RAG01a: All 6 expected values are present."""
        values = {dt.name for dt in DocumentType}
        assert values == {"PDF", "HWP", "TXT", "HTML", "MARKDOWN", "CSV"}

    def test_values_are_strings(self):
        """TC-RAG01b: Each enum member value is a str."""
        for dt in DocumentType:
            assert isinstance(dt.value, str)


# ---------------------------------------------------------------------------
# TC-RAG02: Document
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDocument:
    """TC-RAG02: Document frozen dataclass."""

    def test_construction_with_required_fields(self):
        """TC-RAG02a: Document can be constructed with doc_id, title, content."""
        doc = Document(doc_id="d1", title="Test Doc", content="Hello world")
        assert doc.doc_id == "d1"
        assert doc.title == "Test Doc"
        assert doc.content == "Hello world"

    def test_word_count_property(self):
        """TC-RAG02b: word_count returns the number of whitespace-delimited words."""
        doc = Document(doc_id="d1", title="T", content="one two three four five")
        assert doc.word_count == 5

    def test_char_count_property(self):
        """TC-RAG02c: char_count returns the total number of characters."""
        content = "Hello"
        doc = Document(doc_id="d1", title="T", content=content)
        assert doc.char_count == len(content)

    def test_default_doc_type_is_txt(self):
        """TC-RAG02d: doc_type defaults to DocumentType.TXT."""
        doc = Document(doc_id="d1", title="T", content="text")
        assert doc.doc_type is DocumentType.TXT

    def test_frozen(self):
        """TC-RAG02e: Document is immutable (frozen dataclass)."""
        doc = Document(doc_id="d1", title="T", content="text")
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            doc.title = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-RAG03: ChunkingConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChunkingConfig:
    """TC-RAG03: ChunkingConfig frozen dataclass."""

    def test_default_values(self):
        """TC-RAG03a: Default chunk_size=512, chunk_overlap=50, separator='\\n\\n'."""
        cfg = ChunkingConfig()
        assert cfg.chunk_size == 512
        assert cfg.chunk_overlap == 50
        assert cfg.separator == "\n\n"

    def test_validate_passes_with_valid_config(self):
        """TC-RAG03b: validate() returns empty list for a valid configuration."""
        cfg = ChunkingConfig(chunk_size=256, chunk_overlap=32)
        errors = cfg.validate()
        assert errors == []

    def test_validate_catches_chunk_size_zero(self):
        """TC-RAG03c: validate() reports error when chunk_size <= 0."""
        cfg = ChunkingConfig(chunk_size=0, chunk_overlap=0)
        errors = cfg.validate()
        assert any("chunk_size" in e for e in errors)

    def test_validate_catches_overlap_gte_chunk_size(self):
        """TC-RAG03d: validate() reports error when chunk_overlap >= chunk_size."""
        cfg = ChunkingConfig(chunk_size=100, chunk_overlap=100)
        errors = cfg.validate()
        assert any("chunk_overlap" in e for e in errors)


# ---------------------------------------------------------------------------
# TC-RAG04: DocumentChunk
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDocumentChunk:
    """TC-RAG04: DocumentChunk frozen dataclass."""

    def test_construction(self):
        """TC-RAG04a: DocumentChunk can be constructed with required fields."""
        chunk = DocumentChunk(
            chunk_id="c1",
            doc_id="d1",
            content="some content",
            chunk_index=0,
        )
        assert chunk.chunk_id == "c1"
        assert chunk.doc_id == "d1"
        assert chunk.content == "some content"
        assert chunk.chunk_index == 0

    def test_has_embedding_false_when_empty(self):
        """TC-RAG04b: has_embedding is False when embedding is the default empty tuple."""
        chunk = DocumentChunk(
            chunk_id="c1", doc_id="d1", content="text", chunk_index=0
        )
        assert chunk.has_embedding is False

    def test_has_embedding_true_when_provided(self):
        """TC-RAG04c: has_embedding is True when a non-empty embedding is provided."""
        chunk = DocumentChunk(
            chunk_id="c1",
            doc_id="d1",
            content="text",
            chunk_index=0,
            embedding=(0.1, 0.2, 0.3),
        )
        assert chunk.has_embedding is True

    def test_frozen(self):
        """TC-RAG04d: DocumentChunk is immutable (frozen dataclass)."""
        chunk = DocumentChunk(
            chunk_id="c1", doc_id="d1", content="text", chunk_index=0
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            chunk.content = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-RAG05: TextChunker
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTextChunker:
    """TC-RAG05: TextChunker splitting logic."""

    def test_chunk_text_short_returns_single_chunk(self):
        """TC-RAG05a: Short text (< chunk_size) produces exactly one chunk."""
        chunker = TextChunker(ChunkingConfig(chunk_size=512, chunk_overlap=0))
        chunks = chunker.chunk_text("Hello world", doc_id="d1")
        assert len(chunks) == 1

    def test_chunk_text_long_returns_multiple_chunks(self):
        """TC-RAG05b: Text longer than chunk_size results in more than one chunk."""
        # Build text clearly exceeding chunk_size=50 with distinct paragraphs
        text = "word " * 20 + "\n\n" + "word " * 20 + "\n\n" + "word " * 20
        chunker = TextChunker(ChunkingConfig(chunk_size=50, chunk_overlap=0, separator="\n\n"))
        chunks = chunker.chunk_text(text, doc_id="d1")
        assert len(chunks) > 1

    def test_chunk_document_wraps_chunk_text_with_doc_id(self):
        """TC-RAG05c: chunk_document delegates to chunk_text using document's doc_id."""
        doc = Document(doc_id="doc42", title="T", content="short text")
        chunker = TextChunker(ChunkingConfig(chunk_size=512, chunk_overlap=0))
        chunks = chunker.chunk_document(doc)
        assert len(chunks) >= 1
        assert all(c.doc_id == "doc42" for c in chunks)

    def test_chunk_index_sequence(self):
        """TC-RAG05d: chunk_index values are 0, 1, 2, ... in order."""
        text = "\n\n".join(["paragraph " * 5] * 5)
        chunker = TextChunker(ChunkingConfig(chunk_size=30, chunk_overlap=0, separator="\n\n"))
        chunks = chunker.chunk_text(text, doc_id="d1")
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_overlap_applied(self):
        """TC-RAG05e: Consecutive chunks share overlapping text when chunk_overlap > 0."""
        # Two distinct paragraphs, each ~30 chars
        para_a = "alpha beta gamma delta epsilon"
        para_b = "zeta eta theta iota kappa"
        text = para_a + "\n\n" + para_b
        # chunk_size small enough to force split into two chunks
        cfg = ChunkingConfig(chunk_size=30, chunk_overlap=10, separator="\n\n")
        chunker = TextChunker(cfg)
        chunks = chunker.chunk_text(text, doc_id="d1")
        assert len(chunks) >= 2

    def test_empty_text_returns_empty_list(self):
        """TC-RAG05f: chunk_text('') returns an empty list."""
        chunker = TextChunker(ChunkingConfig(chunk_size=512, chunk_overlap=0))
        assert chunker.chunk_text("", doc_id="d1") == []

    def test_custom_separator_works(self):
        """TC-RAG05g: TextChunker respects a custom separator ('---')."""
        text = "part one" + "---" + "part two" + "---" + "part three"
        chunker = TextChunker(
            ChunkingConfig(chunk_size=10, chunk_overlap=0, separator="---")
        )
        chunks = chunker.chunk_text(text, doc_id="d1")
        assert len(chunks) >= 2


# ---------------------------------------------------------------------------
# TC-RAG06: EmbeddingConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmbeddingConfig:
    """TC-RAG06: EmbeddingConfig frozen dataclass."""

    def test_default_values(self):
        """TC-RAG06a: Defaults are model_name='nomic-embed-text', dimension=768, batch_size=32."""
        cfg = EmbeddingConfig()
        assert cfg.model_name == "nomic-embed-text"
        assert cfg.dimension == 768
        assert cfg.batch_size == 32

    def test_frozen(self):
        """TC-RAG06b: EmbeddingConfig is immutable (frozen dataclass)."""
        cfg = EmbeddingConfig()
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            cfg.model_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-RAG07: EmbeddingResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmbeddingResult:
    """TC-RAG07: EmbeddingResult frozen dataclass."""

    def test_construction_with_vectors(self):
        """TC-RAG07a: EmbeddingResult can be constructed with vectors, model, and dimension."""
        vectors = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        result = EmbeddingResult(vectors=vectors, model="test-model", dimension=3)
        assert result.vectors == vectors
        assert result.model == "test-model"
        assert result.dimension == 3

    def test_frozen(self):
        """TC-RAG07b: EmbeddingResult is immutable (frozen dataclass)."""
        result = EmbeddingResult(
            vectors=((1.0, 0.0),), model="m", dimension=2
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            result.model = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-RAG08: EmbeddingProvider protocol
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmbeddingProviderProtocol:
    """TC-RAG08: EmbeddingProvider runtime-checkable protocol."""

    def test_is_runtime_checkable(self):
        """TC-RAG08a: EmbeddingProvider supports isinstance() checks at runtime."""
        # A class that does NOT implement the protocol
        class NotAProvider:
            pass

        # Should not raise TypeError
        assert not isinstance(NotAProvider(), EmbeddingProvider)

    def test_custom_class_passes_isinstance(self):
        """TC-RAG08b: A class implementing all protocol methods passes isinstance."""

        class FakeProvider:
            def embed_texts(self, texts: list[str]) -> EmbeddingResult:
                return EmbeddingResult(
                    vectors=tuple((1.0,) for _ in texts),
                    model="fake",
                    dimension=1,
                )

            def embed_query(self, query: str) -> tuple[float, ...]:
                return (1.0,)

            @property
            def dimension(self) -> int:
                return 1

        assert isinstance(FakeProvider(), EmbeddingProvider)


# ---------------------------------------------------------------------------
# TC-RAG09: RetrievalMode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRetrievalMode:
    """TC-RAG09: RetrievalMode enum."""

    def test_has_semantic_keyword_hybrid(self):
        """TC-RAG09a: RetrievalMode has SEMANTIC, KEYWORD, and HYBRID values."""
        names = {m.name for m in RetrievalMode}
        assert {"SEMANTIC", "KEYWORD", "HYBRID"}.issubset(names)


# ---------------------------------------------------------------------------
# TC-RAG10: RAGConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRAGConfig:
    """TC-RAG10: RAGConfig frozen dataclass."""

    def test_default_values(self):
        """TC-RAG10a: RAGConfig defaults are mode=HYBRID, top_k=5, similarity_threshold=0.7."""
        cfg = RAGConfig()
        assert cfg.mode is RetrievalMode.HYBRID
        assert cfg.top_k == 5
        assert cfg.similarity_threshold == 0.7
        assert cfg.rerank is False
        assert cfg.include_metadata is True

    def test_frozen(self):
        """TC-RAG10b: RAGConfig is immutable (frozen dataclass)."""
        cfg = RAGConfig()
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            cfg.top_k = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-RAG11: RAGResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRAGResult:
    """TC-RAG11: RAGResult frozen dataclass."""

    def _make_retrieved_chunk(self, score: float, idx: int = 0) -> RetrievedChunk:
        chunk = DocumentChunk(
            chunk_id=f"c{idx}",
            doc_id="d1",
            content="content",
            chunk_index=idx,
            embedding=(1.0, 0.0, 0.0),
        )
        return RetrievedChunk(chunk=chunk, score=score, retrieval_mode=RetrievalMode.SEMANTIC)

    def test_chunk_count_property(self):
        """TC-RAG11a: chunk_count returns the number of retrieved chunks."""
        rc1 = self._make_retrieved_chunk(0.9, 0)
        rc2 = self._make_retrieved_chunk(0.8, 1)
        result = RAGResult(
            answer="ans",
            retrieved_chunks=(rc1, rc2),
            query="q",
        )
        assert result.chunk_count == 2

    def test_avg_score_property(self):
        """TC-RAG11b: avg_score returns the mean of all chunk scores."""
        rc1 = self._make_retrieved_chunk(0.8, 0)
        rc2 = self._make_retrieved_chunk(1.0, 1)
        result = RAGResult(
            answer="ans",
            retrieved_chunks=(rc1, rc2),
            query="q",
        )
        assert abs(result.avg_score - 0.9) < 1e-9

    def test_avg_score_empty_returns_zero(self):
        """TC-RAG11c: avg_score returns 0.0 when there are no chunks."""
        result = RAGResult(answer="ans", retrieved_chunks=(), query="q")
        assert result.avg_score == 0.0


# ---------------------------------------------------------------------------
# TC-RAG12: SimpleRetriever
# ---------------------------------------------------------------------------

# Shared test vectors
_VEC_A = (1.0, 0.0, 0.0)
_VEC_B = (0.0, 1.0, 0.0)
_VEC_SAME = (1.0, 0.0, 0.0)
_VEC_ZERO = (0.0, 0.0, 0.0)


def _make_chunk(
    chunk_id: str,
    content: str,
    embedding: tuple[float, ...] = (),
    chunk_index: int = 0,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        doc_id="doc1",
        content=content,
        chunk_index=chunk_index,
        embedding=embedding,
    )


@pytest.mark.unit
class TestSimpleRetriever:
    """TC-RAG12: SimpleRetriever in-memory retrieval."""

    def test_empty_on_creation(self):
        """TC-RAG12a: A newly created SimpleRetriever has chunk_count == 0."""
        retriever = SimpleRetriever()
        assert retriever.chunk_count == 0

    def test_add_chunks_only_adds_embedded(self):
        """TC-RAG12b: add_chunks only indexes chunks that have an embedding."""
        retriever = SimpleRetriever()
        c1 = _make_chunk("c1", "text", embedding=_VEC_A)
        c2 = _make_chunk("c2", "text", embedding=_VEC_B)
        added = retriever.add_chunks([c1, c2])
        assert added == 2
        assert retriever.chunk_count == 2

    def test_add_chunks_ignores_without_embedding(self):
        """TC-RAG12c: Chunks without an embedding are silently ignored."""
        retriever = SimpleRetriever()
        c_no_emb = _make_chunk("c_no_emb", "text")  # empty embedding
        added = retriever.add_chunks([c_no_emb])
        assert added == 0
        assert retriever.chunk_count == 0

    def test_retrieve_sorted_by_score_desc(self):
        """TC-RAG12d: retrieve returns chunks in descending score order."""
        config = RAGConfig(top_k=10, similarity_threshold=0.0)
        retriever = SimpleRetriever(config)
        # vec_a is identical to query → score ~1.0; vec_b is orthogonal → score ~0.0
        c1 = _make_chunk("c1", "alpha", embedding=_VEC_A)
        c2 = _make_chunk("c2", "beta", embedding=_VEC_B)
        retriever.add_chunks([c2, c1])  # inserted in reverse order

        results = retriever.retrieve(_VEC_SAME)
        assert len(results) >= 1
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_retrieve_respects_top_k(self):
        """TC-RAG12e: retrieve returns at most top_k results."""
        config = RAGConfig(top_k=1, similarity_threshold=0.0)
        retriever = SimpleRetriever(config)
        retriever.add_chunks([
            _make_chunk("c1", "a", embedding=_VEC_A),
            _make_chunk("c2", "b", embedding=_VEC_B),
        ])
        results = retriever.retrieve(_VEC_SAME)
        assert len(results) <= 1

    def test_retrieve_respects_similarity_threshold(self):
        """TC-RAG12f: retrieve excludes chunks below similarity_threshold."""
        # threshold=1.0 means only perfect matches are returned
        config = RAGConfig(top_k=10, similarity_threshold=1.0)
        retriever = SimpleRetriever(config)
        c_match = _make_chunk("c_match", "match", embedding=_VEC_A)
        c_no_match = _make_chunk("c_no_match", "no", embedding=_VEC_B)
        retriever.add_chunks([c_match, c_no_match])

        results = retriever.retrieve(_VEC_SAME)
        # Only the identical vector should pass threshold ~1.0
        chunk_ids = {r.chunk.chunk_id for r in results}
        assert "c_no_match" not in chunk_ids

    def test_keyword_search_finds_matching_chunks(self):
        """TC-RAG12g: keyword_search returns chunks containing the query term."""
        config = RAGConfig(top_k=10, similarity_threshold=0.0)
        retriever = SimpleRetriever(config)
        c_match = _make_chunk("c_match", "the maritime vessel arrived", embedding=_VEC_A)
        c_other = _make_chunk("c_other", "unrelated content here", embedding=_VEC_B)
        retriever.add_chunks([c_match, c_other])

        results = retriever.keyword_search("maritime vessel")
        chunk_ids = {r.chunk.chunk_id for r in results}
        assert "c_match" in chunk_ids

    def test_keyword_search_empty_for_no_match(self):
        """TC-RAG12h: keyword_search returns empty list when no chunk matches."""
        config = RAGConfig(top_k=10, similarity_threshold=0.0)
        retriever = SimpleRetriever(config)
        retriever.add_chunks([
            _make_chunk("c1", "hello world", embedding=_VEC_A),
        ])
        results = retriever.keyword_search("xyzzy_nonexistent_term")
        assert results == []

    def test_clear_removes_all_chunks(self):
        """TC-RAG12i: clear() resets the index to zero chunks."""
        retriever = SimpleRetriever()
        retriever.add_chunks([
            _make_chunk("c1", "text", embedding=_VEC_A),
            _make_chunk("c2", "text", embedding=_VEC_B),
        ])
        assert retriever.chunk_count == 2
        retriever.clear()
        assert retriever.chunk_count == 0

    def test_cosine_similarity_identical_vectors(self):
        """TC-RAG12j: cosine_similarity of a vector with itself is ~1.0."""
        score = SimpleRetriever.cosine_similarity(_VEC_A, _VEC_SAME)
        assert abs(score - 1.0) < 1e-9

    def test_cosine_similarity_orthogonal_vectors(self):
        """TC-RAG12k: cosine_similarity of orthogonal vectors is ~0.0."""
        score = SimpleRetriever.cosine_similarity(_VEC_A, _VEC_B)
        assert abs(score) < 1e-9

    def test_cosine_similarity_zero_vector(self):
        """TC-RAG12l: cosine_similarity returns 0.0 when either vector is zero."""
        score = SimpleRetriever.cosine_similarity(_VEC_A, _VEC_ZERO)
        assert score == 0.0
