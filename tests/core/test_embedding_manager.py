"""Unit tests for kg.embeddings EmbeddingManager and related models.

Covers VectorIndexConfig, IndexMetadata, HybridSearchResult, and
EmbeddingManager registry + Cypher generation. All tests run without
any external dependencies or running services.
"""

from __future__ import annotations

import pytest

from kg.embeddings import EmbeddingManager, HybridSearchResult, IndexMetadata, VectorIndexConfig
from kg.embeddings.models import HybridSearchResult, IndexMetadata, VectorIndexConfig
from kg.embeddings.manager import EmbeddingManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    name: str = "doc_emb",
    label: str = "Document",
    property_name: str = "textEmbedding",
    dimensions: int = 768,
    similarity_function: str = "cosine",
) -> VectorIndexConfig:
    return VectorIndexConfig(
        name=name,
        label=label,
        property_name=property_name,
        dimensions=dimensions,
        similarity_function=similarity_function,
    )


# ===========================================================================
# VectorIndexConfig
# ===========================================================================


@pytest.mark.unit
class TestVectorIndexConfig:
    """VectorIndexConfig default values and frozen behaviour."""

    def test_defaults(self) -> None:
        cfg = VectorIndexConfig(name="idx", label="Node", property_name="embedding")
        assert cfg.dimensions == 768
        assert cfg.similarity_function == "cosine"

    def test_frozen(self) -> None:
        cfg = VectorIndexConfig(name="idx", label="Node", property_name="emb")
        with pytest.raises((AttributeError, TypeError)):
            cfg.dimensions = 512  # type: ignore[misc]

    def test_custom_values(self) -> None:
        cfg = VectorIndexConfig(
            name="vessel_emb",
            label="Vessel",
            property_name="nameEmbedding",
            dimensions=1024,
            similarity_function="euclidean",
        )
        assert cfg.name == "vessel_emb"
        assert cfg.label == "Vessel"
        assert cfg.property_name == "nameEmbedding"
        assert cfg.dimensions == 1024
        assert cfg.similarity_function == "euclidean"

    def test_required_fields(self) -> None:
        # Missing required field should raise TypeError
        with pytest.raises(TypeError):
            VectorIndexConfig()  # type: ignore[call-arg]


# ===========================================================================
# IndexMetadata
# ===========================================================================


@pytest.mark.unit
class TestIndexMetadata:
    """IndexMetadata default values and frozen behaviour."""

    def test_defaults(self) -> None:
        cfg = _make_config()
        meta = IndexMetadata(config=cfg)
        assert meta.status == "pending"
        assert meta.node_count == 0
        assert meta.created_at == ""

    def test_frozen(self) -> None:
        cfg = _make_config()
        meta = IndexMetadata(config=cfg)
        with pytest.raises((AttributeError, TypeError)):
            meta.status = "ready"  # type: ignore[misc]

    def test_custom_values(self) -> None:
        cfg = _make_config()
        meta = IndexMetadata(
            config=cfg,
            node_count=5000,
            created_at="2026-03-01T00:00:00+00:00",
            status="ready",
        )
        assert meta.node_count == 5000
        assert meta.status == "ready"
        assert meta.created_at == "2026-03-01T00:00:00+00:00"

    def test_config_reference(self) -> None:
        cfg = _make_config(name="vessel_idx", label="Vessel")
        meta = IndexMetadata(config=cfg)
        assert meta.config.name == "vessel_idx"
        assert meta.config.label == "Vessel"


# ===========================================================================
# HybridSearchResult
# ===========================================================================


@pytest.mark.unit
class TestHybridSearchResult:
    """HybridSearchResult default values and frozen behaviour."""

    def test_defaults(self) -> None:
        result = HybridSearchResult(node_id="n1", score=0.95)
        assert result.vector_score == 0.0
        assert result.text_score == 0.0
        assert result.properties == {}

    def test_frozen(self) -> None:
        result = HybridSearchResult(node_id="n1", score=0.95)
        with pytest.raises((AttributeError, TypeError)):
            result.score = 0.5  # type: ignore[misc]

    def test_custom_values(self) -> None:
        result = HybridSearchResult(
            node_id="doc-001",
            score=0.87,
            vector_score=0.9,
            text_score=0.84,
            properties={"title": "선박 성능 연구", "docId": "DOC-001"},
        )
        assert result.node_id == "doc-001"
        assert result.score == 0.87
        assert result.vector_score == 0.9
        assert result.text_score == 0.84
        assert result.properties["title"] == "선박 성능 연구"


# ===========================================================================
# EmbeddingManager
# ===========================================================================


@pytest.mark.unit
class TestEmbeddingManager:
    """EmbeddingManager registry operations."""

    def test_create_index(self) -> None:
        mgr = EmbeddingManager()
        cfg = _make_config()
        meta = mgr.create_index(cfg)
        assert meta.config is cfg
        assert meta.status == "pending"
        assert meta.node_count == 0

    def test_create_index_stores_metadata(self) -> None:
        mgr = EmbeddingManager()
        cfg = _make_config()
        mgr.create_index(cfg)
        stored = mgr.get_index("doc_emb")
        assert stored is not None
        assert stored.config.name == "doc_emb"

    def test_get_index(self) -> None:
        mgr = EmbeddingManager()
        cfg = _make_config(name="vessel_emb", label="Vessel")
        mgr.create_index(cfg)
        result = mgr.get_index("vessel_emb")
        assert result is not None
        assert result.config.label == "Vessel"

    def test_get_nonexistent(self) -> None:
        mgr = EmbeddingManager()
        result = mgr.get_index("nonexistent")
        assert result is None

    def test_list_indexes(self) -> None:
        mgr = EmbeddingManager()
        mgr.create_index(_make_config(name="b_idx", label="B"))
        mgr.create_index(_make_config(name="a_idx", label="A"))
        indexes = mgr.list_indexes()
        assert len(indexes) == 2
        # Sorted by name
        assert indexes[0].config.name == "a_idx"
        assert indexes[1].config.name == "b_idx"

    def test_list_indexes_empty(self) -> None:
        mgr = EmbeddingManager()
        assert mgr.list_indexes() == []

    def test_drop_index(self) -> None:
        mgr = EmbeddingManager()
        mgr.create_index(_make_config())
        result = mgr.drop_index("doc_emb")
        assert result is True
        assert mgr.get_index("doc_emb") is None

    def test_drop_nonexistent(self) -> None:
        mgr = EmbeddingManager()
        result = mgr.drop_index("ghost_index")
        assert result is False

    def test_update_status(self) -> None:
        mgr = EmbeddingManager()
        mgr.create_index(_make_config())
        updated = mgr.update_status("doc_emb", status="ready", node_count=1500)
        assert updated is not None
        assert updated.status == "ready"
        assert updated.node_count == 1500
        # Verify stored in registry
        stored = mgr.get_index("doc_emb")
        assert stored is not None
        assert stored.status == "ready"

    def test_update_status_nonexistent(self) -> None:
        mgr = EmbeddingManager()
        result = mgr.update_status("ghost", status="ready")
        assert result is None

    def test_update_status_preserves_config(self) -> None:
        mgr = EmbeddingManager()
        cfg = _make_config(name="doc_emb", label="Document")
        mgr.create_index(cfg)
        updated = mgr.update_status("doc_emb", status="building")
        assert updated is not None
        assert updated.config.label == "Document"

    def test_create_index_overwrites(self) -> None:
        mgr = EmbeddingManager()
        cfg1 = VectorIndexConfig(name="doc_emb", label="Document", property_name="emb1")
        cfg2 = VectorIndexConfig(name="doc_emb", label="Document", property_name="emb2")
        mgr.create_index(cfg1)
        mgr.create_index(cfg2)
        stored = mgr.get_index("doc_emb")
        assert stored is not None
        assert stored.config.property_name == "emb2"


# ===========================================================================
# EmbeddingManager Cypher generators
# ===========================================================================


@pytest.mark.unit
class TestEmbeddingManagerCypherGenerators:
    """EmbeddingManager Cypher DDL and query generation."""

    def test_generate_create_index_cypher(self) -> None:
        mgr = EmbeddingManager()
        cfg = _make_config(
            name="document_text_embedding",
            label="Document",
            property_name="textEmbedding",
            dimensions=768,
            similarity_function="cosine",
        )
        cypher = mgr.generate_create_index_cypher(cfg)
        assert "VECTOR INDEX" in cypher
        assert "document_text_embedding" in cypher
        assert "Document" in cypher
        assert "textEmbedding" in cypher
        assert "768" in cypher
        assert "cosine" in cypher

    def test_generate_create_index_cypher_if_not_exists(self) -> None:
        mgr = EmbeddingManager()
        cfg = _make_config()
        cypher = mgr.generate_create_index_cypher(cfg)
        assert "IF NOT EXISTS" in cypher

    def test_generate_search_cypher(self) -> None:
        mgr = EmbeddingManager()
        cypher, params = mgr.generate_search_cypher("doc_emb", top_k=5)
        assert isinstance(cypher, str)
        assert isinstance(params, dict)
        assert "queryNodes" in cypher
        assert params["indexName"] == "doc_emb"
        assert params["topK"] == 5

    def test_generate_search_cypher_default_top_k(self) -> None:
        mgr = EmbeddingManager()
        _cypher, params = mgr.generate_search_cypher("idx")
        assert params["topK"] == 10

    def test_generate_hybrid_search_cypher(self) -> None:
        mgr = EmbeddingManager()
        cypher, params = mgr.generate_hybrid_search_cypher(
            vector_index="doc_vec",
            fulltext_index="doc_text",
            top_k=10,
        )
        assert isinstance(cypher, str)
        assert isinstance(params, dict)
        # Both index types referenced in cypher
        assert "queryNodes" in cypher
        assert "queryNodes" in cypher or "fulltext" in cypher.lower()
        assert params["vectorIndex"] == "doc_vec"
        assert params["fulltextIndex"] == "doc_text"
        assert params["topK"] == 10

    def test_generate_hybrid_search_cypher_has_rrf_k(self) -> None:
        mgr = EmbeddingManager()
        _cypher, params = mgr.generate_hybrid_search_cypher("vi", "fi")
        assert "rrfK" in params
        assert isinstance(params["rrfK"], int)

    def test_generate_hybrid_search_cypher_default_top_k(self) -> None:
        mgr = EmbeddingManager()
        _cypher, params = mgr.generate_hybrid_search_cypher("vi", "fi")
        assert params["topK"] == 10

    def test_generate_search_cypher_returns_tuple(self) -> None:
        mgr = EmbeddingManager()
        result = mgr.generate_search_cypher("some_index")
        assert len(result) == 2
        assert callable(getattr(result, "__iter__", None))

    def test_generate_hybrid_search_cypher_returns_tuple(self) -> None:
        mgr = EmbeddingManager()
        result = mgr.generate_hybrid_search_cypher("vi", "fi")
        assert len(result) == 2
