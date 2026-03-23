"""Unit tests for BM25 keyword scoring in SimpleRetriever.

Covers:
    TC-BM01: BM25 scoring produces non-zero scores for matching terms
    TC-BM02: BM25 ranking orders relevant docs higher than TF alone
    TC-BM03: BM25 with empty query returns zero scores

All tests are @pytest.mark.unit and require no external dependencies.
PYTHONPATH: .
"""
from __future__ import annotations

import pytest

from rag.documents.models import DocumentChunk
from rag.engines.models import RAGConfig, RetrievalMode
from rag.engines.retriever import SimpleRetriever


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_id: str,
    content: str,
    doc_id: str = "doc-001",
    embedding: tuple[float, ...] = (),
) -> DocumentChunk:
    """Create a DocumentChunk with the given content (no embedding by default)."""
    return DocumentChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        content=content,
        chunk_index=0,
        embedding=embedding,
    )


def _retriever_with_chunks(chunks: list[DocumentChunk]) -> SimpleRetriever:
    """Create a SimpleRetriever pre-loaded with chunks (embeddings optional)."""
    retriever = SimpleRetriever()
    # keyword_search does not require embeddings — add chunks directly
    retriever._chunks = list(chunks)
    return retriever


# ---------------------------------------------------------------------------
# TC-BM01: BM25 scoring is non-zero for matching terms
# ---------------------------------------------------------------------------


class TestBM25NonZeroScores:
    """TC-BM01: BM25 returns positive scores when query terms are present."""

    @pytest.mark.unit
    def test_single_term_match_yields_positive_score(self) -> None:
        """TC-BM01-a: A chunk containing the query term scores > 0."""
        chunk = _make_chunk("c1", "ship navigates the maritime route")
        retriever = _retriever_with_chunks([chunk])
        results = retriever.keyword_search("maritime", top_k=5)
        assert len(results) == 1
        assert results[0].score > 0.0

    @pytest.mark.unit
    def test_no_match_yields_zero_results(self) -> None:
        """TC-BM01-b: A chunk with none of the query terms is excluded."""
        chunk = _make_chunk("c1", "vessel speed fuel consumption")
        retriever = _retriever_with_chunks([chunk])
        results = retriever.keyword_search("maritime route", top_k=5)
        assert len(results) == 0

    @pytest.mark.unit
    def test_multiple_query_terms_increase_score(self) -> None:
        """TC-BM01-c: More matching terms → higher BM25 score."""
        chunk_one_match = _make_chunk("c1", "ship navigates the ocean")
        chunk_two_matches = _make_chunk("c2", "ship navigates the maritime route")
        retriever = _retriever_with_chunks([chunk_one_match, chunk_two_matches])

        results = retriever.keyword_search("ship maritime route", top_k=5)
        # chunk_two_matches has more matching terms — should score higher
        scores = {r.chunk.chunk_id: r.score for r in results}
        assert scores["c2"] > scores.get("c1", 0.0)

    @pytest.mark.unit
    def test_all_results_have_keyword_retrieval_mode(self) -> None:
        """TC-BM01-d: All returned RetrievedChunk items use KEYWORD mode."""
        chunks = [
            _make_chunk("c1", "maritime safety regulations"),
            _make_chunk("c2", "port operations maritime"),
        ]
        retriever = _retriever_with_chunks(chunks)
        results = retriever.keyword_search("maritime", top_k=5)
        assert all(r.retrieval_mode == RetrievalMode.KEYWORD for r in results)


# ---------------------------------------------------------------------------
# TC-BM02: BM25 ranking is better than naive TF
# ---------------------------------------------------------------------------


class TestBM25Ranking:
    """TC-BM02: BM25 ranks truly relevant documents higher."""

    @pytest.mark.unit
    def test_exact_content_match_scores_highest(self) -> None:
        """TC-BM02-a: The chunk most aligned to the query ranks first."""
        chunks = [
            _make_chunk("c1", "weather forecast for the Atlantic ocean"),
            _make_chunk("c2", "maritime safety regulations for port operations"),
            _make_chunk("c3", "vessel collision vessel collision maritime safety maritime safety"),
        ]
        retriever = _retriever_with_chunks(chunks)
        results = retriever.keyword_search("vessel collision maritime safety", top_k=3)

        # c3 has more query term occurrences (doubled) than c2
        top_ids = [r.chunk.chunk_id for r in results]
        assert top_ids[0] == "c3"
        # c1 has no matching terms
        assert "c1" not in top_ids

    @pytest.mark.unit
    def test_document_length_normalisation_penalises_very_long_docs(self) -> None:
        """TC-BM02-b: A shorter doc with same TF as a longer doc scores higher in BM25."""
        # Short doc: "ship collision" (2 words, high TF ratio)
        short = _make_chunk("short", "ship collision")
        # Long doc: same terms buried in 30 words
        long_words = ["ship", "collision"] + ["filler"] * 28
        long = _make_chunk("long", " ".join(long_words))

        retriever = _retriever_with_chunks([short, long])
        results = retriever.keyword_search("ship collision", top_k=2)

        # Short doc should score higher because BM25 penalises document length
        score_map = {r.chunk.chunk_id: r.score for r in results}
        assert score_map["short"] >= score_map["long"]

    @pytest.mark.unit
    def test_top_k_limits_returned_results(self) -> None:
        """TC-BM02-c: top_k parameter limits the number of returned results."""
        chunks = [
            _make_chunk(f"c{i}", f"maritime vessel ship route {i}") for i in range(10)
        ]
        retriever = _retriever_with_chunks(chunks)
        results = retriever.keyword_search("maritime vessel", top_k=3)
        assert len(results) <= 3

    @pytest.mark.unit
    def test_scores_are_normalised_to_zero_one(self) -> None:
        """TC-BM02-d: All BM25 scores are in [0, 1]."""
        chunks = [
            _make_chunk("c1", "ship maritime"),
            _make_chunk("c2", "port maritime safety"),
            _make_chunk("c3", "completely unrelated text"),
        ]
        retriever = _retriever_with_chunks(chunks)
        results = retriever.keyword_search("maritime", top_k=5)
        for r in results:
            assert 0.0 <= r.score <= 1.0, f"score out of range: {r.score}"


# ---------------------------------------------------------------------------
# TC-BM03: BM25 with empty query
# ---------------------------------------------------------------------------


class TestBM25EmptyQuery:
    """TC-BM03: BM25 handles empty or whitespace queries gracefully."""

    @pytest.mark.unit
    def test_empty_query_returns_empty_list(self) -> None:
        """TC-BM03-a: keyword_search('') returns []."""
        chunks = [_make_chunk("c1", "ship route maritime")]
        retriever = _retriever_with_chunks(chunks)
        results = retriever.keyword_search("", top_k=5)
        assert results == []

    @pytest.mark.unit
    def test_whitespace_only_query_returns_empty_list(self) -> None:
        """TC-BM03-b: keyword_search('   ') returns []."""
        chunks = [_make_chunk("c1", "ship route maritime")]
        retriever = _retriever_with_chunks(chunks)
        results = retriever.keyword_search("   ", top_k=5)
        assert results == []

    @pytest.mark.unit
    def test_empty_retriever_returns_empty_list(self) -> None:
        """TC-BM03-c: keyword_search on an empty index returns []."""
        retriever = SimpleRetriever()
        results = retriever.keyword_search("maritime vessel", top_k=5)
        assert results == []

    @pytest.mark.unit
    def test_query_with_no_matching_docs_returns_empty_list(self) -> None:
        """TC-BM03-d: Query that matches no indexed chunks returns []."""
        chunks = [_make_chunk("c1", "weather forecast Atlantic")]
        retriever = _retriever_with_chunks(chunks)
        results = retriever.keyword_search("maritime vessel port", top_k=5)
        assert results == []
