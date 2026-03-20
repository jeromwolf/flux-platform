"""Multi-language Query Generator - Generate queries from structured input.

Ported from flux-ontology-local's QueryGeneratorService.
Supports generating Cypher (Neo4j), SQL (PostgreSQL), and MongoDB queries.

Usage::
    from kg.query_generator import QueryGenerator, StructuredQuery, ExtractedFilter

    generator = QueryGenerator()

    query = StructuredQuery(
        intent=QueryIntent(intent="FIND", confidence=0.9),
        object_types=["Vessel"],
        filters=[
            ExtractedFilter(field="vesselType", operator="equals", value="ContainerShip")
        ],
        pagination=Pagination(limit=10)
    )

    result = generator.generate_cypher(query)
    print(result.query)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from kg.types import FilterOperator, ReasoningType


class QueryIntentType(str, Enum):
    """Types of query intents."""

    FIND = "FIND"
    COUNT = "COUNT"
    AGGREGATE = "AGGREGATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"


class AggregationFunction(str, Enum):
    """Aggregation functions."""

    COUNT = "COUNT"
    SUM = "SUM"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"
    DISTINCT = "DISTINCT"


class QueryComplexity(str, Enum):
    """Query complexity levels."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class QueryIntent:
    """Detected query intent."""

    intent: str | QueryIntentType
    confidence: float = 1.0
    sub_intent: str | None = None


@dataclass
class ExtractedFilter:
    """Filter extracted from natural language."""

    field: str
    operator: str | FilterOperator
    value: Any
    confidence: float = 1.0


@dataclass
class RelationshipSpec:
    """Relationship specification for traversal."""

    type: str
    direction: Literal["incoming", "outgoing", "bidirectional"] = "outgoing"
    target_entity: str | None = None
    alias: str | None = None


@dataclass
class AggregationSpec:
    """Aggregation specification."""

    function: str | AggregationFunction
    field: str | None = None
    alias: str | None = None


@dataclass
class SortSpec:
    """Sort specification."""

    field: str
    direction: Literal["ASC", "DESC"] = "ASC"


@dataclass
class Pagination:
    """Pagination specification."""

    limit: int | None = None
    offset: int | None = None


@dataclass
class StructuredQuery:
    """Structured representation of a query."""

    intent: QueryIntent
    object_types: list[str] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)
    filters: list[ExtractedFilter] = field(default_factory=list)
    relationships: list[RelationshipSpec] = field(default_factory=list)
    aggregations: list[AggregationSpec] | None = None
    group_by: list[str] | None = None
    sorting: list[SortSpec] | None = None
    pagination: Pagination | None = None
    reasoning_type: ReasoningType = ReasoningType.DIRECT


@dataclass
class GeneratedQuery:
    """Result of query generation."""

    language: str
    query: str
    parameters: dict[str, Any] = field(default_factory=dict)
    explanation: str | None = None
    estimated_complexity: str = "simple"
    warnings: list[str] | None = None


class QueryGenerator:
    """Multi-language query generator.

    Generates queries in Cypher (Neo4j), SQL (PostgreSQL), and MongoDB
    from a structured query representation.
    """

    def generate(
        self,
        structured_query: StructuredQuery,
        language: Literal["cypher", "sql", "mongodb"] = "cypher",
    ) -> GeneratedQuery:
        """Generate query in specified language.

        Args:
            structured_query: Structured query representation
            language: Target query language

        Returns:
            Generated query with parameters
        """
        if language == "cypher":
            return self.generate_cypher(structured_query)
        elif language == "sql":
            return self.generate_sql(structured_query)
        elif language == "mongodb":
            return self.generate_mongodb(structured_query)
        else:
            raise ValueError(f"Unsupported query language: {language}")

    def generate_all(self, structured_query: StructuredQuery) -> list[GeneratedQuery]:
        """Generate queries in all supported languages.

        Args:
            structured_query: Structured query representation

        Returns:
            List of generated queries
        """
        return [
            self.generate_cypher(structured_query),
            self.generate_sql(structured_query),
            self.generate_mongodb(structured_query),
        ]

    # =========================================================================
    # Cypher (Neo4j)
    # =========================================================================

    def generate_cypher(self, query: StructuredQuery) -> GeneratedQuery:
        """Generate Neo4j Cypher query.

        Args:
            query: Structured query

        Returns:
            Generated Cypher query
        """
        object_type = query.object_types[0] if query.object_types else "Node"
        alias = object_type.lower()[0]
        parameters: dict[str, Any] = {}
        param_index = 1
        warnings: list[str] = []

        cypher = f"MATCH ({alias}:{object_type})"

        # Relationships
        for rel in query.relationships:
            rel_alias = f"r{param_index}"
            target_alias = f"t{param_index}"

            if rel.direction == "incoming":
                pattern = f"<-[{rel_alias}:{rel.type}]-"
            elif rel.direction == "bidirectional":
                pattern = f"-[{rel_alias}:{rel.type}]-"
            else:
                pattern = f"-[{rel_alias}:{rel.type}]->"

            target = rel.target_entity or "Node"
            cypher += f"\n{pattern}({target_alias}:{target})"
            param_index += 1

        # WHERE clause
        if query.filters:
            conditions = []
            for filter_ in query.filters:
                param_name = f"p{param_index}"
                condition = self._cypher_condition(alias, filter_, param_name)
                if condition:
                    conditions.append(condition)
                    if filter_.operator not in ("is_null", "is_not_null"):
                        parameters[param_name] = filter_.value
                    param_index += 1

            if conditions:
                cypher += f"\nWHERE {' AND '.join(conditions)}"

        # RETURN clause
        intent = query.intent.intent
        intent_str = intent.value if isinstance(intent, QueryIntentType) else intent

        if intent_str == "COUNT":
            cypher += f"\nRETURN count({alias}) AS count"
        elif intent_str == "AGGREGATE" and query.aggregations:
            agg_parts = [self._cypher_aggregation(alias, agg) for agg in query.aggregations]
            if query.group_by:
                group_fields = ", ".join(f"{alias}.{f}" for f in query.group_by)
                cypher += f"\nRETURN {group_fields}, {', '.join(agg_parts)}"
            else:
                cypher += f"\nRETURN {', '.join(agg_parts)}"
        else:
            if query.properties:
                props = ", ".join(f"{alias}.{p} AS {p}" for p in query.properties)
                cypher += f"\nRETURN {props}"
            else:
                cypher += f"\nRETURN {alias}"

        # ORDER BY
        if query.sorting:
            order_parts = [f"{alias}.{s.field} {s.direction}" for s in query.sorting]
            cypher += f"\nORDER BY {', '.join(order_parts)}"

        # LIMIT & SKIP
        if query.pagination:
            if query.pagination.offset:
                cypher += f"\nSKIP {query.pagination.offset}"
            if query.pagination.limit:
                cypher += f"\nLIMIT {query.pagination.limit}"

        return GeneratedQuery(
            language="cypher",
            query=cypher,
            parameters=parameters,
            explanation=f"Neo4j Cypher query for {intent_str} on {object_type}",
            estimated_complexity=self._estimate_complexity(query),
            warnings=warnings if warnings else None,
        )

    def _cypher_condition(
        self,
        alias: str,
        filter_: ExtractedFilter,
        param_name: str,
    ) -> str:
        """Generate Cypher WHERE condition."""
        field = f"{alias}.{filter_.field}"
        op = filter_.operator
        op_str = op.value if isinstance(op, FilterOperator) else op

        conditions = {
            "equals": f"{field} = ${param_name}",
            "not_equals": f"{field} <> ${param_name}",
            "contains": f"{field} CONTAINS ${param_name}",
            "starts_with": f"{field} STARTS WITH ${param_name}",
            "ends_with": f"{field} ENDS WITH ${param_name}",
            "greater_than": f"{field} > ${param_name}",
            "greater_than_or_equals": f"{field} >= ${param_name}",
            "less_than": f"{field} < ${param_name}",
            "less_than_or_equals": f"{field} <= ${param_name}",
            "in": f"{field} IN ${param_name}",
            "not_in": f"NOT {field} IN ${param_name}",
            "is_null": f"{field} IS NULL",
            "is_not_null": f"{field} IS NOT NULL",
            "matches_regex": f"{field} =~ ${param_name}",
        }
        return conditions.get(op_str, f"{field} = ${param_name}")

    def _cypher_aggregation(self, alias: str, agg: AggregationSpec) -> str:
        """Generate Cypher aggregation expression."""
        func = agg.function
        func_str = func.value if isinstance(func, AggregationFunction) else func
        alias_name = agg.alias or func_str.lower()

        if agg.field:
            return f"{func_str}({alias}.{agg.field}) AS {alias_name}"
        return f"{func_str}({alias}) AS {alias_name}"

    # =========================================================================
    # SQL (PostgreSQL)
    # =========================================================================

    def generate_sql(self, query: StructuredQuery) -> GeneratedQuery:
        """Generate PostgreSQL SQL query.

        Args:
            query: Structured query

        Returns:
            Generated SQL query
        """
        object_type = query.object_types[0] if query.object_types else "objects"
        table_name = self._to_snake_case(object_type)
        alias = table_name[0]
        parameters: dict[str, Any] = {}
        param_index = 1
        warnings: list[str] = []

        intent = query.intent.intent
        intent_str = intent.value if isinstance(intent, QueryIntentType) else intent

        # SELECT clause
        if intent_str == "COUNT":
            sql = "SELECT COUNT(*) AS count"
        elif intent_str == "AGGREGATE" and query.aggregations:
            agg_parts = [self._sql_aggregation(alias, agg) for agg in query.aggregations]
            if query.group_by:
                group_fields = ", ".join(
                    f"{alias}.{self._to_snake_case(f)}" for f in query.group_by
                )
                sql = f"SELECT {group_fields}, {', '.join(agg_parts)}"
            else:
                sql = f"SELECT {', '.join(agg_parts)}"
        else:
            if query.properties:
                cols = ", ".join(f"{alias}.{self._to_snake_case(p)}" for p in query.properties)
                sql = f"SELECT {cols}"
            else:
                sql = f"SELECT {alias}.*"

        # FROM clause
        sql += f"\nFROM {table_name} {alias}"

        # JOIN for relationships
        for rel in query.relationships:
            target_table = self._to_snake_case(rel.target_entity or "target")
            join_alias = f"t{param_index}"
            sql += (
                f"\nJOIN {target_table} {join_alias} ON {alias}.id = {join_alias}.{table_name}_id"
            )
            warnings.append(f"Relationship {rel.type} requires proper FK configuration")
            param_index += 1

        # WHERE clause
        if query.filters:
            conditions = []
            for filter_ in query.filters:
                cond = self._sql_condition(alias, filter_, param_index)
                if cond:
                    conditions.append(cond["sql"])
                    if cond["value"] is not None:
                        parameters[f"${param_index}"] = cond["value"]
                    param_index += 1

            if conditions:
                sql += f"\nWHERE {' AND '.join(conditions)}"

        # GROUP BY
        if intent_str == "AGGREGATE" and query.group_by:
            group_fields = ", ".join(f"{alias}.{self._to_snake_case(f)}" for f in query.group_by)
            sql += f"\nGROUP BY {group_fields}"

        # ORDER BY
        if query.sorting:
            order_parts = [
                f"{alias}.{self._to_snake_case(s.field)} {s.direction}" for s in query.sorting
            ]
            sql += f"\nORDER BY {', '.join(order_parts)}"

        # LIMIT & OFFSET
        if query.pagination:
            if query.pagination.limit:
                sql += f"\nLIMIT {query.pagination.limit}"
            if query.pagination.offset:
                sql += f"\nOFFSET {query.pagination.offset}"

        return GeneratedQuery(
            language="sql",
            query=sql,
            parameters=parameters,
            explanation=f"PostgreSQL query for {intent_str} on {object_type}",
            estimated_complexity=self._estimate_complexity(query),
            warnings=warnings if warnings else None,
        )

    def _sql_condition(
        self,
        alias: str,
        filter_: ExtractedFilter,
        _param_index: int,
    ) -> dict[str, Any] | None:
        """Generate SQL WHERE condition."""
        field = f"{alias}.{self._to_snake_case(filter_.field)}"
        op = filter_.operator
        op_str = op.value if isinstance(op, FilterOperator) else op

        conditions = {
            "equals": (f"{field} = ?", filter_.value),
            "not_equals": (f"{field} != ?", filter_.value),
            "contains": (f"{field} ILIKE ?", f"%{filter_.value}%"),
            "starts_with": (f"{field} ILIKE ?", f"{filter_.value}%"),
            "ends_with": (f"{field} ILIKE ?", f"%{filter_.value}"),
            "greater_than": (f"{field} > ?", filter_.value),
            "greater_than_or_equals": (f"{field} >= ?", filter_.value),
            "less_than": (f"{field} < ?", filter_.value),
            "less_than_or_equals": (f"{field} <= ?", filter_.value),
            "in": (f"{field} = ANY(?)", filter_.value),
            "is_null": (f"{field} IS NULL", None),
            "is_not_null": (f"{field} IS NOT NULL", None),
        }

        if op_str in conditions:
            sql, value = conditions[op_str]
            return {"sql": sql, "value": value}
        return {"sql": f"{field} = ?", "value": filter_.value}

    def _sql_aggregation(self, alias: str, agg: AggregationSpec) -> str:
        """Generate SQL aggregation expression."""
        func = agg.function
        func_str = func.value if isinstance(func, AggregationFunction) else func
        alias_name = agg.alias or func_str.lower()

        if agg.field:
            return f"{func_str}({alias}.{self._to_snake_case(agg.field)}) AS {alias_name}"
        return f"{func_str}(*) AS {alias_name}"

    # =========================================================================
    # MongoDB
    # =========================================================================

    def generate_mongodb(self, query: StructuredQuery) -> GeneratedQuery:
        """Generate MongoDB query.

        Args:
            query: Structured query

        Returns:
            Generated MongoDB query
        """
        collection = query.object_types[0] if query.object_types else "objects"
        warnings: list[str] = []

        # Build filter
        filter_doc: dict[str, Any] = {}
        for f in query.filters:
            filter_doc[f.field] = self._mongo_condition(f)

        intent = query.intent.intent
        intent_str = intent.value if isinstance(intent, QueryIntentType) else intent

        if intent_str == "COUNT":
            mongo_query = f"db.{collection}.countDocuments({json.dumps(filter_doc, indent=2)})"
        elif intent_str == "AGGREGATE" and query.aggregations:
            pipeline = self._build_mongo_pipeline(query, filter_doc)
            mongo_query = f"db.{collection}.aggregate({json.dumps(pipeline, indent=2)})"
        else:
            # Build projection
            projection = None
            if query.properties:
                projection = {p: 1 for p in query.properties}

            mongo_query = f"db.{collection}.find(\n  {json.dumps(filter_doc, indent=2)}"
            if projection:
                mongo_query += f",\n  {json.dumps(projection, indent=2)}"
            mongo_query += "\n)"

            # Sort
            if query.sorting:
                sort_doc = {s.field: 1 if s.direction == "ASC" else -1 for s in query.sorting}
                mongo_query += f".sort({json.dumps(sort_doc)})"

            # Skip & Limit
            if query.pagination:
                if query.pagination.offset:
                    mongo_query += f".skip({query.pagination.offset})"
                if query.pagination.limit:
                    mongo_query += f".limit({query.pagination.limit})"

        return GeneratedQuery(
            language="mongodb",
            query=mongo_query,
            explanation=f"MongoDB query for {intent_str} on {collection}",
            estimated_complexity=self._estimate_complexity(query),
            warnings=warnings if warnings else None,
        )

    def _mongo_condition(self, filter_: ExtractedFilter) -> Any:
        """Generate MongoDB filter condition."""
        op = filter_.operator
        op_str = op.value if isinstance(op, FilterOperator) else op

        conditions = {
            "equals": filter_.value,
            "not_equals": {"$ne": filter_.value},
            "contains": {"$regex": filter_.value, "$options": "i"},
            "starts_with": {"$regex": f"^{filter_.value}", "$options": "i"},
            "ends_with": {"$regex": f"{filter_.value}$", "$options": "i"},
            "greater_than": {"$gt": filter_.value},
            "greater_than_or_equals": {"$gte": filter_.value},
            "less_than": {"$lt": filter_.value},
            "less_than_or_equals": {"$lte": filter_.value},
            "in": {"$in": filter_.value},
            "not_in": {"$nin": filter_.value},
            "is_null": {"$eq": None},
            "is_not_null": {"$ne": None},
            "matches_regex": {"$regex": filter_.value},
        }
        return conditions.get(op_str, filter_.value)

    def _build_mongo_pipeline(
        self,
        query: StructuredQuery,
        filter_doc: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build MongoDB aggregation pipeline."""
        pipeline: list[dict[str, Any]] = []

        # $match stage
        if filter_doc:
            pipeline.append({"$match": filter_doc})

        # $group stage
        if query.aggregations:
            group_stage: dict[str, Any] = {"_id": None}
            if query.group_by:
                group_stage["_id"] = {f: f"${f}" for f in query.group_by}

            for agg in query.aggregations:
                func = agg.function
                func_str = func.value if isinstance(func, AggregationFunction) else func
                alias = agg.alias or func_str.lower()

                if func_str == "COUNT":
                    group_stage[alias] = {"$sum": 1}
                elif func_str == "SUM":
                    group_stage[alias] = {"$sum": f"${agg.field}"}
                elif func_str == "AVG":
                    group_stage[alias] = {"$avg": f"${agg.field}"}
                elif func_str == "MIN":
                    group_stage[alias] = {"$min": f"${agg.field}"}
                elif func_str == "MAX":
                    group_stage[alias] = {"$max": f"${agg.field}"}
                elif func_str == "DISTINCT":
                    group_stage[alias] = {"$addToSet": f"${agg.field}"}

            pipeline.append({"$group": group_stage})

        # $sort stage
        if query.sorting:
            sort_stage = {s.field: 1 if s.direction == "ASC" else -1 for s in query.sorting}
            pipeline.append({"$sort": sort_stage})

        # $skip and $limit
        if query.pagination:
            if query.pagination.offset:
                pipeline.append({"$skip": query.pagination.offset})
            if query.pagination.limit:
                pipeline.append({"$limit": query.pagination.limit})

        return pipeline

    # =========================================================================
    # Helpers
    # =========================================================================

    def _to_snake_case(self, s: str) -> str:
        """Convert camelCase to snake_case."""
        s = re.sub(r"([A-Z])", r"_\1", s)
        return s.lower().lstrip("_")

    def _estimate_complexity(self, query: StructuredQuery) -> str:
        """Estimate query complexity."""
        score = 0
        score += len(query.filters)
        score += len(query.relationships) * 2
        score += len(query.aggregations or []) * 2
        score += len(query.group_by or [])
        score += len(query.sorting or []) * 0.5

        if score <= 2:
            return QueryComplexity.SIMPLE.value
        elif score <= 5:
            return QueryComplexity.MODERATE.value
        return QueryComplexity.COMPLEX.value
