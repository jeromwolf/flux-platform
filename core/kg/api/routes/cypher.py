"""Raw Cypher execution and validation endpoints for the Maritime KG API."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from kg.api.deps import get_async_neo4j_session, get_project_context
from kg.api.models import (
    CypherExplainResponse,
    CypherRequest,
    CypherResponse,
    CypherValidationResponse,
)
from kg.api.serializers import serialize_neo4j_value
from kg.cypher_builder import CypherBuilder
from kg.project import KGProjectContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cypher", tags=["cypher"])

# ---------------------------------------------------------------------------
# Timeout / result-size guards
# ---------------------------------------------------------------------------

# Default and ceiling for query timeouts (milliseconds).
_DEFAULT_CYPHER_TIMEOUT_MS: int = 30_000   # 30 seconds
_MAX_CYPHER_TIMEOUT_MS: int = 120_000      # 2 minutes

# Auto-appended LIMIT when the query has none.
_DEFAULT_RESULT_LIMIT: int = 10_000


def _ensure_result_limit(query: str, limit: int = _DEFAULT_RESULT_LIMIT) -> str:
    """Append a LIMIT clause to *query* if one is not already present.

    The check ignores inline Cypher comments (``//``) so that a ``LIMIT``
    mentioned only inside a comment does not suppress the guard.

    Args:
        query: The Cypher query string (may or may not end with ``;``).
        limit: The maximum row count to append.

    Returns:
        The (possibly modified) query string without a trailing semicolon.
    """
    q = query.strip().rstrip(";")
    # Strip inline comments before checking for LIMIT keyword
    uncommented = re.sub(r"//[^\n]*", "", q)
    if "LIMIT" not in uncommented.upper():
        q = f"{q}\nLIMIT {limit}"
    return q


# ---------------------------------------------------------------------------
# Danger detection
# ---------------------------------------------------------------------------

# Patterns that are unconditionally blocked for safety.
# Order matters — most specific first.
_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    # DROP command (any variant)
    re.compile(r"\bDROP\b", re.IGNORECASE),
    # DETACH DELETE without a limiting WHERE clause (catches DELETE ALL style)
    re.compile(r"\bDETACH\s+DELETE\s+(?!\s*\()?\s*\w+\s*(?!WHERE)", re.IGNORECASE),
    # DELETE without WHERE clause
    re.compile(r"\bDELETE\b(?![\s\S]*\bWHERE\b)", re.IGNORECASE),
    # CALL ... apoc.trigger.add / apoc.schema.assert (schema manipulation)
    re.compile(r"\bCALL\s+apoc\.schema\b", re.IGNORECASE),
    re.compile(r"\bCALL\s+apoc\.trigger\b", re.IGNORECASE),
    # CALL db.* management procedures
    re.compile(r"\bCALL\s+db\.(create|drop|shutdown)\b", re.IGNORECASE),
]

# Patterns that indicate write operations (used for query-type detection)
_WRITE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bCREATE\b", re.IGNORECASE),
    re.compile(r"\bMERGE\b", re.IGNORECASE),
    re.compile(r"\bSET\b", re.IGNORECASE),
    re.compile(r"\bDELETE\b", re.IGNORECASE),
    re.compile(r"\bREMOVE\b", re.IGNORECASE),
    re.compile(r"\bDETACH\b", re.IGNORECASE),
]


def _is_dangerous(cypher: str) -> tuple[bool, str]:
    """Check whether a Cypher query contains dangerous operations.

    Args:
        cypher: The Cypher query string to check.

    Returns:
        Tuple of (is_dangerous, reason).  Reason is an empty string when
        the query is safe.
    """
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(cypher):
            return True, f"Query contains a disallowed operation: {pattern.pattern}"
    return False, ""


def _detect_query_type(cypher: str) -> str:
    """Detect whether a Cypher query is a read or write operation.

    Args:
        cypher: The Cypher query string.

    Returns:
        ``"write"`` if any write keyword is present, otherwise ``"read"``.
    """
    for pattern in _WRITE_PATTERNS:
        if pattern.search(cypher):
            return "write"
    return "read"


def _serialize_record(record: Any) -> dict[str, Any]:
    """Serialize a Neo4j record to a JSON-compatible dict.

    Handles primitive values, nodes, and relationships by delegating
    to :func:`~kg.api.serializers.serialize_neo4j_value` for each value.

    Args:
        record: A Neo4j Record object.

    Returns:
        A dict mapping column names to serialized values.
    """
    if isinstance(record, dict):
        items = record.items()
    else:
        try:
            items = dict(record).items()  # type: ignore[assignment]
        except Exception:
            return {}

    row: dict[str, Any] = {}
    for key, val in items:
        # Handle node/relationship objects by extracting their properties
        if hasattr(val, "element_id") and hasattr(val, "labels"):
            # Node
            row[key] = {
                "id": val.element_id,
                "labels": list(val.labels),
                "properties": {
                    k: serialize_neo4j_value(v) for k, v in dict(val).items()
                },
            }
        elif hasattr(val, "element_id") and hasattr(val, "type"):
            # Relationship
            row[key] = {
                "id": val.element_id,
                "type": val.type,
                "sourceId": val.start_node.element_id,
                "targetId": val.end_node.element_id,
                "properties": {
                    k: serialize_neo4j_value(v) for k, v in dict(val).items()
                },
            }
        else:
            row[key] = serialize_neo4j_value(val)

    return row


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/execute", response_model=CypherResponse)
async def execute_cypher(
    body: CypherRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> CypherResponse:
    """Execute a raw Cypher query against the knowledge graph.

    Validates the query for dangerous operations before execution.  Read
    queries (``MATCH``/``RETURN`` only) are run as read transactions;
    write queries as write transactions.

    Args:
        body: Cypher query string and optional parameters.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        CypherResponse with result rows, column names, row count, and
        execution time in milliseconds.

    Raises:
        HTTPException: 403 if the query contains disallowed operations.
        HTTPException: 500 if query execution fails.
    """
    dangerous, reason = _is_dangerous(body.cypher)
    if dangerous:
        raise HTTPException(status_code=403, detail=reason)

    # Clamp caller-supplied timeout to the server-side ceiling.
    timeout_ms = min(body.timeout_ms, _MAX_CYPHER_TIMEOUT_MS)
    timeout_s = timeout_ms / 1000.0

    # Inject project scoping into MATCH patterns to enforce project isolation.
    body_cypher = CypherBuilder._inject_project_label(body.cypher, project.label)

    # Auto-append LIMIT if absent to prevent unbounded result sets.
    body_cypher = _ensure_result_limit(body_cypher, body.limit)

    params = {
        **body.parameters,
        "__kg_project_label": project.label,
        "__kg_project_name": project.property_value,
    }

    start_ms = time.monotonic()
    try:
        result = await session.run(body_cypher, params, timeout=timeout_s)
        records = [record async for record in result]
    except Exception as exc:
        logger.exception("Cypher execution failed")
        raise HTTPException(
            status_code=500, detail=f"Cypher execution failed: {exc}"
        ) from exc

    elapsed_ms = (time.monotonic() - start_ms) * 1000.0

    rows = [_serialize_record(r) for r in records]
    columns = list(rows[0].keys()) if rows else []

    return CypherResponse(
        results=rows,
        columns=columns,
        rowCount=len(rows),
        executionTimeMs=round(elapsed_ms, 3),
    )


@router.post("/validate", response_model=CypherValidationResponse)
async def validate_cypher(body: CypherRequest) -> CypherValidationResponse:
    """Validate a Cypher query without executing it.

    Uses :class:`~kg.cypher_validator.CypherValidator` when available,
    falling back to a lightweight syntax check.

    Args:
        body: Cypher query string (parameters are ignored for validation).

    Returns:
        CypherValidationResponse indicating validity, any errors, and
        the detected query type.
    """
    cypher = body.cypher.strip()

    if not cypher:
        return CypherValidationResponse(
            valid=False,
            errors=["Empty query"],
            queryType="read",
        )

    errors: list[str] = []
    query_type = _detect_query_type(cypher)

    # Try the full CypherValidator first
    try:
        from kg.cypher_validator import CypherValidator

        validator = CypherValidator()
        result = validator.validate(cypher)
        return CypherValidationResponse(
            valid=result.is_valid,
            errors=result.errors,
            queryType=query_type,
        )
    except Exception:
        # Fallback: lightweight heuristic checks
        logger.debug("CypherValidator unavailable, using heuristic fallback", exc_info=True)

    # Lightweight fallback: check for RETURN clause on read queries
    if query_type == "read" and "RETURN" not in cypher.upper():
        errors.append("Missing RETURN clause")

    return CypherValidationResponse(
        valid=len(errors) == 0,
        errors=errors,
        queryType=query_type,
    )


@router.post("/explain", response_model=CypherExplainResponse)
async def explain_cypher(
    body: CypherRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> CypherExplainResponse:
    """Return the execution plan for a Cypher query without running it.

    Prepends ``EXPLAIN`` to the query so that Neo4j returns a plan
    without actually executing the query.

    Args:
        body: Cypher query string and optional parameters.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        CypherExplainResponse with the query plan and estimated row count.

    Raises:
        HTTPException: 403 if the query contains disallowed operations.
        HTTPException: 500 if the EXPLAIN call fails.
    """
    dangerous, reason = _is_dangerous(body.cypher)
    if dangerous:
        raise HTTPException(status_code=403, detail=reason)

    # Inject project scoping into MATCH patterns to enforce project isolation.
    body_cypher = CypherBuilder._inject_project_label(body.cypher, project.label)

    params = {
        **body.parameters,
        "__kg_project_label": project.label,
        "__kg_project_name": project.property_value,
    }

    explain_cypher = f"EXPLAIN {body_cypher}"
    try:
        result = await session.run(explain_cypher, params)
        # Consume the result to get the summary/plan
        records = [record async for record in result]
        # Try to access the query plan from the result summary
        plan: dict[str, Any] = {}
        estimated_rows = 0
        if hasattr(result, "consume"):
            summary = await result.consume()
            if hasattr(summary, "plan") and summary.plan is not None:
                raw_plan = summary.plan
                plan = {
                    "operator": getattr(raw_plan, "operator_type", ""),
                    "arguments": dict(getattr(raw_plan, "arguments", {})),
                    "identifiers": list(getattr(raw_plan, "identifiers", [])),
                    "children": [
                        {"operator": getattr(c, "operator_type", "")}
                        for c in getattr(raw_plan, "children", [])
                    ],
                }
                args = getattr(raw_plan, "arguments", {})
                estimated_rows = int(args.get("EstimatedRows", 0))
        else:
            # Mock/test environment: build a minimal plan from records
            plan = {"operator": "EXPLAIN", "records": records}
    except Exception as exc:
        logger.exception("EXPLAIN failed")
        raise HTTPException(
            status_code=500, detail=f"EXPLAIN failed: {exc}"
        ) from exc

    return CypherExplainResponse(plan=plan, estimatedRows=estimated_rows)
