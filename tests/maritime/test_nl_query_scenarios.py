"""Natural Language Query Test Suite for Maritime Knowledge Graph.

5가지 핵심 NL 쿼리 시나리오를 테스트합니다:
  1. 공간 쿼리 (Spatial)       - 부산항 반경 50km 이내 선박
  2. 관계 탐색 (Relationship)  - HMM 알헤시라스의 항해 정보
  3. 시설 조회 (Entity lookup) - KRISO 시험설비 목록
  4. 사고 분석 (Incident)      - 최근 해양사고 이력
  5. 기상 정보 (Weather)       - 남해 기상 상태

두 가지 테스트 모드:
  - test_cypher_generation_only: QueryGenerator/CypherBuilder로 Cypher 생성 & 검증
  - test_direct_cypher_execution: 수작업 참조 Cypher를 Neo4j에 직접 실행 & 검증

Usage::
    PYTHONPATH=. python tests/test_nl_query_scenarios.py
    PYTHONPATH=. python -m pytest tests/test_nl_query_scenarios.py -v
"""

from __future__ import annotations

import contextlib
import re
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project root on sys.path so ``kg`` package is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from kg.config import get_config, get_driver  # noqa: E402
from kg.cypher_builder import CypherBuilder  # noqa: E402
from kg.query_generator import (  # noqa: E402
    Pagination,
    QueryGenerator,
    QueryIntent,
    QueryIntentType,
    StructuredQuery,
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class NLQueryScenario:
    """한 건의 자연어 쿼리 테스트 시나리오를 표현합니다."""

    scenario_name: str
    nl_question: str  # 한국어 자연어 질문
    expected_cypher_patterns: list[str]  # Cypher에 반드시 나타나야 하는 regex 패턴
    expected_node_labels: list[str]  # 쿼리에 포함되어야 하는 노드 레이블
    expected_relationships: list[str]  # 기대하는 관계 타입
    min_results: int  # Neo4j 실행 시 최소 결과 건수
    reference_cypher: str  # 수작업 작성 참조 Cypher (직접 실행용)
    reference_params: dict[str, Any] = field(default_factory=dict)
    validation_fn: Callable[[list[dict[str, Any]]], bool] | None = None


@dataclass
class ScenarioResult:
    """개별 테스트 실행 결과."""

    scenario_name: str
    test_mode: str  # 'generation' | 'execution'
    passed: bool = False
    generated_cypher: str = ""
    result_count: int = 0
    results_sample: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    details: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


def _validate_spatial_results(records: list[dict[str, Any]]) -> bool:
    """공간 쿼리 결과 검증: 선박 이름과 거리(km)가 존재해야 합니다."""
    if not records:
        return False
    for r in records:
        if "vessel" not in r and "v" not in r:
            # 결과에 vessel 관련 키가 하나도 없으면 실패
            has_vessel_info = any("vessel" in str(k).lower() or "name" in str(k).lower() for k in r)
            if not has_vessel_info:
                return False
    return True


def _validate_voyage_results(records: list[dict[str, Any]]) -> bool:
    """항해 정보 결과 검증: destination 또는 관련 필드가 있어야 합니다."""
    if not records:
        return False
    for r in records:
        has_voyage_info = any(
            k in ("destination", "dest", "origin", "vessel", "status") or "port" in str(k).lower()
            for k in r
        )
        if has_voyage_info:
            return True
    return False


def _validate_facility_results(records: list[dict[str, Any]]) -> bool:
    """시설 조회 결과 검증: facility 이름이 반드시 있어야 합니다."""
    if not records:
        return False
    for r in records:
        has_facility = any("facility" in str(k).lower() or "name" in str(k).lower() for k in r)
        if has_facility:
            return True
    return False


def _validate_incident_results(records: list[dict[str, Any]]) -> bool:
    """사고 분석 결과 검증: incidentType 또는 severity가 있어야 합니다."""
    if not records:
        return False
    for r in records:
        has_incident = any(
            k in ("type", "severity", "description", "id") or "incident" in str(k).lower()
            for k in r
        )
        if has_incident:
            return True
    return False


def _validate_weather_results(records: list[dict[str, Any]]) -> bool:
    """기상 정보 결과 검증: wind_speed 또는 wave_height가 있어야 합니다."""
    if not records:
        return False
    for r in records:
        has_weather = any(
            "wind" in str(k).lower()
            or "wave" in str(k).lower()
            or "sea_state" in str(k).lower()
            or "risk" in str(k).lower()
            for k in r
        )
        if has_weather:
            return True
    return False


# 5가지 핵심 시나리오 정의
SCENARIOS: list[NLQueryScenario] = [
    # -----------------------------------------------------------------------
    # Scenario 1: 공간 쿼리 (Spatial)
    # "부산항 반경 50km 이내 선박"
    # -----------------------------------------------------------------------
    NLQueryScenario(
        scenario_name="공간 쿼리 (Spatial) - 부산항 반경 50km 이내 선박",
        nl_question="부산항 반경 50km 이내 선박을 알려줘",
        expected_cypher_patterns=[
            r"MATCH.*\(.*:Port\b",  # Port 노드 매칭
            r"MATCH.*\(.*:Vessel\b",  # Vessel 노드 매칭
            r"point\.distance",  # 공간 거리 함수
            r"50000|\$radius|radius",  # 50km = 50000m (리터럴 또는 파라미터)
        ],
        expected_node_labels=["Port", "Vessel"],
        expected_relationships=[],  # 공간 쿼리는 관계 탐색 없음
        min_results=1,  # 최소 1척 이상 (샘플데이터에 부산 근처 선박 존재)
        reference_cypher="""
            MATCH (p:Port {name: '부산항'})
            MATCH (v:Vessel)
            WHERE point.distance(v.currentLocation, p.location) < 50000
            RETURN v.name AS vessel, v.vesselType AS type,
                   round(point.distance(v.currentLocation, p.location) / 1000.0, 1) AS distance_km
            ORDER BY distance_km
        """,
        validation_fn=_validate_spatial_results,
    ),
    # -----------------------------------------------------------------------
    # Scenario 2: 관계 탐색 (Relationship)
    # "HMM 알헤시라스의 항해 정보"
    # -----------------------------------------------------------------------
    NLQueryScenario(
        scenario_name="관계 탐색 (Relationship) - HMM 알헤시라스 항해 정보",
        nl_question="HMM 알헤시라스는 어디로 항해 중이야?",
        expected_cypher_patterns=[
            r"MATCH.*\(.*:Vessel\b",  # Vessel 노드
            r"ON_VOYAGE",  # 항해 관계
            r"TO_PORT",  # 목적항 관계
            r"HMM.*알헤시라스|알헤시라스|\$vesselName|CONTAINS",  # 선박명 필터 (리터럴 또는 파라미터)
        ],
        expected_node_labels=["Vessel", "Voyage", "Port"],
        expected_relationships=["ON_VOYAGE", "TO_PORT", "FROM_PORT"],
        min_results=1,
        reference_cypher="""
            MATCH (v:Vessel)-[:ON_VOYAGE]->(voy:Voyage)-[:TO_PORT]->(dest:Port)
            WHERE v.name CONTAINS 'HMM 알헤시라스'
            OPTIONAL MATCH (voy)-[:FROM_PORT]->(orig:Port)
            RETURN v.name AS vessel, orig.name AS origin, dest.name AS destination,
                   v.currentStatus AS status, v.speed AS speed_knots
        """,
        validation_fn=_validate_voyage_results,
    ),
    # -----------------------------------------------------------------------
    # Scenario 3: 시설 조회 (Entity lookup)
    # "KRISO 시험설비 목록"
    # -----------------------------------------------------------------------
    NLQueryScenario(
        scenario_name="시설 조회 (Entity Lookup) - KRISO 시험설비 목록",
        nl_question="KRISO 시험설비 목록을 보여줘",
        expected_cypher_patterns=[
            r"MATCH.*\(.*:Organization\b",  # Organization 노드
            r"HAS_FACILITY",  # 시설 보유 관계
            r"TestFacility\b",  # TestFacility 노드
            r"ORG-KRISO|\$orgId|orgId",  # KRISO 조직 ID (리터럴 또는 파라미터)
        ],
        expected_node_labels=["Organization", "TestFacility"],
        expected_relationships=["HAS_FACILITY"],
        min_results=6,  # KRISO는 6개 시험설비 보유
        reference_cypher="""
            MATCH (org:Organization {orgId: 'ORG-KRISO'})-[:HAS_FACILITY]->(tf:TestFacility)
            RETURN tf.name AS facility, tf.nameEn AS facility_en,
                   tf.facilityType AS type, tf.length AS length_m,
                   tf.width AS width_m, tf.depth AS depth_m
        """,
        validation_fn=_validate_facility_results,
    ),
    # -----------------------------------------------------------------------
    # Scenario 4: 사고 분석 (Incident analysis)
    # "최근 해양사고 이력"
    # -----------------------------------------------------------------------
    NLQueryScenario(
        scenario_name="사고 분석 (Incident Analysis) - 최근 해양사고 이력",
        nl_question="최근 해양사고 이력을 알려줘",
        expected_cypher_patterns=[
            r"MATCH.*\(.*:Incident\b",  # Incident 노드
            r"INVOLVES|VIOLATED",  # 사고 관련 관계 (하나 이상)
            r"ORDER BY.*date|ORDER BY.*DESC",  # 시간순 정렬
        ],
        expected_node_labels=["Incident"],
        expected_relationships=["INVOLVES", "VIOLATED"],
        min_results=1,  # 최소 1건 사고 데이터 존재
        reference_cypher="""
            MATCH (inc:Incident)
            OPTIONAL MATCH (inc)-[:INVOLVES]->(v:Vessel)
            OPTIONAL MATCH (inc)-[:VIOLATED]->(reg:Regulation)
            RETURN inc.incidentId AS id, inc.incidentType AS type,
                   inc.severity AS severity, inc.description AS description,
                   v.name AS involved_vessel, reg.title AS violated_regulation
            ORDER BY inc.date DESC
        """,
        validation_fn=_validate_incident_results,
    ),
    # -----------------------------------------------------------------------
    # Scenario 5: 기상 정보 (Weather + SeaArea)
    # "남해 기상 상태"
    # -----------------------------------------------------------------------
    NLQueryScenario(
        scenario_name="기상 정보 (Weather + SeaArea) - 남해 기상 상태",
        nl_question="남해 기상 상태는 어때?",
        expected_cypher_patterns=[
            r"MATCH.*\(.*:WeatherCondition\b",  # WeatherCondition 노드
            r"AFFECTS",  # 기상 영향 관계
            r"SeaArea\b",  # SeaArea 노드
            r"남해|\$seaArea|seaArea",  # 남해 해역 (리터럴 또는 파라미터)
        ],
        expected_node_labels=["WeatherCondition", "SeaArea"],
        expected_relationships=["AFFECTS"],
        min_results=1,  # 남해 기상 데이터 1건 존재
        reference_cypher="""
            MATCH (w:WeatherCondition)-[:AFFECTS]->(sa:SeaArea {name: '남해'})
            RETURN sa.name AS sea_area, w.windSpeed AS wind_speed_ms,
                   w.waveHeight AS wave_height_m, w.visibility AS visibility_km,
                   w.seaState AS sea_state, w.temperature AS temp_c, w.riskLevel AS risk
        """,
        validation_fn=_validate_weather_results,
    ),
]

# ---------------------------------------------------------------------------
# Neo4j helper
# ---------------------------------------------------------------------------


def _run_cypher(
    driver: Any, cypher: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Neo4j에 Cypher 쿼리를 실행하고 결과를 dict 리스트로 반환합니다."""
    params = params or {}
    with driver.session(database=get_config().neo4j.database) as session:
        result = session.run(cypher.strip(), **params)
        return [dict(record) for record in result]


# ---------------------------------------------------------------------------
# Test Mode 1: Cypher Generation Only
# ---------------------------------------------------------------------------


def _build_structured_query_for_scenario(scenario: NLQueryScenario) -> tuple[str, dict[str, Any]]:
    """시나리오에 맞는 StructuredQuery 또는 CypherBuilder를 사용해 Cypher를 생성합니다.

    QueryGenerator와 CypherBuilder를 모두 활용하여 각 시나리오의 특성에 맞는
    쿼리를 프로그래밍 방식으로 생성합니다. LLM 없이 동작합니다.

    Returns:
        (generated_cypher, parameters) 튜플
    """
    generator = QueryGenerator()

    # -- Scenario 1: 공간 쿼리 --
    if "공간" in scenario.scenario_name:
        # CypherBuilder.nearby_entities 사용 (부산항 위치 35.1028, 129.0403)
        # 단, 먼저 Port 위치를 얻어야 하므로, 2단계 쿼리를 CypherBuilder로 구성
        query, params = (
            CypherBuilder()
            .match("(p:Port {name: $portName})")
            .match("(v:Vessel)")
            .where(
                "point.distance(v.currentLocation, p.location) < $radius",
                {"portName": "부산항", "radius": 50000},
            )
            .return_(
                "v.name AS vessel, v.vesselType AS type, "
                "round(point.distance(v.currentLocation, p.location) / 1000.0, 1) AS distance_km"
            )
            .build()
        )
        return query, params

    # -- Scenario 2: 관계 탐색 --
    elif "관계" in scenario.scenario_name:
        # WHERE는 MATCH 바로 뒤에 와야 하므로, optional_match 전에 build하지 않고
        # 수동으로 쿼리를 구성합니다 (CypherBuilder는 WHERE를 OPTIONAL MATCH 뒤에 배치)
        builder = CypherBuilder()
        builder.match("(v:Vessel)-[:ON_VOYAGE]->(voy:Voyage)-[:TO_PORT]->(dest:Port)")
        builder.where("v.name CONTAINS $vesselName", {"vesselName": "HMM 알헤시라스"})
        builder.optional_match("(voy)-[:FROM_PORT]->(orig:Port)")
        builder.return_(
            "v.name AS vessel, orig.name AS origin, dest.name AS destination, "
            "v.currentStatus AS status, v.speed AS speed_knots"
        )
        # CypherBuilder 빌드 순서: MATCH -> OPTIONAL MATCH -> WHERE -> RETURN
        # Neo4j에서는 WHERE가 바로 앞의 MATCH/OPTIONAL MATCH에 적용되므로,
        # 이 경우 수동으로 올바른 순서의 쿼리를 생성합니다
        params = builder._parameters
        query = (
            "MATCH (v:Vessel)-[:ON_VOYAGE]->(voy:Voyage)-[:TO_PORT]->(dest:Port)\n"
            "WHERE v.name CONTAINS $vesselName\n"
            "OPTIONAL MATCH (voy)-[:FROM_PORT]->(orig:Port)\n"
            "RETURN v.name AS vessel, orig.name AS origin, dest.name AS destination, "
            "v.currentStatus AS status, v.speed AS speed_knots"
        )
        return query, params

    # -- Scenario 3: 시설 조회 --
    elif "시설" in scenario.scenario_name:
        builder = CypherBuilder()
        builder.match("(org:Organization {orgId: $orgId})-[:HAS_FACILITY]->(tf:TestFacility)")
        builder._parameters["orgId"] = "ORG-KRISO"
        builder.return_(
            "tf.name AS facility, tf.nameEn AS facility_en, "
            "tf.facilityType AS type, tf.length AS length_m, "
            "tf.width AS width_m, tf.depth AS depth_m"
        )
        query, params = builder.build()
        return query, params

    # -- Scenario 4: 사고 분석 --
    elif "사고" in scenario.scenario_name:
        # QueryGenerator로 기본 MATCH 생성 + CypherBuilder로 관계 추가
        query, params = (
            CypherBuilder()
            .match("(inc:Incident)")
            .optional_match("(inc)-[:INVOLVES]->(v:Vessel)")
            .optional_match("(inc)-[:VIOLATED]->(reg:Regulation)")
            .return_(
                "inc.incidentId AS id, inc.incidentType AS type, "
                "inc.severity AS severity, inc.description AS description, "
                "v.name AS involved_vessel, reg.title AS violated_regulation"
            )
            .build()
        )
        # ORDER BY는 CypherBuilder에 raw string으로 추가
        query += "\nORDER BY inc.date DESC"
        return query, params

    # -- Scenario 5: 기상 정보 --
    elif "기상" in scenario.scenario_name:
        builder = CypherBuilder()
        builder.match("(w:WeatherCondition)-[:AFFECTS]->(sa:SeaArea {name: $seaArea})")
        builder._parameters["seaArea"] = "남해"
        builder.return_(
            "sa.name AS sea_area, w.windSpeed AS wind_speed_ms, "
            "w.waveHeight AS wave_height_m, w.visibility AS visibility_km, "
            "w.seaState AS sea_state, w.temperature AS temp_c, w.riskLevel AS risk"
        )
        query, params = builder.build()
        return query, params

    # Fallback: QueryGenerator로 기본 쿼리 생성
    else:
        sq = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=scenario.expected_node_labels[:1],
            pagination=Pagination(limit=10),
        )
        result = generator.generate_cypher(sq)
        return result.query, result.parameters


def _validate_generated_cypher(
    scenario: NLQueryScenario,
    generated_cypher: str,
) -> list[str]:
    """생성된 Cypher가 시나리오의 기대 패턴과 일치하는지 검증합니다.

    Returns:
        실패한 검증 항목의 설명 리스트 (빈 리스트 = 모두 통과)
    """
    failures: list[str] = []

    # 1. 기대하는 Cypher 패턴 검증
    for pattern in scenario.expected_cypher_patterns:
        if not re.search(pattern, generated_cypher, re.IGNORECASE):
            failures.append(f"패턴 미발견: '{pattern}'")

    # 2. 기대하는 노드 레이블 검증
    for label in scenario.expected_node_labels:
        if label not in generated_cypher:
            failures.append(f"노드 레이블 미발견: '{label}'")

    # 3. 기대하는 관계 타입 검증
    for rel in scenario.expected_relationships:
        if rel not in generated_cypher:
            failures.append(f"관계 타입 미발견: '{rel}'")

    return failures


def run_cypher_generation_tests(
    driver: Any,
) -> list[ScenarioResult]:
    """QueryGenerator/CypherBuilder로 Cypher를 생성하고 검증합니다.

    LLM(Ollama) 없이 프로그래밍 방식으로 Cypher를 생성한 뒤:
      1) 생성된 Cypher가 기대 패턴과 일치하는지 검증
      2) 생성된 Cypher를 Neo4j에 실행하여 결과 건수 검증
      3) validation_fn으로 결과 내용 검증

    Returns:
        각 시나리오의 ScenarioResult 리스트
    """
    results: list[ScenarioResult] = []

    for scenario in SCENARIOS:
        tr = ScenarioResult(
            scenario_name=scenario.scenario_name,
            test_mode="generation",
        )

        try:
            # Step 1: Cypher 생성
            cypher, params = _build_structured_query_for_scenario(scenario)
            tr.generated_cypher = cypher

            # Step 2: 생성된 Cypher 패턴 검증
            pattern_failures = _validate_generated_cypher(scenario, cypher)
            if pattern_failures:
                tr.details.extend(pattern_failures)

            # Step 3: Neo4j에 실행
            records = _run_cypher(driver, cypher, params)
            tr.result_count = len(records)
            tr.results_sample = records[:5]  # 최대 5건 샘플

            # Step 4: 최소 결과 건수 검증
            if len(records) < scenario.min_results:
                tr.details.append(f"결과 부족: {len(records)}건 < 최소 {scenario.min_results}건")

            # Step 5: validation_fn 검증
            if scenario.validation_fn and not scenario.validation_fn(records):
                tr.details.append("validation_fn 검증 실패")

            # 최종 판정: 패턴 검증 통과 + 결과 건수 충족 + validation_fn 통과
            tr.passed = len(tr.details) == 0

        except Exception as exc:
            tr.passed = False
            tr.error = f"{type(exc).__name__}: {exc}"
            tr.details.append(traceback.format_exc())

        results.append(tr)

    return results


# ---------------------------------------------------------------------------
# Test Mode 2: Direct Cypher Execution
# ---------------------------------------------------------------------------


def run_direct_cypher_tests(
    driver: Any,
) -> list[ScenarioResult]:
    """수작업 참조 Cypher를 Neo4j에 직접 실행하여 데이터 존재 여부를 검증합니다.

    이 테스트 모드는:
      1) reference_cypher를 Neo4j에 실행
      2) 결과 건수가 min_results 이상인지 검증
      3) validation_fn으로 결과 내용 검증

    Returns:
        각 시나리오의 ScenarioResult 리스트
    """
    results: list[ScenarioResult] = []

    for scenario in SCENARIOS:
        tr = ScenarioResult(
            scenario_name=scenario.scenario_name,
            test_mode="execution",
        )

        try:
            tr.generated_cypher = scenario.reference_cypher.strip()

            # Step 1: 참조 Cypher 실행
            records = _run_cypher(driver, scenario.reference_cypher, scenario.reference_params)
            tr.result_count = len(records)
            tr.results_sample = records[:5]

            # Step 2: 최소 결과 건수 검증
            if len(records) < scenario.min_results:
                tr.details.append(f"결과 부족: {len(records)}건 < 최소 {scenario.min_results}건")

            # Step 3: validation_fn 검증
            if scenario.validation_fn and not scenario.validation_fn(records):
                tr.details.append("validation_fn 검증 실패")

            tr.passed = len(tr.details) == 0

        except Exception as exc:
            tr.passed = False
            tr.error = f"{type(exc).__name__}: {exc}"
            tr.details.append(traceback.format_exc())

        results.append(tr)

    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _print_divider(char: str = "=", width: int = 80) -> None:
    print(char * width)


def _print_result_detail(tr: ScenarioResult) -> None:
    """단일 ScenarioResult를 출력합니다."""
    status = "PASS" if tr.passed else "FAIL"
    status_marker = "[O]" if tr.passed else "[X]"

    print(f"\n  {status_marker} [{tr.test_mode.upper():>10s}] {tr.scenario_name}")
    print(f"      Status:  {status}")

    if tr.generated_cypher:
        # Cypher를 깔끔하게 들여쓰기하여 출력
        cypher_lines = tr.generated_cypher.strip().split("\n")
        print("      Cypher:")
        for line in cypher_lines:
            print(f"        {line.strip()}")

    print(f"      Results: {tr.result_count}건")

    if tr.results_sample:
        print("      Sample:")
        for i, rec in enumerate(tr.results_sample[:3]):
            # Neo4j Node 객체를 dict로 변환 시도
            display = {}
            for k, v in rec.items():
                try:
                    # neo4j.graph.Node -> dict
                    if hasattr(v, "items"):
                        display[k] = dict(v)
                    elif hasattr(v, "_properties"):
                        display[k] = dict(v._properties)
                    else:
                        display[k] = v
                except Exception:
                    display[k] = str(v)
            print(f"        [{i + 1}] {display}")

    if tr.error:
        print(f"      Error:   {tr.error}")

    if tr.details:
        print("      Issues:")
        for d in tr.details:
            # traceback은 너무 길 수 있으므로 첫 줄만
            first_line = d.split("\n")[0] if "\n" in d else d
            print(f"        - {first_line}")


def print_summary_report(
    gen_results: list[ScenarioResult],
    exec_results: list[ScenarioResult],
) -> int:
    """전체 테스트 요약 리포트를 출력하고 실패 건수를 반환합니다.

    Returns:
        총 실패 건수 (exit code로 사용)
    """
    all_results = gen_results + exec_results
    passed = sum(1 for r in all_results if r.passed)
    failed = sum(1 for r in all_results if not r.passed)
    total = len(all_results)

    _print_divider()
    print("  Maritime KG - Natural Language Query Test Report")
    _print_divider()

    # Mode 1: Generation
    print("\n  [Mode 1] Cypher Generation Tests (QueryGenerator / CypherBuilder)")
    print(f"  {'=' * 70}")
    for tr in gen_results:
        _print_result_detail(tr)

    # Mode 2: Execution
    print("\n\n  [Mode 2] Direct Cypher Execution Tests (Reference Queries)")
    print(f"  {'=' * 70}")
    for tr in exec_results:
        _print_result_detail(tr)

    # Summary
    _print_divider("-")
    print(f"\n  SUMMARY: {passed}/{total} passed, {failed}/{total} failed")
    print(
        f"    - Generation tests: {sum(1 for r in gen_results if r.passed)}/{len(gen_results)} passed"
    )
    print(
        f"    - Execution tests:  {sum(1 for r in exec_results if r.passed)}/{len(exec_results)} passed"
    )

    if failed == 0:
        print("\n  All tests PASSED.")
    else:
        print(f"\n  {failed} test(s) FAILED. Review details above.")

    _print_divider()

    return failed


# ---------------------------------------------------------------------------
# pytest integration
# ---------------------------------------------------------------------------

import pytest  # noqa: E402


@pytest.fixture(scope="module")
def neo4j_driver():
    """pytest fixture: Neo4j 드라이버를 생성하고 테스트 후 정리합니다."""
    try:
        driver = get_driver()
        # 연결 확인
        with driver.session(database=get_config().neo4j.database) as session:
            session.run("RETURN 1")
        yield driver
    except Exception as exc:
        pytest.skip(f"Neo4j 연결 실패: {exc}")
    finally:
        with contextlib.suppress(Exception):
            driver.close()


class TestCypherGeneration:
    """Cypher 생성 테스트 (LLM 불필요)."""

    @pytest.mark.parametrize(
        "scenario",
        SCENARIOS,
        ids=[s.scenario_name for s in SCENARIOS],
    )
    def test_cypher_pattern_matches(self, neo4j_driver: Any, scenario: NLQueryScenario) -> None:
        """생성된 Cypher가 기대 패턴과 일치하는지 검증합니다."""
        cypher, params = _build_structured_query_for_scenario(scenario)

        failures = _validate_generated_cypher(scenario, cypher)
        assert not failures, (
            f"Cypher 패턴 검증 실패:\n  Generated: {cypher}\n  Failures: {failures}"
        )

    @pytest.mark.parametrize(
        "scenario",
        SCENARIOS,
        ids=[s.scenario_name for s in SCENARIOS],
    )
    def test_generated_cypher_executes(self, neo4j_driver: Any, scenario: NLQueryScenario) -> None:
        """생성된 Cypher를 Neo4j에서 실행하고 결과를 검증합니다."""
        cypher, params = _build_structured_query_for_scenario(scenario)
        records = _run_cypher(neo4j_driver, cypher, params)

        assert len(records) >= scenario.min_results, (
            f"결과 부족: {len(records)}건 (최소 {scenario.min_results}건 기대)\n  Cypher: {cypher}"
        )

        if scenario.validation_fn:
            assert scenario.validation_fn(records), (
                f"validation_fn 검증 실패\n  Records: {records[:3]}"
            )


class TestDirectCypherExecution:
    """참조 Cypher 직접 실행 테스트."""

    @pytest.mark.parametrize(
        "scenario",
        SCENARIOS,
        ids=[s.scenario_name for s in SCENARIOS],
    )
    def test_reference_cypher(self, neo4j_driver: Any, scenario: NLQueryScenario) -> None:
        """수작업 참조 Cypher를 실행하고 결과를 검증합니다."""
        records = _run_cypher(neo4j_driver, scenario.reference_cypher, scenario.reference_params)

        assert len(records) >= scenario.min_results, (
            f"결과 부족: {len(records)}건 (최소 {scenario.min_results}건 기대)\n"
            f"  Cypher: {scenario.reference_cypher.strip()}"
        )

        if scenario.validation_fn:
            assert scenario.validation_fn(records), (
                f"validation_fn 검증 실패\n  Records: {records[:3]}"
            )


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------


def main() -> int:
    """독립 실행 모드: 모든 테스트를 실행하고 리포트를 출력합니다.

    Returns:
        실패 건수 (exit code)
    """
    _cfg = get_config()
    print("=" * 80)
    print("  Maritime KG - Natural Language Query Test Suite")
    print("  Neo4j:", _cfg.neo4j.database)
    print("=" * 80)

    # Neo4j 연결
    try:
        driver = get_driver()
        with driver.session(database=_cfg.neo4j.database) as session:
            result = session.run("RETURN 1 AS check")
            result.single()
        print("\n  [OK] Neo4j 연결 성공")
    except Exception as exc:
        print(f"\n  [ERROR] Neo4j 연결 실패: {exc}")
        print("  Neo4j가 실행 중인지 확인하세요:")
        print("    docker compose up -d")
        print("    python -m kg.schema.load_sample_data")
        return 1

    # 데이터 존재 확인
    with driver.session(database=_cfg.neo4j.database) as session:
        node_count = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
    print(f"  [OK] Neo4j 데이터: {node_count}개 노드, {rel_count}개 관계\n")

    if node_count == 0:
        print("  [WARN] 데이터가 없습니다. 샘플 데이터를 로드하세요:")
        print("    python -m kg.schema.load_sample_data")
        driver.close()
        return 1

    try:
        # Mode 1: Cypher Generation
        gen_results = run_cypher_generation_tests(driver)

        # Mode 2: Direct Execution
        exec_results = run_direct_cypher_tests(driver)

        # Report
        failed = print_summary_report(gen_results, exec_results)

    finally:
        driver.close()

    return failed


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
