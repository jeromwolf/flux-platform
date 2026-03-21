"""EmbeddingManager: registry and Cypher generator for Neo4j vector indexes.

Maintains an in-memory registry of VectorIndexConfig objects and generates
the Cypher DDL and query strings needed to create and query those indexes
in Neo4j 5.x.

Example::

    from kg.embeddings import EmbeddingManager, VectorIndexConfig

    manager = EmbeddingManager()
    config = VectorIndexConfig(
        name="document_text_embedding",
        label="Document",
        property_name="textEmbedding",
        dimensions=768,
        similarity_function="cosine",
    )
    meta = manager.create_index(config)
    cypher = manager.generate_create_index_cypher(config)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from kg.embeddings.models import HybridSearchResult, IndexMetadata, VectorIndexConfig

logger = logging.getLogger(__name__)

# Reciprocal Rank Fusion constant (standard default)
_RRF_K: int = 60


class EmbeddingManager:
    """In-memory registry and Cypher generator for Neo4j vector indexes.

    Tracks :class:`~kg.embeddings.models.IndexMetadata` objects keyed by
    index name. Does **not** connect to Neo4j directly — callers are
    responsible for executing the generated Cypher strings against a driver.

    Example::

        manager = EmbeddingManager()
        config = VectorIndexConfig("doc_emb", "Document", "textEmbedding")
        manager.create_index(config)
        cypher = manager.generate_create_index_cypher(config)
        # driver.session().run(cypher)
    """

    def __init__(self) -> None:
        self._indexes: dict[str, IndexMetadata] = {}

    # ------------------------------------------------------------------
    # Registry operations
    # ------------------------------------------------------------------

    def create_index(self, config: VectorIndexConfig) -> IndexMetadata:
        """Register a new vector index configuration.

        If an index with the same name already exists it is silently replaced.

        Args:
            config: The VectorIndexConfig to register.

        Returns:
            A new IndexMetadata in "pending" status for the given config.
        """
        now = datetime.now(tz=timezone.utc).isoformat()
        meta = IndexMetadata(
            config=config,
            node_count=0,
            created_at=now,
            status="pending",
        )
        self._indexes[config.name] = meta
        logger.debug(
            "Registered vector index: name=%s label=%s property=%s dims=%d",
            config.name,
            config.label,
            config.property_name,
            config.dimensions,
        )
        return meta

    def get_index(self, name: str) -> IndexMetadata | None:
        """Retrieve index metadata by name.

        Args:
            name: The index name as registered via :meth:`create_index`.

        Returns:
            The matching IndexMetadata, or ``None`` if not found.
        """
        return self._indexes.get(name)

    def list_indexes(self) -> list[IndexMetadata]:
        """Return all registered index metadata objects sorted by name.

        Returns:
            Sorted list of IndexMetadata.
        """
        return sorted(self._indexes.values(), key=lambda m: m.config.name)

    def drop_index(self, name: str) -> bool:
        """Remove an index from the registry.

        This does not execute ``DROP INDEX`` against Neo4j — callers must
        do that separately if needed.

        Args:
            name: The index name to remove.

        Returns:
            ``True`` if the index existed and was removed, ``False`` otherwise.
        """
        if name in self._indexes:
            del self._indexes[name]
            logger.debug("Dropped index from registry: name=%s", name)
            return True
        return False

    def update_status(
        self,
        name: str,
        status: str,
        node_count: int = 0,
    ) -> IndexMetadata | None:
        """Update the status and optionally the node_count for a registered index.

        Because IndexMetadata is frozen, a replacement object is created.

        Args:
            name: The index name to update.
            status: New lifecycle status — one of "pending", "building",
                "ready", "error".
            node_count: Updated count of indexed nodes. Defaults to 0 (no change).

        Returns:
            The updated IndexMetadata, or ``None`` if ``name`` is not registered.
        """
        existing = self._indexes.get(name)
        if existing is None:
            logger.warning("update_status: index not found — name=%s", name)
            return None

        updated = IndexMetadata(
            config=existing.config,
            node_count=node_count if node_count else existing.node_count,
            created_at=existing.created_at,
            status=status,
        )
        self._indexes[name] = updated
        logger.debug("Updated index status: name=%s status=%s nodes=%d", name, status, updated.node_count)
        return updated

    # ------------------------------------------------------------------
    # Cypher generators
    # ------------------------------------------------------------------

    def generate_create_index_cypher(self, config: VectorIndexConfig) -> str:
        """Generate the Cypher DDL statement to create a Neo4j vector index.

        The generated statement uses ``IF NOT EXISTS`` to be idempotent.

        Args:
            config: The VectorIndexConfig describing the index to create.

        Returns:
            A Cypher string that can be executed directly against a Neo4j session.

        Example::

            cypher = manager.generate_create_index_cypher(config)
            # CREATE VECTOR INDEX document_text_embedding IF NOT EXISTS
            #   FOR (n:Document) ON (n.textEmbedding)
            #   OPTIONS {indexConfig: {`vector.dimensions`: 768,
            #            `vector.similarity_function`: 'cosine'}}
        """
        return (
            f"CREATE VECTOR INDEX {config.name} IF NOT EXISTS "
            f"FOR (n:{config.label}) ON (n.{config.property_name}) "
            f"OPTIONS {{indexConfig: {{`vector.dimensions`: {config.dimensions}, "
            f"`vector.similarity_function`: '{config.similarity_function}'}}}}"
        )

    def generate_search_cypher(
        self,
        index_name: str,
        top_k: int = 10,
    ) -> tuple[str, dict[str, object]]:
        """Generate a parametrised Cypher statement for vector index search.

        The caller must supply ``queryVector`` (list[float]) and may override
        ``indexName`` and ``topK`` in the returned parameters dict.

        Args:
            index_name: The name of the vector index to query.
            top_k: Maximum number of results to return.

        Returns:
            A (cypher_string, parameters) tuple.  ``parameters`` pre-populates
            ``$indexName`` and ``$topK``; the caller must add ``$queryVector``.

        Example::

            cypher, params = manager.generate_search_cypher("doc_emb", top_k=5)
            params["queryVector"] = embedder.embed_query("선박 성능")
            session.run(cypher, params)
        """
        cypher = (
            "CALL db.index.vector.queryNodes($indexName, $topK, $queryVector) "
            "YIELD node, score "
            "RETURN node, score"
        )
        params: dict[str, object] = {
            "indexName": index_name,
            "topK": top_k,
        }
        return cypher, params

    def generate_hybrid_search_cypher(
        self,
        vector_index: str,
        fulltext_index: str,
        top_k: int = 10,
    ) -> tuple[str, dict[str, object]]:
        """Generate a Cypher statement for hybrid vector + full-text search with RRF.

        Uses Reciprocal Rank Fusion (RRF, k=60) to merge results from a Neo4j
        vector index and a full-text index.  The caller must supply:
        - ``$queryVector`` (list[float])
        - ``$queryText`` (str)

        Args:
            vector_index: Name of the Neo4j vector index.
            fulltext_index: Name of the Neo4j full-text index.
            top_k: Maximum number of fused results to return.

        Returns:
            A (cypher_string, parameters) tuple. ``parameters`` pre-populates
            ``$vectorIndex``, ``$fulltextIndex``, ``$topK``, and ``$rrfK``.

        Example::

            cypher, params = manager.generate_hybrid_search_cypher(
                "doc_emb", "doc_fulltext", top_k=10
            )
            params["queryVector"] = embedder.embed_query(query)
            params["queryText"] = query
            session.run(cypher, params)
        """
        cypher = (
            # Vector search branch
            "CALL db.index.vector.queryNodes($vectorIndex, $topK, $queryVector) "
            "YIELD node AS vNode, score AS vScore "
            "WITH collect({node: vNode, score: vScore}) AS vectorResults "
            # Full-text search branch
            "CALL db.index.fulltext.queryNodes($fulltextIndex, $queryText) "
            "YIELD node AS tNode, score AS tScore "
            "WITH vectorResults, collect({node: tNode, score: tScore}) AS textResults "
            # RRF fusion
            "WITH [r IN vectorResults | {node: r.node, vRank: r.score}] AS vr, "
            "     [r IN textResults  | {node: r.node, tRank: r.score}] AS tr "
            "UNWIND vr AS vItem "
            "WITH vItem, tr, $rrfK AS k "
            "OPTIONAL MATCH (n) WHERE n = vItem.node "
            "WITH n, "
            "     1.0 / (k + vItem.vRank) AS vScore, "
            "     coalesce(([ t IN tr WHERE t.node = n | 1.0 / (k + t.tRank) ][0]), 0.0) AS tScore "
            "WITH n, vScore, tScore, vScore + tScore AS combinedScore "
            "ORDER BY combinedScore DESC "
            "LIMIT $topK "
            "RETURN n AS node, combinedScore AS score, vScore AS vectorScore, tScore AS textScore"
        )
        params: dict[str, object] = {
            "vectorIndex": vector_index,
            "fulltextIndex": fulltext_index,
            "topK": top_k,
            "rrfK": _RRF_K,
        }
        return cypher, params
