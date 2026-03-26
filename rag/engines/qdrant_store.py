"""Qdrant vector store backend with graceful fallback.

Provides :class:`QdrantVectorStore` -- a :class:`~rag.engines.vector_store.VectorStore`
implementation backed by `qdrant-client <https://github.com/qdrant/qdrant-client>`_.

When ``qdrant-client`` is not installed the store falls back transparently to
:class:`~rag.engines.vector_store.InMemoryVectorStore`, keeping the rest of
the pipeline functional without the optional dependency.
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from rag.engines.vector_store import InMemoryVectorStore, VectorSearchResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QdrantConfig:
    """Connection and collection settings for Qdrant.

    Attributes:
        host: Qdrant server hostname.
        port: Qdrant HTTP/REST port.
        grpc_port: Qdrant gRPC port.
        api_key: Optional API key for Qdrant Cloud.
        collection_name: Target collection name.
        distance: Distance metric -- ``"cosine"``, ``"euclid"``, or ``"dot"``.
        dimension: Embedding vector dimensionality.
        prefer_grpc: Prefer gRPC transport over REST.
        timeout: Client timeout in seconds.
    """

    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    api_key: str = ""
    collection_name: str = "imsp_documents"
    distance: str = "cosine"  # cosine | euclid | dot
    dimension: int = 768
    prefer_grpc: bool = True
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> QdrantConfig:
        """Create config from ``QDRANT_*`` environment variables.

        Returns:
            A :class:`QdrantConfig` populated from the environment, with
            sensible defaults for any unset variables.
        """
        return cls(
            host=os.environ.get("QDRANT_HOST", "localhost"),
            port=int(os.environ.get("QDRANT_PORT", "6333")),
            grpc_port=int(os.environ.get("QDRANT_GRPC_PORT", "6334")),
            api_key=os.environ.get("QDRANT_API_KEY", ""),
            collection_name=os.environ.get("QDRANT_COLLECTION", "imsp_documents"),
        )


# ---------------------------------------------------------------------------
# Connection pool (singleton)
# ---------------------------------------------------------------------------


class QdrantPool:
    """Thread-safe singleton connection manager for Qdrant.

    Follows the same singleton pattern as ``core.kg.db.connection``
    (``get_pg_pool`` / ``close_pg_pool`` / ``reset_pg_pool``), but
    implemented as a class with :meth:`get_instance`.

    Example::

        pool = QdrantPool.get_instance(config)
        pool.client.get_collections()
    """

    _instance: ClassVar[QdrantPool | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, config: QdrantConfig) -> None:
        self._config = config
        self._client: Any = None

    @classmethod
    def get_instance(cls, config: QdrantConfig | None = None) -> QdrantPool:
        """Return the singleton pool, creating it on first call.

        Args:
            config: Qdrant configuration.  Required on the very first call;
                ignored on subsequent calls (the existing instance is
                returned).

        Returns:
            The singleton :class:`QdrantPool` instance.

        Raises:
            ValueError: If *config* is ``None`` on the first call.
        """
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            # Double-checked locking
            if cls._instance is not None:
                return cls._instance

            if config is None:
                raise ValueError(
                    "QdrantPool.get_instance() requires config on first call"
                )

            cls._instance = cls(config)
            return cls._instance

    @property
    def client(self) -> Any:
        """Lazy-initialise and return the ``QdrantClient``.

        Returns:
            A ``qdrant_client.QdrantClient`` instance.

        Raises:
            ConnectionError: If the client cannot be created.
        """
        if self._client is None:
            try:
                from qdrant_client import QdrantClient  # type: ignore[import]

                self._client = QdrantClient(
                    host=self._config.host,
                    port=self._config.port,
                    grpc_port=self._config.grpc_port,
                    api_key=self._config.api_key or None,
                    prefer_grpc=self._config.prefer_grpc,
                    timeout=self._config.timeout,
                )
            except Exception as exc:
                raise ConnectionError(
                    f"Failed to create QdrantClient: {exc}"
                ) from exc
        return self._client

    def close(self) -> None:
        """Close the underlying client connection.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
            logger.info("Qdrant client closed")

    @classmethod
    def reset(cls) -> None:
        """Destroy the singleton (for testing).

        Closes the underlying client before discarding the instance.
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deterministic_uuid(string_id: str) -> str:
    """Produce a deterministic UUID-5 from a string identifier.

    Uses ``uuid.uuid5`` with ``uuid.NAMESPACE_DNS`` so the same input
    always produces the same UUID.

    Args:
        string_id: Arbitrary string identifier.

    Returns:
        UUID string representation.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, string_id))


def _normalize_score(raw_score: float, distance: str) -> float:
    """Normalise a Qdrant similarity / distance score to [0, 1].

    For *cosine* distance Qdrant returns similarity in [-1, 1]; we map to
    ``(raw + 1) / 2``.  For *euclid* we use ``1 / (1 + raw)``.  For *dot*
    the score is already a similarity; we clamp to [0, 1].

    Args:
        raw_score: Raw score returned by Qdrant.
        distance: Distance metric name (``cosine``, ``euclid``, or ``dot``).

    Returns:
        Normalised score in [0, 1].
    """
    if distance == "cosine":
        return max(0.0, min(1.0, (raw_score + 1.0) / 2.0))
    if distance == "euclid":
        return 1.0 / (1.0 + abs(raw_score))
    # dot -- clamp to [0, 1]
    return max(0.0, min(1.0, raw_score))


# ---------------------------------------------------------------------------
# QdrantVectorStore
# ---------------------------------------------------------------------------


class QdrantVectorStore:
    """Qdrant-backed vector store with in-memory fallback.

    Implements the :class:`~rag.engines.vector_store.VectorStore` protocol.
    Falls back transparently to :class:`InMemoryVectorStore` when
    ``qdrant-client`` is not installed or when the server is unreachable,
    so the rest of the system works without the optional dependency.

    Example::

        cfg = QdrantConfig(host="qdrant-server", dimension=384)
        store = QdrantVectorStore(cfg)
        store.add(["id1"], [(0.1, 0.2, 0.3)], ["text"])
        results = store.query((0.1, 0.2, 0.3), top_k=5)
    """

    def __init__(self, config: QdrantConfig | None = None) -> None:
        self._config = config or QdrantConfig()
        self._pool: QdrantPool | None = None
        self._fallback: InMemoryVectorStore | None = None
        self._init_client()

    def _init_client(self) -> None:
        """Attempt to connect to Qdrant; fall back to in-memory on failure."""
        try:
            from qdrant_client import QdrantClient  # noqa: F401

            self._pool = QdrantPool.get_instance(self._config)
            # Force connection to verify server is reachable
            _ = self._pool.client
            self._ensure_collection()
            logger.info(
                "Qdrant initialized: collection=%s, host=%s:%s",
                self._config.collection_name,
                self._config.host,
                self._config.port,
            )
        except ImportError:
            logger.warning(
                "qdrant-client not installed -- falling back to in-memory store"
            )
            self._fallback = InMemoryVectorStore()
        except Exception as exc:
            logger.warning(
                "Qdrant init failed: %s -- falling back to in-memory", exc
            )
            self._fallback = InMemoryVectorStore()

    def _ensure_collection(self) -> None:
        """Create the collection if it does not already exist.

        Maps the configured distance string to the appropriate Qdrant
        ``Distance`` enum value and creates a payload index on the
        ``_id`` field for fast lookups.
        """
        from qdrant_client.models import (  # type: ignore[import]
            Distance,
            PayloadSchemaType,
            VectorParams,
        )

        assert self._pool is not None
        client = self._pool.client

        distance_map = {
            "cosine": Distance.COSINE,
            "euclid": Distance.EUCLID,
            "dot": Distance.DOT,
        }
        qdrant_distance = distance_map.get(
            self._config.distance, Distance.COSINE
        )

        try:
            client.get_collection(
                collection_name=self._config.collection_name,
            )
            logger.debug(
                "Collection '%s' already exists", self._config.collection_name
            )
        except Exception:
            # Collection does not exist -- create it
            client.create_collection(
                collection_name=self._config.collection_name,
                vectors_config=VectorParams(
                    size=self._config.dimension,
                    distance=qdrant_distance,
                ),
            )
            logger.info(
                "Created Qdrant collection '%s' (dim=%d, distance=%s)",
                self._config.collection_name,
                self._config.dimension,
                self._config.distance,
            )

        # Ensure payload index on _id for fast filtering
        try:
            client.create_payload_index(
                collection_name=self._config.collection_name,
                field_name="_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:  # noqa: BLE001
            # Index may already exist
            pass

    # -- properties ----------------------------------------------------------

    @property
    def _is_fallback(self) -> bool:
        """Return ``True`` when operating in in-memory fallback mode."""
        return self._pool is None

    # -- public API (VectorStore protocol) -----------------------------------

    def add(
        self,
        ids: list[str],
        embeddings: list[tuple[float, ...]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Upsert documents into Qdrant (or fallback).

        String IDs are converted to deterministic UUIDs via
        ``uuid.uuid5(NAMESPACE_DNS, id)``.  The original string ID is
        preserved in the payload under ``_id``.

        Args:
            ids: Unique identifiers aligned with *embeddings* and *documents*.
            embeddings: Dense vectors.
            documents: Raw text strings.
            metadatas: Optional metadata dicts.
        """
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.add(ids, embeddings, documents, metadatas)

        from qdrant_client.models import PointStruct  # type: ignore[import]

        assert self._pool is not None
        metas = metadatas or [{} for _ in ids]
        points = [
            PointStruct(
                id=_deterministic_uuid(id_),
                vector=list(emb),
                payload={
                    "_id": id_,
                    "document": doc,
                    "metadata": meta,
                },
            )
            for id_, emb, doc, meta in zip(ids, embeddings, documents, metas)
        ]

        self._pool.client.upsert(
            collection_name=self._config.collection_name,
            points=points,
        )

    def query(
        self,
        embedding: tuple[float, ...],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Return the *top_k* most similar documents.

        Qdrant returns cosine similarity in ``[-1, 1]``.  Scores are
        normalised to ``[0, 1]`` via ``(score + 1) / 2``.

        Args:
            embedding: Query vector.
            top_k: Maximum number of results.
            where: Optional metadata equality filter.  Keys are looked up
                inside the nested ``metadata`` payload field.

        Returns:
            Results sorted by descending normalised score.
        """
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.query(embedding, top_k, where)

        assert self._pool is not None

        kwargs: dict[str, Any] = {
            "collection_name": self._config.collection_name,
            "query": list(embedding),
            "limit": top_k,
        }

        if where:
            kwargs["query_filter"] = self._build_filter(where)

        results = self._pool.client.query_points(**kwargs)

        out: list[VectorSearchResult] = []
        for point in results.points:
            payload = point.payload or {}
            raw_score: float = point.score if point.score is not None else 0.0
            score = _normalize_score(raw_score, self._config.distance)

            out.append(
                VectorSearchResult(
                    id=payload.get("_id", str(point.id)),
                    score=score,
                    document=payload.get("document", ""),
                    metadata=payload.get("metadata", {}),
                )
            )

        out.sort(key=lambda r: r.score, reverse=True)
        return out

    def delete(self, ids: list[str]) -> None:
        """Delete documents by their original string ids.

        Args:
            ids: String identifiers to remove (converted to UUIDs internally).
        """
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.delete(ids)

        from qdrant_client.models import PointIdsList  # type: ignore[import]

        assert self._pool is not None
        self._pool.client.delete(
            collection_name=self._config.collection_name,
            points_selector=PointIdsList(
                points=[_deterministic_uuid(id_) for id_ in ids],
            ),
        )

    def count(self) -> int:
        """Return the number of documents in the collection."""
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.count()

        assert self._pool is not None
        result = self._pool.client.count(
            collection_name=self._config.collection_name,
        )
        return result.count

    def clear(self) -> None:
        """Delete and recreate the collection (effectively empties it)."""
        if self._is_fallback:
            assert self._fallback is not None
            return self._fallback.clear()

        assert self._pool is not None
        self._pool.client.delete_collection(
            collection_name=self._config.collection_name,
        )
        self._ensure_collection()

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _build_filter(where: dict[str, Any]) -> Any:
        """Translate a simple ``{key: value}`` dict to a Qdrant ``Filter``.

        Filter conditions target the nested ``metadata`` payload field
        (e.g. ``metadata.key``).

        Args:
            where: Equality filter dict.

        Returns:
            A ``qdrant_client.models.Filter`` instance.
        """
        from qdrant_client.models import (  # type: ignore[import]
            FieldCondition,
            Filter,
            MatchValue,
        )

        conditions = [
            FieldCondition(
                key=f"metadata.{key}",
                match=MatchValue(value=value),
            )
            for key, value in where.items()
        ]
        return Filter(must=conditions)
