"""Unit tests for DocumentPipeline.

Covers:
    TC-DP01: IngestionResult model
    TC-DP02: DocumentPipeline construction
    TC-DP03: ingest_text
    TC-DP04: ingest_document - chunker only (no embedder/retriever)
    TC-DP05: ingest_document - empty content
    TC-DP06: ingest_document with embedder
    TC-DP07: ingest_document with embedder + retriever
    TC-DP08: _embed_chunks failure
    TC-DP09: reset
    TC-DP10: ingested_count property

All tests are marked @pytest.mark.unit and require no external dependencies.
PYTHONPATH: .
"""
from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import MagicMock

import pytest

from rag.documents.chunker import TextChunker
from rag.documents.models import Document, DocumentChunk, DocumentType
from rag.documents.pipeline import DocumentPipeline, IngestionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeEmbeddingResult:
    """Minimal stand-in for EmbeddingResult carrying a .vectors attribute."""

    def __init__(self, vectors: tuple[tuple[float, ...], ...]) -> None:
        self.vectors = vectors


def _make_fake_embedder(dimension: int = 3) -> MagicMock:
    """Return a mock that satisfies the EmbeddingProvider.embed_texts interface."""
    embedder = MagicMock()
    embedder.embed_texts.side_effect = lambda texts: _FakeEmbeddingResult(
        vectors=tuple((1.0,) * dimension for _ in texts)
    )
    return embedder


def _make_fake_retriever(added: int = 2) -> MagicMock:
    """Return a mock retriever whose add_chunks returns a fixed count."""
    retriever = MagicMock()
    retriever.add_chunks.return_value = added
    return retriever


def _doc(
    content: str = "Hello maritime world",
    doc_id: str = "doc-001",
    title: str = "Test Doc",
) -> Document:
    return Document(doc_id=doc_id, title=title, content=content)


# ---------------------------------------------------------------------------
# TC-DP01: IngestionResult model
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIngestionResult:
    """TC-DP01: IngestionResult frozen dataclass."""

    def test_frozen(self):
        """TC-DP01a: IngestionResult은 불변(frozen) 데이터클래스이어야 한다."""
        result = IngestionResult(doc_id="doc-001")
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            result.doc_id = "changed"  # type: ignore[misc]

    def test_default_values(self):
        """TC-DP01b: doc_id 외 모든 필드의 기본값이 올바르게 설정된다."""
        result = IngestionResult(doc_id="doc-001")
        assert result.chunks_created == 0
        assert result.chunks_embedded == 0
        assert result.chunks_indexed == 0
        assert result.duration_ms == 0.0
        assert result.success is True
        assert result.error == ""

    def test_metadata_default_is_empty_dict(self):
        """TC-DP01c: metadata 기본값은 빈 딕셔너리이다."""
        result = IngestionResult(doc_id="doc-001")
        assert result.metadata == {}

    def test_metadata_dict_stored(self):
        """TC-DP01d: metadata에 임의 키-값을 저장할 수 있다."""
        result = IngestionResult(doc_id="d1", metadata={"source": "pdf", "lang": "ko"})
        assert result.metadata["source"] == "pdf"
        assert result.metadata["lang"] == "ko"

    def test_explicit_failure_fields(self):
        """TC-DP01e: success=False와 error 메시지를 함께 설정할 수 있다."""
        result = IngestionResult(doc_id="d1", success=False, error="No chunks produced")
        assert result.success is False
        assert "No chunks" in result.error


# ---------------------------------------------------------------------------
# TC-DP02: DocumentPipeline construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDocumentPipelineConstruction:
    """TC-DP02: DocumentPipeline 생성 검증."""

    def test_default_construction_uses_text_chunker(self):
        """TC-DP02a: 기본 생성 시 TextChunker가 자동 할당된다."""
        pipeline = DocumentPipeline()
        assert isinstance(pipeline._chunker, TextChunker)

    def test_custom_chunker_is_used(self):
        """TC-DP02b: 커스텀 chunker를 주입하면 해당 chunker가 사용된다."""
        from rag.documents.models import ChunkingConfig

        chunker = TextChunker(ChunkingConfig(chunk_size=128, chunk_overlap=10))
        pipeline = DocumentPipeline(chunker=chunker)
        assert pipeline._chunker is chunker

    def test_embedder_none_by_default(self):
        """TC-DP02c: embedder 미주입 시 _embedder는 None이다."""
        pipeline = DocumentPipeline()
        assert pipeline._embedder is None

    def test_retriever_none_by_default(self):
        """TC-DP02d: retriever 미주입 시 _retriever는 None이다."""
        pipeline = DocumentPipeline()
        assert pipeline._retriever is None

    def test_ingested_count_starts_at_zero(self):
        """TC-DP02e: 생성 직후 ingested_count는 0이다."""
        pipeline = DocumentPipeline()
        assert pipeline.ingested_count == 0

    def test_embedder_and_retriever_stored(self):
        """TC-DP02f: embedder와 retriever를 주입하면 해당 인스턴스가 저장된다."""
        embedder = _make_fake_embedder()
        retriever = _make_fake_retriever()
        pipeline = DocumentPipeline(embedder=embedder, retriever=retriever)
        assert pipeline._embedder is embedder
        assert pipeline._retriever is retriever


# ---------------------------------------------------------------------------
# TC-DP03: ingest_text
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIngestText:
    """TC-DP03: ingest_text 메서드 검증."""

    def test_ingest_text_returns_ingestion_result(self):
        """TC-DP03a: ingest_text는 IngestionResult를 반환한다."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_text("Hello maritime world")
        assert isinstance(result, IngestionResult)

    def test_ingest_text_assigns_doc_id(self):
        """TC-DP03b: doc_id를 명시하면 결과의 doc_id에 반영된다."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_text("some content", doc_id="my-doc")
        assert result.doc_id == "my-doc"

    def test_ingest_text_auto_doc_id_when_empty(self):
        """TC-DP03c: doc_id가 빈 문자열이면 자동 생성된 ID가 사용된다."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_text("some content", doc_id="")
        assert result.doc_id.startswith("doc-")

    def test_ingest_text_increments_counter(self):
        """TC-DP03d: ingest_text 호출마다 ingested_count가 증가한다."""
        pipeline = DocumentPipeline()
        assert pipeline.ingested_count == 0
        pipeline.ingest_text("first document")
        assert pipeline.ingested_count == 1
        pipeline.ingest_text("second document")
        assert pipeline.ingested_count == 2

    def test_ingest_text_delegates_to_ingest_document(self):
        """TC-DP03e: ingest_text가 내부적으로 ingest_document를 호출한다."""
        pipeline = DocumentPipeline()
        called_docs: list[Document] = []
        original_ingest = pipeline.ingest_document

        def capturing_ingest(doc: Document) -> IngestionResult:
            called_docs.append(doc)
            return original_ingest(doc)

        pipeline.ingest_document = capturing_ingest  # type: ignore[method-assign]
        pipeline.ingest_text("delegate me", doc_id="d-delegate", title="MyTitle")

        assert len(called_docs) == 1
        assert called_docs[0].doc_id == "d-delegate"
        assert called_docs[0].title == "MyTitle"
        assert called_docs[0].content == "delegate me"

    def test_ingest_text_success_true_for_valid_content(self):
        """TC-DP03f: 유효한 텍스트 수집 시 success=True이다."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_text("valid maritime content here")
        assert result.success is True


# ---------------------------------------------------------------------------
# TC-DP04: ingest_document - chunker only
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIngestDocumentChunkerOnly:
    """TC-DP04: embedder/retriever 없이 chunker만 사용하는 ingest_document."""

    def test_success_true_for_valid_document(self):
        """TC-DP04a: 유효한 문서 수집 시 success=True이다."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_document(_doc())
        assert result.success is True

    def test_doc_id_preserved_in_result(self):
        """TC-DP04b: 결과의 doc_id가 입력 문서의 doc_id와 동일하다."""
        pipeline = DocumentPipeline()
        doc = _doc(doc_id="my-doc-999")
        result = pipeline.ingest_document(doc)
        assert result.doc_id == "my-doc-999"

    def test_chunks_created_positive(self):
        """TC-DP04c: 유효한 문서의 chunks_created는 양수이다."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_document(_doc("word " * 30))
        assert result.chunks_created > 0

    def test_chunks_embedded_zero_without_embedder(self):
        """TC-DP04d: embedder 없이 수집하면 chunks_embedded는 0이다."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_document(_doc())
        assert result.chunks_embedded == 0

    def test_chunks_indexed_zero_without_retriever(self):
        """TC-DP04e: retriever 없이 수집하면 chunks_indexed는 0이다."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_document(_doc())
        assert result.chunks_indexed == 0

    def test_metadata_contains_title_and_doc_type(self):
        """TC-DP04f: 결과 metadata에 title과 doc_type이 포함된다."""
        pipeline = DocumentPipeline()
        doc = Document(doc_id="d1", title="Ship Report", content="Content here")
        result = pipeline.ingest_document(doc)
        assert result.metadata["title"] == "Ship Report"
        assert "doc_type" in result.metadata

    def test_duration_ms_non_negative(self):
        """TC-DP04g: duration_ms는 음수가 아니어야 한다."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_document(_doc())
        assert result.duration_ms >= 0.0

    def test_ingested_count_increments_after_ingest_document(self):
        """TC-DP04h: ingest_document 성공 후 ingested_count가 1 증가한다."""
        pipeline = DocumentPipeline()
        pipeline.ingest_document(_doc())
        assert pipeline.ingested_count == 1


# ---------------------------------------------------------------------------
# TC-DP05: ingest_document - empty content
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIngestDocumentEmptyContent:
    """TC-DP05: 빈 content 문서 수집 시 에러 반환 검증."""

    def test_empty_content_returns_failure(self):
        """TC-DP05a: content가 빈 문자열이면 success=False이다."""
        pipeline = DocumentPipeline()
        doc = Document(doc_id="empty-doc", title="Empty", content="")
        result = pipeline.ingest_document(doc)
        assert result.success is False

    def test_empty_content_has_error_message(self):
        """TC-DP05b: content가 빈 문자열이면 error 필드에 메시지가 있다."""
        pipeline = DocumentPipeline()
        doc = Document(doc_id="empty-doc", title="Empty", content="")
        result = pipeline.ingest_document(doc)
        assert result.error != ""

    def test_empty_content_preserves_doc_id(self):
        """TC-DP05c: 빈 content 수집 실패 시에도 doc_id는 보존된다."""
        pipeline = DocumentPipeline()
        doc = Document(doc_id="fail-doc", title="Empty", content="")
        result = pipeline.ingest_document(doc)
        assert result.doc_id == "fail-doc"

    def test_empty_content_does_not_increment_counter(self):
        """TC-DP05d: 빈 content로 실패하면 ingested_count가 증가하지 않는다."""
        pipeline = DocumentPipeline()
        doc = Document(doc_id="empty-doc", title="Empty", content="")
        pipeline.ingest_document(doc)
        # Counter should NOT be incremented on failure
        assert pipeline.ingested_count == 0

    def test_whitespace_only_content_returns_failure(self):
        """TC-DP05e: 공백만 있는 content도 실패로 처리된다."""
        pipeline = DocumentPipeline()
        doc = Document(doc_id="ws-doc", title="Whitespace", content="   \n\n   ")
        result = pipeline.ingest_document(doc)
        assert result.success is False


# ---------------------------------------------------------------------------
# TC-DP06: ingest_document with embedder
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIngestDocumentWithEmbedder:
    """TC-DP06: embedder를 포함한 ingest_document 검증."""

    def test_chunks_embedded_matches_chunks_created(self):
        """TC-DP06a: embedder가 있으면 chunks_embedded == chunks_created이다."""
        embedder = _make_fake_embedder(dimension=3)
        pipeline = DocumentPipeline(embedder=embedder)
        result = pipeline.ingest_document(_doc("maritime vessel navigation rules"))
        assert result.chunks_embedded == result.chunks_created

    def test_embedder_embed_texts_called(self):
        """TC-DP06b: embedder.embed_texts가 청크 텍스트 목록으로 호출된다."""
        embedder = _make_fake_embedder()
        pipeline = DocumentPipeline(embedder=embedder)
        pipeline.ingest_document(_doc("call embed please"))
        embedder.embed_texts.assert_called_once()
        call_args = embedder.embed_texts.call_args[0][0]
        assert isinstance(call_args, list)
        assert len(call_args) > 0

    def test_success_true_with_embedder(self):
        """TC-DP06c: embedder가 있어도 수집 성공 시 success=True이다."""
        embedder = _make_fake_embedder()
        pipeline = DocumentPipeline(embedder=embedder)
        result = pipeline.ingest_document(_doc())
        assert result.success is True

    def test_chunks_indexed_zero_without_retriever(self):
        """TC-DP06d: embedder는 있지만 retriever가 없으면 chunks_indexed는 0이다."""
        embedder = _make_fake_embedder()
        pipeline = DocumentPipeline(embedder=embedder)
        result = pipeline.ingest_document(_doc())
        assert result.chunks_indexed == 0

    def test_embedded_chunks_carry_embedding_vectors(self):
        """TC-DP06e: embedder가 반환한 벡터가 청크에 저장된다 (retriever에 전달 검증)."""
        dimension = 4
        embedder = _make_fake_embedder(dimension=dimension)
        retriever = _make_fake_retriever(added=1)
        pipeline = DocumentPipeline(embedder=embedder, retriever=retriever)
        pipeline.ingest_document(_doc("embed and index this text"))

        # retriever.add_chunks should have been called with chunks that have embeddings
        retriever.add_chunks.assert_called_once()
        chunks_arg: list[DocumentChunk] = retriever.add_chunks.call_args[0][0]
        assert all(len(c.embedding) == dimension for c in chunks_arg)


# ---------------------------------------------------------------------------
# TC-DP07: ingest_document with embedder + retriever
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIngestDocumentWithEmbedderAndRetriever:
    """TC-DP07: embedder + retriever 모두 주입된 ingest_document 검증."""

    def test_chunks_indexed_equals_retriever_add_chunks_return(self):
        """TC-DP07a: chunks_indexed는 retriever.add_chunks() 반환값과 동일하다."""
        embedder = _make_fake_embedder()
        retriever = _make_fake_retriever(added=3)
        pipeline = DocumentPipeline(embedder=embedder, retriever=retriever)
        result = pipeline.ingest_document(_doc("index me properly please"))
        assert result.chunks_indexed == 3

    def test_retriever_add_chunks_called(self):
        """TC-DP07b: retriever.add_chunks가 임베딩된 청크로 호출된다."""
        embedder = _make_fake_embedder()
        retriever = _make_fake_retriever()
        pipeline = DocumentPipeline(embedder=embedder, retriever=retriever)
        pipeline.ingest_document(_doc())
        retriever.add_chunks.assert_called_once()

    def test_success_true_with_embedder_and_retriever(self):
        """TC-DP07c: embedder + retriever 모두 있을 때 success=True이다."""
        embedder = _make_fake_embedder()
        retriever = _make_fake_retriever()
        pipeline = DocumentPipeline(embedder=embedder, retriever=retriever)
        result = pipeline.ingest_document(_doc())
        assert result.success is True

    def test_all_counts_populated(self):
        """TC-DP07d: chunks_created, chunks_embedded, chunks_indexed 모두 양수이다."""
        embedder = _make_fake_embedder()
        retriever = _make_fake_retriever(added=1)
        pipeline = DocumentPipeline(embedder=embedder, retriever=retriever)
        result = pipeline.ingest_document(_doc("content for full pipeline"))
        assert result.chunks_created > 0
        assert result.chunks_embedded > 0
        assert result.chunks_indexed > 0

    def test_retriever_not_called_when_embedded_count_zero(self):
        """TC-DP07e: chunks_embedded==0이면 retriever.add_chunks는 호출되지 않는다."""
        # embedder가 항상 예외를 발생시켜 embedded_count=0을 강제
        embedder = MagicMock()
        embedder.embed_texts.side_effect = RuntimeError("embed failed")
        retriever = _make_fake_retriever()
        pipeline = DocumentPipeline(embedder=embedder, retriever=retriever)
        pipeline.ingest_document(_doc())
        retriever.add_chunks.assert_not_called()


# ---------------------------------------------------------------------------
# TC-DP08: _embed_chunks failure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmbedChunksFailure:
    """TC-DP08: embedder가 예외를 발생시킬 때의 _embed_chunks 동작 검증."""

    def test_embedder_exception_returns_original_chunks(self):
        """TC-DP08a: embedder 예외 시 원본 청크가 그대로 반환된다."""
        embedder = MagicMock()
        embedder.embed_texts.side_effect = ValueError("embedding service down")
        pipeline = DocumentPipeline(embedder=embedder)

        chunks = [
            DocumentChunk(
                chunk_id="c0", doc_id="d1", content="test content", chunk_index=0
            )
        ]
        returned_chunks, count = pipeline._embed_chunks(chunks)
        assert count == 0
        assert len(returned_chunks) == 1
        assert returned_chunks[0].chunk_id == "c0"

    def test_embedder_exception_sets_count_to_zero(self):
        """TC-DP08b: embedder 예외 시 반환된 count는 0이다."""
        embedder = MagicMock()
        embedder.embed_texts.side_effect = Exception("network error")
        pipeline = DocumentPipeline(embedder=embedder)

        chunks = [
            DocumentChunk(
                chunk_id=f"c{i}", doc_id="d1", content=f"chunk {i}", chunk_index=i
            )
            for i in range(3)
        ]
        _, count = pipeline._embed_chunks(chunks)
        assert count == 0

    def test_embedder_exception_does_not_propagate(self):
        """TC-DP08c: embedder 예외가 ingest_document 밖으로 전파되지 않는다."""
        embedder = MagicMock()
        embedder.embed_texts.side_effect = RuntimeError("fatal embed error")
        pipeline = DocumentPipeline(embedder=embedder)

        # ingest_document should catch the exception internally and return a result
        result = pipeline.ingest_document(_doc("recover from embed failure"))
        # The pipeline should still succeed at the chunk stage
        # (embed failure causes chunks_embedded=0, but overall result depends on
        #  whether the exception propagates out of ingest_document)
        assert isinstance(result, IngestionResult)

    def test_returned_chunks_have_no_embedding_after_failure(self):
        """TC-DP08d: embedder 예외 후 반환된 청크는 embedding이 비어있다."""
        embedder = MagicMock()
        embedder.embed_texts.side_effect = RuntimeError("fail")
        pipeline = DocumentPipeline(embedder=embedder)

        chunks = [
            DocumentChunk(
                chunk_id="c0", doc_id="d1", content="content", chunk_index=0
            )
        ]
        returned_chunks, _ = pipeline._embed_chunks(chunks)
        # Original chunks have no embedding (empty tuple default)
        assert returned_chunks[0].has_embedding is False


# ---------------------------------------------------------------------------
# TC-DP09: reset
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReset:
    """TC-DP09: reset 메서드 검증."""

    def test_reset_sets_ingested_count_to_zero(self):
        """TC-DP09a: reset() 후 ingested_count는 0이다."""
        pipeline = DocumentPipeline()
        pipeline.ingest_text("first")
        pipeline.ingest_text("second")
        assert pipeline.ingested_count == 2
        pipeline.reset()
        assert pipeline.ingested_count == 0

    def test_reset_idempotent_when_already_zero(self):
        """TC-DP09b: 카운터가 이미 0일 때 reset()을 호출해도 문제없다."""
        pipeline = DocumentPipeline()
        pipeline.reset()
        assert pipeline.ingested_count == 0

    def test_reset_allows_recount(self):
        """TC-DP09c: reset() 후 다시 수집하면 카운터가 정상 증가한다."""
        pipeline = DocumentPipeline()
        pipeline.ingest_text("before reset")
        pipeline.reset()
        pipeline.ingest_text("after reset")
        assert pipeline.ingested_count == 1

    def test_reset_does_not_affect_chunker_or_embedder(self):
        """TC-DP09d: reset()은 chunker, embedder, retriever를 변경하지 않는다."""
        embedder = _make_fake_embedder()
        retriever = _make_fake_retriever()
        chunker = TextChunker()
        pipeline = DocumentPipeline(
            chunker=chunker, embedder=embedder, retriever=retriever
        )
        pipeline.ingest_text("some text")
        pipeline.reset()
        assert pipeline._chunker is chunker
        assert pipeline._embedder is embedder
        assert pipeline._retriever is retriever


# ---------------------------------------------------------------------------
# TC-DP10: ingested_count property
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIngestedCount:
    """TC-DP10: ingested_count 프로퍼티 증가 검증."""

    def test_count_increments_per_successful_ingest(self):
        """TC-DP10a: 성공적인 수집마다 ingested_count가 1씩 증가한다."""
        pipeline = DocumentPipeline()
        for i in range(5):
            assert pipeline.ingested_count == i
            pipeline.ingest_text(f"document number {i} with sufficient content")
        assert pipeline.ingested_count == 5

    def test_count_does_not_increment_on_failure(self):
        """TC-DP10b: 수집 실패(빈 content) 시 ingested_count가 증가하지 않는다."""
        pipeline = DocumentPipeline()
        pipeline.ingest_document(Document(doc_id="fail", title="T", content=""))
        assert pipeline.ingested_count == 0

    def test_count_increments_with_embedder(self):
        """TC-DP10c: embedder가 있어도 성공 시 ingested_count가 증가한다."""
        embedder = _make_fake_embedder()
        pipeline = DocumentPipeline(embedder=embedder)
        pipeline.ingest_text("text with embedder active now")
        assert pipeline.ingested_count == 1

    def test_count_is_read_only_property(self):
        """TC-DP10d: ingested_count는 외부에서 직접 쓸 수 없는 프로퍼티이다."""
        pipeline = DocumentPipeline()
        with pytest.raises(AttributeError):
            pipeline.ingested_count = 99  # type: ignore[misc]
