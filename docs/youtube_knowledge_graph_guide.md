# 실전 Knowledge Graph 구축 가이드: 데이터 수집부터 자연어 검색까지

> 해사(Maritime) 도메인을 예시로, 지식그래프를 설계하고 Neo4j에 적재하고, 자연어로 검색하는 전체 과정을 다룹니다.

---

## 1. 원본 데이터: 어떤 데이터로 지식그래프를 만드나?

### 1.1 데이터 소스 유형

지식그래프의 원본 데이터는 크게 3가지로 나뉩니다.

| 유형 | 예시 | 특징 |
|------|------|------|
| **정형 데이터** | 선박 AIS 위치 데이터, 항만 통계 DB | 스키마가 명확, 바로 노드/관계로 변환 가능 |
| **반정형 데이터** | 논문 메타데이터(Dublin Core), 기상 API JSON | 구조는 있지만 관계가 암시적 |
| **비정형 데이터** | 사고 보고서 텍스트, 뉴스 기사 | NLP로 엔티티/관계 추출 필요 |

### 1.2 실제 사용한 데이터 4종

```
1. 학술 논문 메타데이터 (~11,000건)
   - 제목, 저자, 초록, 키워드, 발행일
   - 웹 크롤링 + BeautifulSoup 파싱

2. 해양 기상 관측 데이터 (10개 해역)
   - 풍향, 풍속, 파고, 수온, 시정
   - 기상청 API 연동

3. 해양 사고 이력 데이터
   - 사고 유형(충돌/좌초/화재/전복/침몰)
   - 위치, 시간, 심각도, 관련 선박

4. 시험시설 운영 데이터
   - 시설 제원, 실험 이력, 계측 데이터
   - 조직-시설-실험-계측 관계 체인
```

### 1.3 데이터 수집기 아키텍처

모든 크롤러는 공통 기반 클래스를 상속합니다.

```python
class BaseCrawler:
    """데이터 수집기 공통 인터페이스"""

    def __init__(self, delay: float = 1.0, max_retries: int = 3):
        self.delay = delay          # 요청 간 대기 (서버 부하 방지)
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "KG-Crawler/1.0",
            "Accept-Language": "ko-KR,ko;q=0.9",
        })

    def fetch(self, url: str) -> str | None:
        """HTTP GET + 지수 백오프 재시도"""
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.delay)
                resp = self._session.get(url, timeout=30)
                if resp.status_code == 404:
                    return None
                if resp.status_code == 429:       # Rate limit
                    time.sleep(int(resp.headers.get("Retry-After", 60)))
                    continue
                resp.raise_for_status()
                return resp.text
            except requests.RequestException:
                time.sleep(2 ** attempt)           # 지수 백오프
        return None

    @abstractmethod
    def save_to_neo4j(self, records, session):
        """수집된 데이터를 Neo4j에 적재 (하위 클래스에서 구현)"""
        ...
```

**핵심 포인트:**
- 요청 간 `delay`로 대상 서버 보호
- 429/5xx 에러 시 자동 재시도 (지수 백오프)
- `save_to_neo4j()`는 각 크롤러가 자체 구현

---

## 2. 지식그래프 설계: 노드, 관계, 프로퍼티

### 2.1 노드(Node) 설계

노드는 도메인의 **엔티티(개체)**를 나타냅니다.

```
노드 설계 원칙:
- 레이블(Label)은 PascalCase: Vessel, Port, Experiment
- 고유 식별자(ID)를 반드시 가져야 함: mmsi, unlocode, experimentId
- 속성명은 camelCase: vesselType, currentLocation
```

**실제 노드 예시 (11개 그룹, 127개 유형):**

```
선박 그룹          항만/해역 그룹        연구/실험 그룹
├─ Vessel          ├─ Port              ├─ Experiment
├─ CargoShip       ├─ Berth             ├─ TestFacility
├─ Tanker          ├─ Waterway          ├─ ModelShip
├─ PassengerShip   ├─ SeaArea           ├─ Measurement
└─ AutonomousShip  └─ AnchorageArea     └─ Sensor

안전 그룹          기상 그룹             조직/문서 그룹
├─ Incident        ├─ WeatherCondition  ├─ Organization
├─ Collision       ├─ SeaState          ├─ Document
├─ Grounding       └─ CurrentData       └─ Regulation
└─ Fire
```

### 2.2 관계(Relationship) 설계

관계는 노드 간의 **연결**을 나타냅니다.

```
관계 설계 원칙:
- 타입명은 SCREAMING_SNAKE_CASE: DOCKED_AT, OWNED_BY
- 방향이 있어야 함: (Vessel)-[:DOCKED_AT]->(Port)
- from_type과 to_type을 명확히 정의
```

**핵심 관계 패턴 (83개 유형):**

```cypher
-- 선박-항만 관계
(vessel:Vessel)-[:DOCKED_AT]->(port:Port)
(vessel:Vessel)-[:ON_VOYAGE]->(voyage:Voyage)
(vessel:Vessel)-[:CARRIES]->(cargo:Cargo)

-- 소유/운영 관계
(vessel:Vessel)-[:OWNED_BY]->(org:Organization)
(org:Organization)-[:OPERATES]->(facility:TestFacility)

-- 실험 관계 체인 (3-hop)
(experiment:Experiment)-[:CONDUCTED_AT]->(facility:TestFacility)
(experiment:Experiment)-[:USES_MODEL]->(modelShip:ModelShip)
(experiment:Experiment)-[:HAS_MEASUREMENT]->(measurement:Measurement)

-- 사고/안전 관계
(incident:Incident)-[:OCCURRED_NEAR]->(port:Port)
(incident:Incident)-[:INVOLVES]->(vessel:Vessel)

-- 접근 제어(RBAC) 관계
(user:User)-[:HAS_ROLE]->(role:Role)
(role:Role)-[:CAN_ACCESS]->(dataClass:DataClass)
```

### 2.3 프로퍼티(Property) 설계

프로퍼티는 노드와 관계의 **속성값**입니다.

```python
# 프로퍼티 정의 예시 (29개 속성 스키마)
PROPERTY_DEFINITIONS = {
    "mmsi": {
        "type": "INTEGER",
        "required": True,
        "unique": True,
        "description": "해상이동업무식별번호 (9자리)"
    },
    "currentLocation": {
        "type": "POINT",           # Neo4j 공간 타입
        "indexed": True,
        "description": "현재 위치 (위도, 경도)"
    },
    "vesselType": {
        "type": "STRING",
        "enum_values": ["ContainerShip", "Tanker", "BulkCarrier", "PassengerShip"],
        "indexed": True,
    },
    "createdAt": {
        "type": "DATETIME",
        "description": "생성 시각"
    },
}
```

**프로퍼티 타입 종류:**

| 타입 | Neo4j 타입 | 용도 | 예시 |
|------|-----------|------|------|
| `STRING` | String | 텍스트 | name, vesselType |
| `INTEGER` | Integer | 정수 | mmsi, tonnage |
| `FLOAT` | Float | 실수 | latitude, speed |
| `DATETIME` | DateTime | 시간 | createdAt, departureTime |
| `POINT` | Point | 좌표 | currentLocation |
| `LIST<STRING>` | List | 목록 | keywords[], authors[] |

---

## 3. Neo4j에 넣는 방법

### 3.1 스키마 초기화: 제약조건 + 인덱스

데이터를 넣기 전에 반드시 **제약조건(Constraint)**과 **인덱스(Index)**를 먼저 설정합니다.

#### 제약조건 (24개)

```cypher
-- 비즈니스 키 유니크 제약조건
CREATE CONSTRAINT vessel_mmsi IF NOT EXISTS
  FOR (v:Vessel) REQUIRE v.mmsi IS UNIQUE;

CREATE CONSTRAINT port_unlocode IF NOT EXISTS
  FOR (p:Port) REQUIRE p.unlocode IS UNIQUE;

CREATE CONSTRAINT experiment_id IF NOT EXISTS
  FOR (e:Experiment) REQUIRE e.experimentId IS UNIQUE;

-- RBAC 관련 제약조건
CREATE CONSTRAINT user_id IF NOT EXISTS
  FOR (u:User) REQUIRE u.userId IS UNIQUE;

CREATE CONSTRAINT role_id IF NOT EXISTS
  FOR (r:Role) REQUIRE r.roleId IS UNIQUE;
```

**왜 제약조건이 먼저인가?**
- MERGE 시 유니크 키를 기준으로 매칭
- 제약조건 없으면 중복 노드 생성 위험
- 유니크 제약조건은 자동으로 인덱스도 생성

#### 범위 인덱스 (29개) - 자주 쓰는 WHERE 조건

```cypher
CREATE INDEX vessel_type IF NOT EXISTS
  FOR (v:Vessel) ON (v.vesselType);

CREATE INDEX incident_date IF NOT EXISTS
  FOR (i:Incident) ON (i.date);

CREATE INDEX weather_risk IF NOT EXISTS
  FOR (w:WeatherCondition) ON (w.riskLevel);
```

#### 풀텍스트 인덱스 (8개) - 텍스트 검색

```cypher
-- 여러 속성을 하나의 풀텍스트 인덱스로 묶기
CREATE FULLTEXT INDEX document_search IF NOT EXISTS
  FOR (d:Document) ON EACH [d.title, d.content, d.summary];

CREATE FULLTEXT INDEX vessel_search IF NOT EXISTS
  FOR (v:Vessel) ON EACH [v.name, v.callSign];

CREATE FULLTEXT INDEX regulation_search IF NOT EXISTS
  FOR (r:Regulation) ON EACH [r.title, r.description, r.code];
```

#### 공간 인덱스 (5개) - 위치 기반 검색

```cypher
CREATE POINT INDEX vessel_location IF NOT EXISTS
  FOR (v:Vessel) ON (v.currentLocation);

CREATE POINT INDEX port_location IF NOT EXISTS
  FOR (p:Port) ON (p.location);

CREATE POINT INDEX incident_location IF NOT EXISTS
  FOR (i:Incident) ON (i.location);
```

#### 벡터 인덱스 (4개) - 임베딩 유사도 검색

```cypher
-- 텍스트 임베딩 (768차원, 코사인 유사도)
CREATE VECTOR INDEX text_embedding IF NOT EXISTS
  FOR (n:Document) ON (n.textEmbedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }};

-- 이미지 임베딩 (512차원)
CREATE VECTOR INDEX visual_embedding IF NOT EXISTS
  FOR (n:Observation) ON (n.visualEmbedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 512,
    `vector.similarity_function`: 'cosine'
  }};

-- 궤적(trajectory) 임베딩 (256차원)
CREATE VECTOR INDEX trajectory_embedding IF NOT EXISTS
  FOR (n:TrackSegment) ON (n.trajectoryEmbedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 256,
    `vector.similarity_function`: 'cosine'
  }};

-- 멀티모달 퓨전 임베딩 (1024차원)
CREATE VECTOR INDEX fused_embedding IF NOT EXISTS
  FOR (n:Observation) ON (n.fusedEmbedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 1024,
    `vector.similarity_function`: 'cosine'
  }};
```

**벡터 인덱스 핵심 파라미터:**

| 파라미터 | 설명 | 권장값 |
|----------|------|--------|
| `vector.dimensions` | 임베딩 차원 수 | 모델에 맞게 (768, 1536 등) |
| `vector.similarity_function` | 유사도 함수 | `cosine` (가장 범용) |

**벡터 검색 쿼리:**

```cypher
-- 유사한 문서 찾기 (Top 10)
CALL db.index.vector.queryNodes('text_embedding', 10, $queryVector)
YIELD node, score
RETURN node.title, score
ORDER BY score DESC
```

### 3.2 데이터 적재: MERGE 패턴

데이터 적재의 핵심은 **MERGE**입니다. INSERT가 아닙니다.

```cypher
-- MERGE = "있으면 업데이트, 없으면 생성"

-- 1단계: 노드 생성 (UNWIND로 배치 처리)
UNWIND $vessels AS v
MERGE (vessel:Vessel {mmsi: v.mmsi})     -- 유니크 키로 매칭
  ON CREATE SET                           -- 최초 생성 시
    vessel.name = v.name,
    vessel.vesselType = v.vesselType,
    vessel.currentLocation = point({
      latitude: v.lat,
      longitude: v.lon
    }),
    vessel.createdAt = datetime()
  ON MATCH SET                            -- 이미 존재 시 (업데이트)
    vessel.name = v.name,
    vessel.currentLocation = point({
      latitude: v.lat,
      longitude: v.lon
    }),
    vessel.updatedAt = datetime()
RETURN count(vessel) AS cnt

-- 2단계: 관계 생성
MATCH (vessel:Vessel {mmsi: $mmsi})
MATCH (port:Port {unlocode: $portCode})
MERGE (vessel)-[r:DOCKED_AT]->(port)
  ON CREATE SET r.since = datetime(), r.status = 'arrived'
  ON MATCH SET r.lastSeen = datetime()
```

**왜 MERGE인가?**
- 멱등성(idempotent): 몇 번 실행해도 결과 동일
- 중복 노드/관계 방지
- 증분 업데이트에 적합

### 3.3 Python에서 적재하는 코드

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "your-password")
)

def load_vessels(vessels: list[dict]):
    """선박 데이터 배치 적재"""
    query = """
    UNWIND $vessels AS v
    MERGE (vessel:Vessel {mmsi: v.mmsi})
      ON CREATE SET
        vessel.name = v.name,
        vessel.vesselType = v.vesselType,
        vessel.currentLocation = point({
          latitude: v.lat, longitude: v.lon
        }),
        vessel.createdAt = datetime()
      ON MATCH SET
        vessel.updatedAt = datetime()
    RETURN count(vessel) AS cnt
    """
    with driver.session() as session:
        result = session.run(query, vessels=vessels)
        print(f"Loaded {result.single()['cnt']} vessels")

# 사용 예시
vessels = [
    {"mmsi": 440123456, "name": "태평양호", "vesselType": "ContainerShip",
     "lat": 35.1028, "lon": 129.0403},
    {"mmsi": 440789012, "name": "한라호", "vesselType": "Tanker",
     "lat": 37.4563, "lon": 126.5922},
]
load_vessels(vessels)
```

### 3.4 ETL 파이프라인으로 자동화

실제 운영에서는 ETL 파이프라인으로 자동화합니다.

```python
from kg.etl import ETLPipeline, PipelineConfig, RecordEnvelope
from kg.etl import Neo4jBatchLoader, RecordValidator, TextNormalizer

# 1. 파이프라인 구성
pipeline = (
    ETLPipeline(PipelineConfig(name="vessel-etl"))
    .set_validator(RecordValidator())      # 온톨로지 준수 검증
    .add_transform(TextNormalizer())       # 텍스트 정규화
    .set_loader(Neo4jBatchLoader(          # Neo4j 배치 적재
        label="Vessel",
        id_field="mmsi"
    ))
)

# 2. 데이터를 RecordEnvelope로 감싸기
records = [
    RecordEnvelope(
        record_id="V001",
        source="ais-api",
        data={"mmsi": 440123456, "name": "태평양호", "vesselType": "ContainerShip"}
    )
]

# 3. 실행
result = pipeline.run(records, session=neo4j_session)
print(f"성공: {result.records_processed}, 실패: {result.errors}")
```

**ETL 파이프라인 흐름:**

```
원본 데이터
    │
    ▼
[RecordValidator]     ← 온톨로지 스키마 검증
    │  ├─ 통과 → 다음 단계
    │  └─ 실패 → Dead Letter Queue (DLQ)
    ▼
[TransformStep]       ← 텍스트 정규화, 날짜 변환 등
    │
    ▼
[Neo4jBatchLoader]    ← MERGE로 배치 적재
    │
    ▼
[LineageRecorder]     ← 데이터 계보(Lineage) 기록
```

---

## 4. 조회하는 방법

### 4.1 기본 Cypher 쿼리

```cypher
-- 특정 선박 조회
MATCH (v:Vessel {vesselType: 'ContainerShip'})
RETURN v.name, v.mmsi
LIMIT 10

-- 특정 항만에 정박 중인 선박
MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port {name: '부산항'})
RETURN v.name, v.vesselType

-- 3-hop 관계 탐색: 기관 → 시설 → 실험 → 계측
MATCH (org:Organization)-[:OPERATES]->(f:TestFacility)
      -[:HAS_EXPERIMENT]->(e:Experiment)
      -[:HAS_MEASUREMENT]->(m:Measurement)
RETURN org.name, f.name, e.name, m.value
```

### 4.2 Fluent Cypher Builder (SQL Injection 방지)

직접 문자열로 Cypher를 만들면 위험합니다. Builder 패턴을 사용하세요.

```python
from kg import CypherBuilder

# 안전한 쿼리 생성 (파라미터 바인딩)
query, params = (
    CypherBuilder()
    .match("(v:Vessel)")
    .where("v.vesselType = $type", {"type": "ContainerShip"})
    .where("v.tonnage >= $minTonnage", {"minTonnage": 5000})
    .return_("v.name, v.mmsi, v.tonnage")
    .order_by("v.tonnage DESC")
    .limit(10)
    .build()
)

# 생성 결과:
# query: MATCH (v:Vessel) WHERE v.vesselType = $type AND v.tonnage >= $minTonnage
#        RETURN v.name, v.mmsi, v.tonnage ORDER BY v.tonnage DESC LIMIT 10
# params: {"type": "ContainerShip", "minTonnage": 5000}
```

### 4.3 공간(위치) 기반 검색

```python
# 특정 좌표 반경 10km 이내 선박 검색
query, params = CypherBuilder.nearby_entities(
    entity_type="Vessel",
    center_lat=35.1028,    # 부산항 위도
    center_lon=129.0403,   # 부산항 경도
    radius_km=10,
    location_property="currentLocation",
    limit=20
)
```

생성되는 Cypher:

```cypher
MATCH (v:Vessel)
WHERE point.distance(
    v.currentLocation,
    point({latitude: $lat, longitude: $lon, crs: 'WGS-84'})
) < $radius
RETURN v, point.distance(v.currentLocation, point({...})) AS distance
ORDER BY distance ASC
LIMIT 20
```

### 4.4 풀텍스트 검색

```python
# 문서 풀텍스트 검색
query, params = CypherBuilder.fulltext_search(
    index_name="document_search",
    search_term="자율운항 충돌회피",
    limit=10
)
```

생성되는 Cypher:

```cypher
CALL db.index.fulltext.queryNodes($indexName, $searchTerm)
YIELD node, score
RETURN node, score
ORDER BY score DESC
LIMIT 10
```

### 4.5 벡터 유사도 검색

```cypher
-- 텍스트 임베딩으로 유사 문서 검색
WITH $queryEmbedding AS queryVec
CALL db.index.vector.queryNodes('text_embedding', 10, queryVec)
YIELD node, score
RETURN node.title AS title, score
ORDER BY score DESC
```

Python에서:

```python
# 1. 텍스트를 임베딩 벡터로 변환
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
query_vec = model.encode("자율운항 선박 충돌 방지").tolist()

# 2. Neo4j 벡터 검색
with driver.session() as session:
    result = session.run("""
        CALL db.index.vector.queryNodes('text_embedding', 10, $vec)
        YIELD node, score
        RETURN node.title, score
    """, vec=query_vec)

    for record in result:
        print(f"{record['node.title']} (score: {record['score']:.4f})")
```

---

## 5. 자연어로 검색: Text-to-Cypher

### 5.1 왜 Text-to-Cypher인가?

```
사용자: "부산항 근처에 정박 중인 5000톤 이상 컨테이너선 알려줘"

                    ↓ Text-to-Cypher

MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port)
WHERE p.name CONTAINS '부산'
  AND v.vesselType = 'ContainerShip'
  AND v.tonnage >= 5000
RETURN v.name, v.tonnage, p.name
```

사용자는 Cypher를 몰라도 자연어로 지식그래프를 검색할 수 있습니다.

### 5.2 5단계 파이프라인

```
한국어 텍스트
    │
    ▼
[Stage 1: Parse]          한국어 → StructuredQuery
    │  - 엔티티 추출 (105개 한국어 동의어 사전)
    │  - 관계 추출 (22개 관계 키워드)
    │  - 필터 추출 (숫자 비교, 속성값 매핑)
    │  - 추론 유형 분류 (DIRECT/BRIDGE/COMPARISON 등)
    ▼
[Stage 2: Generate]       StructuredQuery → Cypher
    │  - 노드 패턴 생성
    │  - 관계 패턴 생성
    │  - WHERE 절 파라미터화
    ▼
[Stage 3: Validate]       Cypher 검증 (선택)
    │  - 레이블이 온톨로지에 존재하는지
    │  - 관계 타입이 유효한지
    │  - 문법 오류 검사
    ▼
[Stage 4: Correct]        자동 교정 (선택)
    │  - 대소문자 수정 (vessel → Vessel)
    │  - 누락된 RETURN 절 추가
    │  - 관계 방향 수정
    ▼
[Stage 5: Detect]         환각 감지 (선택)
    │  - 생성된 Cypher에 존재하지 않는 엔티티가 있는지
    │  - 온톨로지에 없는 레이블/관계 검출
    ▼
PipelineOutput (성공/실패, Cypher, 검증 결과)
```

### 5.3 한국어 해사용어 사전

자연어 파싱의 핵심은 **도메인 용어 사전**입니다.

```python
# 한국어 → Neo4j 레이블 매핑 (105개)
ENTITY_SYNONYMS = {
    "선박": "Vessel",    "배": "Vessel",     "함선": "Vessel",
    "컨테이너선": "CargoShip",  "화물선": "CargoShip",
    "유조선": "Tanker",  "탱커": "Tanker",
    "항구": "Port",      "항만": "Port",     "부두": "Berth",
    "예인수조": "TowingTank",
    "사고": "Incident",  "충돌": "Collision",
    # ... 105개
}

# 한국어 → Neo4j 관계 매핑 (22개)
RELATIONSHIP_KEYWORDS = {
    "정박한": "DOCKED_AT",   "접안한": "DOCKED_AT",
    "소유한": "OWNED_BY",    "소속된": "OWNED_BY",
    "항해중인": "ON_VOYAGE",  "운항중인": "ON_VOYAGE",
    "운반하는": "CARRIES",    "적재한": "CARRIES",
    "운영하는": "OPERATES",   "관리하는": "OPERATES",
    # ... 22개
}

# 속성값 한국어 → 영어 매핑
PROPERTY_VALUE_MAP = {
    "vesselType": {
        "컨테이너선": "ContainerShip",
        "유조선": "Tanker",
        "벌크선": "BulkCarrier",
    },
    "severity": {
        "경미": "LOW", "보통": "MEDIUM",
        "심각": "HIGH", "치명적": "CRITICAL",
    },
}
```

### 5.4 실제 사용 코드

```python
from kg.pipeline import TextToCypherPipeline
from kg.cypher_validator import CypherValidator
from kg.cypher_corrector import CypherCorrector

# 파이프라인 생성 (2단계: 기본)
pipeline = TextToCypherPipeline()

# 파이프라인 생성 (5단계: 검증+교정 포함)
validator = CypherValidator.from_maritime_ontology()
corrector = CypherCorrector.from_maritime_ontology()
pipeline = TextToCypherPipeline(
    validator=validator,
    corrector=corrector
)

# 자연어 → Cypher 변환
output = pipeline.process("부산항 근처 컨테이너선 5000톤 이상")

if output.success:
    print(f"생성된 Cypher: {output.generated_query.query}")
    print(f"파라미터: {output.generated_query.parameters}")
    print(f"추론 유형: {output.reasoning_type}")
    print(f"검증 점수: {output.validation_score}")

    if output.corrections_applied:
        print(f"자동 교정: {output.corrections_applied}")
```

### 5.5 추론 유형 분류 (Multi-hop Reasoning)

한국어 텍스트에서 어떤 유형의 그래프 탐색이 필요한지 자동 분류합니다.

| 유형 | 설명 | 한국어 예시 |
|------|------|-----------|
| **DIRECT** | 1-hop 단순 조회 | "부산항 정보 알려줘" |
| **BRIDGE** | A→B→C 순차 탐색 | "부산항에 정박중인 선박의 소유 기관" |
| **COMPARISON** | A vs B 비교 | "예인수조 vs 빙해수조 실험 비교" |
| **INTERSECTION** | A∩B 교집합 | "부산항과 인천항에 공통으로 입항한 선박" |
| **COMPOSITION** | 집계+정렬 | "가장 많은 실험을 수행한 시설 Top 3" |

**분류 키워드:**

```python
COMPARISON_KEYWORDS = ["비교", "차이", "vs", "대비", "어느 쪽"]
INTERSECTION_KEYWORDS = ["공통", "겹치는", "둘 다", "모두", "동시에"]
COMPOSITION_KEYWORDS = ["Top", "가장 많", "순위", "합계", "총", "평균"]
# BRIDGE: 소유격 체인 "~의 ~의", 관계 2개 이상
# DIRECT: 위 키워드 모두 해당 없음 (기본값)
```

---

## 6. 지식그래프 메모리

### 6.1 KG 메모리란?

KG 메모리는 **AI 에이전트가 대화 맥락과 학습한 지식을 지식그래프에 저장**하여, 세션을 넘어서도 기억을 유지하는 패턴입니다.

```
전통적 방식: 대화 히스토리를 텍스트로 저장
    → 맥락 창 제한, 검색 어려움

KG 메모리 방식: 대화에서 추출한 엔티티/관계를 그래프에 저장
    → 구조화된 지식, 관계 기반 검색, 무제한 메모리
```

### 6.2 KG 메모리 아키텍처

```
[사용자 대화]
     │
     ▼
[엔티티/관계 추출]  ← NLP 파이프라인
     │
     ▼
[Neo4j 지식그래프]  ← 저장 (MERGE 패턴)
     │
     ▼
[맥락 검색]         ← 다음 대화 시 관련 지식 조회
     │
     ▼
[LLM 프롬프트 보강] ← 검색된 지식을 프롬프트에 주입
```

### 6.3 데이터 리니지 (W3C PROV-O)

KG 메모리의 신뢰성을 위해 **"이 데이터가 어디서 왔는지"** 추적합니다.

```python
# 리니지 이벤트 유형
class LineageEventType(str, Enum):
    CREATION = "CREATION"              # 최초 생성
    TRANSFORMATION = "TRANSFORMATION"  # 변환/가공
    DERIVATION = "DERIVATION"          # 파생 데이터
    INGESTION = "INGESTION"            # 외부 수집
    MERGE = "MERGE"                    # 엔티티 병합
    DELETION = "DELETION"             # 삭제

# 리니지 3요소 (W3C PROV-O)
# Entity: 무엇이 (데이터 객체)
# Activity: 어떻게 (변환/수집 과정)
# Agent: 누가 (사용자/시스템)
```

**리니지 기록 예시:**

```python
from kg.lineage import LineageRecorder, LineagePolicy

recorder = LineageRecorder(policy=LineagePolicy())

# 데이터 수집 이벤트 기록
recorder.record_event(
    entity_type="Document",
    entity_id="DOC-001",
    event_type=LineageEventType.INGESTION,
    source="scholar-crawler",
    agent="etl-pipeline",
    metadata={"url": "https://..."}
)

# 리니지 그래프 조회 (이 데이터의 계보)
graph = recorder.get_graph()
ancestors = graph.get_ancestors("DOC-001")  # BFS 탐색
```

**Neo4j에 저장되는 리니지 구조:**

```cypher
-- 리니지 노드/관계
(entity:LineageEntity {entityId: 'DOC-001', type: 'Document'})
(activity:LineageActivity {type: 'INGESTION', pipeline: 'etl'})
(agent:LineageAgent {agentId: 'crawler-v1', role: 'AGENT'})

(entity)-[:WAS_GENERATED_BY]->(activity)
(activity)-[:WAS_ASSOCIATED_WITH]->(agent)
(entity)-[:WAS_DERIVED_FROM]->(source_entity)
```

---

## 7. 온톨로지: 지식그래프의 설계도

### 7.1 온톨로지를 사용했는가?

**네, 온톨로지를 적극 활용했습니다.** 온톨로지는 지식그래프의 **스키마(설계도)**입니다.

```
온톨로지 없는 KG       온톨로지 있는 KG
─────────────          ──────────────
아무 노드/관계 허용      정의된 타입만 허용
일관성 보장 없음        스키마 검증 가능
확장 시 충돌 위험       체계적 확장 가능
의미 모호              의미 명확 (정의 포함)
```

### 7.2 온톨로지 구조 (Palantir Foundry 패턴)

```python
from kg.ontology import Ontology, ObjectTypeDefinition, PropertyDefinition

# 온톨로지 생성
ontology = Ontology(name="maritime", version="1.0")

# 객체 유형(Object Type) 정의
ontology.define_object_type(ObjectTypeDefinition(
    name="Vessel",
    display_name="선박",
    description="해상에서 운항하는 모든 수상 교통수단",
    properties={
        "mmsi": PropertyDefinition(
            type="INTEGER", required=True, unique=True,
            description="해상이동업무식별번호"
        ),
        "name": PropertyDefinition(
            type="STRING", required=True,
            description="선박명"
        ),
        "vesselType": PropertyDefinition(
            type="STRING", indexed=True,
            enum_values=["ContainerShip", "Tanker", "BulkCarrier"],
            description="선종"
        ),
        "currentLocation": PropertyDefinition(
            type="POINT", indexed=True,
            description="현재 위치 (위도/경도)"
        ),
    },
    interfaces=["Trackable", "Classifiable"],  # 인터페이스 상속
))

# 관계 유형(Link Type) 정의
ontology.define_link_type(LinkTypeDefinition(
    name="DOCKED_AT",
    from_type="Vessel",
    to_type="Port",
    cardinality=Cardinality.MANY_TO_ONE,  # 선박 N : 항만 1
    properties={
        "since": PropertyDefinition(type="DATETIME"),
        "status": PropertyDefinition(
            type="STRING",
            enum_values=["arrived", "departing", "anchored"]
        ),
    },
))
```

### 7.3 온톨로지 활용 사례

| 활용 영역 | 설명 |
|-----------|------|
| **ETL 검증** | 데이터 적재 시 레이블/속성이 온톨로지와 일치하는지 검사 |
| **Cypher 검증** | 생성된 쿼리의 노드 레이블이 온톨로지에 존재하는지 확인 |
| **환각 감지** | LLM이 생성한 엔티티가 온톨로지에 정의되어 있는지 검증 |
| **품질 게이트** | CI/CD에서 온톨로지 정합성 8가지 자동 검증 |
| **LLM 프롬프트** | "사용 가능한 엔티티/관계 목록"을 LLM에 제공 |

### 7.4 품질 게이트 (CI/CD 연동)

```python
from kg.quality_gate import QualityGate

gate = QualityGate()
report = gate.run()

# 8가지 자동 검증
# 1. 온톨로지 엔티티 수 >= 100개
# 2. 온톨로지 관계 수 >= 50개
# 3. 모든 관계의 from_type/to_type이 존재하는 엔티티
# 4. 평가 데이터셋 30개 질문 존재
# 5. 파이프라인 기본 동작 확인
# 6. 속성 정의 완성도
# 7. 엔티티 그룹 분류 완성도
# 8. 중복 레이블 없음

print(f"통과: {report.passed_count}, 실패: {report.failed_count}")
print(f"전체 결과: {'PASS' if report.is_passed else 'FAIL'}")
```

---

## 8. 전체 아키텍처 요약

```
┌─────────────────────────────────────────────────────────────────┐
│                        데이터 소스                               │
│  논문 메타데이터 · 기상 API · 사고 이력 · 시설 데이터            │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────┐     ┌────────────────────────────────────┐
│  크롤러 (4종)         │     │  온톨로지 (설계도)                  │
│  HTTP + 재시도        │     │  127 엔티티 · 83 관계 · 29 속성    │
│  + 관계 추출         │     │  Palantir Foundry 패턴             │
└──────────┬───────────┘     └──────────┬─────────────────────────┘
           │                            │
           ▼                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  ETL 파이프라인                                                  │
│  검증(Validate) → 변환(Transform) → 적재(Load)                  │
│  + Dead Letter Queue + 리니지 기록                               │
└──────────┬──────────────────────────────────────────────────────┘
           │  MERGE 패턴 (멱등성)
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Neo4j 지식그래프                                                │
│  제약조건 24 · 인덱스 44 (벡터/공간/풀텍스트/범위)               │
│  RBAC 접근 제어 · W3C PROV-O 리니지                             │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Text-to-Cypher 5단계 파이프라인                                 │
│  파싱 → 생성 → 검증 → 교정 → 환각감지                           │
│  한국어 해사용어 사전 (105 동의어)                                │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  REST API (FastAPI)                                             │
│  자연어 질의 · 그래프 탐색 · 리니지 조회 · 스키마 조회           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 부록: 유용한 Cypher 쿼리 모음

```cypher
-- 1. 그래프 전체 통계
CALL apoc.meta.stats() YIELD labels, relTypes
RETURN labels, relTypes

-- 2. 노드 레이블별 개수
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt
ORDER BY cnt DESC

-- 3. 관계 타입별 개수
MATCH ()-[r]->() RETURN type(r) AS relType, count(*) AS cnt
ORDER BY cnt DESC

-- 4. 최단 경로 찾기
MATCH p = shortestPath(
  (a:Vessel {name: '태평양호'})-[*..5]-(b:Port {name: '부산항'})
)
RETURN p

-- 5. 특정 노드의 모든 이웃
MATCH (n {name: '부산항'})-[r]-(neighbor)
RETURN type(r) AS relationship, labels(neighbor)[0] AS label,
       neighbor.name AS name

-- 6. 벡터 유사도 검색
CALL db.index.vector.queryNodes('text_embedding', 10, $queryVector)
YIELD node, score
RETURN node.title, score ORDER BY score DESC

-- 7. 풀텍스트 검색
CALL db.index.fulltext.queryNodes('document_search', '자율운항 충돌')
YIELD node, score
RETURN node.title, score ORDER BY score DESC

-- 8. 공간 범위 검색 (반경 10km)
MATCH (v:Vessel)
WHERE point.distance(
  v.currentLocation,
  point({latitude: 35.1028, longitude: 129.0403})
) < 10000
RETURN v.name, v.vesselType

-- 9. 데이터 리니지 추적
MATCH path = (e:LineageEntity {entityId: 'DOC-001'})
  -[:WAS_DERIVED_FROM*1..5]->(source)
RETURN path

-- 10. RBAC 접근 가능 데이터 확인
MATCH (u:User {userId: 'user-001'})-[:HAS_ROLE]->(r:Role)
  -[:CAN_ACCESS]->(dc:DataClass)
RETURN r.name AS role, collect(dc.name) AS accessible_data
```
