"""Unit tests for HybridRAGEngine.

Covers:
    TC-HRE01: Construction - default config, custom config, injected reranker
    TC-HRE02: query SEMANTIC mode
    TC-HRE03: query KEYWORD mode
    TC-HRE04: query HYBRID mode
    TC-HRE05: query with reranking
    TC-HRE06: _reciprocal_rank_fusion static method
    TC-HRE07: _generate_answer
    TC-HRE08: _empty_result

All tests are marked @pytest.mark.unit and require no external dependencies.
PYTHONPATH: .
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from rag.documents.models import DocumentChunk
from rag.engines.models import RAGConfig, RAGResult, RetrievalMode, RetrievedChunk
from rag.engines.orchestrator import HybridRAGEngine
from rag.engines.retriever import SimpleRetriever


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VEC_A = (1.0, 0.0, 0.0)
_VEC_B = (0.0, 1.0, 0.0)
_VEC_C = (0.0, 0.0, 1.0)


def _make_doc_chunk(
    chunk_id: str,
    content: str,
    doc_id: str = "d1",
    embedding: tuple[float, ...] = _VEC_A,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        content=content,
        chunk_index=0,
        embedding=embedding,
    )


def _make_retrieved_chunk(
    chunk_id: str,
    content: str,
    score: float = 0.8,
    mode: RetrievalMode = RetrievalMode.SEMANTIC,
) -> RetrievedChunk:
    chunk = _make_doc_chunk(chunk_id, content)
    return RetrievedChunk(chunk=chunk, score=score, retrieval_mode=mode)


def _engine_with_chunks(
    chunks: list[DocumentChunk],
    config: RAGConfig | None = None,
    reranker: Any = None,
    llm: Any = None,
) -> HybridRAGEngine:
    """Build a HybridRAGEngine pre-loaded with the given chunks."""
    cfg = config or RAGConfig(similarity_threshold=0.0)
    engine = HybridRAGEngine(config=cfg, reranker=reranker, llm=llm)
    engine.retriever.add_chunks(chunks)
    return engine


# ---------------------------------------------------------------------------
# TC-HRE01: Construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHybridRAGEngineConstruction:
    """TC-HRE01: HybridRAGEngine 생성 검증."""

    def test_default_construction(self):
        """TC-HRE01a: 기본 생성 시 RAGConfig 기본값이 적용된다."""
        engine = HybridRAGEngine()
        assert engine.config.mode is RetrievalMode.HYBRID
        assert engine.config.top_k == 5

    def test_custom_config(self):
        """TC-HRE01b: 커스텀 RAGConfig가 올바르게 저장된다."""
        config = RAGConfig(mode=RetrievalMode.SEMANTIC, top_k=10)
        engine = HybridRAGEngine(config=config)
        assert engine.config.mode is RetrievalMode.SEMANTIC
        assert engine.config.top_k == 10

    def test_injected_retriever_is_used(self):
        """TC-HRE01c: 주입된 retriever가 engine.retriever에 저장된다."""
        retriever = SimpleRetriever()
        engine = HybridRAGEngine(retriever=retriever)
        assert engine.retriever is retriever

    def test_default_retriever_is_simple_retriever(self):
        """TC-HRE01d: retriever를 주입하지 않으면 SimpleRetriever가 생성된다."""
        engine = HybridRAGEngine()
        assert isinstance(engine.retriever, SimpleRetriever)

    def test_injected_reranker_is_stored(self):
        """TC-HRE01e: 주입된 reranker가 _reranker에 저장된다."""
        from rag.engines.reranker import ScoreBoostReranker

        reranker = ScoreBoostReranker()
        engine = HybridRAGEngine(reranker=reranker)
        assert engine._reranker is reranker

    def test_default_reranker_from_config_backend(self):
        """TC-HRE01f: reranker 미주입 시 config.reranker_backend로 생성된다."""
        from rag.engines.reranker import ScoreBoostReranker

        config = RAGConfig(reranker_backend="score_boost")
        engine = HybridRAGEngine(config=config)
        assert isinstance(engine._reranker, ScoreBoostReranker)

    def test_llm_stored(self):
        """TC-HRE01g: llm 주입 시 _llm에 저장된다."""
        mock_llm = MagicMock()
        engine = HybridRAGEngine(llm=mock_llm)
        assert engine._llm is mock_llm


# ---------------------------------------------------------------------------
# TC-HRE02: query SEMANTIC mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQuerySemanticMode:
    """TC-HRE02: SEMANTIC 모드 query 검증."""

    def test_semantic_requires_query_embedding(self):
        """TC-HRE02a: query_embedding=None이면 에러 RAGResult를 반환한다."""
        config = RAGConfig(mode=RetrievalMode.SEMANTIC, similarity_threshold=0.0)
        engine = HybridRAGEngine(config=config)
        result = engine.query("maritime safety", query_embedding=None)
        assert isinstance(result, RAGResult)
        assert len(result.retrieved_chunks) == 0
        assert "query_embedding" in result.answer.lower() or "required" in result.answer.lower() or "semantic" in result.answer.lower()

    def test_semantic_error_result_has_query_text(self):
        """TC-HRE02b: 에러 결과에도 원래 query 텍스트가 보존된다."""
        config = RAGConfig(mode=RetrievalMode.SEMANTIC)
        engine = HybridRAGEngine(config=config)
        result = engine.query("vessel collision rules", query_embedding=None)
        assert result.query == "vessel collision rules"

    def test_semantic_returns_results_with_embedding(self):
        """TC-HRE02c: query_embedding이 있으면 관련 청크를 반환한다."""
        config = RAGConfig(
            mode=RetrievalMode.SEMANTIC, top_k=5, similarity_threshold=0.0
        )
        chunks = [
            _make_doc_chunk("c1", "COLREG maritime rule", embedding=_VEC_A),
            _make_doc_chunk("c2", "port operations Busan", embedding=_VEC_B),
        ]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("maritime rule", query_embedding=_VEC_A)
        assert isinstance(result, RAGResult)
        assert result.chunk_count >= 1

    def test_semantic_result_sorted_by_score_desc(self):
        """TC-HRE02d: SEMANTIC 결과는 점수 내림차순으로 정렬된다."""
        config = RAGConfig(
            mode=RetrievalMode.SEMANTIC, top_k=10, similarity_threshold=0.0
        )
        chunks = [
            _make_doc_chunk("c1", "alpha", embedding=_VEC_A),
            _make_doc_chunk("c2", "beta", embedding=_VEC_B),
        ]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("query", query_embedding=_VEC_A)
        scores = [rc.score for rc in result.retrieved_chunks]
        assert scores == sorted(scores, reverse=True)

    def test_semantic_respects_top_k(self):
        """TC-HRE02e: SEMANTIC 결과는 top_k를 초과하지 않는다."""
        config = RAGConfig(
            mode=RetrievalMode.SEMANTIC, top_k=1, similarity_threshold=0.0
        )
        chunks = [
            _make_doc_chunk("c1", "alpha", embedding=_VEC_A),
            _make_doc_chunk("c2", "beta", embedding=_VEC_A),
            _make_doc_chunk("c3", "gamma", embedding=_VEC_A),
        ]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("query", query_embedding=_VEC_A)
        assert result.chunk_count <= 1


# ---------------------------------------------------------------------------
# TC-HRE03: query KEYWORD mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryKeywordMode:
    """TC-HRE03: KEYWORD 모드 query 검증."""

    def test_keyword_delegates_to_keyword_search(self):
        """TC-HRE03a: KEYWORD 모드는 retriever.keyword_search를 호출한다."""
        config = RAGConfig(
            mode=RetrievalMode.KEYWORD, top_k=5, similarity_threshold=0.0
        )
        chunks = [
            _make_doc_chunk("c1", "maritime vessel safety rule", embedding=_VEC_A),
            _make_doc_chunk("c2", "port container handling guide", embedding=_VEC_B),
        ]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("maritime safety", query_embedding=None)
        assert isinstance(result, RAGResult)
        assert result.chunk_count >= 1
        chunk_ids = {rc.chunk.chunk_id for rc in result.retrieved_chunks}
        assert "c1" in chunk_ids

    def test_keyword_works_without_query_embedding(self):
        """TC-HRE03b: KEYWORD 모드는 query_embedding 없이 동작한다."""
        config = RAGConfig(
            mode=RetrievalMode.KEYWORD, top_k=5, similarity_threshold=0.0
        )
        chunks = [_make_doc_chunk("c1", "vessel collision avoidance", embedding=_VEC_A)]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("vessel collision", query_embedding=None)
        assert isinstance(result, RAGResult)

    def test_keyword_returns_rag_result(self):
        """TC-HRE03c: KEYWORD 모드 결과는 RAGResult 타입이다."""
        config = RAGConfig(
            mode=RetrievalMode.KEYWORD, top_k=5, similarity_threshold=0.0
        )
        engine = HybridRAGEngine(config=config)
        result = engine.query("no match query", query_embedding=None)
        assert isinstance(result, RAGResult)

    def test_keyword_respects_top_k(self):
        """TC-HRE03d: KEYWORD 결과는 top_k를 초과하지 않는다."""
        config = RAGConfig(
            mode=RetrievalMode.KEYWORD, top_k=2, similarity_threshold=0.0
        )
        chunks = [
            _make_doc_chunk(f"c{i}", f"maritime vessel ship route {i}", embedding=_VEC_A)
            for i in range(10)
        ]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("maritime vessel", query_embedding=None)
        assert result.chunk_count <= 2


# ---------------------------------------------------------------------------
# TC-HRE04: query HYBRID mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryHybridMode:
    """TC-HRE04: HYBRID 모드 query 검증."""

    def test_hybrid_combines_semantic_and_keyword(self):
        """TC-HRE04a: HYBRID 모드는 시맨틱 + 키워드 결과를 RRF로 합친다."""
        config = RAGConfig(
            mode=RetrievalMode.HYBRID, top_k=5, similarity_threshold=0.0
        )
        chunks = [
            _make_doc_chunk("c1", "maritime vessel safety colreg", embedding=_VEC_A),
            _make_doc_chunk("c2", "port container operations busan", embedding=_VEC_B),
        ]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("maritime safety", query_embedding=_VEC_A)
        assert isinstance(result, RAGResult)
        assert result.chunk_count >= 1

    def test_hybrid_without_embedding_uses_keyword_only(self):
        """TC-HRE04b: query_embedding=None이면 키워드 결과만으로 HYBRID를 수행한다."""
        config = RAGConfig(
            mode=RetrievalMode.HYBRID, top_k=5, similarity_threshold=0.0
        )
        chunks = [_make_doc_chunk("c1", "maritime vessel rule safety", embedding=_VEC_A)]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("maritime safety", query_embedding=None)
        assert isinstance(result, RAGResult)

    def test_hybrid_result_chunks_have_hybrid_mode(self):
        """TC-HRE04c: HYBRID 결과 청크의 retrieval_mode는 HYBRID이다."""
        config = RAGConfig(
            mode=RetrievalMode.HYBRID, top_k=10, similarity_threshold=0.0
        )
        chunks = [
            _make_doc_chunk("c1", "maritime vessel safety rule", embedding=_VEC_A),
        ]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("maritime safety", query_embedding=_VEC_A)
        for rc in result.retrieved_chunks:
            assert rc.retrieval_mode is RetrievalMode.HYBRID

    def test_hybrid_respects_top_k(self):
        """TC-HRE04d: HYBRID 결과는 top_k를 초과하지 않는다."""
        config = RAGConfig(
            mode=RetrievalMode.HYBRID, top_k=2, similarity_threshold=0.0
        )
        chunks = [
            _make_doc_chunk(f"c{i}", f"maritime vessel safety {i}", embedding=_VEC_A)
            for i in range(8)
        ]
        engine = _engine_with_chunks(chunks, config=config)
        result = engine.query("maritime vessel", query_embedding=_VEC_A)
        assert result.chunk_count <= 2


# ---------------------------------------------------------------------------
# TC-HRE05: query with reranking
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryWithReranking:
    """TC-HRE05: rerank=True일 때 reranker 호출 검증."""

    def test_reranker_called_when_rerank_true(self):
        """TC-HRE05a: config.rerank=True이면 reranker.rerank가 호출된다."""
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = []

        config = RAGConfig(
            mode=RetrievalMode.KEYWORD,
            top_k=5,
            similarity_threshold=0.0,
            rerank=True,
        )
        chunks = [_make_doc_chunk("c1", "maritime vessel route", embedding=_VEC_A)]
        engine = _engine_with_chunks(chunks, config=config, reranker=mock_reranker)
        engine.query("maritime vessel", query_embedding=None)
        mock_reranker.rerank.assert_called_once()

    def test_reranker_not_called_when_rerank_false(self):
        """TC-HRE05b: config.rerank=False이면 reranker.rerank가 호출되지 않는다."""
        mock_reranker = MagicMock()

        config = RAGConfig(
            mode=RetrievalMode.KEYWORD,
            top_k=5,
            similarity_threshold=0.0,
            rerank=False,
        )
        chunks = [_make_doc_chunk("c1", "maritime vessel route", embedding=_VEC_A)]
        engine = _engine_with_chunks(chunks, config=config, reranker=mock_reranker)
        engine.query("maritime vessel", query_embedding=None)
        mock_reranker.rerank.assert_not_called()

    def test_reranker_receives_query_text(self):
        """TC-HRE05c: reranker.rerank의 첫 번째 인수는 원래 query 텍스트이다."""
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = []

        config = RAGConfig(
            mode=RetrievalMode.KEYWORD,
            top_k=5,
            similarity_threshold=0.0,
            rerank=True,
        )
        chunks = [_make_doc_chunk("c1", "maritime safety colreg", embedding=_VEC_A)]
        engine = _engine_with_chunks(chunks, config=config, reranker=mock_reranker)
        engine.query("colreg rule 8", query_embedding=None)
        call_args = mock_reranker.rerank.call_args
        assert call_args[0][0] == "colreg rule 8"

    def test_reranker_not_called_when_no_chunks_retrieved(self):
        """TC-HRE05d: 검색된 청크가 없으면 reranker가 호출되지 않는다."""
        mock_reranker = MagicMock()

        config = RAGConfig(
            mode=RetrievalMode.KEYWORD,
            top_k=5,
            similarity_threshold=0.0,
            rerank=True,
        )
        # Empty index — keyword search will return nothing
        engine = HybridRAGEngine(config=config, reranker=mock_reranker)
        engine.query("any query", query_embedding=None)
        mock_reranker.rerank.assert_not_called()


# ---------------------------------------------------------------------------
# TC-HRE06: _reciprocal_rank_fusion static method
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReciprocalRankFusion:
    """TC-HRE06: _reciprocal_rank_fusion 정적 메서드 검증."""

    def test_single_list_scores_computed(self):
        """TC-HRE06a: 단일 리스트 입력 시 RRF 점수가 계산된다."""
        chunks = [
            _make_retrieved_chunk("c1", "first chunk", score=0.9),
            _make_retrieved_chunk("c2", "second chunk", score=0.5),
        ]
        result = HybridRAGEngine._reciprocal_rank_fusion(chunks, top_k=10)
        assert len(result) == 2
        # Higher-ranked chunk (c1 at index 0) should have higher RRF score
        scores = {rc.chunk.chunk_id: rc.score for rc in result}
        assert scores["c1"] > scores["c2"]

    def test_two_lists_merged_by_rrf(self):
        """TC-HRE06b: 두 리스트를 병합하면 양쪽에 등장한 청크가 더 높은 점수를 받는다."""
        chunk_both = _make_doc_chunk("c_both", "appears in both lists")
        chunk_sem = _make_doc_chunk("c_sem_only", "semantic only")
        chunk_kw = _make_doc_chunk("c_kw_only", "keyword only")

        semantic_list = [
            RetrievedChunk(chunk=chunk_both, score=0.9, retrieval_mode=RetrievalMode.SEMANTIC),
            RetrievedChunk(chunk=chunk_sem, score=0.7, retrieval_mode=RetrievalMode.SEMANTIC),
        ]
        keyword_list = [
            RetrievedChunk(chunk=chunk_both, score=0.8, retrieval_mode=RetrievalMode.KEYWORD),
            RetrievedChunk(chunk=chunk_kw, score=0.6, retrieval_mode=RetrievalMode.KEYWORD),
        ]
        result = HybridRAGEngine._reciprocal_rank_fusion(
            semantic_list, keyword_list, top_k=5
        )
        scores = {rc.chunk.chunk_id: rc.score for rc in result}
        # c_both appears in both lists → higher combined RRF score
        assert scores["c_both"] > scores.get("c_sem_only", 0.0)
        assert scores["c_both"] > scores.get("c_kw_only", 0.0)

    def test_result_sorted_by_score_descending(self):
        """TC-HRE06c: RRF 결과는 점수 내림차순으로 정렬된다."""
        chunks = [
            _make_retrieved_chunk("c1", "alpha", score=0.9),
            _make_retrieved_chunk("c2", "beta", score=0.5),
            _make_retrieved_chunk("c3", "gamma", score=0.7),
        ]
        result = HybridRAGEngine._reciprocal_rank_fusion(chunks, top_k=10)
        scores = [rc.score for rc in result]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limits_output(self):
        """TC-HRE06d: top_k 인수로 결과 개수를 제한한다."""
        chunks = [
            _make_retrieved_chunk(f"c{i}", f"chunk {i}", score=1.0 - i * 0.1)
            for i in range(10)
        ]
        result = HybridRAGEngine._reciprocal_rank_fusion(chunks, top_k=3)
        assert len(result) <= 3

    def test_empty_input_returns_empty(self):
        """TC-HRE06e: 빈 리스트 입력 시 빈 리스트를 반환한다."""
        result = HybridRAGEngine._reciprocal_rank_fusion([], top_k=5)
        assert result == []

    def test_output_mode_is_hybrid(self):
        """TC-HRE06f: RRF 결과 청크의 retrieval_mode는 HYBRID이다."""
        chunks = [
            _make_retrieved_chunk("c1", "content", score=0.8, mode=RetrievalMode.SEMANTIC),
        ]
        result = HybridRAGEngine._reciprocal_rank_fusion(chunks, top_k=5)
        assert all(rc.retrieval_mode is RetrievalMode.HYBRID for rc in result)

    def test_scores_are_positive(self):
        """TC-HRE06g: RRF 점수는 모두 양수이다 (RRF 공식 특성)."""
        chunks = [_make_retrieved_chunk(f"c{i}", f"text {i}", score=0.5) for i in range(3)]
        result = HybridRAGEngine._reciprocal_rank_fusion(chunks, top_k=10)
        assert all(rc.score > 0.0 for rc in result)


# ---------------------------------------------------------------------------
# TC-HRE07: _generate_answer
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateAnswer:
    """TC-HRE07: _generate_answer 메서드 검증."""

    def test_no_chunks_returns_no_relevant_information(self):
        """TC-HRE07a: 청크가 없으면 'No relevant information found.'를 반환한다."""
        engine = HybridRAGEngine()
        answer = engine._generate_answer("any question", [])
        assert answer == "No relevant information found."

    def test_no_llm_returns_first_chunk_content(self):
        """TC-HRE07b: LLM이 없으면 첫 번째 청크의 content를 반환한다."""
        engine = HybridRAGEngine()
        chunks = [
            _make_retrieved_chunk("c1", "COLREG defines right-of-way rules.", score=0.9),
            _make_retrieved_chunk("c2", "Other maritime content.", score=0.7),
        ]
        answer = engine._generate_answer("What is COLREG?", chunks)
        assert answer == "COLREG defines right-of-way rules."

    def test_with_llm_calls_llm_generate(self):
        """TC-HRE07c: LLM이 있으면 llm.generate를 호출하고 response.text를 반환한다."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "COLREG is the International Regulations for Preventing Collisions at Sea."
        mock_llm.generate.return_value = mock_response

        engine = HybridRAGEngine(llm=mock_llm)
        chunks = [_make_retrieved_chunk("c1", "COLREG maritime safety rules.", score=0.9)]
        answer = engine._generate_answer("What is COLREG?", chunks)

        mock_llm.generate.assert_called_once()
        assert answer == "COLREG is the International Regulations for Preventing Collisions at Sea."

    def test_with_llm_failure_falls_back_to_first_chunk(self):
        """TC-HRE07d: LLM generate가 예외를 발생시키면 첫 번째 청크 content로 폴백한다."""
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = RuntimeError("LLM service unavailable")

        engine = HybridRAGEngine(llm=mock_llm)
        chunks = [_make_retrieved_chunk("c1", "Fallback answer content.", score=0.9)]
        answer = engine._generate_answer("question", chunks)
        assert answer == "Fallback answer content."

    def test_llm_prompt_contains_query_and_context(self):
        """TC-HRE07e: LLM에 전달되는 프롬프트에 query와 청크 content가 포함된다."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "generated answer"
        mock_llm.generate.return_value = mock_response

        engine = HybridRAGEngine(llm=mock_llm)
        chunks = [_make_retrieved_chunk("c1", "maritime collision rules", score=0.9)]
        engine._generate_answer("COLREG rule 8?", chunks)

        prompt_arg = mock_llm.generate.call_args[0][0]
        assert "COLREG rule 8?" in prompt_arg
        assert "maritime collision rules" in prompt_arg


# ---------------------------------------------------------------------------
# TC-HRE08: _empty_result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmptyResult:
    """TC-HRE08: _empty_result 메서드 검증."""

    def test_empty_result_has_no_chunks(self):
        """TC-HRE08a: _empty_result의 retrieved_chunks는 빈 튜플이다."""
        import time

        engine = HybridRAGEngine()
        start = time.monotonic()
        result = engine._empty_result("test query", start, "some error")
        assert result.retrieved_chunks == ()

    def test_empty_result_preserves_query(self):
        """TC-HRE08b: _empty_result의 query 필드에 원래 query가 저장된다."""
        import time

        engine = HybridRAGEngine()
        start = time.monotonic()
        result = engine._empty_result("vessel collision query", start)
        assert result.query == "vessel collision query"

    def test_empty_result_answer_contains_error_message(self):
        """TC-HRE08c: _empty_result의 answer 필드에 error 메시지가 반영된다."""
        import time

        engine = HybridRAGEngine()
        start = time.monotonic()
        result = engine._empty_result("query", start, "embedding required")
        assert "embedding required" in result.answer

    def test_empty_result_default_answer_when_no_error(self):
        """TC-HRE08d: error가 비어있으면 answer는 기본 메시지이다."""
        import time

        engine = HybridRAGEngine()
        start = time.monotonic()
        result = engine._empty_result("query", start, error="")
        assert result.answer != ""  # Should have some fallback message

    def test_empty_result_duration_ms_non_negative(self):
        """TC-HRE08e: duration_ms는 음수가 아니어야 한다."""
        import time

        engine = HybridRAGEngine()
        start = time.monotonic()
        result = engine._empty_result("query", start)
        assert result.duration_ms >= 0.0

    def test_empty_result_returns_rag_result(self):
        """TC-HRE08f: _empty_result는 RAGResult 타입을 반환한다."""
        import time

        engine = HybridRAGEngine()
        start = time.monotonic()
        result = engine._empty_result("query", start)
        assert isinstance(result, RAGResult)

    def test_semantic_mode_missing_embedding_calls_empty_result(self):
        """TC-HRE08g: SEMANTIC 모드에서 embedding 없이 query 시 _empty_result가 반환된다."""
        config = RAGConfig(mode=RetrievalMode.SEMANTIC)
        engine = HybridRAGEngine(config=config)
        result = engine.query("maritime rule", query_embedding=None)
        # _empty_result path: empty chunks, error in answer
        assert result.chunk_count == 0
        assert result.answer != ""
