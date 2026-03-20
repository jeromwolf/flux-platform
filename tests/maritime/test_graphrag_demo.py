"""Unit tests for poc.graphrag_demo module.

Tests query lists and module structure without running the demo.
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
class TestDemoQueries:
    """Verify demo query sets are properly defined."""

    def test_vector_queries_not_empty(self) -> None:
        from poc.graphrag_demo import VECTOR_QUERIES
        assert len(VECTOR_QUERIES) >= 2

    def test_vector_cypher_queries_not_empty(self) -> None:
        from poc.graphrag_demo import VECTOR_CYPHER_QUERIES
        assert len(VECTOR_CYPHER_QUERIES) >= 1

    def test_text2cypher_queries_not_empty(self) -> None:
        from poc.graphrag_demo import TEXT2CYPHER_QUERIES
        assert len(TEXT2CYPHER_QUERIES) >= 2

    def test_hybrid_queries_not_empty(self) -> None:
        from poc.graphrag_demo import HYBRID_QUERIES
        assert len(HYBRID_QUERIES) >= 1

    def test_agentic_queries_not_empty(self) -> None:
        from poc.graphrag_demo import AGENTIC_QUERIES
        assert len(AGENTIC_QUERIES) >= 3

    def test_all_queries_are_korean(self) -> None:
        from poc.graphrag_demo import (
            AGENTIC_QUERIES,
            HYBRID_QUERIES,
            TEXT2CYPHER_QUERIES,
            VECTOR_CYPHER_QUERIES,
            VECTOR_QUERIES,
        )
        all_queries = (
            VECTOR_QUERIES + VECTOR_CYPHER_QUERIES +
            TEXT2CYPHER_QUERIES + HYBRID_QUERIES + AGENTIC_QUERIES
        )
        for q in all_queries:
            assert any('\uAC00' <= c <= '\uD7A3' for c in q), f"Not Korean: {q}"

    def test_no_duplicate_queries(self) -> None:
        from poc.graphrag_demo import (
            AGENTIC_QUERIES,
            HYBRID_QUERIES,
            TEXT2CYPHER_QUERIES,
            VECTOR_CYPHER_QUERIES,
            VECTOR_QUERIES,
        )
        all_queries = (
            VECTOR_QUERIES + VECTOR_CYPHER_QUERIES +
            TEXT2CYPHER_QUERIES + HYBRID_QUERIES + AGENTIC_QUERIES
        )
        assert len(all_queries) == len(set(all_queries))


@pytest.mark.unit
class TestDemoFunctions:
    """Test demo utility functions."""

    def test_run_demo_callable(self) -> None:
        from poc.graphrag_demo import run_demo
        assert callable(run_demo)

    def test_main_callable(self) -> None:
        from poc.graphrag_demo import main
        assert callable(main)
