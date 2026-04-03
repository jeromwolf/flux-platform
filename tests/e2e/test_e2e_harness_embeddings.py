"""E2E harness tests for embedding endpoints (/api/v1/embeddings/*).

Tests vector search, hybrid search, and vector index management using
MockNeo4jSession -- no real Neo4j needed.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from tests.helpers.mock_neo4j import (
    MockNeo4jResult,
    make_neo4j_node,
)
from tests.e2e.conftest import _reset

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ===========================================================================
# Vector Search
# ===========================================================================


class TestEmbeddingVectorSearch:
    """POST /api/v1/embeddings/search endpoint tests."""

    async def test_vector_search(self, harness: Any) -> None:
        """Valid vector search returns results with serialized FakeNode."""
        client, session, _app = harness

        node = make_neo4j_node(
            element_id="4:emb:1",
            labels=["Document"],
            props={"name": "Test Doc", "topic": "maritime"},
        )
        # The search Cypher returns records with 'node' and 'score' keys
        _reset(session, [MockNeo4jResult([{"node": node, "score": 0.95}])])

        resp = await client.post(
            "/api/v1/embeddings/search",
            json={
                "label": "Document",
                "property": "embedding",
                "queryVector": [0.1] * 768,
                "topK": 5,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert "meta" in body
        assert body["meta"]["label"] == "Document"
        assert body["meta"]["topK"] == 5
        assert body["meta"]["indexName"] == "document_embedding_index"
        assert len(body["results"]) == 1
        # The node should be serialized with id/labels/properties
        row = body["results"][0]
        assert row["score"] == 0.95
        assert row["node"]["id"] == "4:emb:1"

    async def test_vector_search_invalid_label(self, harness: Any) -> None:
        """Invalid label (not a valid Python identifier) returns 400."""
        client, session, _app = harness

        resp = await client.post(
            "/api/v1/embeddings/search",
            json={
                "label": "123invalid",
                "property": "embedding",
                "queryVector": [0.1] * 10,
                "topK": 5,
            },
        )
        assert resp.status_code == 400
        assert "Invalid label" in resp.json()["detail"]

    async def test_vector_search_session_error(self, harness: Any) -> None:
        """Session.run raising an exception returns 500."""
        client, session, _app = harness

        # Patch session.run to raise
        session.run = AsyncMock(side_effect=Exception("connection lost"))

        resp = await client.post(
            "/api/v1/embeddings/search",
            json={
                "label": "Vessel",
                "property": "embedding",
                "queryVector": [0.5] * 10,
                "topK": 3,
            },
        )
        assert resp.status_code == 500
        assert "Vector search failed" in resp.json()["detail"]


# ===========================================================================
# Hybrid Search
# ===========================================================================


class TestEmbeddingHybridSearch:
    """POST /api/v1/embeddings/hybrid endpoint tests."""

    async def test_hybrid_search(self, harness: Any) -> None:
        """Valid hybrid search returns results with fused scores."""
        client, session, _app = harness

        node = make_neo4j_node(
            element_id="4:emb:2",
            labels=["Vessel"],
            props={"name": "Test Vessel"},
        )
        _reset(
            session,
            [MockNeo4jResult([{"node": node, "score": 0.88, "vectorScore": 0.9, "textScore": 0.1}])],
        )

        resp = await client.post(
            "/api/v1/embeddings/hybrid",
            json={
                "label": "Vessel",
                "property": "embedding",
                "queryVector": [0.2] * 768,
                "textQuery": "cargo vessel",
                "topK": 10,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["fusion"] == "rrf"
        assert body["meta"]["textQuery"] == "cargo vessel"
        assert len(body["results"]) == 1

    async def test_hybrid_search_invalid_label(self, harness: Any) -> None:
        """Invalid label in hybrid search returns 400."""
        client, session, _app = harness

        resp = await client.post(
            "/api/v1/embeddings/hybrid",
            json={
                "label": "999bad",
                "property": "embedding",
                "queryVector": [0.1] * 10,
                "textQuery": "test",
                "topK": 5,
            },
        )
        assert resp.status_code == 400
        assert "Invalid label" in resp.json()["detail"]


# ===========================================================================
# Index Management
# ===========================================================================


class TestEmbeddingIndexManagement:
    """GET/POST /api/v1/embeddings/indexes endpoint tests."""

    async def test_list_indexes_empty(self, harness: Any) -> None:
        """Initially the index list is empty (module-level manager starts empty)."""
        client, _session, _app = harness

        resp = await client.get("/api/v1/embeddings/indexes")
        assert resp.status_code == 200
        body = resp.json()
        assert "indexes" in body
        # May already have indexes from other tests in this session;
        # just verify the response shape
        assert isinstance(body["indexes"], list)

    async def test_create_index(self, harness: Any) -> None:
        """Creating a vector index returns 201 with index metadata."""
        client, session, _app = harness

        # session.run is called for the CREATE INDEX DDL
        _reset(session, [MockNeo4jResult([])])

        resp = await client.post(
            "/api/v1/embeddings/indexes",
            json={
                "label": "Port",
                "property": "embedding",
                "dimensions": 384,
                "similarity": "cosine",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["created"] is True
        assert body["indexName"] == "port_embedding_index"
        assert body["label"] == "Port"
        assert body["dimensions"] == 384
        assert body["similarity"] == "cosine"

    async def test_create_index_invalid_label(self, harness: Any) -> None:
        """Creating an index with an invalid label returns 400."""
        client, _session, _app = harness

        resp = await client.post(
            "/api/v1/embeddings/indexes",
            json={
                "label": "0invalid",
                "property": "embedding",
                "dimensions": 768,
                "similarity": "cosine",
            },
        )
        assert resp.status_code == 400
        assert "Invalid label" in resp.json()["detail"]
