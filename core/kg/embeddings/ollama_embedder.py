"""Ollama embedding wrapper with batch generation for Neo4j Document nodes.

Usage::

    from kg.embeddings import OllamaEmbedder, generate_embeddings_batch

    embedder = OllamaEmbedder()  # uses nomic-embed-text by default
    vector = embedder.embed_query("선박 저항 성능")  # list[float], 768-dim

    # Batch: embed all Document nodes missing textEmbedding
    from kg.config import get_driver, get_config
    results = generate_embeddings_batch(
        driver=get_driver(),
        database=get_config().neo4j.database,
        embedder=embedder,
        batch_size=50,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Dimension constants matching kg/schema/indexes.cypher line 9
NOMIC_EMBED_TEXT_DIM = 768
DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


@dataclass
class EmbeddingResult:
    """Summary of a batch embedding run.

    Attributes:
        total_processed: Number of documents where embedding was attempted.
        total_success: Number of documents successfully embedded and stored.
        total_skipped: Documents already having an embedding or with empty text.
        total_failed: Documents where embedding generation failed.
        errors: List of (doc_id, error_message) tuples for failures.
    """

    total_processed: int = 0
    total_success: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


class OllamaEmbedder:
    """Thin wrapper around neo4j_graphrag OllamaEmbeddings.

    Provides a consistent interface and factory pattern for the Maritime KG
    platform. Delegates actual embedding to the neo4j-graphrag package.

    Args:
        model: Ollama model name. Defaults to "nomic-embed-text" (768-dim).
        base_url: Ollama API base URL. Defaults to "http://localhost:11434".
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self._dimension = NOMIC_EMBED_TEXT_DIM
        self._embedder: Any = None

    @property
    def dimension(self) -> int:
        """Expected embedding vector dimension."""
        return self._dimension

    def _get_embedder(self) -> Any:
        """Lazily initialize the neo4j_graphrag OllamaEmbeddings instance."""
        if self._embedder is None:
            from neo4j_graphrag.embeddings.ollama import OllamaEmbeddings

            self._embedder = OllamaEmbeddings(
                model=self.model,
                base_url=self.base_url,
            )
        return self._embedder

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding vector for a single text string.

        Args:
            text: Input text (Korean or English).

        Returns:
            List of floats with length == self.dimension.

        Raises:
            ConnectionError: If Ollama is not running.
            ValueError: If returned vector dimension mismatches.
        """
        embedder = self._get_embedder()
        vector = embedder.embed_query(text)
        if len(vector) != self._dimension:
            raise ValueError(
                f"Expected {self._dimension}-dim vector, got {len(vector)}"
            )
        return vector

    def get_neo4j_graphrag_embedder(self) -> Any:
        """Return the underlying neo4j_graphrag Embedder for retriever use.

        This is needed because VectorRetriever/HybridRetriever accept
        an Embedder instance from neo4j_graphrag.embeddings, not our wrapper.
        """
        return self._get_embedder()


def generate_embeddings_batch(
    driver: Any,
    database: str,
    embedder: OllamaEmbedder,
    *,
    batch_size: int = 50,
    property_name: str = "textEmbedding",
    text_fields: tuple[str, ...] = ("title", "content"),
    min_text_length: int = 20,
) -> EmbeddingResult:
    """Batch-generate embeddings for Document nodes missing the embedding property.

    Queries all Document nodes where the specified property is NULL,
    generates embeddings via the given embedder, and writes them back
    using UNWIND for efficient batch writes.

    Args:
        driver: Neo4j driver instance (from kg.config.get_driver()).
        database: Neo4j database name (from kg.config.get_config().neo4j.database).
        embedder: OllamaEmbedder instance.
        batch_size: Number of documents to process per transaction.
        property_name: Neo4j property to store the embedding vector.
        text_fields: Tuple of Document properties to concatenate for embedding.
        min_text_length: Minimum text length to generate embedding (skip shorter).

    Returns:
        EmbeddingResult summarizing the batch run.
    """
    result = EmbeddingResult()

    # Phase 1: fetch all docs needing embeddings
    field_returns = ", ".join(f"d.{f} AS {f}" for f in text_fields)
    fetch_query = (
        f"MATCH (d:Document) WHERE d.{property_name} IS NULL "
        f"RETURN d.docId AS docId, {field_returns}"
    )

    with driver.session(database=database) as session:
        records = session.run(fetch_query).data()

    logger.info("Found %d documents needing embeddings", len(records))

    # Phase 2: generate and store in batches
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        updates: list[dict[str, Any]] = []

        for rec in batch:
            doc_id = rec["docId"]
            text_parts = [str(rec.get(f) or "") for f in text_fields]
            text = " ".join(part for part in text_parts if part.strip())

            if len(text.strip()) < min_text_length:
                result.total_skipped += 1
                logger.debug("Skipped %s: text too short (%d chars)", doc_id, len(text))
                continue

            result.total_processed += 1

            try:
                vector = embedder.embed_query(text)
                updates.append({"id": doc_id, "emb": vector})
                result.total_success += 1
            except Exception as exc:
                result.total_failed += 1
                result.errors.append((doc_id, str(exc)))
                logger.warning("Embedding failed for %s: %s", doc_id, exc)

        # Write batch to Neo4j using UNWIND for efficiency
        if updates:
            write_query = (
                "UNWIND $updates AS u "
                f"MATCH (d:Document {{docId: u.id}}) "
                f"SET d.{property_name} = u.emb"
            )
            with driver.session(database=database) as session:
                session.run(write_query, {"updates": updates})
            logger.debug("Wrote %d embeddings to Neo4j", len(updates))

    logger.info(
        "Embedding batch complete: %d processed, %d success, %d skipped, %d failed",
        result.total_processed,
        result.total_success,
        result.total_skipped,
        result.total_failed,
    )
    return result
