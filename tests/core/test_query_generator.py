"""QueryGenerator 단위 테스트.

TC-E01 ~ TC-E08: kg/query_generator.py의 다중 언어 쿼리 생성기 검증.
모든 테스트는 Neo4j 없이 순수 Python으로 동작한다.
"""

from __future__ import annotations

import pytest

from kg.query_generator import (
    AggregationFunction,
    AggregationSpec,
    ExtractedFilter,
    GeneratedQuery,
    Pagination,
    QueryGenerator,
    QueryIntent,
    QueryIntentType,
    RelationshipSpec,
    SortSpec,
    StructuredQuery,
)


@pytest.fixture
def generator() -> QueryGenerator:
    """QueryGenerator 인스턴스."""
    return QueryGenerator()


@pytest.fixture
def find_vessel_query() -> StructuredQuery:
    """FIND Vessel 기본 StructuredQuery."""
    return StructuredQuery(
        intent=QueryIntent(intent=QueryIntentType.FIND, confidence=0.95),
        object_types=["Vessel"],
        properties=["name", "mmsi", "vesselType"],
        filters=[
            ExtractedFilter(
                field="vesselType",
                operator="equals",
                value="ContainerShip",
            ),
        ],
        sorting=[SortSpec(field="name", direction="ASC")],
        pagination=Pagination(limit=10),
    )


# =========================================================================
# TC-E01: FIND Cypher 생성
# =========================================================================


@pytest.mark.unit
class TestFindCypher:
    """FIND 인텐트 Cypher 생성 검증."""

    def test_find_cypher_structure(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E01-a: FIND 인텐트로 MATCH/WHERE/RETURN Cypher 생성."""
        result = generator.generate_cypher(find_vessel_query)

        assert isinstance(result, GeneratedQuery)
        assert result.language == "cypher"
        assert "MATCH" in result.query
        assert "Vessel" in result.query
        assert "RETURN" in result.query
        assert "WHERE" in result.query

    def test_find_cypher_properties(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E01-b: FIND 시 properties 지정 -> 개별 프로퍼티 RETURN."""
        result = generator.generate_cypher(find_vessel_query)
        assert "v.name AS name" in result.query
        assert "v.mmsi AS mmsi" in result.query

    def test_find_cypher_filter_param(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E01-c: 필터 파라미터가 생성되어야 한다."""
        result = generator.generate_cypher(find_vessel_query)
        assert len(result.parameters) > 0, "필터 파라미터가 비어있음"
        assert "ContainerShip" in result.parameters.values()

    def test_find_cypher_sorting(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E01-d: ORDER BY 절 생성."""
        result = generator.generate_cypher(find_vessel_query)
        assert "ORDER BY" in result.query
        assert "v.name ASC" in result.query

    def test_find_cypher_pagination(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E01-e: LIMIT 절 생성."""
        result = generator.generate_cypher(find_vessel_query)
        assert "LIMIT 10" in result.query

    def test_find_without_properties(self, generator: QueryGenerator) -> None:
        """TC-E01-f: properties 미지정 시 전체 노드 RETURN."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Port"],
        )
        result = generator.generate_cypher(query)
        assert "RETURN p" in result.query  # Port -> alias 'p'

    def test_find_with_skip_and_limit(self, generator: QueryGenerator) -> None:
        """TC-E01-g: SKIP + LIMIT 동시 적용."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Vessel"],
            pagination=Pagination(limit=5, offset=10),
        )
        result = generator.generate_cypher(query)
        assert "SKIP 10" in result.query
        assert "LIMIT 5" in result.query


# =========================================================================
# TC-E02: COUNT Cypher 생성
# =========================================================================


@pytest.mark.unit
class TestCountCypher:
    """COUNT 인텐트 Cypher 생성 검증."""

    def test_count_cypher(self, generator: QueryGenerator) -> None:
        """TC-E02-a: COUNT 인텐트로 count() 함수 포함 Cypher 생성."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.COUNT),
            object_types=["Vessel"],
            filters=[
                ExtractedFilter(field="vesselType", operator="equals", value="Tanker"),
            ],
        )
        result = generator.generate_cypher(query)

        assert "count(" in result.query, "count() 함수 미포함"
        assert "AS count" in result.query
        assert "WHERE" in result.query

    def test_count_without_filter(self, generator: QueryGenerator) -> None:
        """TC-E02-b: 필터 없는 COUNT."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.COUNT),
            object_types=["Incident"],
        )
        result = generator.generate_cypher(query)
        assert "count(" in result.query
        assert "WHERE" not in result.query


# =========================================================================
# TC-E03: AGGREGATE Cypher 생성
# =========================================================================


@pytest.mark.unit
class TestAggregateCypher:
    """AGGREGATE 인텐트 Cypher 생성 검증."""

    def test_aggregate_with_group_by(self, generator: QueryGenerator) -> None:
        """TC-E03-a: AGGREGATE + group_by로 집계 Cypher 생성."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.AGGREGATE),
            object_types=["Vessel"],
            aggregations=[
                AggregationSpec(
                    function=AggregationFunction.COUNT,
                    alias="cnt",
                ),
            ],
            group_by=["vesselType"],
        )
        result = generator.generate_cypher(query)

        assert "COUNT(" in result.query
        assert "AS cnt" in result.query
        assert "v.vesselType" in result.query

    def test_aggregate_avg(self, generator: QueryGenerator) -> None:
        """TC-E03-b: AVG 집계."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.AGGREGATE),
            object_types=["Vessel"],
            aggregations=[
                AggregationSpec(
                    function=AggregationFunction.AVG,
                    field="grossTonnage",
                    alias="avg_tonnage",
                ),
            ],
        )
        result = generator.generate_cypher(query)
        assert "AVG(" in result.query
        assert "grossTonnage" in result.query

    def test_aggregate_multiple_functions(self, generator: QueryGenerator) -> None:
        """TC-E03-c: 복수 집계 함수."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.AGGREGATE),
            object_types=["Vessel"],
            aggregations=[
                AggregationSpec(function=AggregationFunction.COUNT, alias="total"),
                AggregationSpec(
                    function=AggregationFunction.MAX,
                    field="grossTonnage",
                    alias="max_gt",
                ),
            ],
        )
        result = generator.generate_cypher(query)
        assert "COUNT(" in result.query
        assert "MAX(" in result.query


# =========================================================================
# TC-E04: FIND SQL 생성
# =========================================================================


@pytest.mark.unit
class TestFindSQL:
    """SQL 생성 검증."""

    def test_find_sql_structure(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E04-a: FIND 인텐트로 SELECT/FROM SQL 생성."""
        result = generator.generate_sql(find_vessel_query)

        assert result.language == "sql"
        assert "SELECT" in result.query
        assert "FROM" in result.query
        assert "vessel" in result.query.lower()  # table name = snake_case

    def test_find_sql_where(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E04-b: SQL WHERE 절 생성."""
        result = generator.generate_sql(find_vessel_query)
        assert "WHERE" in result.query

    def test_find_sql_order_by(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E04-c: SQL ORDER BY 절 생성."""
        result = generator.generate_sql(find_vessel_query)
        assert "ORDER BY" in result.query

    def test_find_sql_limit(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E04-d: SQL LIMIT 절 생성."""
        result = generator.generate_sql(find_vessel_query)
        assert "LIMIT 10" in result.query

    def test_count_sql(self, generator: QueryGenerator) -> None:
        """TC-E05: COUNT 인텐트로 SELECT COUNT(*) SQL 생성."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.COUNT),
            object_types=["Vessel"],
        )
        result = generator.generate_sql(query)
        assert "COUNT(*)" in result.query

    def test_sql_snake_case_conversion(self, generator: QueryGenerator) -> None:
        """TC-E04-e: camelCase -> snake_case 변환 확인."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["WeatherCondition"],
            properties=["windSpeed", "waveHeight"],
        )
        result = generator.generate_sql(query)
        # camelCase -> snake_case 변환
        assert "wind_speed" in result.query.lower()
        assert "wave_height" in result.query.lower()


# =========================================================================
# TC-E06: FIND MongoDB 생성
# =========================================================================


@pytest.mark.unit
class TestFindMongoDB:
    """MongoDB 쿼리 생성 검증."""

    def test_find_mongodb_structure(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E06-a: FIND 인텐트로 db.collection.find() MongoDB 쿼리 생성."""
        result = generator.generate_mongodb(find_vessel_query)

        assert result.language == "mongodb"
        assert "db.Vessel.find" in result.query
        assert "vesselType" in result.query

    def test_find_mongodb_with_projection(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E06-b: properties 지정 시 projection 포함."""
        result = generator.generate_mongodb(find_vessel_query)
        # projection에 name, mmsi, vesselType이 포함되어야 함
        assert '"name": 1' in result.query
        assert '"mmsi": 1' in result.query

    def test_find_mongodb_sort(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E06-c: sorting 시 .sort() 체인."""
        result = generator.generate_mongodb(find_vessel_query)
        assert ".sort(" in result.query

    def test_find_mongodb_limit(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E06-d: pagination 시 .limit() 체인."""
        result = generator.generate_mongodb(find_vessel_query)
        assert ".limit(10)" in result.query

    def test_count_mongodb(self, generator: QueryGenerator) -> None:
        """TC-E06-e: COUNT 인텐트로 countDocuments() 생성."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.COUNT),
            object_types=["Vessel"],
            filters=[
                ExtractedFilter(field="flag", operator="equals", value="KR"),
            ],
        )
        result = generator.generate_mongodb(query)
        assert "countDocuments" in result.query

    def test_aggregate_mongodb(self, generator: QueryGenerator) -> None:
        """TC-E06-f: AGGREGATE 인텐트로 aggregate() 파이프라인 생성."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.AGGREGATE),
            object_types=["Vessel"],
            aggregations=[
                AggregationSpec(
                    function=AggregationFunction.COUNT,
                    alias="cnt",
                ),
            ],
            group_by=["vesselType"],
        )
        result = generator.generate_mongodb(query)
        assert "aggregate" in result.query
        assert "$group" in result.query


# =========================================================================
# TC-E07: 관계 포함 복합 Cypher
# =========================================================================


@pytest.mark.unit
class TestRelationshipCypher:
    """관계(RelationshipSpec) 포함 쿼리 생성 검증."""

    def test_outgoing_relationship(self, generator: QueryGenerator) -> None:
        """TC-E07-a: outgoing 관계 패턴 생성."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Vessel"],
            properties=["name"],
            relationships=[
                RelationshipSpec(
                    type="ON_VOYAGE",
                    direction="outgoing",
                    target_entity="Voyage",
                ),
            ],
        )
        result = generator.generate_cypher(query)
        assert "ON_VOYAGE" in result.query
        assert "Voyage" in result.query
        assert "->" in result.query or "]->" in result.query

    def test_incoming_relationship(self, generator: QueryGenerator) -> None:
        """TC-E07-b: incoming 관계 패턴 생성."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Port"],
            relationships=[
                RelationshipSpec(
                    type="TO_PORT",
                    direction="incoming",
                    target_entity="Voyage",
                ),
            ],
        )
        result = generator.generate_cypher(query)
        assert "TO_PORT" in result.query
        assert "<-" in result.query

    def test_bidirectional_relationship(self, generator: QueryGenerator) -> None:
        """TC-E07-c: bidirectional 관계 패턴 생성."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Vessel"],
            relationships=[
                RelationshipSpec(
                    type="INVOLVES",
                    direction="bidirectional",
                    target_entity="Incident",
                ),
            ],
        )
        result = generator.generate_cypher(query)
        assert "INVOLVES" in result.query

    def test_relationship_with_filters(self, generator: QueryGenerator) -> None:
        """TC-E07-d: 관계 + 필터 조합."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Vessel"],
            relationships=[
                RelationshipSpec(
                    type="ON_VOYAGE",
                    direction="outgoing",
                    target_entity="Voyage",
                ),
            ],
            filters=[
                ExtractedFilter(field="vesselType", operator="equals", value="ContainerShip"),
                ExtractedFilter(field="name", operator="contains", value="HMM"),
            ],
        )
        result = generator.generate_cypher(query)
        assert "WHERE" in result.query
        assert "AND" in result.query  # 2개 필터 -> AND 결합


# =========================================================================
# TC-E08: generate_all 다중 언어
# =========================================================================


@pytest.mark.unit
class TestGenerateAll:
    """generate_all() 및 generate() 라우팅 검증."""

    def test_generate_all_returns_three(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E08-a: generate_all()은 3개 언어 결과를 반환해야 한다."""
        results = generator.generate_all(find_vessel_query)
        assert len(results) == 3, f"3개 결과 기대, {len(results)}개 반환"

        languages = {r.language for r in results}
        assert languages == {"cypher", "sql", "mongodb"}

    def test_generate_router_cypher(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E08-b: generate(language='cypher') 라우팅."""
        result = generator.generate(find_vessel_query, language="cypher")
        assert result.language == "cypher"

    def test_generate_router_sql(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E08-c: generate(language='sql') 라우팅."""
        result = generator.generate(find_vessel_query, language="sql")
        assert result.language == "sql"

    def test_generate_router_mongodb(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E08-d: generate(language='mongodb') 라우팅."""
        result = generator.generate(find_vessel_query, language="mongodb")
        assert result.language == "mongodb"

    def test_generate_unsupported_language(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """TC-E08-e: 지원하지 않는 언어 시 ValueError."""
        with pytest.raises(ValueError, match="Unsupported"):
            generator.generate(find_vessel_query, language="graphql")  # type: ignore[arg-type]


# =========================================================================
# 추가: 복잡도 추정 및 메타데이터
# =========================================================================


@pytest.mark.unit
class TestQueryMetadata:
    """GeneratedQuery 메타데이터 검증."""

    def test_simple_complexity(self, generator: QueryGenerator) -> None:
        """간단한 쿼리의 복잡도는 'simple'이어야 한다."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Vessel"],
        )
        result = generator.generate_cypher(query)
        assert result.estimated_complexity == "simple"

    def test_complex_complexity(self, generator: QueryGenerator) -> None:
        """복잡한 쿼리의 복잡도는 'moderate' 이상이어야 한다."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Vessel"],
            filters=[
                ExtractedFilter(field="f1", operator="equals", value="v1"),
                ExtractedFilter(field="f2", operator="equals", value="v2"),
            ],
            relationships=[
                RelationshipSpec(type="ON_VOYAGE", direction="outgoing", target_entity="Voyage"),
            ],
            aggregations=[
                AggregationSpec(function=AggregationFunction.COUNT, alias="cnt"),
            ],
        )
        result = generator.generate_cypher(query)
        assert result.estimated_complexity in ("moderate", "complex")

    def test_explanation_present(
        self, generator: QueryGenerator, find_vessel_query: StructuredQuery
    ) -> None:
        """explanation 필드가 존재하고 비어있지 않아야 한다."""
        result = generator.generate_cypher(find_vessel_query)
        assert result.explanation is not None
        assert len(result.explanation) > 0
        assert "FIND" in result.explanation
        assert "Vessel" in result.explanation

    def test_filter_operators_in_cypher(self, generator: QueryGenerator) -> None:
        """다양한 필터 연산자가 Cypher에 올바르게 반영되어야 한다."""
        query = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Vessel"],
            filters=[
                ExtractedFilter(field="name", operator="contains", value="test"),
                ExtractedFilter(field="grossTonnage", operator="greater_than", value=10000),
                ExtractedFilter(field="destination", operator="is_null", value=None),
            ],
        )
        result = generator.generate_cypher(query)
        assert "CONTAINS" in result.query
        assert ">" in result.query
        assert "IS NULL" in result.query
