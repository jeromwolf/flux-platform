"""Neo4j output node — execute Cypher queries to store data in Knowledge Graph."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.workflow.base_node import BaseNode
from core.workflow.registry import NodeRegistry

logger = logging.getLogger(__name__)


@NodeRegistry.register
class Neo4jOutputNode(BaseNode):
    name = "output"
    display_name = "KG 저장"
    description = "Neo4j Knowledge Graph에 데이터 저장"
    category = "storage"

    async def execute(
        self,
        input_data: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        mode = params.get("mode", "merge")

        if mode == "custom":
            queries = self._build_custom_cypher(input_data, params)
        else:
            queries = self._build_auto_cypher(input_data, params, mode)

        return await self._execute_queries(queries, params)

    def _build_auto_cypher(
        self,
        input_data: list[dict[str, Any]],
        params: dict[str, Any],
        mode: str,
    ) -> list[dict[str, Any]]:
        """Build Cypher queries from label + properties."""
        label = params.get("label", "Entity")
        properties = params.get("properties", [])

        queries = []
        for item in input_data:
            if properties:
                props = {k: item.get(k) for k in properties if k in item}
            else:
                props = {
                    k: v for k, v in item.items()
                    if isinstance(v, (str, int, float, bool))
                }

            if not props:
                queries.append({
                    "cypher": "",
                    "params": {},
                    "status": "skipped",
                    "reason": "no properties",
                })
                continue

            if mode == "merge":
                merge_key = list(props.keys())[0]
                cypher = (
                    f"MERGE (n:{label} {{{merge_key}: ${merge_key}}}) "
                    f"SET n += $props RETURN n"
                )
                query_params = {merge_key: props[merge_key], "props": props}
            else:
                props_str = ", ".join(f"{k}: ${k}" for k in props)
                cypher = f"CREATE (n:{label} {{{props_str}}}) RETURN n"
                query_params = props

            queries.append({
                "cypher": cypher,
                "params": query_params,
                "label": label,
                "properties": props,
            })

        return queries

    def _build_custom_cypher(
        self,
        input_data: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build custom Cypher from template."""
        cypher_template = params.get("cypher", "")
        if not cypher_template:
            raise ValueError("Custom mode requires 'cypher' parameter")

        queries = []
        for item in input_data:
            cypher = cypher_template
            for key, val in item.items():
                cypher = cypher.replace(f"{{{{{key}}}}}", str(val))
            queries.append({"cypher": cypher, "params": item})

        return queries

    async def _execute_queries(
        self,
        queries: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Execute queries against Neo4j. Falls back to 'prepared' if unavailable."""
        project = params.get("project", "")

        driver = None
        db_name = "neo4j"
        try:
            from kg.config import get_driver, get_config
            driver = get_driver()
            cfg = get_config()
            db_name = cfg.neo4j.database
        except Exception:
            logger.debug("Neo4j driver not available — returning prepared queries")

        results = []
        for q in queries:
            if q.get("status") == "skipped":
                results.append(q)
                continue

            cypher = q["cypher"]
            query_params = q.get("params", {})

            # Apply project label injection if project is specified
            if project and cypher:
                try:
                    from kg.cypher_builder import CypherBuilder
                    cypher = CypherBuilder._inject_project_label(cypher, f"KG_{project}")
                except Exception:
                    pass  # Injection is best-effort

            if driver is None:
                results.append({**q, "status": "prepared"})
                continue

            # Execute against Neo4j (offloaded to thread to avoid blocking event loop)
            try:
                outcome = await asyncio.to_thread(
                    self._run_query_sync, driver, db_name, cypher, query_params
                )
                results.append({**q, **outcome})
            except Exception as exc:
                logger.warning("Neo4j execution failed for query: %s", exc)
                results.append({
                    **q,
                    "status": "error",
                    "error": str(exc),
                })

        return results

    def _run_query_sync(
        self,
        driver: Any,
        db_name: str,
        cypher: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Synchronous Neo4j execution — must be called via asyncio.to_thread."""
        session = driver.session(database=db_name)
        try:
            neo4j_result = session.run(cypher, query_params)
            records = [dict(r) for r in neo4j_result]
            summary = neo4j_result.consume()
            return {
                "status": "executed",
                "records_affected": (
                    summary.counters.nodes_created
                    + summary.counters.properties_set
                ),
                "records": [
                    self._serialize_record(r) for r in records[:10]
                ],
            }
        finally:
            session.close()

    @staticmethod
    def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
        """Serialize a Neo4j record to JSON-safe dict."""
        serialized = {}
        for key, val in record.items():
            if hasattr(val, "items"):
                serialized[key] = dict(val) if hasattr(val, "__iter__") else str(val)
            else:
                serialized[key] = val
        return serialized

    def get_parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["create", "merge", "custom"],
                    "default": "merge",
                    "description": "저장 모드",
                },
                "label": {
                    "type": "string",
                    "default": "Entity",
                    "description": "노드 레이블 (create/merge 모드)",
                },
                "properties": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "저장할 속성 목록",
                },
                "cypher": {
                    "type": "string",
                    "description": "Cypher 쿼리 (custom 모드 전용)",
                },
                "project": {
                    "type": "string",
                    "description": "KG 프로젝트명 (레이블 격리)",
                },
            },
        }
