"""RAG evaluation framework for comparing retrieval strategies.

Compares standard RAG (vector/BM25) vs LightRAG (graph-based) approaches
using standard IR metrics: precision, recall, F1, and MRR.

Usage::

    evaluator = RAGEvaluator()
    metrics = evaluator.evaluate_batch(my_retriever, queries, top_k=5)
    comparison = evaluator.compare(
        {"standard": standard_fn, "lightrag": lightrag_fn},
        queries,
    )
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from rag.engines.models import RetrievedChunk


@dataclass(frozen=True)
class EvalQuery:
    """A test query with expected relevant chunk IDs.

    Attributes:
        query: Natural language query string.
        relevant_chunk_ids: Ground-truth set of chunk IDs that are relevant.
        category: Optional category label for grouped analysis.
    """

    query: str
    relevant_chunk_ids: frozenset[str]
    category: str = ""


@dataclass(frozen=True)
class RetrievalMetrics:
    """Metrics for a single retrieval evaluation.

    Attributes:
        precision: Fraction of retrieved chunks that are relevant.
        recall: Fraction of relevant chunks that were retrieved.
        f1: Harmonic mean of precision and recall.
        mrr: Mean Reciprocal Rank (1/rank of first relevant result).
        latency_ms: Wall-clock retrieval time in milliseconds.
        results_count: Number of chunks returned by the retriever.
    """

    precision: float
    recall: float
    f1: float
    mrr: float
    latency_ms: float
    results_count: int


# Type alias for retriever callables
RetrieverFn = Callable[[str, int], list[RetrievedChunk]]


@dataclass
class RAGEvaluator:
    """Evaluates and compares RAG retrieval strategies.

    Stateless evaluator -- all state lives in the queries and retriever
    functions passed to :meth:`evaluate_batch` and :meth:`compare`.
    """

    def evaluate_single(
        self,
        results: list[RetrievedChunk],
        relevant_ids: frozenset[str],
        latency_ms: float,
    ) -> RetrievalMetrics:
        """Compute IR metrics for a single query result.

        Args:
            results: Retrieved chunks (in ranked order).
            relevant_ids: Ground-truth relevant chunk IDs.
            latency_ms: Measured retrieval latency.

        Returns:
            Computed metrics.
        """
        retrieved_ids = [r.chunk.chunk_id for r in results]
        retrieved_set = set(retrieved_ids)

        true_positives = len(retrieved_set & relevant_ids)
        precision = true_positives / len(retrieved_set) if retrieved_set else 0.0
        recall = true_positives / len(relevant_ids) if relevant_ids else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        # Mean Reciprocal Rank: 1/rank of first relevant result
        mrr = 0.0
        for i, cid in enumerate(retrieved_ids):
            if cid in relevant_ids:
                mrr = 1.0 / (i + 1)
                break

        return RetrievalMetrics(
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            mrr=round(mrr, 4),
            latency_ms=round(latency_ms, 2),
            results_count=len(results),
        )

    def evaluate_batch(
        self,
        retriever_fn: RetrieverFn,
        queries: list[EvalQuery],
        top_k: int = 10,
    ) -> dict[str, Any]:
        """Evaluate a retriever function across multiple queries.

        Args:
            retriever_fn: Callable ``(query, top_k) -> list[RetrievedChunk]``.
            queries: Test queries with ground-truth labels.
            top_k: Number of results to request from the retriever.

        Returns:
            Aggregated metrics dictionary.
        """
        metrics_list: list[RetrievalMetrics] = []

        for eq in queries:
            start = time.perf_counter()
            results = retriever_fn(eq.query, top_k)
            latency = (time.perf_counter() - start) * 1000

            m = self.evaluate_single(results, eq.relevant_chunk_ids, latency)
            metrics_list.append(m)

        n = len(metrics_list)
        if n == 0:
            return {"error": "No queries evaluated"}

        return {
            "query_count": n,
            "avg_precision": round(sum(m.precision for m in metrics_list) / n, 4),
            "avg_recall": round(sum(m.recall for m in metrics_list) / n, 4),
            "avg_f1": round(sum(m.f1 for m in metrics_list) / n, 4),
            "avg_mrr": round(sum(m.mrr for m in metrics_list) / n, 4),
            "avg_latency_ms": round(sum(m.latency_ms for m in metrics_list) / n, 2),
            "avg_results_count": round(
                sum(m.results_count for m in metrics_list) / n, 1,
            ),
        }

    def compare(
        self,
        retrievers: dict[str, RetrieverFn],
        queries: list[EvalQuery],
        top_k: int = 10,
    ) -> dict[str, dict[str, Any]]:
        """Compare multiple retriever strategies side by side.

        Args:
            retrievers: Mapping of ``name -> retriever_fn``.
            queries: Shared test queries with ground-truth labels.
            top_k: Number of results to request from each retriever.

        Returns:
            ``{name: aggregated_metrics}`` dictionary.
        """
        results: dict[str, dict[str, Any]] = {}
        for name, retriever_fn in retrievers.items():
            results[name] = self.evaluate_batch(retriever_fn, queries, top_k)
        return results
