"""Vector store abstraction and ChromaDB implementation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector store backends."""

    def add(
        self,
        ids: list[str],
        embeddings: list[tuple[float, ...]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None: ...

    def query(
        self,
        embedding: tuple[float, ...],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]: ...

    def delete(self, ids: list[str]) -> None: ...

    def count(self) -> int: ...

    def clear(self) -> None: ...


@dataclass(frozen=True)
class VectorSearchResult:
    """Single result from vector similarity search.

    Attributes:
        id: Unique identifier of the stored document.
        score: Similarity score in [0, 1] (higher is more similar).
        document: Raw document text.
        metadata: Arbitrary key-value pairs stored alongside the document.
    """

    id: str
    score: float
    document: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VectorStoreConfig:
    """Configuration for a vector store backend.

    Attributes:
        backend: Storage backend identifier — ``"memory"``, ``"chromadb"``, or ``"qdrant"``.
        collection_name: Name of the ChromaDB collection (ignored for memory).
        persist_directory: Filesystem path for ChromaDB persistent storage.
        distance_metric: Similarity metric — ``"cosine"``, ``"l2"``, or ``"ip"``.
    """

    backend: str = "memory"
    collection_name: str = "imsp_documents"
    persist_directory: str = ".chromadb"
    distance_metric: str = "cosine"


class InMemoryVectorStore:
    """Simple in-memory vector store using cosine similarity.

    Stores embeddings in a plain dict keyed by document id.  All computation
    uses pure Python stdlib — no numpy, no external packages.

    Example::

        store = InMemoryVectorStore()
        store.add(["id1"], [(0.1, 0.2, 0.3)], ["hello world"])
        results = store.query((0.1, 0.2, 0.3), top_k=1)
    """

    def __init__(self) -> None:
        # id -> (embedding, document, metadata)
        self._store: dict[str, tuple[tuple[float, ...], str, dict[str, Any]]] = {}

    def add(
        self,
        ids: list[str],
        embeddings: list[tuple[float, ...]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Upsert documents into the store.

        Args:
            ids: Unique identifiers, one per document.
            embeddings: Dense vectors aligned with *ids*.
            documents: Raw text strings aligned with *ids*.
            metadatas: Optional metadata dicts aligned with *ids*.
        """
        metas = metadatas or [{} for _ in ids]
        for id_, emb, doc, meta in zip(ids, embeddings, documents, metas):
            self._store[id_] = (emb, doc, meta)

    def query(
        self,
        embedding: tuple[float, ...],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Return the top-k most similar documents by cosine similarity.

        Args:
            embedding: Query vector.
            top_k: Maximum number of results to return.
            where: Optional metadata filter (key-equality only).  Items whose
                metadata does not satisfy ALL constraints are excluded.

        Returns:
            Up to *top_k* results sorted by descending similarity score.
        """
        if not self._store:
            return []

        results: list[VectorSearchResult] = []
        for id_, (emb, doc, meta) in self._store.items():
            if where and not _matches_where(meta, where):
                continue
            score = _cosine_similarity(embedding, emb)
            results.append(VectorSearchResult(id=id_, score=score, document=doc, metadata=meta))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def delete(self, ids: list[str]) -> None:
        """Remove documents by id (missing ids are silently ignored).

        Args:
            ids: Identifiers to remove.
        """
        for id_ in ids:
            self._store.pop(id_, None)

    def count(self) -> int:
        """Return the number of documents currently stored."""
        return len(self._store)

    def clear(self) -> None:
        """Remove all documents from the store."""
        self._store.clear()


class ChromaVectorStore:
    """ChromaDB-backed persistent vector store.

    Falls back transparently to :class:`InMemoryVectorStore` when
    ``chromadb`` is not installed or when the client fails to initialise,
    so the rest of the system works without the optional dependency.

    Example::

        config = VectorStoreConfig(backend="chromadb", persist_directory="/tmp/chroma")
        store = ChromaVectorStore(config)
        store.add(["id1"], [(0.1, 0.2)], ["document text"])
    """

    def __init__(self, config: VectorStoreConfig | None = None) -> None:
        self._config = config or VectorStoreConfig(backend="chromadb")
        self._client: Any = None
        self._collection: Any = None
        self._fallback: InMemoryVectorStore | None = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            import chromadb  # type: ignore[import]

            self._client = chromadb.PersistentClient(path=self._config.persist_directory)
            self._collection = self._client.get_or_create_collection(
                name=self._config.collection_name,
                metadata={"hnsw:space": self._config.distance_metric},
            )
            logger.info(
                "ChromaDB initialized: collection=%s, path=%s",
                self._config.collection_name,
                self._config.persist_directory,
            )
        except ImportError:
            logger.warning("chromadb not installed — falling back to in-memory store")
            self._fallback = InMemoryVectorStore()
        except Exception as exc:
            logger.warning("ChromaDB init failed: %s — falling back to in-memory", exc)
            self._fallback = InMemoryVectorStore()

    @property
    def _is_fallback(self) -> bool:
        return self._collection is None

    def add(
        self,
        ids: list[str],
        embeddings: list[tuple[float, ...]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Upsert documents into ChromaDB (or fallback).

        Args:
            ids: Unique identifiers aligned with *embeddings* and *documents*.
            embeddings: Dense vectors (converted to lists for ChromaDB).
            documents: Raw text strings.
            metadatas: Optional metadata dicts.
        """
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.add(ids, embeddings, documents, metadatas)

        self._collection.upsert(
            ids=ids,
            embeddings=[list(e) for e in embeddings],
            documents=documents,
            metadatas=metadatas or [{} for _ in ids],
        )

    def query(
        self,
        embedding: tuple[float, ...],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Query ChromaDB for nearest neighbours (or fallback).

        ChromaDB returns *distances* which are converted to similarity
        scores: ``score = 1 - distance`` for cosine, ``1 / (1 + distance)``
        for l2/ip metrics.

        Args:
            embedding: Query vector.
            top_k: Maximum number of results.
            where: Metadata equality filter forwarded to ChromaDB.

        Returns:
            Results sorted by descending similarity score.
        """
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.query(embedding, top_k, where)

        kwargs: dict[str, Any] = {
            "query_embeddings": [list(embedding)],
            "n_results": top_k,
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        out: list[VectorSearchResult] = []
        if results and results.get("ids"):
            ids = results["ids"][0]
            distances = results.get("distances", [[]])[0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            for i, id_ in enumerate(ids):
                distance = distances[i] if i < len(distances) else 0.0
                if self._config.distance_metric == "cosine":
                    score = max(0.0, 1.0 - distance)
                else:
                    score = 1.0 / (1.0 + distance)
                out.append(
                    VectorSearchResult(
                        id=id_,
                        score=score,
                        document=documents[i] if i < len(documents) else "",
                        metadata=metadatas[i] if i < len(metadatas) else {},
                    )
                )

        return out

    def delete(self, ids: list[str]) -> None:
        """Delete documents by id.

        Args:
            ids: Identifiers to remove.
        """
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.delete(ids)
        self._collection.delete(ids=ids)

    def count(self) -> int:
        """Return the number of documents in the collection."""
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.count()
        return self._collection.count()

    def clear(self) -> None:
        """Delete and recreate the collection (effectively empties it)."""
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.clear()
        if self._client and self._collection:
            name = self._collection.name
            meta = self._collection.metadata
            self._client.delete_collection(name)
            self._collection = self._client.get_or_create_collection(name=name, metadata=meta)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Compute cosine similarity between two vectors.

    Pure Python implementation using built-in ``sum``.  Returns 0.0 when
    either vector has zero magnitude or the lengths differ.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Cosine similarity in [-1, 1].
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _matches_where(metadata: dict[str, Any], where: dict[str, Any]) -> bool:
    """Return True when *metadata* satisfies all equality constraints in *where*.

    Args:
        metadata: Document metadata dict.
        where: Filter dict; each value must equal the corresponding metadata value.

    Returns:
        ``True`` if all constraints are satisfied, ``False`` otherwise.
    """
    return all(metadata.get(k) == v for k, v in where.items())


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def create_vector_store(config: VectorStoreConfig | None = None) -> VectorStore:
    """Create a :class:`VectorStore` backend from *config*.

    Args:
        config: Store configuration.  Defaults to
            :class:`VectorStoreConfig` (in-memory).

    Returns:
        A :class:`QdrantVectorStore` when ``config.backend == "qdrant"``,
        a :class:`ChromaVectorStore` when ``config.backend == "chromadb"``,
        otherwise an :class:`InMemoryVectorStore`.
    """
    cfg = config or VectorStoreConfig()
    if cfg.backend == "qdrant":
        from rag.engines.qdrant_store import QdrantConfig, QdrantVectorStore
        qdrant_cfg = QdrantConfig(
            collection_name=cfg.collection_name,
            distance=cfg.distance_metric,
        )
        return QdrantVectorStore(qdrant_cfg)
    if cfg.backend == "chromadb":
        return ChromaVectorStore(cfg)
    return InMemoryVectorStore()
