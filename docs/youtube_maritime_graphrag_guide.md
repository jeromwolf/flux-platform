# 해사 데이터로 만드는 GraphRAG — 지식그래프 실전 구축 가이드

> Neo4j + 한국어 NLP + 자체 Text-to-Cypher 파이프라인으로 해사 데이터를 지식그래프화하고, 5가지 검색 방식(Text2Cypher / Vector / VectorCypher / Hybrid / ToolsRetriever)을 구현합니다.

---

## 타임라인

| 시간 | 주제 |
|------|------|
| 00:00 | 영상 미리보기 — "부산항 근처 선박 알려줘" 라이브 데모 |
| 00:30 | 시작 — 왜 해사 데이터에 지식그래프가 필요한가? |
| 02:00 | 크롤링할 해사 데이터 4종 소개 |
| 03:30 | 데이터 속 그래프 관계 추출하기 |
| 05:00 | 온톨로지 설계 — 127개 엔티티를 10개 그룹으로 |
| 07:00 | 지식그래프 구조 이해하기 (노드, 관계, 속성) |
| 09:00 | GraphRAG 패키지와 검색 방식 5가지 |
| 10:30 | 우리의 5단계 Text-to-Cypher 파이프라인 |
| 12:00 | [실습 1] Docker로 Neo4j 시작 + 스키마 초기화 |
| 14:00 | [실습 2] 크롤러로 해사 데이터 수집 |
| 16:30 | [실습 2'] Neo4j Browser에서 그래프 확인 |
| 18:00 | [실습 3] ETL 파이프라인으로 데이터 적재 |
| 20:00 | [실습 4] Text2Cypher — 한국어 자연어 검색 |
| 22:30 | [실습 5] Vector Retriever — 임베딩 기반 유사 검색 |
| 25:00 | [실습 6] VectorCypher Retriever — 벡터 + 그래프 결합 |
| 26:00 | [실습 6.5] HybridRetriever — 풀텍스트 + 벡터 결합 |
| 27:30 | [실습 7] ToolsRetriever — AI가 검색 방법을 선택 |
| 30:00 | [실습 8] Neosemantics (n10s) — OWL 온톨로지 ↔ Neo4j 통합 |
| 33:00 | 정리 + 프로젝트 구조 한눈에 보기 |

---

## 1. 영상 미리보기 (00:00 - 00:30)

**무엇을 보여줄지**

완성된 시스템을 먼저 시연해서 시청자가 "오늘 이걸 만든다"는 목표를 명확히 인식하게 합니다.

**화면 구성**

1. 터미널에서 Python 코드 실행 — 한국어 자연어 쿼리 입력
2. 5단계 파이프라인 로그가 출력되면서 Cypher가 생성되는 과정
3. Neo4j Browser에서 그래프 시각화 — 노드와 관계가 연결된 화면

**실제 코드**

```python
from kg.pipeline import TextToCypherPipeline
from kg.cypher_validator import CypherValidator
from kg.cypher_corrector import CypherCorrector

validator = CypherValidator.from_maritime_ontology()
corrector = CypherCorrector.from_maritime_ontology()
pipeline = TextToCypherPipeline(validator=validator, corrector=corrector)

result = pipeline.process("부산항 근처 컨테이너선 알려줘")
print(result.generated_query.query)
print(result.generated_query.parameters)
print(f"검증 점수: {result.validation_score:.2f}")
print(f"자동 교정: {result.corrections_applied}")
```

**기대 출력**

```
MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port)
WHERE p.name = $port AND v.vesselType = $vesselType
RETURN v.name, v.vesselType, v.imoNumber
{'port': '부산항', 'vesselType': 'ContainerShip'}
검증 점수: 0.92
자동 교정: []
```

**한 줄 요약**: "오늘 이 시스템을 처음부터 끝까지 만들어 봅니다."

---

## 2. 왜 해사 데이터에 지식그래프가 필요한가 (00:30 - 02:00)

**무엇을 보여줄지**

해사 데이터의 복잡성을 시각적으로 설명하고, 관계형 DB의 한계와 지식그래프의 장점을 대비합니다.

### 해사 데이터의 특성

해사 도메인에는 다양한 엔티티가 복잡하게 연결되어 있습니다.

```
선박 ↔ 항구 ↔ 해역 ↔ 기상 ↔ 사고 ↔ 규정
 │                              │
 └──────── 운항 이력 ────────────┘
```

관계형 DB로 "이 선박이 방문한 항구에서 발생한 사고 중 기상 영향을 받은 것"을 검색하면:

```sql
-- 관계형 DB: JOIN 5개 필요
SELECT i.*
FROM incidents i
JOIN ports p ON i.port_id = p.id
JOIN vessel_port_visits vpv ON vpv.port_id = p.id
JOIN vessels v ON vpv.vessel_id = v.id
JOIN weather_conditions wc ON wc.sea_area_id = p.sea_area_id
WHERE v.imo_number = 'IMO-1234567'
  AND i.weather_influenced = true;
```

지식그래프(Cypher)로는 1줄입니다:

```cypher
MATCH (v:Vessel {imoNumber: 'IMO-1234567'})-[:VISITED]->(p:Port)
      <-[:OCCURRED_AT]-(i:Incident)-[:INFLUENCED_BY]->(:WeatherCondition)
RETURN i
```

### 지식그래프의 핵심 장점

| 특성 | 설명 |
|------|------|
| 관계가 1등 시민 | 관계 자체에 속성 부여 가능 (방문 날짜, 체류 시간) |
| 다중 홉 탐색 | 5-6단계 연결도 단일 쿼리로 탐색 |
| 스키마 유연성 | 새 엔티티 타입 추가가 기존 데이터에 영향 없음 |
| 시각적 직관성 | 그래프 시각화로 도메인 전문가도 이해 가능 |

---

## 3. 크롤링할 해사 데이터 4종 (02:00 - 03:30)

**무엇을 보여줄지**

각 데이터 소스의 특성과 Neo4j에 어떤 노드로 적재되는지 설명합니다. 기관명은 익명 처리합니다.

| 데이터 | 소스 | 수집 방식 | 적재 노드 |
|--------|------|----------|----------|
| 연구 논문 | 국가 해사 연구소 학술 DB | HTML 파싱 (Dublin Core 메타태그) | `Document` |
| 시험시설 | 국가 해사 연구소 홈페이지 | HTML 파싱 (시설 소개 페이지) | `TestFacility` |
| 해양기상 | 기상청 해양기상 API | REST API (JSON) | `WeatherCondition` |
| 해양사고 | 해양안전 심판원 | 웹 스크래핑 + 텍스트 파싱 | `Incident` |

### 크롤러 아키텍처

모든 크롤러는 `BaseCrawler`를 상속합니다. HTTP 세션 관리, Rate Limiting, 자동 재시도를 공통으로 제공합니다.

```python
from kg.crawlers.base import BaseCrawler, CrawlerInfo

class BaseCrawler:
    """HTTP 세션, Rate Limiting, 재시도를 제공하는 기본 크롤러."""

    def __init__(self, delay: float = 1.0, max_retries: int = 3) -> None:
        self._delay = delay
        self._max_retries = max_retries
        self._session = self._build_session()

    def crawl(self, limit: int = 50) -> list[dict]:
        """데이터 수집. 하위 클래스에서 구현."""
        raise NotImplementedError

    def save_to_neo4j(self, session, data: list[dict]) -> None:
        """수집된 데이터를 Neo4j에 MERGE로 적재."""
        raise NotImplementedError
```

### 논문 크롤러 예시

```python
from kg.crawlers.kriso_papers import KRISOPapersCrawler

crawler = KRISOPapersCrawler(delay=1.0)

# 크롤링 (Dublin Core 메타태그 파싱)
papers = crawler.crawl(limit=50)
# [
#   {
#     'title': '빙해역 선박 저항 성능에 관한 실험적 연구',
#     'authors': ['홍길동', '김철수'],
#     'keywords': ['빙해', '선박저항', '모형시험'],
#     'abstract': '본 연구는 빙해 환경에서...',
#     'published_date': '2024-03-15',
#     'handle': '2021.sw.kriso/1234'
#   },
#   ...
# ]
```

---

## 4. 데이터 속 그래프 관계 추출 (03:30 - 05:00)

**무엇을 보여줄지**

논문 텍스트에서 그래프 관계를 추출하는 과정을 보여줍니다. 키워드 기반 규칙과 한국어 동의어 사전이 핵심입니다.

### RelationExtractor 동작

```python
from kg.crawlers.relation_extractor import RelationExtractor

extractor = RelationExtractor()

text = "이 논문은 대형 예인수조에서 수행된 KVLCC2 저항시험 결과를 분석한다"

relations = extractor.extract(text)
# 추출 결과:
# [
#   Relation(source="Document", rel="CONDUCTED_AT", target="TestFacility",
#            context={"facility_name": "대형 예인수조"}),
#   Relation(source="Experiment", rel="USES", target="ModelShip",
#            context={"model_name": "KVLCC2"}),
#   Relation(source="Experiment", rel="HAS_TYPE", target="ResistanceTest"),
# ]
```

### 한국어 해사 동의어 사전의 역할

동의어 사전이 없으면 같은 엔티티를 다른 노드로 생성하는 문제가 발생합니다.

```python
from kg.nlp.maritime_terms import MARITIME_SYNONYMS

# 105개 동의어 그룹 예시
MARITIME_SYNONYMS = {
    "ContainerShip": ["컨테이너선", "컨테이너 운반선", "Container Ship", "컨선"],
    "BusanPort":     ["부산항", "Busan Port", "KRPUS", "부산 항만"],
    "TowingTank":    ["예인수조", "대형 예인수조", "Towing Tank", "조파수조"],
    "ResistanceTest":["저항시험", "선박 저항 테스트", "resistance test"],
}
```

이 사전 덕분에 "컨선", "컨테이너선", "Container Ship"이 모두 동일한 `Vessel` 노드로 매핑됩니다.

---

## 5. 온톨로지 설계 — 127개 엔티티를 10개 그룹으로 (05:00 - 07:00)

**무엇을 보여줄지**

127개 엔티티 타입을 10개 그룹으로 분류한 설계 논리를 설명합니다. Palantir Foundry 패턴을 참고한 `ObjectType`, `LinkType`, `PropertyDefinition` 구조도 소개합니다.

### 10개 그룹 분류

| 그룹 | 엔티티 수 | 대표 엔티티 |
|------|----------|-----------|
| PhysicalEntity | 24 | Vessel, Port, Cargo, Sensor, Buoy |
| SpatialEntity | 5 | SeaArea, EEZ, GeoPoint, Channel, Anchorage |
| TemporalEntity | 13 | Voyage, Incident, WeatherCondition, Inspection |
| InformationEntity | 13 | Document, Regulation, DataSource, Report |
| Observation | 6 | AISObservation, SARObservation, SensorReading |
| Agent | 7 | Organization, Person, CrewMember, Operator |
| PlatformResource | 8 | Workflow, DataPipeline, AIAgent, KGIndex |
| MultimodalData | 6 | AISData, SatelliteImage, VideoClip, SonarData |
| KRISO | 14 | Experiment, TestFacility, ModelShip, ResearchProject |
| RBAC | 4 | User, Role, DataClass, Permission |

### 온톨로지 정의 코드

```python
from kg.ontology.core import Ontology, ObjectTypeDefinition, PropertyDefinition

ontology = Ontology(name="maritime")

ontology.define_object_type(ObjectTypeDefinition(
    api_name="vessel",
    display_name="선박",
    description="항해 중인 선박 엔티티",
    primary_key="vesselId",
    properties=[
        PropertyDefinition("vesselId",    "string",   required=True),
        PropertyDefinition("name",        "string",   required=True),
        PropertyDefinition("imoNumber",   "string",   required=False),
        PropertyDefinition("vesselType",  "string",   required=False),
        PropertyDefinition("grossTonnage","integer",  required=False),
        PropertyDefinition("flag",        "string",   required=False),
    ],
))

ontology.define_link_type(
    api_name="docked_at",
    display_name="정박",
    source="vessel",
    target="port",
    properties=[
        PropertyDefinition("since",    "datetime", required=False),
        PropertyDefinition("duration", "integer",  required=False),
    ],
)
```

**표준 호환**: 이 온톨로지는 OWL 2 Turtle 형식으로도 제공되어 (maritime.ttl, 1,845줄), IHO S-100 표준 및 Neosemantics (n10s) 플러그인을 통한 Neo4j 통합을 지원합니다. 실습 8에서 다룹니다.

### 83개 관계의 분류

```
물리적 이동:     DOCKED_AT, VISITED, ON_VOYAGE, ANCHORED_AT
공간 포함:       LOCATED_IN, WITHIN_EEZ, PART_OF
사건/사고:       INVOLVED_IN, OCCURRED_AT, CAUSED_BY, INFLUENCED_BY
연구/실험:       CONDUCTED_AT, USES, AUTHORED_BY, REFERENCES
규정/감독:       GOVERNED_BY, INSPECTED_BY, COMPLIANT_WITH
데이터 계보:     DERIVED_FROM, RECORDED_BY, SOURCED_FROM
접근 제어:       HAS_ROLE, CAN_ACCESS, CLASSIFIED_AS
```

---

## 6. 지식그래프 구조 이해 (07:00 - 09:00)

**무엇을 보여줄지**

Cypher 기초 문법과 함께 노드, 관계, 속성의 개념을 실제 해사 데이터로 설명합니다.

### 기본 개념

```
노드(Node):         (v:Vessel {vesselId: 'VES-001', name: 'Korea Star'})
관계(Relationship): (v)-[:DOCKED_AT {since: datetime('2025-01-15')}]->(p)
속성(Property):     v.vesselType = 'ContainerShip'
```

### Cypher 기초 문법

```cypher
-- 노드 생성
CREATE (v:Vessel {
    vesselId:    'VES-001',
    name:        'Korea Star',
    vesselType:  'ContainerShip',
    grossTonnage: 85000,
    flag:        'KR'
})

-- 관계 생성
MATCH (v:Vessel {vesselId: 'VES-001'}),
      (p:Port   {portId:   'PORT-BUSAN'})
CREATE (v)-[:DOCKED_AT {since: datetime('2025-01-15'), berth: 'C3'}]->(p)

-- 패턴 탐색 (다중 홉)
MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port)-[:LOCATED_IN]->(sa:SeaArea)
WHERE v.vesselType = 'ContainerShip'
RETURN v.name, p.name, sa.name
LIMIT 20

-- 집계
MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port)
RETURN p.name AS 항구, count(v) AS 선박수
ORDER BY 선박수 DESC
```

### 기대 출력 (Neo4j Browser 화면)

```
항구         | 선박수
------------|------
부산항       |  47
인천항       |  31
울산항       |  22
광양항       |  18
```

---

## 7. GraphRAG 검색 방식 5가지 (09:00 - 10:30)

**무엇을 보여줄지**

`neo4j-graphrag` 패키지가 제공하는 5가지 Retriever의 차이점과 각각의 적합한 상황을 비교합니다.

| Retriever | 검색 방식 | 장점 | 단점 | 최적 상황 |
|-----------|----------|------|------|----------|
| **Text2Cypher** | 자연어 → Cypher 생성 후 그래프 탐색 | 정확한 구조적 검색, 집계/필터 가능 | LLM 의존, 복잡한 쿼리 실패 가능 | "항구별 선박 수 알려줘" 같은 명확한 질문 |
| **Vector** | 임베딩 유사도 기반 의미 검색 | 의미적 유사성 포착, LLM 불필요 | 구조적 관계 무시 | "선박 저항 관련 논문 찾아줘" |
| **Hybrid** | 풀텍스트 키워드 + 벡터 유사도 결합 | 키워드 정확성 + 의미 유사성 동시 확보 | 인덱스 2개 필요 | "KVLCC2 저항시험 논문", 특정 용어 포함 유사 문서 |
| **VectorCypher** | 벡터 검색 후 Cypher로 그래프 확장 | 유사성 + 구조 관계 동시 활용 | 설정 복잡도 높음 | "빙해수조 관련 논문과 담당 연구팀" |
| **ToolsRetriever** | AI가 질문 유형 판단 후 최적 도구 선택 | 가장 유연, 혼합 질문 처리 | 비용 높음, 디버깅 어려움 | 예측 불가한 다양한 질문 |

### 패키지 설치

```bash
pip install neo4j-graphrag langchain-neo4j langchain-ollama
```

---

## 8. 우리의 5단계 Text-to-Cypher 파이프라인 (10:30 - 12:00)

**무엇을 보여줄지**

`neo4j-graphrag` 패키지의 Text2Cypher와 달리 자체 구현한 5단계 파이프라인을 설명합니다. 검증과 자동 교정이 핵심 차별점입니다.

### 파이프라인 흐름

```
[한국어 입력] "부산항 근처 컨테이너선 찾아줘"
    |
    v Stage 1: Parse (한국어 NLP)
    |   NLParser가 동의어 사전 105개를 참조해 파싱
    |   -> StructuredQuery(
    |        intent=FIND,
    |        object_types=["vessel"],
    |        filters=[vesselType="ContainerShip"],
    |        spatial_filter={port="부산항"}
    |      )
    |
    v Stage 2: Generate (Cypher 생성)
    |   QueryGenerator가 StructuredQuery -> Cypher 변환
    |   -> MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port)
    |      WHERE p.name = $port AND v.vesselType = $type
    |      RETURN v
    |
    v Stage 3: Validate (6가지 검증)
    |   CypherValidator가 온톨로지 기반 검증 수행
    |   - 노드 라벨 존재 여부 (Vessel, Port: OK)
    |   - 관계 타입 유효성 (DOCKED_AT: OK)
    |   - 속성명 camelCase 준수 (vesselType: OK)
    |   - 파라미터 바인딩 일관성
    |   - 방향성 논리 검증
    |   - SQL 키워드 혼용 검사
    |
    v Stage 4: Correct (자동 교정)
    |   CypherCorrector가 감지된 오류 자동 수정
    |   예: vessel_type -> vesselType (camelCase 교정)
    |   예: RETURN * -> RETURN v (와일드카드 제거)
    |
    v Stage 5: Hallucination Detect (환각 감지)
    |   HallucinationDetector가 존재하지 않는
    |   노드 라벨/관계 타입 참조 여부 확인
    |   예: "XyzShip" 라벨 -> 온톨로지에 없음 -> 경고
    |
    v [결과 반환]
      PipelineOutput(
        success=True,
        generated_query=...,
        validation_score=0.92,
        corrections_applied=[]
      )
```

**"직접 만든 Text2Cypher의 강점"**: 패키지 Retriever는 생성된 Cypher를 그대로 실행하지만, 우리 파이프라인은 실행 전에 검증 → 교정 → 환각 감지를 거칩니다. 오류 원인을 `FailureType`으로 분류(`schema` / `retrieval` / `generation`)하므로 디버깅이 쉽습니다.

---

## 9. [실습 1] Docker로 Neo4j 시작 + 스키마 초기화 (12:00 - 14:00)

**무엇을 보여줄지**

프로젝트 최초 설정부터 Neo4j 스키마 초기화까지 전체 과정을 보여줍니다.

### 단계별 실행

```bash
# 1. 프로젝트 클론
git clone https://github.com/your-repo/maritime-kg.git
cd maritime-kg

# 2. 환경변수 설정
cp .env.example .env
# .env 내용:
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=your_password_here
# NEO4J_DATABASE=neo4j

# 3. Docker 시작 (docker-compose.yml에서 n10s 플러그인 포함 확인)
#    NEO4J_PLUGINS: '["apoc", "n10s"]'
#    NEO4J_dbms_security_procedures_allowlist: apoc.*,n10s.*
docker compose up -d

# 4. Neo4j 접속 확인
# 브라우저에서 http://localhost:7474 열기
# ID: neo4j / PW: <your_password>

# 5. Python 의존성 설치
pip install -r requirements.txt

# 6. 스키마 + 샘플 데이터 원클릭 설정
PYTHONPATH=. python3 -m poc.setup_poc
```

### 기대 출력

```
[INFO] Connecting to Neo4j at bolt://localhost:7687...
[INFO] Creating 24 constraints...
[INFO] Creating 44 indexes (vector/spatial/fulltext/range)...
[INFO] Loading sample data: 127 nodes, 83 relationships...
[INFO] Loading RBAC seed data...
[INFO] Setup complete!
      Nodes:         127
      Relationships: 83
      Constraints:   24
      Indexes:       44
```

### 스키마 초기화 내용

```cypher
-- 제약조건 예시 (24개 중 일부)
CREATE CONSTRAINT vessel_id_unique IF NOT EXISTS
FOR (v:Vessel) REQUIRE v.vesselId IS UNIQUE;

CREATE CONSTRAINT port_id_unique IF NOT EXISTS
FOR (p:Port) REQUIRE p.portId IS UNIQUE;

-- 벡터 인덱스 생성 (4종)
CREATE VECTOR INDEX vessel_embedding IF NOT EXISTS
FOR (v:Vessel) ON (v.textEmbedding)
OPTIONS {indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
}};

CREATE VECTOR INDEX document_embedding IF NOT EXISTS
FOR (d:Document) ON (d.textEmbedding)
OPTIONS {indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
}};

-- 공간 인덱스
CREATE POINT INDEX port_location_index IF NOT EXISTS
FOR (p:Port) ON (p.location);

-- 풀텍스트 인덱스
CREATE FULLTEXT INDEX vessel_fulltext IF NOT EXISTS
FOR (v:Vessel) ON EACH [v.name, v.description];
```

---

## 10. [실습 2] 크롤러로 해사 데이터 수집 (14:00 - 16:30)

**무엇을 보여줄지**

4종 크롤러를 순서대로 실행하고 각각 어떤 데이터를 수집하는지 로그로 확인합니다.

### 실행 명령어

```bash
# dry-run: 실제 저장하지 않고 수집 내용만 확인
PYTHONPATH=. python -m kg.crawlers.run_crawlers --dry-run

# 실제 크롤링 (50건씩, 1초 딜레이)
PYTHONPATH=. python -m kg.crawlers.run_crawlers --limit 50 --delay 1.0

# 특정 크롤러만 실행
PYTHONPATH=. python -m kg.crawlers.kriso_papers --limit 100
PYTHONPATH=. python -m kg.crawlers.kriso_facilities
PYTHONPATH=. python -m kg.crawlers.kma_marine
PYTHONPATH=. python -m kg.crawlers.maritime_accidents --limit 30
```

### 기대 출력 (run_crawlers 실행 로그)

```
[kriso-papers]    수집 시작... (limit=50)
[kriso-papers]    완료: 50건 수집, 48건 적재, 2건 실패
  -> Document 노드 48개 생성
  -> AUTHORED_BY 관계 72개 생성

[kriso-facilities] 수집 시작...
[kriso-facilities] 완료: 8개 시험시설 수집
  -> TestFacility 노드 8개 생성
  (해양공학수조, 대형예인수조, 빙해수조, 심해공학수조, ...)

[kma-marine]      수집 시작... (10개 해역)
[kma-marine]      완료: 10개 해역 기상 데이터
  -> WeatherCondition 노드 10개 생성
  -> OBSERVED_IN 관계 10개 생성

[maritime-accidents] 수집 시작... (limit=30)
[maritime-accidents] 완료: 30건 수집, 29건 적재
  -> Incident 노드 29개 생성
  -> OCCURRED_AT 관계 22개 생성
```

### 크롤러가 만드는 관계 예시

```
논문 "빙해역 선박저항" -[CONDUCTED_AT]-> 시험시설 "빙해수조"
논문 "빙해역 선박저항" -[AUTHORED_BY]-->  연구원 "홍길동"
논문 "빙해역 선박저항" -[ISSUED_BY]--->   조직 "국가 해사 연구소"
```

---

## 11. [실습 2'] Neo4j Browser에서 그래프 확인 (16:30 - 18:00)

**무엇을 보여줄지**

수집된 데이터를 Neo4j Browser에서 Cypher로 조회하고 시각화합니다.

### 조회 쿼리

```cypher
-- 적재된 노드 수 확인
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS count
ORDER BY count DESC;

-- 관계 수 확인
MATCH ()-[r]->()
RETURN type(r) AS type, count(*) AS count
ORDER BY count DESC;

-- 시각화 1: 선박-항구-해역 관계 (그래프 뷰에서 보기)
MATCH path = (v:Vessel)-[:DOCKED_AT]->(p:Port)-[:LOCATED_IN]->(sa:SeaArea)
RETURN path LIMIT 20;

-- 시각화 2: 시험시설-실험-모형선 관계
MATCH path = (e:Experiment)-[:CONDUCTED_AT]->(tf:TestFacility)
OPTIONAL MATCH (e)-[:USES]->(ms:ModelShip)
RETURN path LIMIT 10;

-- 시각화 3: 논문-저자-기관 관계
MATCH path = (d:Document)-[:AUTHORED_BY]->(p:Person)-[:WORKS_AT]->(o:Organization)
RETURN path LIMIT 15;

-- 특정 논문의 전체 연결 (에고 그래프)
MATCH path = (d:Document {handle: '2021.sw.kriso/1234'})-[*1..2]-()
RETURN path;
```

### 기대 출력 (노드 수 조회)

```
label              | count
-------------------|------
Document           |   48
WeatherCondition   |   10
TestFacility       |    8
Incident           |   29
Vessel             |   20
Port               |   12
Organization       |    5
Person             |   35
```

---

## 12. [실습 3] ETL 파이프라인으로 데이터 적재 (18:00 - 20:00)

**무엇을 보여줄지**

Fluent Builder 패턴으로 구성하는 ETL 파이프라인을 설명합니다. FULL / INCREMENTAL 모드의 차이도 비교합니다.

### 기본 사용법 (INCREMENTAL 모드)

```python
from kg.etl.pipeline import ETLPipeline
from kg.etl.models import PipelineConfig, ETLMode, IncrementalConfig
from kg.etl.transforms import TextNormalizer, DateTimeNormalizer, IdentifierNormalizer
from kg.etl.validator import RecordValidator, RequiredFieldsRule, OntologyLabelRule
from kg.etl.loader import Neo4jBatchLoader

# 파이프라인 구성 (Fluent Builder 패턴)
pipeline = (
    ETLPipeline(
        PipelineConfig(name="vessels", batch_size=100, enable_dlq=True),
        mode=ETLMode.INCREMENTAL,
        incremental_config=IncrementalConfig(
            timestamp_field="updatedAt",
            lookback_hours=24,
        ),
    )
    .add_transform(TextNormalizer(["name", "description"]))
    .add_transform(DateTimeNormalizer(["launchDate", "lastInspectionDate"]))
    .add_transform(IdentifierNormalizer("vesselId", prefix="VES"))
    .set_validator(RecordValidator([
        RequiredFieldsRule(["vesselId", "name"]),
        OntologyLabelRule("Vessel"),
    ]))
    .set_loader(Neo4jBatchLoader("Vessel", merge_key="vesselId"))
)

# 데이터 실행
records = [
    {"vesselId": "001", "name": "Korea Star", "vesselType": "ContainerShip"},
    {"vesselId": "002", "name": "Ocean King",  "vesselType": "BulkCarrier"},
]

result = pipeline.run(records, session=neo4j_session)
print(f"처리: {result.records_processed}건")
print(f"성공: {result.records_loaded}건")
print(f"실패: {result.records_failed}건 (DLQ 이동)")
print(f"소요: {result.duration_seconds:.2f}초")
```

### FULL vs INCREMENTAL 모드 비교

| 항목 | FULL | INCREMENTAL |
|------|------|-------------|
| 처리 대상 | 전체 레코드 | 변경된 레코드만 |
| 실행 시간 | 길다 | 짧다 |
| 적합한 상황 | 최초 적재, 전체 재빌드 | 일별 갱신, 실시간 반영 |
| DLQ | 지원 | 지원 |

### Dead Letter Queue 확인

```python
from kg.etl.dlq import DLQManager

dlq = DLQManager()
failed_records = dlq.list_failed(pipeline_name="vessels")

for record in failed_records:
    print(f"실패 이유: {record.error_message}")
    print(f"원본 데이터: {record.original_data}")
    # 수동 수정 후 재처리
    dlq.retry(record.id, session=neo4j_session)
```

---

## 13. [실습 4] Text2Cypher — 한국어 자연어 검색 (20:00 - 22:30)

**무엇을 보여줄지**

5단계 파이프라인으로 한국어 자연어를 Cypher로 변환하는 다양한 예시를 보여줍니다. 검증과 교정이 실제로 동작하는 장면도 포함합니다.

### 기본 파이프라인 (2단계: Parse + Generate)

```python
from kg.pipeline import TextToCypherPipeline

pipeline = TextToCypherPipeline()

# 예시 1: 단순 검색
result = pipeline.process("부산항에 정박 중인 선박 알려줘")
print(result.generated_query.query)
# MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port {name: $port})
# RETURN v.name, v.vesselType, v.imoNumber

print(result.generated_query.parameters)
# {'port': '부산항'}
```

### 전체 파이프라인 (5단계: 검증 + 교정 + 환각 감지 포함)

```python
from kg.pipeline import TextToCypherPipeline
from kg.cypher_validator import CypherValidator
from kg.cypher_corrector import CypherCorrector
from kg.hallucination_detector import HallucinationDetector

validator = CypherValidator.from_maritime_ontology()
corrector = CypherCorrector.from_maritime_ontology()
detector  = HallucinationDetector.from_maritime_ontology()

pipeline = TextToCypherPipeline(
    validator=validator,
    corrector=corrector,
    hallucination_detector=detector,
)

# 예시 2: 집계 쿼리
result = pipeline.process("항구별 선박 수 알려줘")
print(result.generated_query.query)
# MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port)
# RETURN p.name AS port, count(v) AS vesselCount
# ORDER BY vesselCount DESC

# 예시 3: 공간 쿼리
result = pipeline.process("부산항 반경 50km 이내 선박")
print(result.generated_query.query)
# MATCH (v:Vessel), (p:Port {name: $port})
# WHERE point.distance(v.location, p.location) < $radius
# RETURN v.name, v.vesselType
# {'port': '부산항', 'radius': 50000}

# 예시 4: 다중 홉 탐색
result = pipeline.process("대형 예인수조에서 수행된 실험의 모형선 제원")
print(result.generated_query.query)
# MATCH (e:Experiment)-[:CONDUCTED_AT]->(tf:TestFacility {name: $facility})
# MATCH (e)-[:USES]->(ms:ModelShip)
# RETURN ms.name, ms.scale, ms.length, ms.displacement
# {'facility': '대형 예인수조'}

# 예시 5: 자동 교정이 동작하는 경우
result = pipeline.process("컨테이너선 vessel_type으로 검색")
print(f"교정 전: {result.corrections_applied}")
# ['vessel_type -> vesselType (camelCase 교정)']
print(f"검증 점수: {result.validation_score:.2f}")
# 0.95 (교정 후 재검증)
```

### API로 호출

```bash
# REST API 호출
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "text": "부산항 근처 컨테이너선",
    "execute": false
  }'

# 응답
{
  "success": true,
  "query": "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port {name: $port}) WHERE v.vesselType = $type RETURN v",
  "parameters": {"port": "부산항", "type": "ContainerShip"},
  "validation_score": 0.92,
  "corrections_applied": [],
  "failure_type": "none"
}
```

---

## 14. [실습 5] Vector Retriever — 임베딩 기반 유사 검색 (22:30 - 25:00)

**무엇을 보여줄지**

논문 텍스트를 벡터로 임베딩하고 의미적으로 유사한 문서를 검색하는 과정을 보여줍니다.

### 임베딩 생성 (오프라인 단계)

```python
from kg.embeddings import OllamaEmbedder, generate_embeddings_batch
from kg.config import get_driver

# OllamaEmbedder: nomic-embed-text (768차원, 로컬 무료)
embedder = OllamaEmbedder()

driver = get_driver()

# Document 노드에 일괄 임베딩 생성 + 저장
result = generate_embeddings_batch(driver=driver, embedder=embedder)

print(f"처리: {result.total_processed}건")
print(f"성공: {result.total_success}건")
print(f"건너뜀: {result.total_skipped}건 (텍스트 20자 미만)")
print(f"실패: {result.total_failed}건")
```

### Vector Retriever 검색

```python
from poc.graphrag_retrievers import create_vector_retriever

vector_retriever = create_vector_retriever(
    driver=driver,
    embedder=embedder.get_neo4j_graphrag_embedder(),
)

# 의미적으로 유사한 논문 검색
results = vector_retriever.search(
    query_text="선박 저항 성능 최적화",
    top_k=5,
)

for item in results.items:
    print(f"제목: {item.content['title']}")
    print(f"유사도: {item.metadata.get('score', 'N/A'):.4f}")
    print(f"키워드: {item.content.get('keywords', [])}")
    print()
```

### 기대 출력

```
제목: KVLCC2 선형의 저항 성능 수치 해석 연구
유사도: 0.9234
키워드: ['KVLCC2', '저항성능', 'CFD', '수치해석']

제목: 컨테이너선 선형 최적화를 위한 실험적 연구
유사도: 0.8891
키워드: ['컨테이너선', '선형최적화', '모형시험', '저항']

제목: 선박 추진 효율 향상을 위한 선미 형상 연구
유사도: 0.8567
키워드: ['추진효율', '선미형상', '선박저항']
```

**Vector 검색의 한계**: "이 논문의 저자가 소속된 기관의 다른 논문"처럼 구조적 관계가 필요한 질문은 벡터 검색만으로 불가능합니다. 다음 단계에서 VectorCypher로 해결합니다.

---

## 15. [실습 6] VectorCypher Retriever — 벡터 + 그래프 결합 (25:00 - 26:00)

**무엇을 보여줄지**

벡터로 유사 논문을 찾은 뒤, Cypher로 관련 엔티티(저자, 시설, 기관)까지 함께 반환하는 방법을 보여줍니다.

### VectorCypher Retriever 설정

```python
from poc.graphrag_retrievers import create_vector_cypher_retriever

vector_cypher_retriever = create_vector_cypher_retriever(
    driver=driver,
    embedder=embedder.get_neo4j_graphrag_embedder(),
)

# 벡터 유사도 + 그래프 관계 동시 반환
results = vector_cypher_retriever.search(
    query_text="빙해 환경에서의 선박 성능",
    top_k=3,
)
```

### 기대 출력

```python
for item in results.items:
    data = item.content
    print(f"제목:     {data['title']}")
    print(f"유사도:   {data['score']:.4f}")
    print(f"저자:     {data['authors']}")
    print(f"기관:     {data['organizations']}")
    print(f"사용시설: {data['facilities']}")
    print()
```

```
제목:     빙해역 쇄빙선 저항 성능에 관한 실험적 연구
유사도:   0.9456
저자:     ['홍길동', '김철수']
기관:     ['국가 해사 연구소']
사용시설: ['빙해수조']

제목:     Arctic 항로 선박 내빙 구조 설계 연구
유사도:   0.9012
저자:     ['이영희']
기관:     ['국가 해사 연구소', 'A 조선소']
사용시설: ['빙해수조', '고압챔버']
```

**VectorCypher의 강점**: "빙해 논문"을 벡터로 찾으면서 동시에 "어떤 시험시설에서 수행됐는지" 까지 그래프에서 가져옵니다. 벡터만 쓰면 불가능한 정보입니다.

---

## 15.5. [실습 6.5] HybridRetriever — 풀텍스트 + 벡터 결합 (26:00 - 27:30)

**무엇을 보여줄지**

키워드 검색(풀텍스트 인덱스)과 의미 검색(벡터 인덱스)을 결합하여 두 장점을 동시에 활용하는 방법을 보여줍니다.

### HybridRetriever 설정

```python
from poc.graphrag_retrievers import create_hybrid_retriever

hybrid_retriever = create_hybrid_retriever(
    driver=driver,
    embedder=embedder.get_neo4j_graphrag_embedder(),
)

# 키워드 + 의미 결합 검색
results = hybrid_retriever.search(
    query_text="KVLCC2 저항시험",
    top_k=5,
)

for item in results.items:
    print(f"제목: {item.content['title']}")
    print(f"키워드: {item.content.get('keywords', [])}")
    print()
```

### 기대 출력

```
제목: KVLCC2 선형의 저항 성능 수치 해석 연구
키워드: ['KVLCC2', '저항성능', 'CFD']

제목: KVLCC2 모형선 저항시험 결과 분석
키워드: ['KVLCC2', '저항시험', '모형시험']

제목: 대형 예인수조에서의 선박 저항 계측 방법론
키워드: ['저항시험', '예인수조', '계측']
```

### Hybrid vs Vector 비교

| 검색 방식 | "KVLCC2 저항시험" 결과 | 설명 |
|----------|---------------------|------|
| Vector만 | 의미적으로 유사한 "선박 저항" 논문 | KVLCC2 미포함 가능 |
| Fulltext만 | "KVLCC2" 키워드 포함 문서 | 의미적 관련성 무시 |
| **Hybrid** | KVLCC2 키워드 포함 + 저항 관련 논문 | **두 장점 결합** |

**Hybrid의 핵심**: "KVLCC2"라는 정확한 용어를 포함하면서 동시에 "저항시험"과 의미적으로 관련된 논문을 찾습니다.

---

## 16. [실습 7] ToolsRetriever — Agentic GraphRAG (27:30 - 30:00)

**무엇을 보여줄지**

AI가 질문의 유형을 판단해서 가장 적합한 Retriever를 자동 선택하는 Agentic 방식을 보여줍니다.

### 4가지 Retriever를 도구로 등록

```python
from poc.graphrag_retrievers import create_tools_retriever
from neo4j_graphrag.llm import OllamaLLM
from neo4j_graphrag.generation import GraphRAG

llm = OllamaLLM(model_name="qwen2.5:7b")

# 4가지 Retriever를 도구로 등록 (LLM이 자동 선택)
tools_retriever = create_tools_retriever(
    driver=driver,
    embedder=embedder.get_neo4j_graphrag_embedder(),
    llm=llm,
)

# GraphRAG 통합 (retriever + LLM)
rag = GraphRAG(retriever=tools_retriever, llm=llm)
```

### AI가 도구를 자동 선택하는 예시

```python
# 질문 1: 구조적 → text2cypher 선택
query = "부산항에 정박 중인 컨테이너선 몇 척이야?"
response = rag.search(query_text=query)
# [선택된 도구: text2cypher]
# [생성된 쿼리: MATCH (v:Vessel {vesselType: 'ContainerShip'})-[:DOCKED_AT]->(p:Port {name: '부산항'}) RETURN count(v)]
# 답변: 부산항에 정박 중인 컨테이너선은 총 12척입니다.

# 질문 2: 의미적 → vector_search 선택
query = "선박 저항 성능 관련 최신 연구 동향은?"
response = rag.search(query_text=query)
# [선택된 도구: vector_search]
# [검색된 문서: 5건, 유사도 0.89-0.94]
# 답변: 최근 연구에서는 CFD 수치해석과 실험을 결합하는 방식이 주류이며...

# 질문 3: 복합 → vector_cypher 선택
query = "빙해수조에서 수행된 논문과 해당 저자 정보 알려줘"
response = rag.search(query_text=query)
# [선택된 도구: vector_cypher]
# [벡터 검색: 3건 + 그래프 확장: 저자 5명, 기관 2개]
# 답변: 빙해수조 관련 논문 3편을 찾았습니다. 홍길동(국가 해사 연구소), ...

# 질문 4: 키워드+의미 → hybrid_search 선택
query = "KVLCC2 저항시험 관련 논문 있어?"
response = rag.search(query_text=query)
# [선택된 도구: hybrid_search]
# [검색: 키워드 'KVLCC2' + 의미 '저항시험' 결합]
# 답변: KVLCC2 관련 저항시험 논문을 3편 찾았습니다...
```

### 각 도구 선택 로그 출력

```python
# 디버그 모드로 실행하면 AI 의사결정 과정 확인 가능
agent = GraphRAGAgent(tools=tools, llm=llm, verbose=True)
agent.query("빙해 논문 저자 소속 기관은?")

# 출력:
# [Thought] 이 질문은 의미적 검색(유사 논문 찾기) +
#           구조적 탐색(저자 → 기관)이 필요하므로 vector_cypher 선택
# [Action]  vector_cypher.search("빙해 논문")
# [Result]  3건 반환, 저자-기관 관계 포함
# [Answer]  ...
```

### 전체 데모 실행 (CLI)

위 실습 전체를 자동화한 데모 스크립트를 제공합니다:

```bash
# 전체 데모 (임베딩 생성 + 5가지 Retriever + Agentic GraphRAG)
PYTHONPATH=. python -m poc.graphrag_demo

# 임베딩 이미 있으면 건너뛰기
PYTHONPATH=. python -m poc.graphrag_demo --skip-embeddings

# Agentic 모드만 실행
PYTHONPATH=. python -m poc.graphrag_demo --agentic-only

# 상세 로그
PYTHONPATH=. python -m poc.graphrag_demo --verbose
```

---

## 17. [실습 8] Neosemantics (n10s) — OWL 온톨로지 ↔ Neo4j 통합 (30:00 - 33:00)

**무엇을 보여줄지**

지금까지 Python 코드로 온톨로지를 정의하고 사용했습니다. 하지만 실제 표준(IHO S-100, W3C OWL)을 준수해야 하는 제안서나 프로덕션 환경에서는 **온톨로지를 OWL 형식으로 공식화**하고, **Neo4j에 직접 임포트**할 수 있어야 합니다.

Neosemantics (n10s)는 Neo4j 공식 플러그인으로, OWL/RDF/Turtle 형식의 온톨로지를 Neo4j Property Graph로 변환합니다.

**화면 구성**

1. Python 온톨로지(127 엔티티, 83 관계) → OWL/Turtle 변환
2. maritime.ttl 파일 내용 확인 (1,845줄, 1,433 트리플)
3. n10s 플러그인으로 Neo4j에 임포트
4. Neo4j Browser에서 임포트된 온톨로지 확인

### 17-1. OWL/Turtle 온톨로지 생성

**OWLExporter로 Python 온톨로지를 Turtle 형식으로 내보내기:**

```python
from kg.n10s import OWLExporter

# 온톨로지를 OWL/Turtle로 변환
exporter = OWLExporter(
    base_uri="https://kg.kriso.re.kr/maritime#",
    ontology_name="maritime"
)
turtle = exporter.export_turtle()
print(f"생성된 Turtle: {len(turtle):,} 문자, {turtle.count(chr(10)):,} 줄")

# 파일로 저장
path = exporter.export_to_file("kg/ontology/maritime.ttl")
print(f"저장 완료: {path}")
```

**기대 출력:**
```
생성된 Turtle: 107,215 문자, 2,868 줄
저장 완료: kg/ontology/maritime.ttl
```

**CLI로도 실행 가능:**
```bash
PYTHONPATH=. python -m kg.n10s.owl_exporter
# → kg/ontology/maritime.ttl 생성
```

### 17-2. maritime.ttl 내부 구조

생성된 Turtle 파일의 핵심 구조를 살펴봅니다:

```turtle
# --- 네임스페이스 선언 ---
@prefix owl:      <http://www.w3.org/2002/07/owl#> .
@prefix maritime: <https://kg.kriso.re.kr/maritime#> .
@prefix s100:     <https://registry.iho.int/s100#> .

# --- 온톨로지 헤더 ---
maritime: a owl:Ontology ;
    dc:title "해사 도메인 온톨로지 (Maritime Domain Ontology)" ;
    dc:creator "인사이트마이닝 (InsightMining)" ;
    owl:versionInfo "1.0.0" .

# --- 11개 슈퍼클래스 그룹 ---
maritime:PhysicalEntity a owl:Class ;
    rdfs:label "물리적 개체" .

maritime:KRISOEntity a owl:Class ;
    rdfs:label "KRISO 시험 관련 개체" .

# --- 127개 엔티티 클래스 (서브클래스 관계 포함) ---
maritime:Vessel a owl:Class ;
    rdfs:subClassOf maritime:PhysicalEntity ;
    rdfs:label "Vessel" ;
    rdfs:comment "Any watercraft or ship operating at sea" .

maritime:CargoShip a owl:Class ;
    rdfs:subClassOf maritime:Vessel ;   # 2단계 서브클래스!
    rdfs:label "CargoShip" .

# --- 83개 관계 (owl:ObjectProperty) ---
maritime:DOCKED_AT a owl:ObjectProperty ;
    rdfs:domain maritime:Vessel ;
    rdfs:range maritime:Berth ;
    rdfs:comment "Vessel is currently docked at a specific berth" .

# --- 속성 (owl:DatatypeProperty) ---
maritime:Vessel_mmsi a owl:DatatypeProperty ;
    rdfs:domain maritime:Vessel ;
    rdfs:range xsd:integer .
```

**핵심 포인트:**
- **11개 슈퍼클래스**: PhysicalEntity, SpatialEntity, TemporalEntity, InformationEntity, ObservationEntity, AgentEntity, PlatformResource, MultimodalData, MultimodalRepresentation, KRISOEntity, RBACEntity
- **2단계 상속**: CargoShip → Vessel → PhysicalEntity
- **IHO S-100 네임스페이스**: `s100:` 프리픽스로 표준 호환성 확보

### 17-3. n10s 플러그인으로 Neo4j에 임포트

**N10sConfig로 그래프 설정 초기화:**

```python
from kg.config import get_driver
from kg.n10s import N10sConfig

driver = get_driver()
config = N10sConfig(driver)

# 1. 그래프 설정 초기화
config.init_graph_config({
    "handleVocabUris": "MAP",        # URI → 커스텀 프리픽스 매핑
    "handleRDFTypes": "LABELS",      # RDF 타입 → Neo4j 라벨
    "handleMultival": "ARRAY",       # 다중값 → 배열
    "applyNeo4jNaming": True,        # PascalCase/camelCase 자동 변환
})

# 2. 네임스페이스 등록 (8개)
count = config.register_namespaces()
print(f"등록된 네임스페이스: {count}개")
# → maritime, s100, owl, rdfs, xsd, dc, dcterms, geo
```

**N10sImporter로 OWL 임포트:**

```python
from kg.n10s import N10sImporter

importer = N10sImporter(driver)

# 방법 1: 전체 파이프라인 (설정 + 임포트)
result = importer.setup_and_import()
print(f"성공: {result.success}")
print(f"로드된 트리플: {result.triples_loaded}")
print(f"네임스페이스: {result.namespaces}")

# 방법 2: 미리보기 (실제 임포트 없이)
preview = importer.preview_import()
print(f"미리보기 트리플: {preview.triples_loaded}")
```

**기대 출력:**
```
성공: True
로드된 트리플: 1433
네임스페이스: 8
```

### 17-4. Neo4j Browser에서 확인

임포트 후 Neo4j Browser에서 온톨로지 구조를 확인합니다:

```cypher
// 임포트된 클래스 확인
MATCH (c:owl__Class)
RETURN c.rdfs__label AS label, c.uri AS uri
LIMIT 20

// 서브클래스 관계 확인
MATCH (sub)-[:rdfs__subClassOf]->(parent)
RETURN sub.rdfs__label AS 하위클래스, parent.rdfs__label AS 상위클래스
LIMIT 20

// KRISO 시험시설 관련 클래스
MATCH path = (tf:owl__Class)-[:rdfs__subClassOf*1..2]->(parent)
WHERE tf.rdfs__label CONTAINS 'Tank' OR tf.rdfs__label CONTAINS 'Tunnel'
RETURN path
```

### 17-5. 왜 n10s가 중요한가?

| 관점 | n10s 없이 | n10s 사용 시 |
|------|----------|------------|
| 온톨로지 형식 | Python dict만 | OWL/Turtle (국제 표준) |
| 표준 호환 | IHO S-100 구두 주장만 | OWL 파일로 검증 가능 |
| 외부 공유 | 코드 공유 필요 | .ttl 파일 1개로 공유 |
| 도구 연동 | 불가 | Protege, WebVOWL 등 활용 가능 |
| RFP 제안서 | "구현 예정" | "구현 완료 + 코드 증빙" |
| SHACL 검증 | 불가 | n10s.validation.shacl.validate 사용 가능 |

**한 줄 요약**: "Python 온톨로지를 국제 표준 OWL 형식으로 공식화하고, n10s 플러그인으로 Neo4j에 통합했습니다."

---

## 18. 정리 + 프로젝트 구조 한눈에 보기 (33:00 - 35:00)

**무엇을 보여줄지**

전체 아키텍처를 10계층 다이어그램으로 정리하고 프로젝트 핵심 수치를 보여줍니다.

### 전체 아키텍처 10계층

```
계층 01: 원본 데이터
         [논문 DB] [시험시설] [해양기상 API] [해양사고 DB]
              |
계층 02: 크롤러 (4종)
         [KRISOPapersCrawler] [FacilitiesCrawler] [KMAMarineCrawler] [AccidentsCrawler]
         공통: BaseCrawler (Rate Limiting, 재시도, 세션 관리)
              |
계층 03: ETL 파이프라인
         ETLPipeline (Fluent Builder)
         [TextNormalizer] [DateTimeNormalizer] [IdentifierNormalizer]
         [RecordValidator] [OntologyLabelRule] [DLQ]
         FULL 모드 / INCREMENTAL 모드
              |
계층 04: 온톨로지 & 스키마
         Ontology (127 엔티티, 83 관계)
         ObjectTypeDefinition / LinkTypeDefinition / PropertyDefinition
         OWL/Turtle (maritime.ttl, 1,433 트리플) + Neosemantics (n10s)
         Neo4j 스키마: 24 제약조건, 44 인덱스
              |
계층 05: 그래프 DB (Neo4j 5.26 Community)
         노드 / 관계 / 속성 / 벡터 인덱스(4종) / 공간 인덱스 / 풀텍스트 인덱스
              |
계층 06: 한국어 NLP
         MaritimeTerms (105 동의어, 22 관계 키워드)
         NLParser -> StructuredQuery
              |
계층 07: Text-to-Cypher 5단계 파이프라인
         Stage1: Parse  -> Stage2: Generate -> Stage3: Validate
         Stage4: Correct -> Stage5: HallucinationDetect
         CypherValidator (6가지 검증, FailureType 분류)
         CypherCorrector (규칙 기반 자동 교정)
              |
계층 08: GraphRAG 검색 (5가지 Retriever)
         [Text2Cypher] [VectorRetriever] [HybridRetriever] [VectorCypherRetriever] [ToolsRetriever]
              |
계층 09: 품질 보증
         QualityGate (8가지 자동 검증)
         EvaluationFramework (30개 해사 평가 질문)
         EntityResolution (3단계 해석기)
         DataLineage (W3C PROV-O)
              |
계층 10: RBAC & API
         Role-Based Access Control (User / Role / DataClass / Permission)
         REST API (/api/query, /api/lineage)
         PoC Demo (langchain_qa.py, kg_visualizer.html)
```

### 프로젝트 핵심 수치

| 항목 | 수치 |
|------|------|
| 온톨로지 엔티티 타입 | 127개 |
| 온톨로지 관계 타입 | 83개 |
| 속성 정의 | 29개 |
| 동의어 사전 | 105개 그룹 |
| 관계 키워드 | 22개 |
| OWL 온톨로지 | maritime.ttl (1,845줄, 1,433 트리플) |
| n10s 네임스페이스 | 8개 (maritime, s100, owl, rdfs, xsd, dc, dcterms, geo) |
| 테스트 | 1,095개 (단위) / 1,140개 (전체) |
| Neo4j 제약조건 | 24개 |
| Neo4j 인덱스 | 44개 |
| 크롤러 | 4종 |
| 검색 방식 | 5가지 (Text2Cypher / Vector / VectorCypher / Hybrid / Tools) |

### 다음 영상 예고

"다음 영상: 2차년도 — 실시간 AIS 스트리밍 + Kafka로 선박 위치를 실시간 그래프에 반영하기"

---

## 부록 A: 공원나연 영상과의 비교표

| 항목 | 공원나연 (뉴스 데이터) | 이 영상 (해사 데이터) |
|------|---------------------|---------------------|
| 데이터 소스 | 네이버 뉴스 1종 | 4종 (논문/시설/기상/사고) |
| 관계 추출 | LLM 자동 추출 | 키워드 기반 + 온톨로지 설계 |
| 엔티티 수 | LLM 생성 (가변) | 127개 (설계된 고정 스키마) |
| 관계 수 | LLM 생성 (가변) | 83개 (설계된 고정 스키마) |
| Text2Cypher | neo4j-graphrag 패키지 사용 | 자체 5단계 파이프라인 + 검증/교정 |
| Cypher 검증 | 없음 | 6가지 규칙 검증 + FailureType 분류 |
| Cypher 자동 교정 | 없음 | 규칙 기반 교정기 |
| 환각 감지 | 없음 | 온톨로지 기반 HallucinationDetector |
| Vector Retriever | 있음 | 있음 (벡터 인덱스 4종) |
| Hybrid Retriever | 없음 | 있음 (풀텍스트 + 벡터 결합) |
| VectorCypher Retriever | 있음 | 있음 |
| ToolsRetriever | 있음 | 있음 |
| 한국어 NLP | LLM 의존 | 전용 동의어 사전 (105개) |
| ETL 파이프라인 | 없음 | FULL/INCREMENTAL + DLQ |
| 데이터 리니지 | 없음 | W3C PROV-O 기반 |
| Entity Resolution | 없음 | 3단계 해석기 |
| 품질 게이트 | 없음 | 8가지 자동 검증 (CI/CD용) |
| RBAC | 없음 | 역할 기반 접근 제어 |
| OWL 온톨로지 | 없음 | OWL 2 Turtle (1,433 트리플) + n10s 임포트 |
| 테스트 | 없음 | 1,095개 단위 테스트 |

---

## 부록 B: 시청자가 따라할 수 있는 퀵스타트

```bash
# 1. 클론
git clone https://github.com/your-repo/maritime-kg.git
cd maritime-kg

# 2. 환경 설정
cp .env.example .env
# .env 편집: NEO4J_PASSWORD=your_password_here 확인

# 3. Docker 시작
docker compose up -d

# 4. Python 의존성
pip install -r requirements.txt

# 5. 스키마 + 샘플 데이터 원클릭 설정
PYTHONPATH=. python3 -m poc.setup_poc

# 6. 데모 실행 (LLM 없이)
PYTHONPATH=. python3 -m poc.run_poc_demo --no-llm

# 7. 자연어 쿼리 테스트
PYTHONPATH=. python3 -c "
from kg.pipeline import TextToCypherPipeline
p = TextToCypherPipeline()
r = p.process('부산항에 정박 중인 선박 알려줘')
print('쿼리:', r.generated_query.query)
print('파라미터:', r.generated_query.parameters)
print('성공:', r.success)
"

# 8. n10s OWL 온톨로지 생성 + 임포트
PYTHONPATH=. python -m kg.n10s.owl_exporter
# Neo4j 연결 후: python -c "from kg.n10s import N10sImporter; from kg.config import get_driver; N10sImporter(get_driver()).setup_and_import()"
```

---

## 부록 C: 사용할 수 있는 자연어 쿼리 예시 10선

| 번호 | 쿼리 | 생성되는 쿼리 유형 |
|------|------|-----------------|
| 1 | "부산항에 정박 중인 선박 알려줘" | 패턴 매칭 + 필터 |
| 2 | "컨테이너선 목록 보여줘" | 단순 노드 조회 |
| 3 | "항구별 선박 수 알려줘" | 집계 (GROUP BY) |
| 4 | "최근 해양사고 목록" | 시간 기반 정렬 |
| 5 | "기상 위험도 HIGH인 해역" | 속성 필터 |
| 6 | "대형 예인수조에서 수행된 실험" | 다중 홉 탐색 |
| 7 | "KVLCC2 모형선 관련 정보" | 특정 엔티티 조회 |
| 8 | "부산항 반경 50km 이내 선박" | 공간 쿼리 |
| 9 | "선박 평균 총톤수" | 수치 집계 |
| 10 | "해양안전 관련 규정" | 키워드 검색 |

---

## 부록 D: 촬영 팁

| 항목 | 권장 |
|------|------|
| 화면 해상도 | 1920x1080, 폰트 16pt 이상 (코드 가독성) |
| 코드 에디터 | VS Code Dark 테마, 탭 너비 4 |
| 터미널 | iTerm2 또는 Windows Terminal (폰트 크게) |
| Neo4j Browser | 전체 화면, 노드 색상 커스텀 (그룹별 다른 색상) |
| 배경 음악 | Lo-fi 코딩 BGM (저작권 프리) |
| 캡션 | 한국어 + 영어 (글로벌 도달) |
| 영상 길이 | 30~35분 (공원나연 영상과 유사) |
| 업로드 | 본편 + 실습 코드 GitHub 링크 함께 제공 |

### Neo4j Browser 노드 색상 가이드

```
Vessel          → 파란색 (#4A90E2)
Port            → 초록색 (#7ED321)
SeaArea         → 하늘색 (#50E3C2)
Incident        → 빨간색 (#D0021B)
WeatherCondition→ 노란색 (#F5A623)
Document        → 보라색 (#9B59B6)
TestFacility    → 주황색 (#E67E22)
Person          → 분홍색 (#E91E8C)
Organization    → 회색   (#95A5A6)
```

---

## 부록 E: 시리즈 확장 아이디어

| 회차 | 제목 아이디어 | 주요 내용 |
|------|-------------|---------|
| EP.1 | 본편 (이 영상) | 해사 GraphRAG 전체 구축 (크롤링 → Neo4j → 5가지 Retriever) |
| EP.2 | "테스트 940개의 비밀" | TDD 관점으로 본 품질 보증 — 품질 게이트 CI/CD 적용기 |
| EP.3 | "실시간 AIS로 선박 추적하기" | Kafka + 스트리밍 → Neo4j 실시간 그래프 갱신 |
| EP.4 | "AI가 만든 쿼리, 믿어도 될까?" | 환각 감지 + FailureType 분류 심화 분석 |
| EP.5 | "한국어 NLP로 해사 검색 만들기" | 동의어 사전 구축, ReasoningType 설계, NLParser 내부 구조 |
| EP.6 | "데이터 리니지: 데이터 출처 추적하기" | W3C PROV-O 기반 리니지 + RBAC 연동 |
| EP.7 | "OWL 온톨로지로 표준 지키기" | Neosemantics (n10s) + IHO S-100 Feature Catalogue → OWL 매핑 심화 |
