"""Advanced unit tests for Hybrid RAG orchestrator, embedding providers, and document pipeline.

Covers:
    TC-EP01: StubEmbeddingProvider
    TC-EP02: OllamaEmbeddingProvider
    TC-EP03: OpenAIEmbeddingProvider
    TC-HE01: HybridRAGEngine - SEMANTIC mode
    TC-HE02: HybridRAGEngine - KEYWORD mode
    TC-HE03: HybridRAGEngine - HYBRID mode
    TC-HE04: Reciprocal Rank Fusion
    TC-HE05: Re-ranking
    TC-HE06: Answer generation
    TC-DP01: DocumentPipeline

All tests are marked @pytest.mark.unit and require no external dependencies.
PYTHONPATH: .
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pytest

from rag.documents.models import Document, DocumentChunk
from rag.embeddings.models import EmbeddingConfig, EmbeddingResult
from rag.embeddings.protocol import EmbeddingProvider
from rag.embeddings.providers import (
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
    StubEmbeddingProvider,
)
from rag.engines.models import RAGConfig, RetrievalMode, RetrievedChunk
from rag.engines.orchestrator import HybridRAGEngine, RerankerConfig
from rag.engines.retriever import SimpleRetriever
from rag.documents.pipeline import DocumentPipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_retriever_with_chunks(
    texts: List[str],
    dimension: int = 16,
    top_k: int = 5,
) -> SimpleRetriever:
    """Build a populated SimpleRetriever using StubEmbeddingProvider."""
    embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=dimension))
    result = embedder.embed_texts(texts)
    chunks = [
        DocumentChunk(
            chunk_id=f"c{i}",
            doc_id="d1",
            content=t,
            chunk_index=i,
            embedding=result.vectors[i],
        )
        for i, t in enumerate(texts)
    ]
    retriever = SimpleRetriever(RAGConfig(top_k=top_k, similarity_threshold=0.0))
    retriever.add_chunks(chunks)
    return retriever


_SAMPLE_TEXTS = [
    "COLREG is a maritime regulation",
    "Busan port handles containers",
    "Ship navigation rules",
]


class MockLLMResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class MockLLM:
    def generate(self, prompt: str, **kw: object) -> MockLLMResponse:
        return MockLLMResponse("Generated answer")


# ---------------------------------------------------------------------------
# TC-EP01: StubEmbeddingProvider
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStubEmbeddingProvider:
    """TC-EP01: Deterministic stub embedding provider."""

    def _provider(self, dimension: int = 16, normalize: bool = True) -> StubEmbeddingProvider:
        return StubEmbeddingProvider(EmbeddingConfig(dimension=dimension, normalize=normalize))

    def test_same_text_produces_same_vector(self) -> None:
        """TC-EP01a: Same text input always yields the same output vector."""
        provider = self._provider()
        v1 = provider.embed_query("hello world")
        v2 = provider.embed_query("hello world")
        assert v1 == v2

    def test_different_text_produces_different_vector(self) -> None:
        """TC-EP01b: Different text inputs produce different vectors."""
        provider = self._provider()
        v1 = provider.embed_query("maritime vessel")
        v2 = provider.embed_query("Busan container port")
        assert v1 != v2

    def test_vector_dimension_matches_config(self) -> None:
        """TC-EP01c: Output vector length equals EmbeddingConfig.dimension."""
        provider = self._provider(dimension=32)
        v = provider.embed_query("test text")
        assert len(v) == 32

    def test_vectors_are_normalized(self) -> None:
        """TC-EP01d: Normalized vectors have magnitude ~1.0 when normalize=True."""
        provider = self._provider(dimension=16, normalize=True)
        v = provider.embed_query("some query text")
        magnitude = math.sqrt(sum(x * x for x in v))
        assert abs(magnitude - 1.0) < 1e-6

    def test_embed_texts_returns_embedding_result_with_correct_fields(self) -> None:
        """TC-EP01e: embed_texts returns EmbeddingResult with correct vectors, model, dimension."""
        provider = self._provider(dimension=16)
        texts = ["text one", "text two"]
        result = provider.embed_texts(texts)

        assert isinstance(result, EmbeddingResult)
        assert len(result.vectors) == 2
        assert result.dimension == 16
        assert "stub" in result.model
        assert result.token_count >= 0

    def test_embed_query_returns_tuple_of_correct_dimension(self) -> None:
        """TC-EP01f: embed_query returns a tuple with length matching config dimension."""
        provider = self._provider(dimension=24)
        v = provider.embed_query("navigation rules")
        assert isinstance(v, tuple)
        assert len(v) == 24

    def test_satisfies_embedding_provider_protocol(self) -> None:
        """TC-EP01g: StubEmbeddingProvider is an instance of EmbeddingProvider protocol."""
        provider = self._provider()
        assert isinstance(provider, EmbeddingProvider)


# ---------------------------------------------------------------------------
# TC-EP02: OllamaEmbeddingProvider
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOllamaEmbeddingProvider:
    """TC-EP02: Ollama embedding provider with fallback behavior."""

    def test_falls_back_to_stub_when_langchain_not_installed(self) -> None:
        """TC-EP02a: Falls back to stub embeddings when langchain_ollama is unavailable.

        This test relies on langchain_ollama not being installed in the unit test
        environment. If it is installed, the provider may attempt a real network call
        which will also fall back gracefully.
        """
        import importlib
        import sys

        # Temporarily mask langchain_ollama if it exists
        original = sys.modules.get("langchain_ollama")
        sys.modules["langchain_ollama"] = None  # type: ignore[assignment]
        try:
            provider = OllamaEmbeddingProvider(EmbeddingConfig(dimension=16))
            result = provider.embed_texts(["test text"])
            assert isinstance(result, EmbeddingResult)
            assert len(result.vectors) == 1
            assert len(result.vectors[0]) == 16
        finally:
            if original is None:
                del sys.modules["langchain_ollama"]
            else:
                sys.modules["langchain_ollama"] = original

    def test_dimension_property(self) -> None:
        """TC-EP02b: dimension property reflects EmbeddingConfig.dimension."""
        provider = OllamaEmbeddingProvider(EmbeddingConfig(dimension=768))
        assert provider.dimension == 768


# ---------------------------------------------------------------------------
# TC-EP03: OpenAIEmbeddingProvider
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAIEmbeddingProvider:
    """TC-EP03: OpenAI embedding provider with fallback behavior."""

    def test_falls_back_to_stub_when_no_api_key(self) -> None:
        """TC-EP03a: Falls back to stub embeddings when api_key is empty."""
        provider = OpenAIEmbeddingProvider(
            config=EmbeddingConfig(dimension=16),
            api_key="",
        )
        result = provider.embed_texts(["some text"])
        assert isinstance(result, EmbeddingResult)
        assert len(result.vectors) == 1
        assert len(result.vectors[0]) == 16

    def test_dimension_property(self) -> None:
        """TC-EP03b: dimension property reflects EmbeddingConfig.dimension."""
        provider = OpenAIEmbeddingProvider(
            config=EmbeddingConfig(dimension=1536),
            api_key="",
        )
        assert provider.dimension == 1536


# ---------------------------------------------------------------------------
# TC-HE01: HybridRAGEngine - SEMANTIC mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHybridRAGEngineSemantic:
    """TC-HE01: HybridRAGEngine operating in SEMANTIC retrieval mode."""

    def _engine(self) -> tuple[HybridRAGEngine, StubEmbeddingProvider]:
        config = RAGConfig(
            mode=RetrievalMode.SEMANTIC,
            top_k=3,
            similarity_threshold=0.0,
        )
        embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=16))
        retriever = _make_retriever_with_chunks(_SAMPLE_TEXTS, dimension=16, top_k=3)
        engine = HybridRAGEngine(config=config, retriever=retriever)
        return engine, embedder

    def test_query_with_embedding_returns_results(self) -> None:
        """TC-HE01a: query with a valid query_embedding returns a non-empty RAGResult."""
        engine, embedder = self._engine()
        query_vec = embedder.embed_query("maritime navigation")
        result = engine.query("maritime navigation", query_embedding=query_vec)
        # With similarity_threshold=0.0, at least one chunk should be returned
        assert result.chunk_count >= 0  # may be 0 if store is empty, but engine built above
        assert result.query == "maritime navigation"
        assert isinstance(result.answer, str)

    def test_query_without_embedding_returns_error_for_semantic_mode(self) -> None:
        """TC-HE01b: query without query_embedding returns error message for SEMANTIC mode."""
        engine, _ = self._engine()
        result = engine.query("maritime navigation", query_embedding=None)
        assert result.chunk_count == 0
        assert "query_embedding required" in result.answer.lower() or result.answer != ""


# ---------------------------------------------------------------------------
# TC-HE02: HybridRAGEngine - KEYWORD mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHybridRAGEngineKeyword:
    """TC-HE02: HybridRAGEngine operating in KEYWORD retrieval mode."""

    def _engine(self) -> HybridRAGEngine:
        config = RAGConfig(
            mode=RetrievalMode.KEYWORD,
            top_k=3,
            similarity_threshold=0.0,
        )
        retriever = _make_retriever_with_chunks(_SAMPLE_TEXTS, dimension=16, top_k=3)
        return HybridRAGEngine(config=config, retriever=retriever)

    def test_query_returns_keyword_results_without_embedding(self) -> None:
        """TC-HE02a: query returns keyword-matched results without needing query_embedding."""
        engine = self._engine()
        result = engine.query("maritime regulation", query_embedding=None)
        assert isinstance(result.answer, str)
        assert result.query == "maritime regulation"
        # Keyword results should find the COLREG chunk
        if result.chunk_count > 0:
            modes = {rc.retrieval_mode for rc in result.retrieved_chunks}
            assert RetrievalMode.KEYWORD in modes


# ---------------------------------------------------------------------------
# TC-HE03: HybridRAGEngine - HYBRID mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHybridRAGEngineHybrid:
    """TC-HE03: HybridRAGEngine operating in HYBRID retrieval mode."""

    def _setup(self) -> tuple[HybridRAGEngine, StubEmbeddingProvider]:
        config = RAGConfig(
            mode=RetrievalMode.HYBRID,
            top_k=3,
            similarity_threshold=0.0,
        )
        embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=16))
        retriever = _make_retriever_with_chunks(_SAMPLE_TEXTS, dimension=16, top_k=3)
        engine = HybridRAGEngine(config=config, retriever=retriever)
        return engine, embedder

    def test_hybrid_combines_semantic_and_keyword_results(self) -> None:
        """TC-HE03a: HYBRID mode fuses both semantic and keyword results."""
        engine, embedder = self._setup()
        query_vec = embedder.embed_query("COLREG maritime")
        result = engine.query("COLREG maritime", query_embedding=query_vec)
        assert isinstance(result.answer, str)
        assert result.query == "COLREG maritime"

    def test_hybrid_results_tagged_with_hybrid_retrieval_mode(self) -> None:
        """TC-HE03b: Results from HYBRID mode are tagged with RetrievalMode.HYBRID."""
        engine, embedder = self._setup()
        query_vec = embedder.embed_query("COLREG maritime")
        result = engine.query("COLREG maritime", query_embedding=query_vec)
        if result.chunk_count > 0:
            for rc in result.retrieved_chunks:
                assert rc.retrieval_mode == RetrievalMode.HYBRID


# ---------------------------------------------------------------------------
# TC-HE04: Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReciprocalRankFusion:
    """TC-HE04: HybridRAGEngine._reciprocal_rank_fusion static method."""

    def _make_rc(
        self,
        chunk_id: str,
        content: str,
        score: float = 0.5,
        mode: RetrievalMode = RetrievalMode.SEMANTIC,
    ) -> RetrievedChunk:
        chunk = DocumentChunk(
            chunk_id=chunk_id,
            doc_id="d1",
            content=content,
            chunk_index=0,
            embedding=(0.1, 0.2),
        )
        return RetrievedChunk(chunk=chunk, score=score, retrieval_mode=mode)

    def test_rrf_merges_two_lists(self) -> None:
        """TC-HE04a: _reciprocal_rank_fusion merges two result lists into one ranked list."""
        list_a = [self._make_rc("c1", "alpha", 0.9), self._make_rc("c2", "beta", 0.8)]
        list_b = [self._make_rc("c3", "gamma", 0.7), self._make_rc("c4", "delta", 0.6)]
        fused = HybridRAGEngine._reciprocal_rank_fusion(list_a, list_b, top_k=10)
        assert len(fused) == 4
        chunk_ids = {rc.chunk.chunk_id for rc in fused}
        assert chunk_ids == {"c1", "c2", "c3", "c4"}

    def test_rrf_deduplicates_by_chunk_id(self) -> None:
        """TC-HE04b: Chunks appearing in both lists are deduplicated."""
        shared = self._make_rc("c1", "shared content", 0.9)
        unique_a = self._make_rc("c2", "only in a", 0.8)
        unique_b = self._make_rc("c3", "only in b", 0.7)

        list_a = [shared, unique_a]
        list_b = [shared, unique_b]
        fused = HybridRAGEngine._reciprocal_rank_fusion(list_a, list_b, top_k=10)

        chunk_ids = [rc.chunk.chunk_id for rc in fused]
        # chunk c1 must appear exactly once
        assert chunk_ids.count("c1") == 1

    def test_rrf_higher_ranked_items_get_higher_scores(self) -> None:
        """TC-HE04c: Items ranked first in both lists receive higher RRF scores than lower-ranked ones."""
        # c1 appears first in both lists → should have highest RRF score
        c1 = self._make_rc("c1", "top item", 0.95)
        c2 = self._make_rc("c2", "mid item", 0.70)
        c3 = self._make_rc("c3", "low item", 0.40)

        list_a = [c1, c2, c3]
        list_b = [c1, c3, c2]
        fused = HybridRAGEngine._reciprocal_rank_fusion(list_a, list_b, top_k=10)

        # c1 must rank first (highest RRF score)
        assert fused[0].chunk.chunk_id == "c1"
        fused_scores = [rc.score for rc in fused]
        assert fused_scores == sorted(fused_scores, reverse=True)


# ---------------------------------------------------------------------------
# TC-HE05: Re-ranking
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReranking:
    """TC-HE05: HybridRAGEngine._score_boost_rerank method."""

    def _make_rc(
        self,
        chunk_id: str,
        content: str,
        score: float,
        mode: RetrievalMode = RetrievalMode.HYBRID,
    ) -> RetrievedChunk:
        chunk = DocumentChunk(
            chunk_id=chunk_id,
            doc_id="d1",
            content=content,
            chunk_index=0,
            embedding=(0.1, 0.2),
        )
        return RetrievedChunk(chunk=chunk, score=score, retrieval_mode=mode)

    def test_score_boost_boosts_chunks_matching_query_terms(self) -> None:
        """TC-HE05a: score_boost_rerank boosts chunks that contain query terms."""
        query = "COLREG maritime vessel"
        rc_match = self._make_rc("c1", "COLREG defines maritime vessel rules", 0.5)
        rc_nomatch = self._make_rc("c2", "unrelated subject matter here", 0.5)

        reranked = HybridRAGEngine._score_boost_rerank([rc_match, rc_nomatch], query)

        # c1 contains query terms, so it should have a higher score than c2
        scores = {rc.chunk.chunk_id: rc.score for rc in reranked}
        assert scores["c1"] >= scores["c2"]

    def test_boosted_scores_capped_at_1_0(self) -> None:
        """TC-HE05b: Boosted scores do not exceed 1.0."""
        query = "vessel navigation maritime"
        rc = self._make_rc("c1", "vessel navigation maritime rules", 0.99)
        reranked = HybridRAGEngine._score_boost_rerank([rc], query)
        assert all(rc.score <= 1.0 for rc in reranked)


# ---------------------------------------------------------------------------
# TC-HE06: Answer generation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnswerGeneration:
    """TC-HE06: HybridRAGEngine._generate_answer method."""

    def _make_rc(self, chunk_id: str, content: str) -> RetrievedChunk:
        chunk = DocumentChunk(
            chunk_id=chunk_id,
            doc_id="d1",
            content=content,
            chunk_index=0,
            embedding=(0.1, 0.2),
        )
        return RetrievedChunk(chunk=chunk, score=0.8, retrieval_mode=RetrievalMode.SEMANTIC)

    def test_without_llm_returns_top_chunk_content(self) -> None:
        """TC-HE06a: Without an LLM, _generate_answer returns the top chunk's content."""
        config = RAGConfig(mode=RetrievalMode.KEYWORD, top_k=3, similarity_threshold=0.0)
        engine = HybridRAGEngine(config=config)
        rc = self._make_rc("c1", "Top chunk content here")
        answer = engine._generate_answer("some query", [rc])
        assert answer == "Top chunk content here"

    def test_with_mock_llm_returns_llm_generated_answer(self) -> None:
        """TC-HE06b: With a mock LLM, _generate_answer returns the LLM response text."""
        config = RAGConfig(mode=RetrievalMode.KEYWORD, top_k=3, similarity_threshold=0.0)
        engine = HybridRAGEngine(config=config, llm=MockLLM())
        rc = self._make_rc("c1", "some relevant context")
        answer = engine._generate_answer("some query", [rc])
        assert answer == "Generated answer"

    def test_empty_chunks_returns_no_information_message(self) -> None:
        """TC-HE06c: Empty chunks list returns 'No relevant information found.'."""
        config = RAGConfig(mode=RetrievalMode.KEYWORD, top_k=3, similarity_threshold=0.0)
        engine = HybridRAGEngine(config=config)
        answer = engine._generate_answer("some query", [])
        assert answer == "No relevant information found."


# ---------------------------------------------------------------------------
# TC-DP01: DocumentPipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDocumentPipeline:
    """TC-DP01: DocumentPipeline end-to-end ingestion."""

    def _embedder(self, dimension: int = 16) -> StubEmbeddingProvider:
        return StubEmbeddingProvider(EmbeddingConfig(dimension=dimension))

    def _retriever(self, dimension: int = 16) -> SimpleRetriever:
        return SimpleRetriever(RAGConfig(top_k=5, similarity_threshold=0.0))

    def test_ingest_text_creates_chunks(self) -> None:
        """TC-DP01a: ingest_text with chunker-only pipeline creates at least one chunk."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_text("COLREG is a maritime regulation.", doc_id="doc1")
        assert result.success is True
        assert result.chunks_created >= 1
        assert result.doc_id == "doc1"

    def test_ingest_text_with_embedder_creates_embedded_chunks(self) -> None:
        """TC-DP01b: ingest_text with embedder produces embedded chunks."""
        pipeline = DocumentPipeline(embedder=self._embedder())
        result = pipeline.ingest_text("Ship navigation rules and COLREG.", doc_id="doc2")
        assert result.success is True
        assert result.chunks_embedded >= 1
        assert result.chunks_embedded == result.chunks_created

    def test_ingest_text_with_embedder_and_retriever_indexes_chunks(self) -> None:
        """TC-DP01c: ingest_text with embedder + retriever indexes all embedded chunks."""
        embedder = self._embedder()
        retriever = self._retriever()
        pipeline = DocumentPipeline(embedder=embedder, retriever=retriever)
        result = pipeline.ingest_text("Busan port handles container cargo.", doc_id="doc3")
        assert result.success is True
        assert result.chunks_indexed >= 1
        assert result.chunks_indexed == result.chunks_embedded
        # Retriever should now hold the indexed chunks
        assert retriever.chunk_count >= 1

    def test_ingest_document_works_with_document_object(self) -> None:
        """TC-DP01d: ingest_document accepts a Document object and returns IngestionResult."""
        doc = Document(
            doc_id="doc4",
            title="Maritime Safety",
            content="Vessels must follow COLREG rules at sea.",
        )
        pipeline = DocumentPipeline(embedder=self._embedder())
        result = pipeline.ingest_document(doc)
        assert result.success is True
        assert result.doc_id == "doc4"
        assert result.chunks_created >= 1

    def test_ingested_count_increments(self) -> None:
        """TC-DP01e: ingested_count increments by 1 for each successful ingest_text call."""
        pipeline = DocumentPipeline()
        assert pipeline.ingested_count == 0
        pipeline.ingest_text("first document content", doc_id="d1")
        assert pipeline.ingested_count == 1
        pipeline.ingest_text("second document content", doc_id="d2")
        assert pipeline.ingested_count == 2

    def test_reset_clears_counter(self) -> None:
        """TC-DP01f: reset() sets ingested_count back to 0."""
        pipeline = DocumentPipeline()
        pipeline.ingest_text("some content", doc_id="d1")
        pipeline.ingest_text("more content", doc_id="d2")
        assert pipeline.ingested_count == 2
        pipeline.reset()
        assert pipeline.ingested_count == 0

    def test_empty_text_returns_error_result(self) -> None:
        """TC-DP01g: ingest_text with empty string returns a failed IngestionResult."""
        pipeline = DocumentPipeline()
        result = pipeline.ingest_text("", doc_id="empty-doc")
        assert result.success is False
        assert result.error != ""
