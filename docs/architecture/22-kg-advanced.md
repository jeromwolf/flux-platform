# 22. 지식그래프 고급 아키텍처

[← 시각화 아키텍처](./21-visualization.md) | [→ README](./README.md)

---

## 22.1 개요

IMSP의 지식그래프 엔진(`core/kg/`)은 Text2Cypher 파이프라인, 온톨로지 프레임워크, ELT, 리니지 등
기본 모듈을 갖추고 있다. 그러나 5개년에 걸쳐 10K → 2M+ 노드로 성장하는 KG를 운영하려면,
시간 모델링, 그래프 알고리즘, 추론/검증, 메타데이터 관리, 스트리밍 업데이트 등 **고급 기능**의
단계적 확장이 필수적이다.

본 문서는 현재 구현된 모듈과 향후 필요한 고급 모듈을 명확히 구분하고,
각 모듈의 설계 원칙, 데이터 모델, API 인터페이스, 코드 매핑, 구현 로드맵을 기술한다.

### 현재 구현 vs 필요 모듈

```
core/kg/
├── ✅ cypher_builder.py         # Fluent Cypher 빌더 (Builder Pattern)
├── ✅ query_generator.py        # 다중 언어 쿼리 생성기
├── ✅ pipeline.py               # Text2Cypher 5단계 파이프라인
├── ✅ cypher_validator.py       # Cypher 검증 (6가지: syntax/injection/schema/param/complexity/readonly)
├── ✅ cypher_corrector.py       # 규칙 기반 Cypher 교정
├── ✅ quality_gate.py           # KG 품질 게이트 (NodeCoverage, PropertyCompleteness 등)
├── ✅ hallucination_detector.py # 온톨로지 기반 환각 감지
├── ✅ ontology_bridge.py        # 온톨로지 ↔ KG 브릿지 (Bridge Pattern)
├── ✅ entity_resolution/        # 3단계 엔티티 해석 (Exact/Fuzzy/Embedding)
├── ✅ embeddings/               # 텍스트 임베딩 (nomic-embed-text, 768d, Ollama)
├── ✅ etl/                      # ELT 파이프라인 + DLQ + LineageRecorder
├── ✅ lineage/                  # W3C PROV-O 리니지 (8 EventTypes, 5 Levels)
├── ✅ rbac/                     # RBAC 정책 + SecureCypherBuilder (Decorator)
├── ✅ n10s/                     # Neosemantics OWL ↔ Neo4j 통합
├── ✅ ontology/core.py          # Palantir Foundry-style 온톨로지 프레임워크
│
├── ⏳ temporal/                 # 시간 지식그래프 (22.2)          — CRITICAL
├── ⏳ algorithms/               # 그래프 알고리즘 (22.3)          — HIGH
├── ⏳ reasoning/                # 추론/검증 엔진 + Axioms (22.4)  — HIGH
├── ⏳ catalog/                  # 메타데이터 카탈로그 (22.5)       — HIGH
├── ⏳ streaming/                # 스트리밍 KG 업데이트 (22.6)      — CRITICAL
├── ⏳ graph_embeddings/         # 그래프 구조 임베딩 (22.7)        — HIGH
├── ⏳ consistency/              # KG 정합성 검증 (22.8)            — HIGH
├── ⏳ ontology/alignment.py     # 온톨로지 정렬 (22.9)             — HIGH
├── ⏳ interchange/              # KG 교환 포맷 (22.10)             — MEDIUM
├── ⏳ analytics/                # 그래프 분석 파이프라인 (22.11)    — MEDIUM
└── ⏳ completion/               # KG 완성 (22.12)                  — MEDIUM (Y3+)
```

### 우선순위 정의

| 등급 | 의미 | 도입 시점 |
|------|------|----------|
| **CRITICAL** | KG 운영의 핵심 전제 조건. 없으면 데이터 무결성/실시간성 불가 | Y1 Q3 ~ Y2 Q1 |
| **HIGH** | KG 고급 분석 및 품질 보증에 필수 | Y2 Q1 ~ Y2 Q3 |
| **MEDIUM** | KG 고도화 및 외부 교환에 필요. 핵심 기능 이후 도입 | Y2 Q3 ~ Y3+ |

---

## 22.2 시간 지식그래프 (Temporal KG) — CRITICAL

### 22.2.1 설계 원칙

IMSP 온톨로지 설계 원칙 3번 "Temporal -- 모든 동적 엔티티에 `validFrom` / `validTo` 적용"을
KG 엔진 수준에서 구현한다. 해사 도메인의 데이터는 본질적으로 시간 의존적이다.
선박은 정박-항해 상태를 반복하고, 기상 조건은 시시각각 변하며, 규제 구역은 시간대별로
적용 여부가 달라진다. 이를 KG에 반영하지 않으면 "3월에 제한되었던 구역"과
"4월에 활성화된 구역"을 구분할 수 없다.

### 22.2.2 시간 모델링 전략

Neo4j에서 시간을 모델링하는 두 가지 접근 방식이 있다.

| 전략 | 설명 | 장점 | 단점 |
|------|------|------|------|
| **속성 기반 시간** | `validFrom`/`validTo`를 노드/관계 속성에 저장 | 구현 간단, 쿼리 성능 양호 | 이력 누적 시 관계 수 증가 |
| **버전 노드 체인** | 상태 변경마다 새 노드 생성 + `NEXT_VERSION` 관계 | 완전한 이력 추적 | 노드 폭증, 쿼리 복잡 |

**IMSP는 속성 기반 시간 모델을 채택한다.** Neo4j CE의 관계 속성 지원을 활용하며,
노드 폭증 없이 시간 범위 쿼리를 효율적으로 처리할 수 있다.

```
(:Vessel {mmsi: 440123456, name: "한바다호"})
    -[:DOCKED_AT {validFrom: datetime('2026-03-20T08:00'), validTo: null}]->
    (:Port {name: "부산항"})

(:Vessel {mmsi: 440123456, name: "한바다호"})
    -[:DOCKED_AT {validFrom: datetime('2026-03-15T10:00'), validTo: datetime('2026-03-20T07:59')}]->
    (:Port {name: "인천항"})
```

위 예시에서 `validTo: null`은 현재 유효한 관계를 의미한다.
시간 범위 인덱스(`CREATE RANGE INDEX ... FOR ()-[r:DOCKED_AT]-() ON (r.validFrom)`)로
쿼리 성능을 확보한다.

### 22.2.3 동적 엔티티 분류

모든 엔티티에 시간 속성을 적용하는 것은 비효율적이다.
변경 빈도와 저장 전략에 따라 4단계로 분류한다.

| 변경 빈도 | 엔티티 예시 | 시간 모델 | 저장소 |
|----------|-----------|----------|--------|
| **초단위** (< 30s) | AIS Position, 속도, 침로 | TimescaleDB 시계열 | TimescaleDB |
| **분~시간** | Vessel Status (정박/항해/정박해제) | 속성 기반 시간 (`validFrom`/`validTo`) | Neo4j |
| **일~주** | Docking Record, Cargo Manifest | 관계 시간 (`validFrom`/`validTo`) | Neo4j |
| **월~년** | Vessel Ownership, Port Certification | 관계 시간 (`validFrom`/`validTo`) | Neo4j |
| **불변** | Port, SeaArea, EEZ, NavigationAid | 시간 없음 (정적 엔티티) | Neo4j |

**핵심 결정:** AIS Position 같은 초고빈도 데이터는 Neo4j가 아닌 TimescaleDB에 저장하고,
Neo4j에는 메타 노드(`(:AISTrack {mmsi, startTime, endTime, pointCount})`)만 생성한다.
상세 설계는 [4. 데이터 아키텍처](./04-data-architecture.md) 4.6절 참조.

### 22.2.4 TemporalCypherBuilder

기존 `CypherBuilder`를 확장하여 시간 조건을 Fluent API로 표현한다.

```python
# core/kg/temporal/builder.py
from __future__ import annotations
from datetime import datetime
from core.kg.cypher_builder import CypherBuilder


class TemporalCypherBuilder(CypherBuilder):
    """CypherBuilder에 시간 필터링을 추가한 확장 빌더.

    Extends CypherBuilder to inject temporal WHERE clauses
    for validFrom/validTo property-based temporal model.
    """

    def __init__(self) -> None:
        super().__init__()
        self._temporal_filters: list[dict] = []

    def at_time(self, timestamp: datetime, rel_alias: str = "r") -> "TemporalCypherBuilder":
        """특정 시점의 KG 상태 조회.

        Args:
            timestamp: 조회 시점
            rel_alias: 관계 alias (기본 "r")

        Returns:
            Self for chaining
        """
        self._temporal_filters.append({
            "type": "at_time",
            "timestamp": timestamp,
            "alias": rel_alias,
        })
        return self

    def between(
        self, start: datetime, end: datetime, rel_alias: str = "r"
    ) -> "TemporalCypherBuilder":
        """기간 내 변경 이력 조회.

        Args:
            start: 기간 시작
            end: 기간 종료
            rel_alias: 관계 alias

        Returns:
            Self for chaining
        """
        self._temporal_filters.append({
            "type": "between",
            "start": start,
            "end": end,
            "alias": rel_alias,
        })
        return self

    def as_of(self, timestamp: datetime) -> "TemporalCypherBuilder":
        """시점 기준 스냅샷 — 해당 시점에 유효했던 모든 관계를 포함.

        Args:
            timestamp: 스냅샷 시점

        Returns:
            Self for chaining
        """
        self._temporal_filters.append({
            "type": "as_of",
            "timestamp": timestamp,
        })
        return self

    def build(self) -> tuple[str, dict]:
        """Build Cypher with temporal WHERE clauses injected."""
        cypher, params = super().build()
        for i, tf in enumerate(self._temporal_filters):
            cypher, params = self._inject_temporal(cypher, params, tf, i)
        return cypher, params

    def _inject_temporal(
        self, cypher: str, params: dict, tf: dict, idx: int
    ) -> tuple[str, dict]:
        alias = tf.get("alias", "r")
        if tf["type"] == "at_time":
            clause = (
                f"{alias}.validFrom <= $__temporal_ts_{idx} "
                f"AND ({alias}.validTo IS NULL OR {alias}.validTo > $__temporal_ts_{idx})"
            )
            params[f"__temporal_ts_{idx}"] = tf["timestamp"].isoformat()
        elif tf["type"] == "between":
            clause = (
                f"{alias}.validFrom <= $__temporal_end_{idx} "
                f"AND ({alias}.validTo IS NULL OR {alias}.validTo >= $__temporal_start_{idx})"
            )
            params[f"__temporal_start_{idx}"] = tf["start"].isoformat()
            params[f"__temporal_end_{idx}"] = tf["end"].isoformat()
        elif tf["type"] == "as_of":
            clause = (
                f"ALL(rel IN relationships(path) WHERE "
                f"rel.validFrom <= $__temporal_asof_{idx} "
                f"AND (rel.validTo IS NULL OR rel.validTo > $__temporal_asof_{idx}))"
            )
            params[f"__temporal_asof_{idx}"] = tf["timestamp"].isoformat()
        else:
            return cypher, params

        # WHERE 절이 이미 있으면 AND로 추가, 없으면 WHERE 생성
        if "WHERE" in cypher:
            cypher = cypher.replace("WHERE", f"WHERE {clause} AND", 1)
        else:
            # MATCH 뒤에 WHERE 삽입
            cypher = cypher.replace("RETURN", f"WHERE {clause} RETURN", 1)

        return cypher, params
```

### 22.2.5 시간 쿼리 사용 예시

```python
from datetime import datetime
from core.kg.temporal.builder import TemporalCypherBuilder

# "2026년 3월 15일에 부산항에 정박 중이던 선박"
query, params = (
    TemporalCypherBuilder()
    .match("(v:Vessel)-[r:DOCKED_AT]->(p:Port)")
    .where("p.name = $port_name", {"port_name": "부산항"})
    .at_time(datetime(2026, 3, 15), rel_alias="r")
    .return_("v.name AS name, v.mmsi AS mmsi")
    .build()
)

# "2026년 1분기 동안 인천항에 입출항한 선박 이력"
query, params = (
    TemporalCypherBuilder()
    .match("(v:Vessel)-[r:DOCKED_AT]->(p:Port)")
    .where("p.name = $port_name", {"port_name": "인천항"})
    .between(datetime(2026, 1, 1), datetime(2026, 3, 31), rel_alias="r")
    .return_("v.name, r.validFrom, r.validTo")
    .build()
)
```

### 22.2.6 Text2Cypher 시간 질의 지원

`TextToCypherPipeline`의 NLParser 단계에서 시간 표현을 인식하고,
`TemporalCypherBuilder`로 라우팅한다.

| 자연어 패턴 | 시간 API | 예시 |
|-----------|---------|------|
| "~에", "~시점에", "~당시" | `at_time()` | "3월 15일에 부산항에 있던 선박" |
| "~동안", "~부터 ~까지", "~기간" | `between()` | "1월부터 3월까지 인천항 입항 선박" |
| "작년", "지난 달", "최근 7일" | `between()` (상대 시간) | "최근 7일간 정박한 선박" |
| "현재", "지금" | `at_time(now)` | "현재 부산항에 정박 중인 선박" |

**구현 순서:**
- Y1 Q3: TemporalCypherBuilder 기본 구현 + 단위 테스트
- Y1 Q4: 동적 엔티티 `validFrom`/`validTo` 스키마 적용 (Neo4j 인덱스 포함)
- Y2 Q1: 시간 쿼리 REST API 엔드포인트 (`GET /api/v1/temporal/snapshot?timestamp=`)
- Y2 Q2: Text2Cypher NLParser 시간 표현 인식 통합

---

## 22.3 그래프 알고리즘 — HIGH

### 22.3.1 Neo4j GDS 라이브러리 통합

Neo4j GDS (Graph Data Science) 라이브러리는 Community Edition에서도
Community License로 사용 가능하다. IMSP는 GDS의 핵심 알고리즘을 래핑하여
해사 도메인 분석에 활용한다.

```
core/kg/algorithms/
├── __init__.py
├── runner.py           # GDS Protocol 래퍼 (GraphAlgorithmRunner)
├── centrality.py       # PageRank, Betweenness, Degree
├── community.py        # Louvain, Label Propagation
├── pathfinding.py      # Shortest Path, A*
├── similarity.py       # Node Similarity, Jaccard
├── link_prediction.py  # Adamic-Adar, Common Neighbors (Y3+)
└── projections.py      # Graph Projection 관리
```

### 22.3.2 핵심 알고리즘 및 해사 활용

| 카테고리 | 알고리즘 | 해사 활용 사례 | GDS Procedure | 도입 |
|----------|---------|--------------|---------------|------|
| **중심성** | PageRank | 항만 중요도 순위 (연결 항로 수 + 물동량 가중) | `gds.pageRank` | Y2 Q1 |
| **중심성** | Betweenness | 핵심 해상 교통 허브 식별 (경유 빈도) | `gds.betweenness` | Y2 Q2 |
| **중심성** | Degree Centrality | 선박별 기항 항만 수 통계 | `gds.degree` | Y2 Q1 |
| **커뮤니티** | Louvain | 선박 함대 클러스터링 (동일 운항 패턴) | `gds.louvain` | Y2 Q2 |
| **커뮤니티** | Label Propagation | 해역별 선박 그룹 분류 | `gds.labelPropagation` | Y2 Q3 |
| **경로** | Dijkstra | 최적 항로 탐색 (거리/연료 가중) | `gds.shortestPath.dijkstra` | Y2 Q1 |
| **경로** | A* | 장애물 회피 항로 탐색 (제한 구역 고려) | `gds.shortestPath.astar` | Y3 Q1 |
| **유사도** | Node Similarity | 유사 항만 추천 (화물 유형, 시설 기반) | `gds.nodeSimilarity` | Y2 Q3 |
| **유사도** | Jaccard Similarity | 선박 항로 패턴 유사도 비교 | `gds.nodeSimilarity` (Jaccard) | Y2 Q3 |
| **링크 예측** | Adamic-Adar | 잠재적 선박-항만 연결 예측 | `gds.linkPrediction.adamicAdar` | Y3 Q2 |

### 22.3.3 GraphAlgorithmRunner

```python
# core/kg/algorithms/runner.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class AlgorithmResult:
    """그래프 알고리즘 실행 결과."""
    algorithm: str
    node_count: int
    relationship_count: int
    compute_millis: int
    results: list[dict[str, Any]]


class GraphAlgorithmRunner:
    """Neo4j GDS 래퍼. Graph Projection 생성 및 알고리즘 실행을 캡슐화한다.

    Protocol 기반으로 설계하여 테스트 시 Mock 주입이 가능하다.
    """

    def __init__(self, driver, default_graph_name: str = "imsp-graph"):
        self._driver = driver
        self._default_graph = default_graph_name

    def create_projection(
        self,
        graph_name: str,
        node_labels: list[str],
        rel_types: list[str],
        rel_properties: list[str] | None = None,
    ) -> dict:
        """Native Graph Projection 생성.

        Args:
            graph_name: 프로젝션 그래프 이름
            node_labels: 포함할 노드 레이블
            rel_types: 포함할 관계 타입
            rel_properties: 관계 가중치 속성 (옵션)
        """
        node_spec = {label: {} for label in node_labels}
        rel_spec = {}
        for rt in rel_types:
            if rel_properties:
                rel_spec[rt] = {"properties": {p: {"property": p} for p in rel_properties}}
            else:
                rel_spec[rt] = {}

        cypher = (
            f"CALL gds.graph.project('{graph_name}', $nodes, $rels) "
            f"YIELD graphName, nodeCount, relationshipCount"
        )
        with self._driver.session() as session:
            result = session.run(cypher, nodes=node_spec, rels=rel_spec)
            return result.single().data()

    def pagerank(
        self,
        node_label: str = "Port",
        rel_type: str = "HAS_ROUTE",
        damping_factor: float = 0.85,
        max_iterations: int = 20,
        top_k: int = 20,
    ) -> AlgorithmResult:
        """PageRank 실행 — 항만 중요도 순위 산출."""
        graph_name = f"pagerank_{node_label}_{rel_type}"
        self.create_projection(graph_name, [node_label], [rel_type])
        try:
            cypher = (
                f"CALL gds.pageRank.stream('{graph_name}', {{"
                f"dampingFactor: {damping_factor}, maxIterations: {max_iterations}"
                f"}}) YIELD nodeId, score "
                f"RETURN gds.util.asNode(nodeId).name AS name, score "
                f"ORDER BY score DESC LIMIT {top_k}"
            )
            with self._driver.session() as session:
                records = list(session.run(cypher))
                return AlgorithmResult(
                    algorithm="pageRank",
                    node_count=len(records),
                    relationship_count=0,
                    compute_millis=0,
                    results=[r.data() for r in records],
                )
        finally:
            self._drop_projection(graph_name)

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
        node_label: str = "Port",
        rel_type: str = "HAS_ROUTE",
        weight_property: str | None = "distance",
    ) -> AlgorithmResult:
        """Dijkstra 최단 경로 탐색."""
        # 구현 상세 생략 — GDS shortestPath.dijkstra 호출
        ...

    def community_detection(
        self,
        algorithm: str = "louvain",
        node_label: str = "Vessel",
        rel_type: str = "SHARES_ROUTE",
    ) -> AlgorithmResult:
        """커뮤니티 탐지 — Louvain 또는 Label Propagation."""
        ...

    def node_similarity(
        self,
        node_label: str,
        rel_type: str,
        similarity_metric: str = "jaccard",
        top_k: int = 10,
    ) -> AlgorithmResult:
        """노드 유사도 계산."""
        ...

    def _drop_projection(self, graph_name: str) -> None:
        """사용 완료된 Graph Projection 제거."""
        with self._driver.session() as session:
            session.run(f"CALL gds.graph.drop('{graph_name}', false)")
```

### 22.3.4 DerivedInsight 온톨로지 연동

그래프 알고리즘 결과는 온톨로지의 `DerivedInsight` 계층 엔티티로 저장된다.
([4. 데이터 아키텍처](./04-data-architecture.md) 4.3.2절 참조)

| DerivedInsight 엔티티 | 소스 알고리즘 | 갱신 주기 | 저장 예시 |
|----------------------|-------------|----------|----------|
| `TrafficDensity` | Community Detection + 시간 집계 | 일간 | `{areaId, density, timestamp, communityId}` |
| `RouteStatistics` | Shortest Path + PageRank | 주간 | `{routeId, avgTransitTime, portRank}` |
| `CollisionRisk` | Proximity 알고리즘 + AIS 궤적 분석 | 실시간 (Near RT) | `{vesselPairId, cpa, tcpa, riskLevel}` |
| `AnomalyReport` | Outlier Detection (그래프 메트릭 이상치) | 일간 | `{entityId, metric, expected, actual, severity}` |
| `RouteDeviation` | Path Similarity + Temporal 비교 | 실시간 | `{vesselId, expectedRoute, actualRoute, deviation}` |

### 22.3.5 Argo CronWorkflow 통합

그래프 알고리즘은 연산 비용이 높으므로, **실시간 API 호출이 아닌 배치 작업**으로 실행한다.
Argo CronWorkflow로 스케줄링하고, 결과를 `DerivedInsight` 노드로 Neo4j에 캐싱한다.

```yaml
# infra/k8s/workflows/graph-algorithms-cron.yaml
apiVersion: argoproj.io/v1alpha1
kind: CronWorkflow
metadata:
  name: kg-graph-algorithms
spec:
  schedule: "0 3 * * *"  # 매일 03:00 실행
  workflowSpec:
    templates:
    - name: run-algorithms
      container:
        image: imsp/kg-engine:latest
        command: ["python", "-m", "core.kg.algorithms.batch_runner"]
        args:
        - "--algorithms=pagerank,louvain,degree"
        - "--output=derived_insight"
```

---

## 22.4 추론 및 검증 엔진 (Axioms 포함) — HIGH

### 22.4.1 아키텍처 전략

IMSP는 **완전한 OWL Reasoner를 채택하지 않는다.** Neo4j CE 환경에서
OWL DL 추론기(예: HermiT, Pellet)를 실행하는 것은 비현실적이다.
대신, OWL/TTL에 정의한 Axiom을 **SHACL + Cypher 규칙**으로 변환하여
런타임에 검증/추론하는 하이브리드 접근을 취한다.

```
core/kg/reasoning/
├── __init__.py
├── axioms.py           # OWL Axiom 정의 (Python dataclass)
├── inference_engine.py # Cypher 기반 규칙 추론 엔진
├── shacl_validator.py  # SHACL Shape 검증기 (Neo4j 연동)
├── rule_registry.py    # InferenceRule 레지스트리
└── anomaly_detector.py # 그래프 메트릭 기반 이상 탐지
```

### 22.4.2 OWL Axioms 정의

`domains/maritime/ontology/maritime.ttl`에 정의된 OWL Axiom을 체계화한다.

**Class Axioms (클래스 공리):**

```turtle
# SubClassOf — 선박 하위 분류
maritime:ContainerShip rdfs:subClassOf maritime:Vessel .
maritime:Tanker rdfs:subClassOf maritime:Vessel .
maritime:BulkCarrier rdfs:subClassOf maritime:Vessel .
maritime:PassengerShip rdfs:subClassOf maritime:Vessel .
maritime:RoRo rdfs:subClassOf maritime:Vessel .

# DisjointClasses — 최상위 엔티티 간 상호 배타
[] a owl:AllDisjointClasses ;
   owl:members (
       maritime:Vessel
       maritime:Port
       maritime:Organization
       maritime:SeaArea
       maritime:NavigationAid
   ) .
```

**Property Axioms (속성 공리):**

```turtle
# Domain/Range — 관계의 시작/끝 타입 제약
maritime:DOCKED_AT rdfs:domain maritime:Vessel ;
                   rdfs:range maritime:Port .
maritime:LOCATED_IN rdfs:domain maritime:Port ;
                    rdfs:range maritime:SeaArea .
maritime:OPERATED_BY rdfs:domain maritime:Vessel ;
                     rdfs:range maritime:Organization .

# Functional Property — 1 MMSI per Vessel (유일성 보장)
maritime:mmsi a owl:FunctionalProperty ;
              rdfs:domain maritime:Vessel .

# Transitive Property — 해역 포함 관계 전이
maritime:PART_OF a owl:TransitiveProperty .
# 예: SeaArea A PART_OF B, B PART_OF C → A PART_OF C 추론 가능
```

**Cardinality Axioms (기수 공리):**

```turtle
# Every Vessel must have exactly 1 MMSI
maritime:Vessel rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty maritime:mmsi ;
    owl:cardinality "1"^^xsd:nonNegativeInteger
] .

# Every Vessel must have at least 1 name
maritime:Vessel rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty maritime:name ;
    owl:minCardinality "1"^^xsd:nonNegativeInteger
] .

# Every Port has at most 1 unlocode
maritime:Port rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty maritime:unlocode ;
    owl:maxCardinality "1"^^xsd:nonNegativeInteger
] .
```

### 22.4.3 SHACL Shapes (런타임 검증)

OWL Axiom을 SHACL NodeShape으로 변환하여 Neo4j 데이터를 검증한다.
n10s(Neosemantics)의 SHACL 검증 기능과 연동한다.

```turtle
# domains/maritime/ontology/shapes/vessel_shape.ttl

@prefix sh:       <http://www.w3.org/ns/shacl#> .
@prefix maritime: <https://kg.kriso.re.kr/maritime#> .
@prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .

maritime:VesselShape a sh:NodeShape ;
    sh:targetClass maritime:Vessel ;
    sh:property [
        sh:path maritime:mmsi ;
        sh:datatype xsd:integer ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:minInclusive 100000000 ;
        sh:maxInclusive 799999999 ;
        sh:message "Vessel MMSI는 9자리 정수 (100000000-799999999)여야 합니다"@ko ;
    ] ;
    sh:property [
        sh:path maritime:name ;
        sh:datatype xsd:string ;
        sh:minCount 1 ;
        sh:minLength 1 ;
        sh:message "Vessel에는 최소 1개의 이름이 필요합니다"@ko ;
    ] ;
    sh:property [
        sh:path maritime:vesselType ;
        sh:in ("ContainerShip" "Tanker" "BulkCarrier" "PassengerShip" "RoRo"
               "FishingVessel" "TugBoat" "NavalVessel" "Other") ;
        sh:message "vesselType은 허용된 값 중 하나여야 합니다"@ko ;
    ] ;
    sh:property [
        sh:path maritime:imo ;
        sh:datatype xsd:integer ;
        sh:maxCount 1 ;
        sh:pattern "^[0-9]{7}$" ;
        sh:message "IMO 번호는 7자리 정수입니다"@ko ;
    ] .

maritime:PortShape a sh:NodeShape ;
    sh:targetClass maritime:Port ;
    sh:property [
        sh:path maritime:name ;
        sh:minCount 1 ;
    ] ;
    sh:property [
        sh:path maritime:unlocode ;
        sh:maxCount 1 ;
        sh:pattern "^[A-Z]{2}[A-Z0-9]{3}$" ;
        sh:message "UNLOCODE는 5자리 영숫자 코드여야 합니다 (예: KRPUS)"@ko ;
    ] .
```

### 22.4.4 Cypher 기반 규칙 추론 엔진

```python
# core/kg/reasoning/inference_engine.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class InferenceRule:
    """Cypher 기반 추론 규칙."""
    name: str
    description: str
    condition: str    # Cypher MATCH 패턴 (조건)
    action: str       # Cypher CREATE/MERGE/SET (결과)
    priority: int     # 실행 우선순위 (1 = 최우선)
    category: str     # "transitive" | "classification" | "aggregation" | "anomaly"
    idempotent: bool = True  # 중복 실행 안전 여부


# 해사 도메인 추론 규칙 레지스트리
MARITIME_INFERENCE_RULES: list[InferenceRule] = [
    InferenceRule(
        name="vessel_at_port_implies_in_sea_area",
        description="선박이 항만에 정박 중이면 해당 해역에서 운항 중인 것으로 추론",
        condition=(
            "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port)-[:LOCATED_IN]->(sa:SeaArea) "
            "WHERE NOT EXISTS((v)-[:OPERATES_IN]->(sa))"
        ),
        action="MERGE (v)-[:OPERATES_IN {inferred: true, rule: 'vessel_at_port'}]->(sa)",
        priority=1,
        category="transitive",
    ),
    InferenceRule(
        name="high_traffic_port_classification",
        description="입항 선박 100척 이상인 항만을 고교통 항만으로 분류",
        condition=(
            "MATCH (p:Port) "
            "WHERE size((p)<-[:DOCKED_AT]-()) > 100 "
            "AND NOT p.trafficLevel = 'HIGH'"
        ),
        action="SET p.trafficLevel = 'HIGH'",
        priority=2,
        category="classification",
    ),
    InferenceRule(
        name="part_of_transitivity",
        description="PART_OF 관계의 전이적 폐쇄 (A⊂B, B⊂C → A⊂C)",
        condition=(
            "MATCH (a:SeaArea)-[:PART_OF]->(b:SeaArea)-[:PART_OF]->(c:SeaArea) "
            "WHERE NOT EXISTS((a)-[:PART_OF]->(c))"
        ),
        action=(
            "MERGE (a)-[:PART_OF {inferred: true, rule: 'transitivity'}]->(c)"
        ),
        priority=1,
        category="transitive",
    ),
    InferenceRule(
        name="orphan_vessel_warning",
        description="관계가 하나도 없는 Vessel 노드에 경고 레이블 부착",
        condition=(
            "MATCH (v:Vessel) WHERE NOT EXISTS((v)--()) "
            "AND NOT v:OrphanWarning"
        ),
        action="SET v:OrphanWarning",
        priority=3,
        category="anomaly",
    ),
]


class InferenceEngine:
    """Cypher 기반 추론 엔진.

    OWL Reasoner 대신 Cypher 규칙으로 경량 추론을 수행한다.
    각 규칙은 idempotent하게 설계되어 반복 실행해도 안전하다.
    """

    def __init__(self, driver, rules: list[InferenceRule] | None = None):
        self._driver = driver
        self._rules = sorted(
            rules or MARITIME_INFERENCE_RULES,
            key=lambda r: r.priority,
        )

    def run_all(self) -> list[dict]:
        """모든 추론 규칙을 우선순위 순으로 실행."""
        results = []
        for rule in self._rules:
            result = self.run_rule(rule)
            results.append(result)
        return results

    def run_rule(self, rule: InferenceRule) -> dict:
        """단일 추론 규칙 실행."""
        cypher = f"{rule.condition} {rule.action}"
        with self._driver.session() as session:
            summary = session.run(cypher).consume()
            return {
                "rule": rule.name,
                "nodes_created": summary.counters.nodes_created,
                "relationships_created": summary.counters.relationships_created,
                "properties_set": summary.counters.properties_set,
            }

    def run_by_category(self, category: str) -> list[dict]:
        """특정 카테고리의 규칙만 실행."""
        filtered = [r for r in self._rules if r.category == category]
        return [self.run_rule(r) for r in filtered]
```

### 22.4.5 검증 레벨 체계 (5단계)

기존 검증 모듈(CypherValidator, QualityGate)과 신규 모듈(SHACL, Inference, Anomaly)을
통합한 5단계 검증 체계이다.

| 레벨 | 검증 대상 | 도구 | 실행 시점 | 상태 |
|------|----------|------|----------|------|
| **L1** | Cypher 쿼리 구문/보안 | `CypherValidator` (기존 6가지 검증) | 실시간 (모든 쿼리) | ✅ 구현 완료 |
| **L2** | KG 스키마 커버리지 | `QualityGate` (기존 NodeCoverage 등) | CI/CD 배포 시 | ✅ 구현 완료 |
| **L3** | 데이터 제약 (SHACL) | `SHACLValidator` (신규) | 배치 (일 1회) | ⏳ Y2 Q2 |
| **L4** | 비즈니스 규칙 추론 | `InferenceEngine` (신규) | 배치 (6시간) | ⏳ Y2 Q2 |
| **L5** | 그래프 이상 탐지 | `AnomalyDetector` (신규, 그래프 메트릭) | 배치 (일 1회) | ⏳ Y2 Q3 |

---

## 22.5 메타데이터 카탈로그 — HIGH

### 22.5.1 필요성

KG 규모가 Y1 10K → Y5 2M+ 노드로 성장하면, "어떤 엔티티가 몇 개이고, 품질 상태는 어떠한지"를
파악하기 어려워진다. 메타데이터 카탈로그는 KG 자체에 대한 KG로서,
모든 엔티티 타입의 현황/품질/출처 정보를 체계적으로 관리한다.

### 22.5.2 카탈로그 데이터 모델

카탈로그 정보 자체도 Neo4j에 저장하여 그래프 탐색과 통합 쿼리를 지원한다.

```
(:CatalogEntry {
    entityType: "Vessel",              # KG 노드 레이블
    nodeCount: 45230,                  # 현재 노드 수
    relationshipCount: 128500,         # 해당 타입의 총 관계 수
    lastUpdated: datetime(),           # 마지막 갱신 시각
    qualityScore: 0.92,                # 종합 데이터 품질 점수 (0.0~1.0)
    completeness: 0.87,                # 필수 속성 완전성 비율
    accuracy: 0.95,                    # SHACL 검증 통과율
    freshness: duration("PT2H"),       # 최신 데이터 경과 시간
    consistency: 0.91,                 # 관계 제약 충족률
    source: "AIS-Crawler",             # 주 데이터 출처
    owner: "kriso",                    # 데이터 소유 테넌트
    description: "해사 선박 정보",       # 설명
    ontologyVersion: "v1.2"            # 온톨로지 버전
})
    -[:GOVERNED_BY]->(:OntologyVersion {version: "v1.2", effectiveDate: date()})
    -[:SOURCED_FROM]->(:DataSource {name: "AIS-Crawler", type: "streaming"})
```

### 22.5.3 품질 스코어 계산

엔티티 타입별 품질 점수는 4가지 차원의 가중 평균으로 산출한다.

```python
# core/kg/catalog/quality.py
from dataclasses import dataclass


@dataclass
class QualityDimension:
    name: str
    score: float     # 0.0 ~ 1.0
    weight: float    # 가중치


def calculate_quality_score(
    completeness: float,  # 필수 속성 채움률
    accuracy: float,      # SHACL 검증 통과율
    freshness: float,     # 최신성 (감쇠 함수 적용)
    consistency: float,   # 관계 제약 충족률
) -> float:
    """4차원 품질 점수 계산.

    가중치: completeness=0.3, accuracy=0.3, freshness=0.2, consistency=0.2
    """
    dimensions = [
        QualityDimension("completeness", completeness, 0.3),
        QualityDimension("accuracy", accuracy, 0.3),
        QualityDimension("freshness", freshness, 0.2),
        QualityDimension("consistency", consistency, 0.2),
    ]
    return sum(d.score * d.weight for d in dimensions)
```

**Freshness 감쇠 함수:**

```
freshness_score = max(0, 1.0 - (hours_since_update / max_acceptable_hours))
```

| 엔티티 타입 | `max_acceptable_hours` | 설명 |
|-----------|----------------------|------|
| VesselPosition | 1 | AIS 위치는 1시간 이내 |
| WeatherObservation | 6 | 기상 데이터는 6시간 이내 |
| Vessel | 168 (7일) | 선박 정보는 주간 갱신 |
| Port | 720 (30일) | 항만 정보는 월간 갱신 |

### 22.5.4 카탈로그 API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/v1/catalog` | GET | 전체 카탈로그 조회 (엔티티 타입 목록 + 요약) |
| `/api/v1/catalog/{label}` | GET | 특정 엔티티 타입 상세 (노드 수, 속성 분포) |
| `/api/v1/catalog/{label}/quality` | GET | 4차원 품질 리포트 |
| `/api/v1/catalog/{label}/history` | GET | 노드 수 변화 이력 (시계열) |
| `/api/v1/catalog/search?q=` | GET | 카탈로그 전문 검색 |
| `/api/v1/catalog/refresh` | POST | 카탈로그 전체 재계산 (배치 트리거) |

### 22.5.5 스키마 레지스트리

온톨로지 버전, 제약 조건 변경, 인덱스 추가/삭제를 타임스탬프와 함께 추적한다.

```
(:SchemaChange {
    changeId: "sc-2026-03-20-001",
    changeType: "ADD_CONSTRAINT",          # ADD_CONSTRAINT | DROP_INDEX | ADD_LABEL | ...
    targetLabel: "Vessel",
    cypher: "CREATE CONSTRAINT vessel_mmsi ...",
    appliedAt: datetime(),
    appliedBy: "admin@kriso",
    ontologyVersion: "v1.2",
    rollbackCypher: "DROP CONSTRAINT vessel_mmsi"
})
```

---

## 22.6 스트리밍 KG 업데이트 — CRITICAL

### 22.6.1 아키텍처

AIS 수신기, 기상 센서 등 실시간 데이터 소스를 Kafka를 통해 KG에 반영하는 파이프라인이다.
[4. 데이터 아키텍처](./04-data-architecture.md) 4.5.3절의 Streaming 모드를 상세화한다.

```
AIS 수신기 / 기상 API / VTS 레이더
         │
         ▼
   Kafka Topics
   ├── ais.raw         (AIS NMEA 원본)
   ├── weather.raw     (기상 GRIB2)
   └── radar.raw       (레이더 접촉)
         │
         ▼
   Stream Processor (Python Kafka Consumer Group)
   ├── (1) 디시리얼라이즈 + 스키마 검증
   ├── (2) 정규화 (MMSI, 좌표, 타임스탬프)
   ├── (3) Entity Resolution (선박 식별)
   ├── (4) Temporal 속성 갱신 (validFrom/validTo)
   └── (5) Micro-batch 버퍼 (5초, 최대 500건)
         │
         ▼
   Neo4j Batch MERGE (UNWIND 패턴, batch=500)
   ├── 노드 MERGE (Vessel, Port 등)
   ├── 관계 MERGE (DOCKED_AT, OPERATES_IN 등)
   ├── Temporal 속성 SET
   └── 리니지 기록 (LineageRecorder)
         │
         ├── DerivedInsight 트리거 (비동기)
         │   └── CollisionRisk, TrafficDensity 재계산
         │
         └── WebSocket 알림 (프론트엔드)
             └── Gateway WebSocket Server → UI Map/Dashboard
```

### 22.6.2 처리 모드

| 모드 | 지연 시간 | 배치 크기 | Kafka Consumer Group | 용도 |
|------|----------|----------|---------------------|------|
| **Near Real-time** | 5초 | 100~500 | `imsp-ais-nrt` | AIS 위치 업데이트 |
| **Micro-batch** | 1분 | 1,000~5,000 | `imsp-weather-mb` | 기상 데이터 |
| **Batch** | 1시간+ | 10,000+ | Argo CronWorkflow | 연구 데이터, 보고서, S-100 동기화 |

### 22.6.3 코드 구조

```
core/kg/streaming/
├── __init__.py
├── consumer.py          # Kafka Consumer 래퍼 (Generic)
├── ais_processor.py     # AIS 메시지 처리 파이프라인
├── weather_processor.py # 기상 데이터 처리
├── batch_merger.py      # Neo4j UNWIND MERGE 배치 실행
├── temporal_updater.py  # validFrom/validTo 자동 갱신
├── backpressure.py      # Back-pressure 및 Consumer Lag 관리
└── dlq.py               # 스트리밍 전용 Dead Letter Queue
```

### 22.6.4 Back-pressure 및 DLQ

```python
# core/kg/streaming/backpressure.py
@dataclass
class BackpressureConfig:
    max_lag: int = 10000            # Consumer Lag 상한 (이 이상이면 경고)
    pause_threshold: int = 50000    # 이 이상이면 Consumer 일시 정지
    resume_threshold: int = 5000    # Lag이 이 이하로 내려가면 재개
    batch_size_min: int = 50        # 최소 배치 크기 (부하 시 축소)
    batch_size_max: int = 500       # 최대 배치 크기 (정상 시)
    dlq_topic: str = "imsp.dlq"    # Dead Letter Queue Kafka Topic
```

실패한 메시지는 DLQ Topic에 저장되며, 원본 데이터 + 에러 사유 + 타임스탬프를 포함한다.
DLQ 메시지는 Argo CronWorkflow(`0 */6 * * *`)로 주기적 재처리를 시도한다.

---

## 22.7 그래프 구조 임베딩 — HIGH

### 22.7.1 텍스트 임베딩 vs 그래프 임베딩

현재 IMSP의 `core/kg/embeddings/` 모듈은 텍스트 속성에 대한 의미 벡터(nomic-embed-text, 768d)만
지원한다. 그래프 구조 임베딩은 **노드의 이웃 구조, 관계 패턴**을 벡터로 인코딩하여
텍스트만으로는 포착할 수 없는 구조적 유사성을 활용한다.

| 구분 | 텍스트 임베딩 (현재) | 그래프 임베딩 (신규) |
|------|-------------------|-------------------|
| 모듈 | `core/kg/embeddings/` | `core/kg/graph_embeddings/` |
| 알고리즘 | nomic-embed-text (Ollama) | FastRP, Node2Vec (Neo4j GDS) |
| 입력 | 텍스트 속성 (name, description) | 그래프 구조 (이웃 노드, 관계 타입) |
| 차원 | 768d | 128d ~ 256d |
| 용도 | 의미 유사도 검색 ("컨테이너선" ≈ "화물선") | 구조적 유사도 ("같은 항로 패턴 선박") |
| Neo4j 속성 | `textEmbedding` | `structuralEmbedding` |
| 인덱스 | `CREATE VECTOR INDEX text_emb_*` | `CREATE VECTOR INDEX struct_emb_*` |

### 22.7.2 FastRP (Fast Random Projection)

Neo4j GDS 내장 알고리즘으로, 그래프 구조를 저차원 벡터로 빠르게 매핑한다.

```python
# core/kg/graph_embeddings/fastrp.py
class FastRPEmbedder:
    """Neo4j GDS FastRP 기반 그래프 구조 임베딩 생성.

    Graph Projection → FastRP 실행 → 노드 속성에 벡터 저장.
    """

    def __init__(self, driver, embedding_dimension: int = 128):
        self._driver = driver
        self._dim = embedding_dimension

    def generate(
        self,
        node_label: str,
        rel_type: str,
        iteration_weights: list[float] | None = None,
    ) -> int:
        """지정된 노드/관계에 대해 FastRP 임베딩 생성 후 노드에 저장.

        Args:
            node_label: 대상 노드 레이블
            rel_type: 관계 타입
            iteration_weights: 반복 가중치 (기본: [0.0, 1.0, 1.0])

        Returns:
            임베딩이 생성된 노드 수
        """
        weights = iteration_weights or [0.0, 1.0, 1.0]
        graph_name = f"fastrp_{node_label}"

        # 1. Graph Projection
        self._driver.session().run(
            f"CALL gds.graph.project('{graph_name}', '{node_label}', '{rel_type}')"
        )

        # 2. FastRP mutate (그래프에 임베딩 속성 추가)
        self._driver.session().run(
            f"CALL gds.fastRP.mutate('{graph_name}', {{"
            f"  embeddingDimension: {self._dim},"
            f"  iterationWeights: {weights},"
            f"  mutateProperty: 'structuralEmbedding'"
            f"}})"
        )

        # 3. Write back to Neo4j
        result = self._driver.session().run(
            f"CALL gds.graph.nodeProperties.write('{graph_name}', "
            f"['structuralEmbedding'])"
        )

        # 4. Cleanup
        self._driver.session().run(f"CALL gds.graph.drop('{graph_name}')")

        return result.single()["propertiesWritten"]
```

### 22.7.3 Hybrid Retrieval (텍스트 + 그래프)

GraphRAG 질의 시 텍스트 임베딩과 그래프 임베딩을 결합하여 검색 품질을 향상한다.

```python
# core/kg/graph_embeddings/hybrid_retrieval.py
def hybrid_search(
    query_text: str,
    text_embedder,       # OllamaEmbedder (기존)
    text_weight: float = 0.6,
    struct_weight: float = 0.4,
    top_k: int = 10,
) -> list[dict]:
    """텍스트 + 구조 임베딩 하이브리드 검색.

    1. 텍스트 임베딩으로 의미 유사 노드 후보 추출 (top_k * 3)
    2. 후보 노드의 구조 임베딩으로 재순위화
    3. 가중 평균 점수로 최종 top_k 반환
    """
    # Step 1: 텍스트 유사도 검색
    query_vec = text_embedder.embed(query_text)
    text_candidates = vector_search("textEmbedding", query_vec, top_k * 3)

    # Step 2: 구조 유사도 재순위화
    for candidate in text_candidates:
        struct_score = cosine_similarity(
            candidate["structuralEmbedding"],
            get_context_embedding(candidate["nodeId"]),
        )
        candidate["hybridScore"] = (
            text_weight * candidate["textScore"]
            + struct_weight * struct_score
        )

    # Step 3: 최종 정렬
    text_candidates.sort(key=lambda x: x["hybridScore"], reverse=True)
    return text_candidates[:top_k]
```

---

## 22.8 KG 정합성 검증 — HIGH

### 22.8.1 개요

기존 `QualityGate`가 스키마 수준의 커버리지를 검증한다면,
`KGConsistencyChecker`는 **데이터 수준의 논리적 일관성**을 검증한다.
`core/kg/ontology/core.py`의 `PropertyDefinition` 제약(`required`, `min_value`, `max_value`,
`pattern`, `enum_values`)을 런타임에 검증한다.

### 22.8.2 검증 항목

| # | 검증 항목 | 설명 | Cypher 예시 |
|---|----------|------|------------|
| 1 | 필수 속성 존재 | `required=True`인 속성이 모든 노드에 존재하는지 | `MATCH (v:Vessel) WHERE v.mmsi IS NULL RETURN count(v)` |
| 2 | 값 범위 | `min_value`/`max_value` 범위 내인지 | `MATCH (v:Vessel) WHERE v.mmsi < 100000000 RETURN v` |
| 3 | 패턴 매칭 | `pattern` 정규식 충족 여부 | `MATCH (p:Port) WHERE NOT p.unlocode =~ '^[A-Z]{2}[A-Z0-9]{3}$'` |
| 4 | 열거형 제약 | `enum_values` 멤버십 | `MATCH (v:Vessel) WHERE NOT v.vesselType IN [...]` |
| 5 | 기수 제약 | `Cardinality` (1:N, M:N) 충족 | `MATCH (v:Vessel) WHERE size((v)-[:DOCKED_AT]->()) > 1` (1:N 위반) |
| 6 | 고아 노드 | 관계 없는 노드 탐지 | `MATCH (n) WHERE NOT (n)--() RETURN labels(n), count(n)` |
| 7 | 허상 관계 | 존재하지 않는 노드를 참조하는 관계 | Neo4j에서는 자동 방지되나, 삭제 후 잔여 확인 |
| 8 | 중복 노드 | 동일 Primary Key를 가진 노드 중복 | `MATCH (v:Vessel) WITH v.mmsi AS m, count(*) AS c WHERE c > 1` |

### 22.8.3 구현

```python
# core/kg/consistency/checker.py
from dataclasses import dataclass
from core.kg.ontology.core import Ontology, PropertyDefinition


@dataclass
class ConsistencyViolation:
    """정합성 위반 건."""
    check_name: str
    label: str
    property_name: str | None
    violation_count: int
    sample_node_ids: list[str]
    severity: str   # "CRITICAL" | "WARNING" | "INFO"
    message: str


@dataclass
class ConsistencyReport:
    """정합성 검증 리포트."""
    label: str
    total_nodes: int
    violations: list[ConsistencyViolation]
    passed: bool
    checked_at: str  # ISO 8601


class KGConsistencyChecker:
    """KG 데이터 수준 정합성 검증기.

    Ontology의 PropertyDefinition 제약을 Cypher로 변환하여
    Neo4j 데이터를 검증한다.
    """

    def __init__(self, driver, ontology: Ontology):
        self._driver = driver
        self._ontology = ontology

    def check_all(self) -> list[ConsistencyReport]:
        """모든 ObjectType에 대해 전체 검증 실행."""
        reports = []
        for ot in self._ontology.get_all_object_types():
            report = self.check_label(ot.name)
            reports.append(report)
        return reports

    def check_label(self, label: str) -> ConsistencyReport:
        """특정 레이블의 모든 정합성 항목을 검증."""
        ot = self._ontology.get_object_type(label)
        if not ot:
            raise ValueError(f"Unknown label: {label}")

        violations = []
        violations.extend(self._check_required_properties(label, ot.properties))
        violations.extend(self._check_value_ranges(label, ot.properties))
        violations.extend(self._check_patterns(label, ot.properties))
        violations.extend(self._check_enum_values(label, ot.properties))
        violations.extend(self._check_duplicates(label, ot))

        total = self._count_nodes(label)
        return ConsistencyReport(
            label=label,
            total_nodes=total,
            violations=violations,
            passed=all(v.severity != "CRITICAL" for v in violations),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

    def check_orphan_nodes(self) -> list[ConsistencyViolation]:
        """관계 없는 고아 노드 탐지."""
        cypher = "MATCH (n) WHERE NOT (n)--() RETURN labels(n)[0] AS label, count(n) AS cnt"
        with self._driver.session() as session:
            records = list(session.run(cypher))
            return [
                ConsistencyViolation(
                    check_name="orphan_nodes",
                    label=r["label"],
                    property_name=None,
                    violation_count=r["cnt"],
                    sample_node_ids=[],
                    severity="WARNING",
                    message=f"{r['label']} 타입에 관계 없는 고아 노드 {r['cnt']}건 발견",
                )
                for r in records if r["cnt"] > 0
            ]

    # ... (내부 검증 메서드 구현)
```

---

## 22.9 온톨로지 정렬 (S-100 호환) — HIGH

### 22.9.1 개요

IMSP 온톨로지의 설계 원칙 5번 "S-100 Compatible -- IHO S-100 표준과 1:1 매핑 경로 확보"를
구현하는 모듈이다. IMSP 해사 엔티티와 IHO S-100 Feature 간의 양방향 매핑을 관리한다.

### 22.9.2 매핑 모델

```python
# core/kg/ontology/alignment.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class MappingType(str, Enum):
    """온톨로지 매핑 유형 (SKOS 기반)."""
    EXACT = "exactMatch"        # 정확히 동일한 개념
    BROADER = "broadMatch"      # IMSP 개념이 S-100보다 넓음
    NARROWER = "narrowMatch"    # IMSP 개념이 S-100보다 좁음
    RELATED = "relatedMatch"    # 관련 개념이나 직접 매핑 불가
    CLOSE = "closeMatch"        # 거의 동일하나 완전 일치는 아님


@dataclass
class OntologyMapping:
    """IMSP ↔ S-100 온톨로지 매핑 항목."""
    source_concept: str          # IMSP 레이블 (예: "Vessel")
    target_concept: str          # S-100 Feature (예: "VesselTrafficService")
    target_standard: str         # S-100 하위 표준 (예: "S-127")
    target_code: str             # S-100 Feature Code (예: "VTSARE")
    mapping_type: MappingType
    confidence: float            # 매핑 신뢰도 (0.0~1.0)
    notes: str = ""              # 매핑 시 참고사항
    validated: bool = False      # KRISO 검증 완료 여부
    validated_by: str | None = None
    validated_at: str | None = None
```

### 22.9.3 S-100 매핑 대상 (33 엔티티)

[4. 데이터 아키텍처](./04-data-architecture.md) 4.3.4절의 S-100 호환성 매핑 계획을 구체화한다.

| S-100 표준 | S-100 Feature | IMSP 엔티티 | 매핑 유형 | 도입 |
|-----------|---------------|------------|----------|------|
| **S-101** | NavigationalSystemOfMarks | NavigationAid | EXACT | Y2 Q1 |
| S-101 | DepthArea | SeaArea | BROADER | Y2 Q1 |
| S-101 | Anchorage | Anchorage | EXACT | Y2 Q1 |
| S-101 | FairwaySystem | Waterway | CLOSE | Y2 Q2 |
| S-101 | Berth | Berth | EXACT | Y2 Q1 |
| S-101 | PortFacility | Terminal | NARROWER | Y2 Q2 |
| S-101 | RestrictedArea | RestrictedArea | EXACT | Y2 Q1 |
| S-101 | TrafficSeparationScheme | TSS | EXACT | Y2 Q1 |
| S-101 | LandArea | -- | (미매핑) | -- |
| S-101 | CoastlineElement | -- | (미매핑) | -- |
| **S-104** | WaterLevelStation | Port (확장 속성) | RELATED | Y2 Q3 |
| S-104 | TidalPrediction | TidalData | EXACT | Y2 Q3 |
| S-104 | WaterLevelTrend | TidalData (확장) | NARROWER | Y3 Q1 |
| S-104 | TidalStream | OceanCurrent | RELATED | Y3 Q1 |
| **S-111** | SurfaceCurrentSpeed | OceanCurrent | CLOSE | Y3 Q1 |
| S-111 | SurfaceCurrentDirection | OceanCurrent | CLOSE | Y3 Q1 |
| S-111 | GridPoint | -- | (구조 차이) | -- |
| S-111 | FeatureInstance | -- | (구조 차이) | -- |
| **S-127** | VesselTrafficServiceArea | TSS | BROADER | Y2 Q2 |
| S-127 | PilotBoardingPlace | Port (확장) | RELATED | Y2 Q3 |
| S-127 | RadioCallingInPoint | -- | (미매핑, Y3+) | Y3 Q2 |
| S-127 | AnchorageArea | Anchorage | EXACT | Y2 Q1 |
| S-127 | FairwaySection | Waterway | CLOSE | Y2 Q2 |
| S-127 | CargoTransferArea | Terminal | RELATED | Y3 Q1 |
| S-127 | TugServiceArea | SeaArea (확장) | BROADER | Y3 Q1 |
| S-127 | VTSDataLink | -- | (통신 인프라) | Y3+ |
| **S-411** | IceArea | WeatherObservation (확장) | RELATED | Y3 Q2 |
| S-411 | IceConcentration | WeatherObservation (확장) | RELATED | Y3 Q2 |
| S-411 | IceEdge | -- | (미매핑) | -- |
| S-411 | IceBerg | -- | (미매핑) | -- |
| **S-412** | WeatherForecastArea | WeatherObservation | BROADER | Y2 Q3 |
| S-412 | WindForecast | WeatherObservation (확장) | NARROWER | Y3 Q1 |
| S-412 | WaveForecast | WeatherObservation (확장) | NARROWER | Y3 Q1 |

### 22.9.4 매핑 검증

```python
# core/kg/ontology/alignment.py (계속)
class OntologyAligner:
    """IMSP ↔ S-100 온톨로지 정렬 관리자."""

    def __init__(self, ontology: Ontology, mappings: list[OntologyMapping]):
        self._ontology = ontology
        self._mappings = mappings

    def coverage_report(self) -> dict:
        """IMSP 해사 엔티티 중 S-100 매핑이 존재하는 비율."""
        all_labels = {ot.name for ot in self._ontology.get_all_object_types()}
        mapped_labels = {m.source_concept for m in self._mappings}
        unmapped = all_labels - mapped_labels
        return {
            "total_entities": len(all_labels),
            "mapped_entities": len(mapped_labels),
            "unmapped_entities": sorted(unmapped),
            "coverage_ratio": len(mapped_labels) / max(len(all_labels), 1),
        }

    def get_mappings_for(self, imsp_label: str) -> list[OntologyMapping]:
        """특정 IMSP 엔티티의 S-100 매핑 목록."""
        return [m for m in self._mappings if m.source_concept == imsp_label]

    def validate_mappings(self) -> list[str]:
        """매핑 일관성 검증 — 존재하지 않는 IMSP 레이블 참조 등."""
        errors = []
        valid_labels = {ot.name for ot in self._ontology.get_all_object_types()}
        for m in self._mappings:
            if m.source_concept not in valid_labels:
                errors.append(f"매핑 {m.source_concept} → {m.target_concept}: "
                              f"IMSP 레이블 '{m.source_concept}'이 온톨로지에 없음")
        return errors
```

---

## 22.10 KG 교환 포맷 — MEDIUM

### 22.10.1 지원 포맷

| 포맷 | 용도 | 라이브러리 | 도입 시기 |
|------|------|----------|----------|
| **OWL/Turtle** | 온톨로지 교환 (n10s 연동) | n10s (기존) | ✅ Y1 |
| **JSON-LD** | 웹 호환 연결 데이터, API 응답 | `pyld`, `rdflib` | Y2 Q2 |
| **GraphML** | 시각화 도구 호환 (Gephi, yEd 등) | `networkx`, `xml.etree` | Y2 Q3 |
| **CSV/TSV** | 대량 데이터 내보내기, 연구자 분석용 | `csv` (표준) | Y1 Q4 |
| **RDF/N-Triples** | 표준 KG 교환, 외부 KG 연동 | `rdflib` | Y3 Q1 |
| **Cypher Script** | Neo4j 마이그레이션, 백업 | 자체 생성 | Y1 Q3 |

### 22.10.2 코드 구조

```
core/kg/interchange/
├── __init__.py
├── exporter.py      # 통합 Export 인터페이스
├── json_ld.py       # JSON-LD 직렬화
├── graphml.py       # GraphML 직렬화
├── csv_export.py    # CSV/TSV 대량 내보내기
├── rdf.py           # RDF/N-Triples 내보내기
└── importer.py      # 외부 KG 데이터 가져오기
```

### 22.10.3 Export API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/v1/export/{format}` | GET | KG 데이터 내보내기 |
| `/api/v1/export/{format}?labels=Vessel,Port&limit=1000` | GET | 특정 레이블 필터링 |
| `/api/v1/export/ontology?format=turtle` | GET | 온톨로지만 내보내기 |
| `/api/v1/import/{format}` | POST | 외부 데이터 가져오기 (JSON-LD, RDF) |

**Export 파라미터:**

| 파라미터 | 타입 | 설명 | 예시 |
|---------|------|------|------|
| `labels` | string (comma-separated) | 포함할 노드 레이블 | `Vessel,Port` |
| `rel_types` | string (comma-separated) | 포함할 관계 타입 | `DOCKED_AT,LOCATED_IN` |
| `limit` | int | 최대 노드 수 | `1000` |
| `include_properties` | bool | 속성 포함 여부 | `true` |
| `temporal_filter` | ISO datetime | 시점 기준 스냅샷 | `2026-03-20T00:00:00` |

---

## 22.11 그래프 분석 파이프라인 — MEDIUM

### 22.11.1 Argo CronWorkflow 기반 배치 분석

KG의 건강 상태 및 성장 추이를 주기적으로 분석하고 리포트를 생성한다.

| 주기 | 분석 항목 | Argo 스케줄 |
|------|----------|------------|
| **일간** | 노드/관계 수, 레이블별 분포, 신규 노드 수, 고아 노드 수 | `0 1 * * *` |
| **주간** | 중심성 메트릭 (PageRank, Degree), 커뮤니티 배정 | `0 2 * * 0` |
| **월간** | KG 성장 보고서, 품질 점수 추이, 온톨로지 커버리지 | `0 3 1 * *` |

### 22.11.2 분석 결과 저장

분석 결과는 `(:AnalyticsReport)` 노드로 Neo4j에 저장하여 시계열 추이를 그래프 내에서 조회할 수 있다.

```
(:AnalyticsReport {
    reportId: "ar-2026-03-20-daily",
    reportType: "daily",
    generatedAt: datetime('2026-03-20T01:30:00'),
    totalNodes: 45230,
    totalRelationships: 128500,
    newNodesLast24h: 342,
    orphanNodes: 15,
    avgDegree: 5.68,
    qualityScore: 0.92,
    labelDistribution: '{"Vessel":12000,"Port":850,"SeaArea":220,...}'
})
```

### 22.11.3 코드 구조

```
core/kg/analytics/
├── __init__.py
├── daily_report.py      # 일간 통계 수집
├── weekly_algorithms.py # 주간 GDS 알고리즘 실행
├── monthly_growth.py    # 월간 성장 보고서
├── report_writer.py     # AnalyticsReport 노드 생성
└── alert_checker.py     # 임계치 초과 시 알림 (Prometheus Alert)
```

**알림 임계치:**

| 메트릭 | 경고 임계치 | 위험 임계치 | 의미 |
|--------|-----------|-----------|------|
| 고아 노드 비율 | > 5% | > 10% | ELT 파이프라인 또는 Entity Resolution 이상 |
| 품질 점수 하락 | < 0.85 | < 0.70 | 데이터 소스 또는 검증 규칙 이상 |
| 일간 신규 노드 | < 예상 50% | < 예상 10% | 데이터 수집 파이프라인 중단 의심 |
| 중복 노드 비율 | > 1% | > 5% | Entity Resolution 성능 저하 |

---

## 22.12 KG 완성 (Knowledge Completion) — MEDIUM (Y3+)

### 22.12.1 개요

KG 완성은 누락된 관계를 예측하여 제안하는 모듈이다. 예를 들어,
"선박 A가 부산항과 울산항에 자주 기항하므로, 울산항 → 부산항 경로도 존재할 가능성이 높다"를
Link Prediction 알고리즘으로 탐지한다.

### 22.12.2 알고리즘

| 알고리즘 | 원리 | 해사 활용 | GDS 프로시저 |
|---------|------|----------|------------|
| **Adamic-Adar** | 공통 이웃 수의 역로그 합 | 잠재적 선박-항만 연결 예측 | `gds.linkPrediction.adamicAdar` |
| **Common Neighbors** | 두 노드의 공통 이웃 수 | 유사 항만 간 항로 제안 | `gds.linkPrediction.commonNeighbors` |
| **Preferential Attachment** | 연결 많은 노드에 더 연결 | 허브 항만 예측 | `gds.linkPrediction.preferentialAttachment` |

### 22.12.3 Human-in-the-Loop

Link Prediction 결과는 자동 반영하지 않고, **제안 큐**에 저장한다.
도메인 전문가(KRISO 연구원)가 UI에서 검토 후 승인/거부한다.

```
(:LinkPrediction {
    predictionId: "lp-001",
    sourceNode: "vessel:440123456",
    targetNode: "port:KRPUS",
    relationType: "FREQUENTLY_VISITS",
    score: 0.87,
    algorithm: "adamic_adar",
    status: "PENDING",           # PENDING | APPROVED | REJECTED
    createdAt: datetime(),
    reviewedBy: null,
    reviewedAt: null
})
```

---

## 22.13 코드 매핑 종합

| 모듈 | 경로 | 상태 | 도입 시기 | 우선순위 |
|------|------|------|----------|---------|
| Temporal KG | `core/kg/temporal/` | ⏳ 설계 | Y1 Q3 | CRITICAL |
| Streaming | `core/kg/streaming/` | ⏳ 설계 | Y2 Q1 | CRITICAL |
| Graph Algorithms | `core/kg/algorithms/` | ⏳ 설계 | Y2 Q1 | HIGH |
| Reasoning + Axioms | `core/kg/reasoning/` | ⏳ 설계 | Y2 Q2 | HIGH |
| Metadata Catalog | `core/kg/catalog/` | ⏳ 설계 | Y2 Q1 | HIGH |
| Graph Embeddings | `core/kg/graph_embeddings/` | ⏳ 설계 | Y2 Q2 | HIGH |
| Consistency Checker | `core/kg/consistency/` | ⏳ 설계 | Y1 Q4 | HIGH |
| Ontology Alignment | `core/kg/ontology/alignment.py` | ⏳ 설계 | Y2 Q1 | HIGH |
| Interchange | `core/kg/interchange/` | ⏳ 설계 | Y2 Q2 | MEDIUM |
| Analytics Pipeline | `core/kg/analytics/` | ⏳ 설계 | Y2 Q3 | MEDIUM |
| KG Completion | `core/kg/completion/` | ⏳ 설계 | Y3 Q1 | MEDIUM |

**기존 모듈과의 의존 관계:**

```
신규 모듈                      의존 대상 (기존 모듈)
────────────────────────────────────────────────────
TemporalCypherBuilder     →    CypherBuilder (확장)
GraphAlgorithmRunner      →    Neo4j GDS (외부), Ontology
InferenceEngine           →    Ontology, CypherBuilder
SHACLValidator            →    n10s, Ontology
KGConsistencyChecker      →    Ontology (PropertyDefinition)
MetadataCatalog           →    QualityGate, Ontology
StreamProcessor           →    EntityResolution, ELT, LineageRecorder
FastRPEmbedder            →    Neo4j GDS (외부)
HybridRetrieval           →    OllamaEmbedder (기존), FastRPEmbedder
OntologyAligner           →    Ontology, n10s
InterchangeExporter       →    Ontology, CypherBuilder
AnalyticsPipeline         →    GraphAlgorithmRunner, QualityGate
KGCompletion              →    GraphAlgorithmRunner, Neo4j GDS
```

---

## 22.14 구현 로드맵

```
Y1 Q3 (2026.07-09) ──────────────────────────────────────────────
  │
  ├── TemporalCypherBuilder 기본 구현 + 단위 테스트
  ├── validFrom/validTo 스키마 설계 (어떤 엔티티/관계에 적용할지 확정)
  └── CSV/Cypher Script Export 기본 구현

Y1 Q4 (2026.10-12) ──────────────────────────────────────────────
  │
  ├── validFrom/validTo 스키마 적용 (Neo4j 인덱스 생성)
  ├── KGConsistencyChecker v1 (required/range/pattern 검증)
  └── 고아 노드 탐지 + 중복 노드 탐지

Y2 Q1 (2027.01-03) ──────────────────────────────────────────────
  │
  ├── Kafka Consumer 기본 구현 (AIS Near RT 처리)
  ├── Neo4j Batch MERGE 스트리밍 파이프라인
  ├── GraphAlgorithmRunner v1 (PageRank, Dijkstra, Degree)
  ├── MetadataCatalog v1 (노드 수, 품질 점수)
  ├── OntologyAligner v1 (S-101 + S-127 매핑)
  └── 시간 쿼리 REST API 엔드포인트

Y2 Q2 (2027.04-06) ──────────────────────────────────────────────
  │
  ├── InferenceEngine v1 (전이 추론, 분류 규칙)
  ├── SHACL Validator (VesselShape, PortShape)
  ├── FastRP 그래프 임베딩 생성
  ├── Text2Cypher 시간 질의 지원
  ├── JSON-LD Export
  └── 스트리밍 Back-pressure + DLQ

Y2 Q3 (2027.07-09) ──────────────────────────────────────────────
  │
  ├── Community Detection (Louvain, Label Propagation)
  ├── Node Similarity (Jaccard)
  ├── GraphML Export
  ├── AnalyticsPipeline v1 (일간/주간 리포트)
  ├── S-104 + S-412 매핑 추가
  └── Hybrid Retrieval (텍스트 + 그래프 임베딩)

Y2 Q4 (2027.10-12) ──────────────────────────────────────────────
  │
  ├── MetadataCatalog v2 (스키마 레지스트리, 이력 추적)
  ├── KGConsistencyChecker v2 (기수 제약, SHACL 연동)
  ├── AnomalyDetector (그래프 메트릭 이상 탐지, L5 검증)
  └── DerivedInsight 자동 갱신 파이프라인

Y3 Q1 (2028.01-03) ──────────────────────────────────────────────
  │
  ├── KG Completion v1 (Adamic-Adar, Common Neighbors)
  ├── A* 경로 탐색
  ├── RDF/N-Triples Export
  ├── S-111 + S-411 매핑 추가
  └── Human-in-the-Loop Link Prediction UI

Y3 Q2-Q4 (2028.04-12) ──────────────────────────────────────────
  │
  ├── 전체 모듈 안정화 + 성능 최적화
  ├── 1M 노드 규모 벤치마크 (GDS 알고리즘 성능 확인)
  ├── 온톨로지 정렬 커버리지 90% 이상 달성
  └── MVP 통합 — 모든 고급 모듈이 통합 환경에서 동작
```

---

## 22.15 성능 요구사항

| 모듈 | 지표 | Y2 목표 | Y3 목표 | Y5 목표 |
|------|------|---------|---------|---------|
| Temporal Query | `at_time()` 응답 시간 | < 500ms (50K nodes) | < 300ms (200K) | < 200ms (2M) |
| Streaming Ingest | AIS Near RT 지연 | < 10s | < 5s | < 3s |
| PageRank | 실행 시간 | < 30s (50K) | < 60s (200K) | < 5min (2M) |
| Community Detection | 실행 시간 | < 60s (50K) | < 2min (200K) | < 10min (2M) |
| Consistency Check | 전체 검증 소요 | < 5min | < 15min | < 30min |
| Graph Embedding | FastRP 생성 | < 30s (50K) | < 60s (200K) | < 5min (2M) |
| Hybrid Retrieval | 검색 응답 시간 | < 1s | < 500ms | < 300ms |
| Export (CSV) | 10K 노드 내보내기 | < 10s | < 10s | < 10s |

**Neo4j CE 제약 대응:**
- Neo4j CE는 단일 인스턴스만 지원하므로, 읽기 부하가 큰 GDS 알고리즘은
  **배치 시간대(새벽 01:00~05:00)**에 실행
- Y4에서 Neo4j EE 전환 검토 시, Read Replica 도입으로 쿼리/알고리즘 분리

---

*관련 문서: [4. 데이터 아키텍처](./04-data-architecture.md), [11. AI/LLM 아키텍처](./11-ai-llm.md), [12. 설계 원칙](./12-design-principles.md), [13. 연차별 로드맵](./13-roadmap.md), [20. NLP/NER 전략](./20-nlp-ner.md)*

---

[← 시각화 아키텍처](./21-visualization.md) | [→ README](./README.md)
