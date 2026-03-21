"""Domain-specific business metric helpers.

Convenience functions for recording IMSP-specific metrics from route
handlers and services. All metrics use the ``imsp_`` prefix.

Usage::

    from kg.api.middleware.business_metrics import record_kg_query

    @router.get("/query")
    async def query(text: str):
        result = run_query(text)
        record_kg_query("text2cypher", success=True)
        return result
"""
from __future__ import annotations

from kg.api.middleware.metrics import get_metrics_store


def record_kg_query(query_type: str = "cypher", *, success: bool = True) -> None:
    """Record a KG query execution.

    Args:
        query_type: Type of query (e.g. "cypher", "text2cypher", "graphrag").
        success: Whether the query succeeded.
    """
    store = get_metrics_store()
    status = "success" if success else "error"
    store.record_business_metric("imsp_kg_queries_total", {"type": query_type, "status": status})


def record_etl_processed(pipeline: str, count: int = 1) -> None:
    """Record ETL records processed.

    Args:
        pipeline: Pipeline name (e.g. "papers", "accidents").
        count: Number of records processed.
    """
    store = get_metrics_store()
    store.record_business_metric("imsp_etl_records_processed_total", {"pipeline": pipeline}, count)


def record_cypher_error(error_type: str = "syntax") -> None:
    """Record a Cypher query error.

    Args:
        error_type: Type of error (e.g. "syntax", "forbidden", "timeout").
    """
    store = get_metrics_store()
    store.record_business_metric("imsp_cypher_errors_total", {"type": error_type})
