"""CypherBuilder 단위 테스트.

TC-D01 ~ TC-D10: kg/cypher_builder.py의 Fluent Cypher 쿼리 빌더 검증.
모든 테스트는 Neo4j 없이 순수 Python으로 동작한다.
"""

from __future__ import annotations

import pytest

from kg.cypher_builder import (
    CypherBuilder,
    QueryFilter,
    QueryOptions,
)

# =========================================================================
# TC-D01: 기본 MATCH/RETURN 빌드
# =========================================================================


@pytest.mark.unit
class TestBasicBuild:
    """CypherBuilder 기본 MATCH/RETURN 빌드 검증."""

    def test_simple_match_return(self) -> None:
        """TC-D01-a: 기본 MATCH/RETURN 쿼리 생성."""
        query, params = CypherBuilder().match("(v:Vessel)").return_("v").build()
        assert "MATCH (v:Vessel)" in query, f"MATCH 절 미포함: {query}"
        assert "RETURN v" in query, f"RETURN 절 미포함: {query}"
        assert len(params) == 0, "파라미터가 비어있어야 함"

    def test_multiple_match_clauses(self) -> None:
        """TC-D01-b: 다중 MATCH 절 생성."""
        query, params = (
            CypherBuilder().match("(v:Vessel)").match("(p:Port)").return_("v, p").build()
        )
        assert query.count("MATCH") == 2, "MATCH 절이 2개여야 함"

    def test_empty_build(self) -> None:
        """TC-D01-c: 아무 절도 없이 build() 호출 시 빈 쿼리."""
        query, params = CypherBuilder().build()
        assert query == "", "빈 빌더는 빈 문자열 반환"
        assert len(params) == 0


# =========================================================================
# TC-D02: WHERE 조건 + 파라미터
# =========================================================================


@pytest.mark.unit
class TestWhereClause:
    """WHERE 절 및 파라미터 바인딩 검증."""

    def test_where_with_params(self) -> None:
        """TC-D02-a: WHERE 절 + 파라미터 바인딩."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where("v.vesselType = $type", {"type": "ContainerShip"})
            .return_("v")
            .build()
        )
        assert "WHERE" in query
        assert "v.vesselType = $type" in query
        assert params["type"] == "ContainerShip"

    def test_where_without_params(self) -> None:
        """TC-D02-b: WHERE 절 파라미터 없이."""
        query, params = (
            CypherBuilder().match("(v:Vessel)").where("v.name IS NOT NULL").return_("v").build()
        )
        assert "WHERE v.name IS NOT NULL" in query
        assert len(params) == 0

    def test_multiple_where_and_combination(self) -> None:
        """TC-D03: 다중 WHERE 절은 AND로 결합."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where("v.vesselType = $type", {"type": "Tanker"})
            .where("v.flag = $flag", {"flag": "KR"})
            .return_("v")
            .build()
        )
        assert "AND" in query, "다중 WHERE는 AND로 결합되어야 함"
        assert params["type"] == "Tanker"
        assert params["flag"] == "KR"


# =========================================================================
# TC-D04: OPTIONAL MATCH
# =========================================================================


@pytest.mark.unit
class TestOptionalMatch:
    """OPTIONAL MATCH 절 검증."""

    def test_optional_match(self) -> None:
        """TC-D04: OPTIONAL MATCH 절 포함 쿼리 생성."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .optional_match("(v)-[:ON_VOYAGE]->(voy:Voyage)")
            .return_("v, voy")
            .build()
        )
        assert "OPTIONAL MATCH" in query, "OPTIONAL MATCH 절 미포함"
        assert "ON_VOYAGE" in query

    def test_match_and_optional_match_order(self) -> None:
        """TC-D04-b: MATCH 다음에 OPTIONAL MATCH이 배치되어야 함."""
        query, _ = (
            CypherBuilder()
            .match("(v:Vessel)")
            .optional_match("(v)-[:CARRIES]->(c:Cargo)")
            .return_("v, c")
            .build()
        )
        match_pos = query.index("MATCH (v:Vessel)")
        opt_pos = query.index("OPTIONAL MATCH")
        assert match_pos < opt_pos, "MATCH가 OPTIONAL MATCH보다 먼저 나와야 함"


# =========================================================================
# TC-D05: ORDER BY / LIMIT / SKIP
# =========================================================================


@pytest.mark.unit
class TestOrderLimitSkip:
    """ORDER BY, LIMIT, SKIP 절 검증."""

    def test_order_by(self) -> None:
        """TC-D05-a: ORDER BY 절 생성."""
        query, _ = (
            CypherBuilder().match("(v:Vessel)").return_("v").order_by("name", "asc", "v").build()
        )
        assert "ORDER BY v.name ASC" in query

    def test_order_by_desc(self) -> None:
        """TC-D05-b: ORDER BY DESC 방향."""
        query, _ = (
            CypherBuilder().match("(v:Vessel)").return_("v").order_by("mmsi", "desc", "v").build()
        )
        assert "ORDER BY v.mmsi DESC" in query

    def test_limit(self) -> None:
        """TC-D05-c: LIMIT 절 생성."""
        query, _ = CypherBuilder().match("(v:Vessel)").return_("v").limit(10).build()
        assert "LIMIT 10" in query

    def test_skip(self) -> None:
        """TC-D05-d: SKIP 절 생성."""
        query, _ = CypherBuilder().match("(v:Vessel)").return_("v").skip(20).build()
        assert "SKIP 20" in query

    def test_skip_before_limit(self) -> None:
        """TC-D05-e: SKIP이 LIMIT보다 먼저 나와야 한다."""
        query, _ = CypherBuilder().match("(v:Vessel)").return_("v").skip(10).limit(5).build()
        skip_pos = query.index("SKIP")
        limit_pos = query.index("LIMIT")
        assert skip_pos < limit_pos, "SKIP이 LIMIT보다 먼저 나와야 함"

    def test_with_clause(self) -> None:
        """TC-D05-f: WITH 절 생성."""
        query, _ = (
            CypherBuilder()
            .match("(v:Vessel)")
            .with_("v, count(*) AS cnt")
            .return_("v.vesselType, cnt")
            .build()
        )
        assert "WITH v, count(*) AS cnt" in query


# =========================================================================
# TC-D06: QueryOptions 기반 빌드
# =========================================================================


@pytest.mark.unit
class TestQueryOptions:
    """from_query_options() 팩토리 메서드 검증."""

    def test_basic_query_options(self) -> None:
        """TC-D06-a: QueryOptions로 기본 쿼리 생성."""
        opts = QueryOptions(
            type="Vessel",
            limit=10,
        )
        query, params = CypherBuilder.from_query_options(opts).build()
        assert "MATCH (v:Vessel)" in query
        assert "RETURN v" in query
        assert "LIMIT 10" in query

    def test_query_options_with_filter(self) -> None:
        """TC-D06-b: QueryOptions filter 적용."""
        opts = QueryOptions(
            type="Vessel",
            filter={
                "vesselType": {"equals": "ContainerShip"},
            },
            limit=5,
        )
        query, params = CypherBuilder.from_query_options(opts).build()
        assert "WHERE" in query
        assert "v.vesselType" in query
        # 파라미터에 ContainerShip 값이 있어야 함
        assert "ContainerShip" in params.values()

    def test_query_options_with_properties(self) -> None:
        """TC-D06-c: QueryOptions properties (SELECT 대상) 적용."""
        opts = QueryOptions(
            type="Vessel",
            properties=["name", "mmsi", "vesselType"],
        )
        query, params = CypherBuilder.from_query_options(opts).build()
        assert "v.name AS name" in query
        assert "v.mmsi AS mmsi" in query
        assert "v.vesselType AS vesselType" in query

    def test_query_options_with_order(self) -> None:
        """TC-D06-d: QueryOptions order_by 적용."""
        opts = QueryOptions(
            type="Vessel",
            order_by={"name": "asc"},
        )
        query, params = CypherBuilder.from_query_options(opts).build()
        assert "ORDER BY" in query
        assert "v.name ASC" in query

    def test_query_options_with_offset(self) -> None:
        """TC-D06-e: QueryOptions offset (SKIP) 적용."""
        opts = QueryOptions(
            type="Vessel",
            offset=10,
            limit=5,
        )
        query, params = CypherBuilder.from_query_options(opts).build()
        assert "SKIP 10" in query
        assert "LIMIT 5" in query


# =========================================================================
# TC-D07: 공간 쿼리 (nearby_entities)
# =========================================================================


@pytest.mark.unit
class TestSpatialQueries:
    """공간 쿼리 관련 메서드 검증."""

    def test_nearby_entities(self) -> None:
        """TC-D07-a: nearby_entities() 반환 Cypher에 point.distance 포함."""
        query, params = CypherBuilder.nearby_entities(
            entity_type="Vessel",
            center_lat=35.1028,
            center_lon=129.0403,
            radius_km=50.0,
            limit=20,
        )
        assert "point.distance" in query, "point.distance 미포함"
        assert "Vessel" in query
        assert params["lat"] == 35.1028
        assert params["lon"] == 129.0403
        assert params["radius"] == 50000.0  # km -> m 변환

    def test_nearby_entities_limit(self) -> None:
        """TC-D07-b: nearby_entities() LIMIT 적용."""
        query, _ = CypherBuilder.nearby_entities(
            entity_type="Port",
            center_lat=35.0,
            center_lon=129.0,
            radius_km=10.0,
            limit=5,
        )
        assert "LIMIT 5" in query

    def test_where_within_distance(self) -> None:
        """TC-D07-c: where_within_distance() 체인 방식 공간 쿼리."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_within_distance("v", "currentLocation", 35.1, 129.0, 30000)
            .return_("v")
            .build()
        )
        assert "point.distance" in query
        assert "currentLocation" in query
        # 파라미터에 위도, 경도, 반경이 존재해야 함
        param_values = list(params.values())
        assert 35.1 in param_values
        assert 129.0 in param_values
        assert 30000 in param_values

    def test_where_within_bounds(self) -> None:
        """TC-D07-d: where_within_bounds() 바운딩 박스 공간 쿼리."""
        query, _ = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_within_bounds("v", "currentLocation", 34.0, 128.0, 36.0, 130.0)
            .return_("v")
            .build()
        )
        assert "latitude" in query
        assert "longitude" in query
        # 4개 조건이 모두 있어야 함
        assert ">=" in query
        assert "<=" in query


# =========================================================================
# TC-D08: 전문 검색 (fulltext_search)
# =========================================================================


@pytest.mark.unit
class TestFulltextSearch:
    """fulltext_search() 검증."""

    def test_fulltext_search(self) -> None:
        """TC-D08-a: fulltext_search() Cypher 구조 검증."""
        query, params = CypherBuilder.fulltext_search(
            index_name="vesselSearch",
            search_term="container",
            limit=10,
        )
        assert "db.index.fulltext.queryNodes" in query, "fulltext 호출 미포함"
        assert "$indexName" in query
        assert "$searchTerm" in query
        assert "LIMIT 10" in query
        assert params["indexName"] == "vesselSearch"
        assert params["searchTerm"] == "container"

    def test_fulltext_search_custom_limit(self) -> None:
        """TC-D08-b: fulltext_search() 커스텀 LIMIT."""
        query, _ = CypherBuilder.fulltext_search(
            index_name="docSearch",
            search_term="KRISO",
            limit=50,
        )
        assert "LIMIT 50" in query


# =========================================================================
# TC-D09: where_property 필터 연산자
# =========================================================================


@pytest.mark.unit
class TestWherePropertyOperators:
    """where_property() 각 필터 연산자 검증."""

    def test_equals_operator(self) -> None:
        """TC-D09-a: equals 연산자."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_property("v", "vesselType", QueryFilter(equals="Tanker"))
            .return_("v")
            .build()
        )
        assert "v.vesselType = $" in query
        assert "Tanker" in params.values()

    def test_contains_operator(self) -> None:
        """TC-D09-b: contains 연산자."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_property("v", "name", QueryFilter(contains="HMM"))
            .return_("v")
            .build()
        )
        assert "CONTAINS" in query
        assert "HMM" in params.values()

    def test_gt_lt_operators(self) -> None:
        """TC-D09-c: greater_than / less_than 연산자."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_property("v", "grossTonnage", QueryFilter(gt=10000, lt=50000))
            .return_("v")
            .build()
        )
        assert ">" in query
        assert "<" in query
        assert 10000 in params.values()
        assert 50000 in params.values()

    def test_in_operator(self) -> None:
        """TC-D09-d: in_ 연산자."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_property("v", "flag", QueryFilter(in_=["KR", "JP", "CN"]))
            .return_("v")
            .build()
        )
        assert "IN" in query
        assert ["KR", "JP", "CN"] in params.values()

    def test_is_null_operator(self) -> None:
        """TC-D09-e: is_null 연산자."""
        query, _ = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_property("v", "destination", QueryFilter(is_null=True))
            .return_("v")
            .build()
        )
        assert "IS NULL" in query

    def test_is_not_null_operator(self) -> None:
        """TC-D09-f: is_not_null 연산자."""
        query, _ = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_property("v", "currentLocation", QueryFilter(is_not_null=True))
            .return_("v")
            .build()
        )
        assert "IS NOT NULL" in query

    def test_starts_with_operator(self) -> None:
        """TC-D09-g: starts_with 연산자."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_property("v", "name", QueryFilter(starts_with="HMM"))
            .return_("v")
            .build()
        )
        assert "STARTS WITH" in query

    def test_regex_operator(self) -> None:
        """TC-D09-h: matches_regex 연산자."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_property("v", "name", QueryFilter(matches_regex=".*선$"))
            .return_("v")
            .build()
        )
        assert "=~" in query
        assert ".*선$" in params.values()

    def test_dict_filter_spec(self) -> None:
        """TC-D09-i: dict로 전달된 filter_spec 처리."""
        query, params = (
            CypherBuilder()
            .match("(v:Vessel)")
            .where_property("v", "vesselType", {"equals": "ContainerShip"})
            .return_("v")
            .build()
        )
        assert "v.vesselType = $" in query
        assert "ContainerShip" in params.values()


# =========================================================================
# TC-D10: find_related_objects 방향
# =========================================================================


@pytest.mark.unit
class TestFindRelatedObjects:
    """find_related_objects() 방향별 쿼리 검증."""

    def test_outgoing_direction(self) -> None:
        """TC-D10-a: outgoing 방향."""
        query, params = CypherBuilder.find_related_objects(
            object_id="vessel-001",
            relationship_type="ON_VOYAGE",
            direction="outgoing",
        )
        assert "-[:ON_VOYAGE]->" in query
        assert params["objectId"] == "vessel-001"

    def test_incoming_direction(self) -> None:
        """TC-D10-b: incoming 방향."""
        query, params = CypherBuilder.find_related_objects(
            object_id="port-001",
            relationship_type="TO_PORT",
            direction="incoming",
        )
        assert "<-[:TO_PORT]-" in query

    def test_both_direction(self) -> None:
        """TC-D10-c: both (양방향)."""
        query, params = CypherBuilder.find_related_objects(
            object_id="node-001",
            relationship_type="CONNECTS",
            direction="both",
        )
        assert "-[:CONNECTS]-" in query
        # 방향 화살표가 없어야 함 (양방향)
        assert "->" not in query or "<-" not in query

    def test_find_shortest_path(self) -> None:
        """TC-D10-d: find_shortest_path() 쿼리 생성."""
        query, params = CypherBuilder.find_shortest_path(
            from_id="A",
            to_id="B",
            max_depth=3,
        )
        assert "shortestPath" in query
        assert params["fromId"] == "A"
        assert params["toId"] == "B"
        assert "*..3" in query

    def test_call_clause(self) -> None:
        """TC-D10-e: CALL 절 생성."""
        query, _ = CypherBuilder().call("db.labels() YIELD label").return_("label").build()
        assert "CALL db.labels()" in query
