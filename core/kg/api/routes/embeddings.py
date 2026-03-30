"""Embedding vector search endpoints.

Provides REST API routes for vector similarity search, hybrid search,
and vector index management backed by Neo4j vector indexes.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from kg.api.deps import get_async_neo4j_session, get_project_context
from kg.api.models import (
    CreateIndexRequest,
    EmbeddingSearchRequest,
    EmbeddingSearchResponse,
    HybridSearchRequest,
)
from kg.embeddings.manager import EmbeddingManager
from kg.embeddings.models import VectorIndexConfig
from kg.project import KGProjectContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

# Module-level EmbeddingManager instance (shared across requests)
_embedding_manager = EmbeddingManager()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/search", response_model=EmbeddingSearchResponse)
async def vector_search(
    body: EmbeddingSearchRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> EmbeddingSearchResponse:
    """Run a vector similarity search against a Neo4j vector index.

    Generates the GDS vector search Cypher via :class:`EmbeddingManager`,
    then executes it against Neo4j and returns the top-K ranked results.

    Args:
        body: Search parameters including label, property, query vector, and topK.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        EmbeddingSearchResponse with matched nodes and metadata.

    Raises:
        HTTPException: 400 if the label is not a valid identifier.
        HTTPException: 500 if query execution fails.
    """
    if not body.label.isidentifier():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid label '{body.label}': must be a valid identifier",
        )

    # Derive index name from label + property (convention)
    index_name = f"{body.label.lower()}_{body.property}_index"

    cypher, params = _embedding_manager.generate_search_cypher(
        index_name=index_name,
        top_k=body.topK,
    )
    params["queryVector"] = body.queryVector
    # NOTE: Vector search currently spans all projects.
    # Per-project vector indexes will be added in Phase 2.
    params["__kg_project_label"] = project.label
    params["__kg_project_name"] = project.property_value

    try:
        result = await session.run(cypher, params)
        records = [record async for record in result]
    except Exception as exc:
        logger.exception("Vector search failed: index=%s", index_name)
        raise HTTPException(status_code=500, detail=f"Vector search failed: {exc}") from exc

    results: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {}
        if hasattr(record, "keys"):
            for key in record.keys():
                val = record[key]
                if hasattr(val, "element_id"):
                    # Neo4j node — serialize properties
                    row[key] = {
                        "id": val.element_id,
                        "labels": list(val.labels) if hasattr(val, "labels") else [],
                        "properties": dict(val),
                    }
                else:
                    row[key] = val
        results.append(row)

    return EmbeddingSearchResponse(
        results=results,
        meta={
            "algorithm": "cosine",
            "topK": body.topK,
            "indexName": index_name,
            "label": body.label,
            "property": body.property,
        },
    )


@router.post("/hybrid", response_model=EmbeddingSearchResponse)
async def hybrid_search(
    body: HybridSearchRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> EmbeddingSearchResponse:
    """Run a hybrid vector + full-text search with Reciprocal Rank Fusion.

    Combines a Neo4j vector index search with a full-text index search
    and merges results using RRF (k=60) for improved relevance.

    Args:
        body: Hybrid search parameters including query vector, text query, and topK.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        EmbeddingSearchResponse with fused ranked results and metadata.

    Raises:
        HTTPException: 400 if the label is not a valid identifier.
        HTTPException: 500 if query execution fails.
    """
    if not body.label.isidentifier():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid label '{body.label}': must be a valid identifier",
        )

    # Derive index names from label + property (convention)
    vector_index = f"{body.label.lower()}_{body.property}_index"
    from kg.fulltext import get_fulltext_index
    fulltext_index = get_fulltext_index(body.label) or f"{body.label.lower()}_search"

    cypher, params = _embedding_manager.generate_hybrid_search_cypher(
        vector_index=vector_index,
        fulltext_index=fulltext_index,
        top_k=body.topK,
    )
    params["queryVector"] = body.queryVector
    params["queryText"] = body.textQuery
    # NOTE: Vector search currently spans all projects.
    # Per-project vector indexes will be added in Phase 2.
    params["__kg_project_label"] = project.label
    params["__kg_project_name"] = project.property_value

    try:
        result = await session.run(cypher, params)
        records = [record async for record in result]
    except Exception as exc:
        logger.exception("Hybrid search failed: vector=%s fulltext=%s", vector_index, fulltext_index)
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {exc}") from exc

    results: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {}
        if hasattr(record, "keys"):
            for key in record.keys():
                val = record[key]
                if hasattr(val, "element_id"):
                    row[key] = {
                        "id": val.element_id,
                        "labels": list(val.labels) if hasattr(val, "labels") else [],
                        "properties": dict(val),
                    }
                else:
                    row[key] = val
        results.append(row)

    return EmbeddingSearchResponse(
        results=results,
        meta={
            "fusion": "rrf",
            "topK": body.topK,
            "vectorIndex": vector_index,
            "fulltextIndex": fulltext_index,
            "label": body.label,
            "property": body.property,
            "textQuery": body.textQuery,
        },
    )


@router.get("/indexes")
async def list_indexes() -> dict[str, Any]:
    """List all registered vector indexes.

    Returns the in-memory registry of vector index configurations
    tracked by the EmbeddingManager.

    Returns:
        Dict with ``indexes`` list containing serialized IndexMetadata objects.
    """
    indexes = _embedding_manager.list_indexes()
    serialized = []
    for meta in indexes:
        serialized.append(
            {
                "name": meta.config.name,
                "label": meta.config.label,
                "property": meta.config.property_name,
                "dimensions": meta.config.dimensions,
                "similarityFunction": meta.config.similarity_function,
                "status": meta.status,
                "nodeCount": meta.node_count,
                "createdAt": meta.created_at,
            }
        )
    return {"indexes": serialized}


@router.post("/indexes", status_code=201)
async def create_index(
    body: CreateIndexRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> dict[str, Any]:
    """Create a Neo4j vector index for a node label and property.

    Registers the index configuration in the EmbeddingManager and
    generates + executes the DDL Cypher against Neo4j.

    Args:
        body: Index configuration including label, property, dimensions, and similarity.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        Dict with ``created`` flag and the generated ``cypher`` string.

    Raises:
        HTTPException: 400 if label is not a valid identifier.
        HTTPException: 500 if index creation fails.
    """
    if not body.label.isidentifier():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid label '{body.label}': must be a valid identifier",
        )

    index_name = f"{body.label.lower()}_{body.property}_index"

    config = VectorIndexConfig(
        name=index_name,
        label=body.label,
        property_name=body.property,
        dimensions=body.dimensions,
        similarity_function=body.similarity,
    )

    # Register in manager
    _embedding_manager.create_index(config)

    # Generate and execute DDL
    cypher = _embedding_manager.generate_create_index_cypher(config)
    try:
        await session.run(cypher)
    except Exception as exc:
        logger.exception("Failed to create vector index: %s", index_name)
        raise HTTPException(
            status_code=500,
            detail=f"Vector index creation failed: {exc}",
        ) from exc

    logger.info("Created vector index: %s on %s.%s", index_name, body.label, body.property)

    return {
        "created": True,
        "indexName": index_name,
        "cypher": cypher,
        "label": body.label,
        "property": body.property,
        "dimensions": body.dimensions,
        "similarity": body.similarity,
    }
