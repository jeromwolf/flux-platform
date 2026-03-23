"""Unit tests for the LightRAG engine and evaluation framework.

Covers:
    - RegexEntityExtractor: entity/relationship extraction
    - LightRAGEngine: indexing, dual-level retrieval, graph inspection
    - RAGEvaluator: metrics computation and strategy comparison

All tests are marked @pytest.mark.unit and require no external dependencies.
PYTHONPATH: .
"""
from __future__ import annotations

import dataclasses

import pytest

from rag.documents.models import DocumentChunk
from rag.engines.lightrag import (
    EntityExtractionResult,
    ExtractedEntity,
    ExtractedRelationship,
    LightRAGEngine,
    RegexEntityExtractor,
    EntityExtractor,
)
from rag.engines.evaluation import EvalQuery, RAGEvaluator, RetrievalMetrics
from rag.engines.models import RetrievalMode, RetrievedChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_id: str,
    content: str,
    doc_id: str = "doc1",
    chunk_index: int = 0,
) -> DocumentChunk:
    """Create a DocumentChunk for testing."""
    return DocumentChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        content=content,
        chunk_index=chunk_index,
    )


# ---------------------------------------------------------------------------
# RegexEntityExtractor tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRegexExtractor:
    """Entity extraction via regex patterns."""

    def test_regex_extractor_finds_vessels(self):
        """Vessel patterns match -함 and -호 suffixes."""
        extractor = RegexEntityExtractor()
        result = extractor.extract("세종대왕함이 부산항에 입항했다. 한라호도 대기 중이다.")
        names = {e.name for e in result.entities}
        assert "세종대왕함" in names
        assert "한라호" in names

    def test_regex_extractor_finds_ports(self):
        """Port patterns match -항 suffix."""
        extractor = RegexEntityExtractor()
        result = extractor.extract("부산항은 한국 최대 항만이다. 인천항도 크다.")
        names = {e.name for e in result.entities}
        assert "부산항" in names
        assert "인천항" in names

    def test_regex_extractor_finds_organizations(self):
        """Organization patterns match KRISO, IMO, etc."""
        extractor = RegexEntityExtractor()
        result = extractor.extract("KRISO와 IMO는 해사 안전을 연구한다.")
        names = {e.name for e in result.entities}
        assert "KRISO" in names
        assert "IMO" in names

    def test_regex_extractor_finds_relationships(self):
        """Co-occurring entities in the same sentence produce relationships."""
        extractor = RegexEntityExtractor()
        result = extractor.extract("부산항에 세종대왕함이 정박 중이다.")
        assert len(result.relationships) >= 1
        rel = result.relationships[0]
        pair = {rel.source, rel.target}
        assert "부산항" in pair
        assert "세종대왕함" in pair

    def test_regex_extractor_empty_text(self):
        """Empty text produces empty results."""
        extractor = RegexEntityExtractor()
        result = extractor.extract("")
        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    def test_regex_extractor_korean_content(self):
        """Mixed Korean maritime content extracts multiple entity types."""
        extractor = RegexEntityExtractor()
        text = (
            "SOLAS 규정에 따라 독도함은 대한해협을 통과했다. "
            "해양수산부 산하 해양연구소가 모니터링한다."
        )
        result = extractor.extract(text)
        types = {e.entity_type for e in result.entities}
        # Should find at least Vessel (독도함), SeaArea (대한해협), Regulation (SOLAS),
        # Organization (해양수산부, 해양연구소)
        assert "Vessel" in types
        assert "SeaArea" in types
        assert "Regulation" in types
        assert "Organization" in types

    def test_extractor_protocol_compliance(self):
        """RegexEntityExtractor satisfies the EntityExtractor protocol."""
        extractor = RegexEntityExtractor()
        assert isinstance(extractor, EntityExtractor)

    def test_entity_types_correct(self):
        """Each extracted entity carries the correct entity_type label."""
        extractor = RegexEntityExtractor()
        result = extractor.extract("부산항에 VLCC가 입항했다.")
        entity_map = {e.name: e.entity_type for e in result.entities}
        assert entity_map.get("부산항") == "Port"
        assert entity_map.get("VLCC") == "Vessel"

    def test_deduplication(self):
        """Same entity mentioned twice is extracted only once."""
        extractor = RegexEntityExtractor()
        result = extractor.extract("부산항은 크다. 부산항은 바쁘다.")
        port_count = sum(1 for e in result.entities if e.name == "부산항")
        assert port_count == 1


# ---------------------------------------------------------------------------
# LightRAGEngine tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLightRAGEngine:
    """LightRAG engine indexing and retrieval."""

    def test_index_single_chunk(self):
        """Indexing a single chunk updates entity and chunk counts."""
        engine = LightRAGEngine()
        chunk = _make_chunk("c1", "부산항에 세종대왕함이 정박했다.")
        result = engine.index_chunk(chunk)
        assert len(result.entities) >= 2
        assert engine.chunk_count == 1
        assert engine.entity_count >= 2

    def test_index_multiple_chunks(self):
        """index_chunks processes all chunks and returns total entity count."""
        engine = LightRAGEngine()
        chunks = [
            _make_chunk("c1", "부산항에 세종대왕함이 입항했다.", chunk_index=0),
            _make_chunk("c2", "인천항에서 KRISO가 조사를 실시했다.", chunk_index=1),
        ]
        total = engine.index_chunks(chunks)
        assert total >= 4  # 부산항, 세종대왕함, 인천항, KRISO at minimum
        assert engine.chunk_count == 2

    def test_retrieve_low_level_by_entity(self):
        """Low-level retrieval finds chunks containing named entities."""
        engine = LightRAGEngine()
        c1 = _make_chunk("c1", "부산항에 세종대왕함이 정박했다.")
        c2 = _make_chunk("c2", "날씨가 좋다. 바람이 분다.", chunk_index=1)
        engine.index_chunks([c1, c2])

        results = engine.retrieve_low_level("부산항 현황")
        assert len(results) >= 1
        assert results[0].chunk.chunk_id == "c1"

    def test_retrieve_high_level_by_type(self):
        """High-level retrieval finds chunks by entity type/topic."""
        engine = LightRAGEngine()
        c1 = _make_chunk("c1", "부산항은 한국 최대 항만이다.")
        c2 = _make_chunk("c2", "SOLAS 규정은 안전을 위한 것이다.", chunk_index=1)
        engine.index_chunks([c1, c2])

        # Query about regulations should surface c2
        results = engine.retrieve_high_level("안전 규정", top_k=5)
        chunk_ids = {r.chunk.chunk_id for r in results}
        assert "c2" in chunk_ids

    def test_retrieve_dual_level_combines(self):
        """Dual-level retrieve() returns results from both levels."""
        engine = LightRAGEngine()
        c1 = _make_chunk("c1", "부산항에 세종대왕함이 정박했다.")
        c2 = _make_chunk("c2", "SOLAS 규정에 따라 점검한다.", chunk_index=1)
        c3 = _make_chunk("c3", "날씨 정보: 맑음.", chunk_index=2)
        engine.index_chunks([c1, c2, c3])

        results = engine.retrieve("부산항 안전 규정")
        chunk_ids = {r.chunk.chunk_id for r in results}
        # Should find c1 (부산항) and c2 (규정/안전) but not necessarily c3
        assert "c1" in chunk_ids or "c2" in chunk_ids

    def test_retrieve_empty_index(self):
        """Retrieving from an empty index returns empty list."""
        engine = LightRAGEngine()
        results = engine.retrieve("부산항")
        assert results == []

    def test_retrieve_no_matching_entities(self):
        """Query with no matching entities returns empty list."""
        engine = LightRAGEngine()
        engine.index_chunks([
            _make_chunk("c1", "부산항에 세종대왕함이 있다."),
        ])
        # Query with no maritime entities
        results = engine.retrieve("오늘 점심 메뉴")
        assert results == []

    def test_get_entity_graph(self):
        """get_entity_graph returns correct structure."""
        engine = LightRAGEngine()
        engine.index_chunks([
            _make_chunk("c1", "부산항에 세종대왕함이 정박했다."),
        ])
        graph = engine.get_entity_graph()
        assert "nodes" in graph
        assert "edges" in graph
        assert "entity_count" in graph
        assert "relationship_count" in graph
        assert "chunk_count" in graph
        assert graph["entity_count"] >= 2
        assert graph["chunk_count"] == 1
        # Nodes should have id, label, type, description
        for node in graph["nodes"]:
            assert "id" in node
            assert "label" in node
            assert "type" in node

    def test_entity_count_property(self):
        """entity_count tracks unique entities."""
        engine = LightRAGEngine()
        assert engine.entity_count == 0
        engine.index_chunks([
            _make_chunk("c1", "부산항에 세종대왕함이 있다."),
        ])
        assert engine.entity_count >= 2

    def test_incremental_indexing(self):
        """New chunks can be added without affecting previously indexed data."""
        engine = LightRAGEngine()
        engine.index_chunks([_make_chunk("c1", "부산항에 입항했다.")])
        count_1 = engine.entity_count
        chunks_1 = engine.chunk_count

        engine.index_chunks([_make_chunk("c2", "인천항에서 KRISO가 조사했다.", chunk_index=1)])
        assert engine.entity_count > count_1
        assert engine.chunk_count == chunks_1 + 1

        # First chunk's entities still retrievable
        results = engine.retrieve_low_level("부산항")
        chunk_ids = {r.chunk.chunk_id for r in results}
        assert "c1" in chunk_ids

    def test_relationship_count_property(self):
        """relationship_count tracks extracted relationships."""
        engine = LightRAGEngine()
        assert engine.relationship_count == 0
        # Two entities in same sentence => at least 1 relationship
        engine.index_chunks([
            _make_chunk("c1", "부산항에 세종대왕함이 정박했다."),
        ])
        assert engine.relationship_count >= 1

    def test_retrieve_scores_normalized(self):
        """All retrieval scores are in [0, 1]."""
        engine = LightRAGEngine()
        engine.index_chunks([
            _make_chunk("c1", "부산항에 세종대왕함이 정박했다."),
            _make_chunk("c2", "인천항에서 한라호가 출항했다.", chunk_index=1),
        ])
        for result in engine.retrieve("부산항 세종대왕함"):
            assert 0.0 <= result.score <= 1.0

    def test_retrieve_respects_top_k(self):
        """retrieve returns at most top_k results."""
        engine = LightRAGEngine()
        for i in range(10):
            engine.index_chunks([
                _make_chunk(f"c{i}", f"부산항 관련 내용 {i}", chunk_index=i),
            ])
        results = engine.retrieve("부산항", top_k=3)
        assert len(results) <= 3

    def test_retrieval_mode_is_hybrid(self):
        """All retrieved chunks report HYBRID retrieval mode."""
        engine = LightRAGEngine()
        engine.index_chunks([
            _make_chunk("c1", "부산항에 세종대왕함이 있다."),
        ])
        results = engine.retrieve("부산항")
        for r in results:
            assert r.retrieval_mode == RetrievalMode.HYBRID

    def test_neighbor_expansion(self):
        """1-hop neighbor expansion retrieves related chunks."""
        engine = LightRAGEngine()
        # c1 has 부산항 and 세종대왕함 (creates relationship)
        c1 = _make_chunk("c1", "부산항에 세종대왕함이 정박했다.")
        # c2 only has 세종대왕함
        c2 = _make_chunk("c2", "세종대왕함은 대형 군함이다.", chunk_index=1)
        engine.index_chunks([c1, c2])

        # Query for 부산항 should find c1 directly and c2 via neighbor expansion
        # (부산항 -> RELATED_TO -> 세종대왕함 -> c2)
        results = engine.retrieve_low_level("부산항", top_k=10)
        chunk_ids = {r.chunk.chunk_id for r in results}
        assert "c1" in chunk_ids
        # c2 is reachable via 세종대왕함 neighbor
        assert "c2" in chunk_ids


# ---------------------------------------------------------------------------
# RAGEvaluator tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRAGEvaluator:
    """Evaluation framework for retrieval strategies."""

    def _dummy_retriever(
        self, results: list[RetrievedChunk],
    ):
        """Create a retriever function that always returns *results*."""
        def fn(query: str, top_k: int = 10) -> list[RetrievedChunk]:
            return results[:top_k]
        return fn

    def _make_retrieved(self, chunk_id: str, score: float = 0.9) -> RetrievedChunk:
        """Create a RetrievedChunk for testing."""
        chunk = _make_chunk(chunk_id, f"content of {chunk_id}")
        return RetrievedChunk(
            chunk=chunk, score=score, retrieval_mode=RetrievalMode.HYBRID,
        )

    def test_evaluator_perfect_retrieval(self):
        """Perfect retrieval yields precision=1, recall=1, f1=1, mrr=1."""
        evaluator = RAGEvaluator()
        results = [self._make_retrieved("c1"), self._make_retrieved("c2")]
        relevant = frozenset({"c1", "c2"})
        metrics = evaluator.evaluate_single(results, relevant, latency_ms=1.0)
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0
        assert metrics.mrr == 1.0

    def test_evaluator_no_matches(self):
        """No overlap yields precision=0, recall=0, f1=0, mrr=0."""
        evaluator = RAGEvaluator()
        results = [self._make_retrieved("c1")]
        relevant = frozenset({"c99"})
        metrics = evaluator.evaluate_single(results, relevant, latency_ms=1.0)
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0
        assert metrics.mrr == 0.0

    def test_evaluator_partial_match(self):
        """Partial overlap produces fractional precision and recall."""
        evaluator = RAGEvaluator()
        results = [self._make_retrieved("c1"), self._make_retrieved("c2")]
        relevant = frozenset({"c1", "c3"})  # c1 matches, c3 not retrieved, c2 irrelevant
        metrics = evaluator.evaluate_single(results, relevant, latency_ms=1.0)
        assert metrics.precision == 0.5  # 1/2 retrieved are relevant
        assert metrics.recall == 0.5    # 1/2 relevant are retrieved
        assert metrics.mrr == 1.0       # First result is relevant

    def test_evaluator_mrr(self):
        """MRR reflects the rank of the first relevant result."""
        evaluator = RAGEvaluator()
        # Relevant chunk is at position 2 (0-indexed: rank 1 is irrelevant, rank 2 is relevant)
        results = [self._make_retrieved("c_irr"), self._make_retrieved("c_rel")]
        relevant = frozenset({"c_rel"})
        metrics = evaluator.evaluate_single(results, relevant, latency_ms=1.0)
        assert metrics.mrr == 0.5  # 1/(1+1) = 0.5

    def test_compare_two_retrievers(self):
        """compare() returns metrics for each named retriever."""
        evaluator = RAGEvaluator()

        good_results = [self._make_retrieved("c1")]
        bad_results = [self._make_retrieved("c_wrong")]

        queries = [
            EvalQuery(query="test", relevant_chunk_ids=frozenset({"c1"})),
        ]

        comparison = evaluator.compare(
            {
                "good": self._dummy_retriever(good_results),
                "bad": self._dummy_retriever(bad_results),
            },
            queries,
        )

        assert "good" in comparison
        assert "bad" in comparison
        assert comparison["good"]["avg_precision"] == 1.0
        assert comparison["bad"]["avg_precision"] == 0.0

    def test_eval_query_frozen(self):
        """EvalQuery is a frozen dataclass."""
        eq = EvalQuery(query="test", relevant_chunk_ids=frozenset({"c1"}))
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            eq.query = "changed"  # type: ignore[misc]

    def test_retrieval_metrics_frozen(self):
        """RetrievalMetrics is a frozen dataclass."""
        m = RetrievalMetrics(
            precision=1.0, recall=1.0, f1=1.0, mrr=1.0,
            latency_ms=1.0, results_count=1,
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            m.precision = 0.5  # type: ignore[misc]

    def test_evaluate_batch_aggregates(self):
        """evaluate_batch returns averaged metrics across all queries."""
        evaluator = RAGEvaluator()
        results = [self._make_retrieved("c1")]

        queries = [
            EvalQuery(query="q1", relevant_chunk_ids=frozenset({"c1"})),
            EvalQuery(query="q2", relevant_chunk_ids=frozenset({"c1"})),
        ]

        batch = evaluator.evaluate_batch(
            self._dummy_retriever(results), queries, top_k=5,
        )
        assert batch["query_count"] == 2
        assert batch["avg_precision"] == 1.0
        assert batch["avg_recall"] == 1.0

    def test_evaluate_batch_empty_queries(self):
        """evaluate_batch with no queries returns error dict."""
        evaluator = RAGEvaluator()
        result = evaluator.evaluate_batch(
            self._dummy_retriever([]), queries=[], top_k=5,
        )
        assert "error" in result

    def test_evaluate_single_empty_results(self):
        """Empty result list yields precision=0, recall=0."""
        evaluator = RAGEvaluator()
        metrics = evaluator.evaluate_single(
            results=[], relevant_ids=frozenset({"c1"}), latency_ms=0.0,
        )
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.results_count == 0

    def test_evaluate_single_empty_relevant(self):
        """Empty relevant set yields recall=0 (vacuously)."""
        evaluator = RAGEvaluator()
        metrics = evaluator.evaluate_single(
            results=[self._make_retrieved("c1")],
            relevant_ids=frozenset(),
            latency_ms=0.0,
        )
        assert metrics.recall == 0.0


# ---------------------------------------------------------------------------
# Frozen dataclass tests for extraction models
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractionModels:
    """Frozen dataclass properties of extraction models."""

    def test_extracted_entity_frozen(self):
        """ExtractedEntity is immutable."""
        e = ExtractedEntity(name="부산항", entity_type="Port")
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            e.name = "인천항"  # type: ignore[misc]

    def test_extracted_relationship_frozen(self):
        """ExtractedRelationship is immutable."""
        r = ExtractedRelationship(
            source="부산항", target="세종대왕함", relationship_type="RELATED_TO",
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            r.source = "인천항"  # type: ignore[misc]

    def test_entity_extraction_result_frozen(self):
        """EntityExtractionResult is immutable."""
        result = EntityExtractionResult()
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            result.entities = ()  # type: ignore[misc]

    def test_extraction_result_defaults_empty(self):
        """EntityExtractionResult defaults to empty tuples."""
        result = EntityExtractionResult()
        assert result.entities == ()
        assert result.relationships == ()
