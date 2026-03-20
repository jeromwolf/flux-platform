"""Natural language query endpoint for the Maritime KG API.

Accepts Korean text, parses it into a structured query, generates Cypher,
and optionally executes it against the Neo4j database.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from kg.api.deps import get_async_neo4j_session
from kg.api.models import NLQueryRequest, NLQueryResponse
from kg.api.serializers import serialize_neo4j_value
from kg.pipeline import TextToCypherPipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])

# Module-level pipeline singleton (stateless, safe to share).
_pipeline = TextToCypherPipeline()


@router.post("/api/query", response_model=NLQueryResponse)
async def natural_language_query(
    body: NLQueryRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> NLQueryResponse:
    """Execute a Korean natural language query against the knowledge graph.

    Parses the input text, generates a Cypher query, and optionally runs
    it against the Neo4j database.

    Args:
        body: Request body containing the Korean text and options.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        NLQueryResponse with generated Cypher, parameters, and results.
    """
    output = _pipeline.process(body.text)

    # Build base response
    response = NLQueryResponse(
        input_text=output.input_text,
        confidence=output.parse_result.confidence,
        parse_details=output.parse_result.parse_details,
    )

    if not output.success or output.generated_query is None:
        response.error = output.error
        return response

    response.generated_cypher = output.generated_query.query
    response.parameters = output.generated_query.parameters

    # Optionally execute against Neo4j
    if body.execute:
        try:
            # Inject limit into the query if not already present
            cypher = output.generated_query.query
            params = dict(output.generated_query.parameters)

            # Append LIMIT if the generated query does not have one
            if "LIMIT" not in cypher.upper():
                cypher += f"\nLIMIT {body.limit}"

            result = await session.run(cypher, params)
            records = [record async for record in result]
            rows: list[dict[str, Any]] = []
            for record in records:
                row = {
                    k: serialize_neo4j_value(v) for k, v in dict(record).items()
                }
                rows.append(row)
            response.results = rows
        except Exception as exc:
            logger.exception("Failed to execute generated Cypher")
            response.error = f"Execution error: {exc}"
            response.results = None

    return response
