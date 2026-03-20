# 지식그래프 처음부터 만들기 -- 4단계 구축법 (해사 도메인) | YouTube 스크립트

## 메타데이터

| 항목 | 내용 |
|------|------|
| 제목 (확정) | **지식그래프 처음부터 만들기 -- 4단계 구축법 (해사 도메인)** |
| 부제 | 온톨로지 설계부터 Cypher 쿼리까지, 코드와 함께 따라하는 KG 구축 튜토리얼 |
| 예상 길이 | 약 22분 |
| 대상 | 한국 개발자/엔지니어 (KG 구축에 관심 있는 입문~중급) |
| 내레이터 | 일론 (Elon) |
| 핵심 컨셉 | 기능 소개가 아닌 **구축 과정 튜토리얼**. 시청자가 따라 만들 수 있어야 함 |

---

## 타임스탬프

```
00:00 - 인트로: 지식그래프, 왜 어렵게 느껴질까?
01:30 - 오늘의 목표: 4단계로 KG를 만든다
02:30 - STEP 1: 세상을 정의한다 -- 온톨로지 설계 (가장 중요)
10:30 - STEP 2: 데이터베이스에 법을 세운다 -- Neo4j 스키마
15:00 - STEP 3: 그래프에 생명을 불어넣는다 -- 데이터 적재
19:30 - STEP 4: 그래프에 질문한다 -- Cypher 쿼리
22:00 - 마무리: 전체 구조 복습 + 다음 영상 예고
```

---

## 스크립트 본문

---

### [00:00] 인트로 -- 지식그래프, 왜 어렵게 느껴질까?

[SCREEN: 검정 화면에 흰 글씨 -- "지식그래프"라는 단어가 크게 뜬다]

**일론:**
"지식그래프 만들어야 하는데..."

이 말을 듣는 순간, 대부분의 개발자는 이렇게 생각합니다.

[SCREEN: 개발자 머릿속 -- 물음표가 하나씩 나타남]

"온톨로지? OWL? RDF? 트리플? 시맨틱 웹?"
용어부터 무섭죠.

그런데요, 사실 지식그래프의 본질은 아주 단순합니다.

[SCREEN: 화이트보드에 손으로 그린 듯한 다이어그램]

```
[선박] ---정박---> [부두] ---속해있다---> [항구]
```

이게 끝이에요.
**무엇이 존재하고, 그것들이 어떻게 연결되어 있는가.**

문제는 "어떻게 잘 만드느냐"입니다.
127개 엔티티, 83개 관계, 29종 속성 정의를 가진 실제 프로젝트에서, 저희가 밟았던 구축 과정을 오늘 전부 보여드리겠습니다.

[B-ROLL: 바다 위 컨테이너선 항공 촬영 + Neo4j 그래프 시각화 오버레이]

---

### [01:30] 오늘의 목표 -- 4단계로 KG를 만든다

[SCREEN: 4단계 로드맵이 세로로 나열]

**일론:**
오늘 영상의 구조는 명확합니다. 딱 네 단계.

[SCREEN: 각 단계가 하나씩 애니메이션으로 나타남]

**STEP 1. 세상을 정의한다** -- 온톨로지 설계
"해사 세계에 뭐가 있지? 어떻게 연결되지?" 이 질문에 답하는 과정.

**STEP 2. 데이터베이스에 법을 세운다** -- Neo4j 스키마
"같은 MMSI의 선박이 두 개 존재하면 안 된다." 이런 규칙을 코드로 만드는 과정.

**STEP 3. 그래프에 생명을 불어넣는다** -- 데이터 적재
"HMM 알헤시라스호, 399.9미터, 부산항 정박 중." 실제 데이터를 넣는 과정.

**STEP 4. 그래프에 질문한다** -- Cypher 쿼리
"부산항 50km 이내 선박 보여줘." 그래프를 탐색하는 과정.

이 네 단계를 밟으면, 여러분도 자기 도메인의 지식그래프를 만들 수 있습니다.
해사가 아니어도 괜찮아요. 의료든, 금융이든, 제조든, 과정은 똑같습니다.

자, 출발합니다.

---

### [02:30] STEP 1: 세상을 정의한다 -- 온톨로지 설계

[SCREEN: 큰 숫자 "STEP 1" + "온톨로지 설계" + 부제: "가장 중요한 단계"]

**일론:**
여기가 이 영상에서 가장 중요한 파트입니다.
나머지 세 단계는 솔직히 기계적이에요. 한번 배우면 반복할 수 있습니다.
그런데 이 첫 번째 단계, 온톨로지 설계는 **생각하는 과정**이에요.

[SCREEN: 빈 화이트보드. 질문이 하나 크게 뜬다 -- "해사 세계에 뭐가 있지?"]

#### 1단계: 세상에 뭐가 있는지 나열하기

먼저 해사 도메인에 존재하는 것들을 그냥 나열합니다.

[SCREEN: 포스트잇이 하나씩 화이트보드에 붙여지는 애니메이션]

선박. 항구. 부두. 해역. 항해. 사고. 기상. 규정. 논문. 조직. 사람. 센서. 실험시설...

이것들을 전문 용어로 **엔티티(Entity)**라고 합니다.
Neo4j에서는 **노드(Node)**라고 부르고, 코드에서는 **레이블(Label)**이라고 합니다.

그런데 여기서 포인트. "선박"이 하나로 끝나지 않아요.

[SCREEN: "선박" 포스트잇에서 가지가 뻗어나감]

```
선박(Vessel)
  ├── 화물선(CargoShip)
  ├── 유조선(Tanker)
  ├── 어선(FishingVessel)
  ├── 여객선(PassengerShip)
  ├── 군함(NavalVessel)
  └── 자율운항선(AutonomousVessel)
```

화물선이 유조선하고 같은 속성을 가질까요? 아니요. 유조선에는 `hazardClass`(위험물 등급)가 있어야 하고, 여객선에는 `passengerCapacity`(승객 정원)가 있어야 합니다.

이런 식으로 나열하다 보면, 금방 수십 개가 됩니다.
저희 프로젝트에서는 최종적으로 **127개 엔티티**가 나왔어요.

[SCREEN: 숫자 127이 크게]

#### 2단계: 그룹으로 묶기

127개를 그냥 나열하면 혼돈입니다. 그래서 그룹으로 묶습니다.

[SCREEN: 11개 그룹이 색깔별로 분류되어 나타남]

```
PhysicalEntity (27)   -- 선박, 항구, 화물, 센서 등 물리적으로 존재하는 것
SpatialEntity (5)     -- 해역, 배타적경제수역, 영해 등 공간 개념
TemporalEntity (17)   -- 항해, 사고, 기상 등 시간에 묶인 사건
InformationEntity (19)-- 규정, 문서, API 등 정보 자원
ObservationEntity (6) -- AIS 관측, 위성 관측, CCTV 관측 등
OrganizationEntity (8)-- KRISO, 해양수산부, HMM 등 조직과 사람
PlatformEntity (8)    -- 워크플로우, AI 모델, 데이터 파이프라인
MultimodalData (6)    -- AIS 데이터, 위성영상, 레이더, 센서 리딩
Embedding (4)         -- 벡터 임베딩 (텍스트, 시각, 궤적, 융합)
KRISOEntity (24)      -- 실험, 시험시설, 모형선, 측정값
RBACEntity (4)        -- 사용자, 역할, 데이터 분류
```

왜 그룹이 중요하냐면요, 나중에 "실험 관련 엔티티만 보여줘"라고 했을 때 KRISOEntity 그룹을 통째로 필터링할 수 있습니다. 127개를 하나하나 뒤질 필요가 없어요.

[SCREEN: `kg/ontology/maritime_ontology.py` 파일이 에디터에 열린다]

#### 3단계: 코드로 정의하기

자, 이제 이 설계를 코드로 옮깁니다. 여기서 중요한 설계 결정이 있었어요.

**온톨로지를 어디에 정의할 것인가?**

선택지가 여럿 있었습니다.
YAML? JSON? Protege(OWL 편집기)? 아니면 Python?

[SCREEN: 4가지 선택지가 나열되고, Python에 체크 표시]

저희는 **Python을 Single Source of Truth**로 선택했습니다.

이유는 세 가지예요.

[SCREEN: 이유가 하나씩 나타남]

**첫째, IDE 자동완성.**
"Vessel"을 "Vesssel"로 오타 내면 바로 잡힙니다. YAML에서는 오타가 런타임에서야 터져요.

**둘째, 테스트 가능.**
"온톨로지에 Vessel 레이블이 있나?" 이걸 pytest로 돌릴 수 있습니다. CI/CD에 넣으면 누군가 실수로 레이블을 삭제해도 배포가 차단돼요.

**셋째, 자동 변환.**
이 Python 정의 하나에서 OWL Turtle 파일, Neo4j 스키마, LLM 프롬프트를 전부 자동 생성합니다.

[SCREEN: 변환 플로우 다이어그램 -- Python --> OWL Turtle / Neo4j Cypher / LLM Prompt]

자, 실제 코드를 보겠습니다.

먼저 온톨로지의 뼈대 -- ObjectType과 LinkType을 정의하는 클래스입니다.

[SCREEN: `kg/ontology/core.py` 코드 하이라이트]

```python
# kg/ontology/core.py -- 온톨로지 뼈대

@dataclass
class PropertyDefinition:
    """엔티티의 속성 하나를 정의합니다."""
    type: str | PropertyType        # STRING, INTEGER, FLOAT, POINT...
    required: bool = False          # 필수 속성인가?
    primary_key: bool = False       # 고유 식별자인가?
    indexed: bool = False           # 검색 인덱스를 만들 것인가?
    unique: bool = False            # 중복 불허인가?
    description: str | None = None  # 사람이 읽는 설명

@dataclass
class ObjectTypeDefinition:
    """엔티티(노드) 타입 하나를 정의합니다."""
    name: str                       # Neo4j 레이블 (예: "Vessel")
    display_name: str | None = None # 화면 표시명 (예: "선박")
    description: str | None = None  # 설명
    properties: dict[str, PropertyDefinition] = field(default_factory=dict)
    parent_type: str | None = None  # 상속 (CargoShip -> Vessel)

@dataclass
class LinkTypeDefinition:
    """관계(엣지) 타입 하나를 정의합니다."""
    name: str                       # 관계명 (예: "DOCKED_AT")
    from_type: str                  # 출발 엔티티 (예: "Vessel")
    to_type: str                    # 도착 엔티티 (예: "Berth")
    cardinality: str = "MANY_TO_MANY"
    properties: dict[str, PropertyDefinition] = field(default_factory=dict)
```

이게 뼈대입니다. 이 구조 위에 해사 도메인의 구체적인 엔티티를 쌓아올립니다.

[SCREEN: `kg/ontology/maritime_ontology.py`로 전환]

```python
# kg/ontology/maritime_ontology.py -- 해사 도메인 엔티티 정의

ENTITY_LABELS: dict[str, str] = {
    # ----- PhysicalEntity group (27개) -----
    "Vessel": "Any watercraft or ship operating at sea",
    "CargoShip": "Vessel designed for transporting goods",
    "Tanker": "Vessel designed for transporting liquid cargo (oil, chemicals, LNG)",
    "FishingVessel": "Vessel used for commercial or artisanal fishing",
    "PassengerShip": "Vessel carrying passengers (ferry, cruise ship)",
    "Port": "Harbour facility where vessels dock for loading/unloading",
    "Berth": "Designated mooring position within a port",
    "Anchorage": "Designated area where vessels anchor outside a port",
    "Sensor": "Any device producing observational data",
    "AISTransceiver": "Automatic Identification System transponder",
    # ...

    # ----- SpatialEntity group (5개) -----
    "SeaArea": "Named or regulated sea region",
    "EEZ": "Exclusive Economic Zone (200 NM from baseline)",
    # ...

    # ----- KRISOEntity group (24개) -----
    "Experiment": "KRISO experimental test campaign",
    "TestFacility": "Physical test facility at KRISO",
    "TowingTank": "Towing tank facility for resistance/propulsion tests",
    "ModelShip": "Scale model ship used in a KRISO experiment",
    "Measurement": "A single measurement record from a test",
    "Resistance": "Resistance measurement (drag force)",
    # ... 총 127개
}
```

[SCREEN: 127이라는 숫자 위에 11개 그룹 색깔이 오버레이]

보이시나요? 그냥 Python 딕셔너리입니다. 키가 Neo4j 레이블, 값이 설명.
복잡한 게 아니에요. 정리를 얼마나 잘 하느냐의 문제입니다.

#### 4단계: 속성을 정의하기

엔티티를 정의했으면, 각 엔티티가 **어떤 정보를 가지는지** 속성을 정해야 합니다.

[SCREEN: Vessel 속성 정의가 하이라이트됨]

```python
# kg/ontology/maritime_ontology.py -- 속성 정의

PROPERTY_DEFINITIONS: dict[str, dict[str, str]] = {
    "Vessel": {
        "mmsi": "INTEGER",           # 해상이동업무식별번호 (AIS 고유번호)
        "imo": "INTEGER",            # 국제해사기구 선박번호
        "name": "STRING",            # 선박명
        "callSign": "STRING",        # 호출부호
        "vesselType": "STRING",      # 선종
        "flag": "STRING",            # 국적 (선적국)
        "grossTonnage": "FLOAT",     # 총톤수
        "deadweight": "FLOAT",       # 재화중량톤수
        "length": "FLOAT",           # 전장(m)
        "beam": "FLOAT",             # 선폭(m)
        "draft": "FLOAT",            # 흘수(m)
        "yearBuilt": "INTEGER",      # 건조년도
        "currentStatus": "STRING",   # 현재 상태
        "currentLocation": "POINT",  # GPS 위치 (위도, 경도)
        "speed": "FLOAT",            # 대지속력(knots)
        "course": "FLOAT",           # 대지침로(도)
        "heading": "FLOAT",          # 선수방위(도)
        "destination": "STRING",     # 목적지
        "eta": "DATETIME",           # 도착예정시간
        "lastUpdated": "DATETIME",   # 마지막 갱신
    },
    "Port": {
        "unlocode": "STRING",        # UN/LOCODE (예: KRPUS = 부산)
        "name": "STRING",
        "location": "POINT",         # GPS 위치
        "portType": "STRING",        # 무역항, 연안항, 어항
        "maxDraft": "FLOAT",         # 최대 흘수(m) -- 이보다 큰 배는 못 들어옴
        "berthCount": "INTEGER",     # 선석 수
    },
    # ... 29종 엔티티에 대한 상세 속성 정의
}
```

**여기서 중요한 설계 포인트 하나.**

[SCREEN: mmsi와 imo 두 필드가 빨간 박스로 강조됨]

선박에는 고유 식별자가 **두 개**입니다.

`mmsi` -- Maritime Mobile Service Identity. AIS(선박자동식별장치)에서 쓰는 9자리 번호. 실시간 위치 추적할 때 이걸로 식별해요.

`imo` -- International Maritime Organization 번호. 선급에서 부여하는 7자리 번호. 선박의 "주민등록번호" 같은 거예요. 배 이름이 바뀌어도, 국적이 바뀌어도 이 번호는 안 바뀝니다.

왜 두 개일까요? 서로 다른 시스템에서 같은 배를 찾아야 하기 때문입니다.
AIS 데이터에는 MMSI만 있고, 선급 데이터에는 IMO만 있어요. 두 개 다 고유 제약조건을 걸어야 합니다.

이런 식으로 "왜 이 속성이 필요한지"를 하나하나 따져가는 게 온톨로지 설계예요.

#### 5단계: 관계를 정의하기

엔티티와 속성을 정했으면, 이제 **관계**입니다.
"누가 누구와 어떻게 연결되는가."

[SCREEN: 관계 정의 코드]

```python
# kg/ontology/maritime_ontology.py -- 83개 관계 정의

RELATIONSHIP_TYPES: list[dict[str, Any]] = [
    # --- 물리적 관계 ---
    {
        "type": "DOCKED_AT",           # 관계명
        "from_label": "Vessel",        # 출발: 선박
        "to_label": "Berth",           # 도착: 부두
        "description": "Vessel is currently docked at a specific berth",
        "properties": ["since", "until"],  # 언제부터 언제까지 정박했는지
    },
    {
        "type": "LOCATED_AT",
        "from_label": "Vessel",
        "to_label": "SeaArea",
        "description": "Current or last-known location of a vessel",
        "properties": ["timestamp", "source"],  # 언제, 어디서 온 데이터인지
    },
    # --- 운항 관계 ---
    {
        "type": "ON_VOYAGE",
        "from_label": "Vessel",
        "to_label": "Voyage",
        "description": "Vessel is performing a voyage",
        "properties": [],
    },
    {
        "type": "FROM_PORT",
        "from_label": "Voyage",
        "to_label": "Port",
        "description": "Voyage originates from a port",
        "properties": ["departureTime"],  # 출항 시각
    },
    {
        "type": "TO_PORT",
        "from_label": "Voyage",
        "to_label": "Port",
        "description": "Voyage is destined for a port",
        "properties": ["eta", "ata"],  # 예정시각, 실제도착시각
    },
    # --- KRISO 연구 관계 ---
    {
        "type": "CONDUCTED_AT",
        "from_label": "Experiment",
        "to_label": "TestFacility",
        "description": "Experiment was conducted at a test facility",
        "properties": [],
    },
    {
        "type": "TESTED",
        "from_label": "Experiment",
        "to_label": "ModelShip",
        "description": "Experiment tested a model ship",
        "properties": [],
    },
    {
        "type": "PRODUCED",
        "from_label": "Experiment",
        "to_label": "ExperimentalDataset",
        "description": "Experiment produced a dataset",
        "properties": [],
    },
    {
        "type": "MODEL_OF",
        "from_label": "ModelShip",
        "to_label": "Vessel",
        "description": "Scale model represents a real vessel design",
        "properties": ["scale"],  # 축척 (예: 1/58)
    },
    # ... 총 83개 관계
]
```

**여기서 핵심 포인트.**

[SCREEN: DOCKED_AT 관계에 "since", "until" 속성이 강조됨]

관계에도 속성이 있습니다!

`DOCKED_AT` 관계에 `since`와 `until`이 있죠? "이 배가 이 부두에 언제부터 언제까지 정박했는지"를 관계 자체에 기록하는 겁니다.

관계형 데이터베이스였으면 이걸 위해 중간 테이블을 하나 더 만들어야 해요. 그래프에서는 관계 위에 바로 속성을 달면 됩니다.

[SCREEN: 비교]
```
RDB: vessels 테이블 + berths 테이블 + vessel_berth_history 중간 테이블
Neo4j: (Vessel)-[:DOCKED_AT {since, until}]->(Berth)  -- 끝.
```

**그리고 상속.**

[SCREEN: CargoShip이 Vessel에서 상속받는 다이어그램]

`CargoShip`은 `Vessel`의 하위 타입입니다. Neo4j에서는 멀티 레이블로 구현해요.

```
(:Vessel:CargoShip {mmsi: 440123001, name: 'HMM 알헤시라스'})
```

이 노드는 Vessel이면서 동시에 CargoShip입니다.
`MATCH (v:Vessel)` 하면 모든 선박이 나오고, `MATCH (v:CargoShip)` 하면 화물선만 나옵니다.

[B-ROLL: 화이트보드에 엔티티-관계 다이어그램을 그리는 타임랩스]

#### 온톨로지 설계 요약

[SCREEN: 정리 카드]

| 결과물 | 숫자 |
|--------|------|
| 엔티티 타입 | 127개, 11개 그룹 |
| 관계 타입 | 83개 |
| 속성 정의 | 29종 엔티티에 대한 상세 속성 |
| 설계 원칙 | Python = Single Source of Truth |

이 온톨로지가 나머지 모든 것의 기반입니다.
스키마도, 데이터 적재도, 쿼리도, 전부 이 정의에서 출발합니다.

자, 설계는 끝났습니다. 이제 이걸 데이터베이스에 넣을 차례예요.

---

### [10:30] STEP 2: 데이터베이스에 법을 세운다 -- Neo4j 스키마

[SCREEN: 큰 숫자 "STEP 2" + "Neo4j 스키마" + 부제: "규칙 없는 그래프는 혼돈이다"]

**일론:**
온톨로지가 "뭘 저장하겠다"는 **약속**이라면,
스키마는 "이 약속을 어기면 에러를 낸다"는 **법**입니다.

Neo4j는 기본적으로 스키마가 없어요.
노드를 아무 레이블로 만들 수 있고, 관계도 자유롭게 만들 수 있습니다.

[SCREEN: 위험 경고 아이콘]

이게 자유로운 것 같지만, 프로덕션에서는 재앙입니다.
누군가 "Vesssel"(l이 3개)이라는 오타 레이블로 노드를 만들면, 아무 에러 없이 조용히 들어갑니다. 그리고 3개월 뒤에 "왜 이 선박이 검색 안 되지?" 하게 되죠.

그래서 법을 세웁니다.

#### 제약조건 (Constraints): 이것은 절대 안 된다

[SCREEN: `kg/schema/constraints.cypher` 파일이 열린다]

```cypher
-- kg/schema/constraints.cypher (24개 제약조건)

-- 같은 MMSI의 선박은 두 개 존재할 수 없다
CREATE CONSTRAINT vessel_mmsi IF NOT EXISTS
  FOR (v:Vessel) REQUIRE v.mmsi IS UNIQUE;

-- 같은 IMO의 선박도 두 개 존재할 수 없다
CREATE CONSTRAINT vessel_imo IF NOT EXISTS
  FOR (v:Vessel) REQUIRE v.imo IS UNIQUE;

-- 같은 UN/LOCODE의 항구도 두 개 존재할 수 없다
CREATE CONSTRAINT port_unlocode IF NOT EXISTS
  FOR (p:Port) REQUIRE p.unlocode IS UNIQUE;

-- 실험 ID, 시설 ID, 사고 ID... 전부 유일해야 한다
CREATE CONSTRAINT experiment_id IF NOT EXISTS
  FOR (e:Experiment) REQUIRE e.experimentId IS UNIQUE;
CREATE CONSTRAINT test_facility_id IF NOT EXISTS
  FOR (f:TestFacility) REQUIRE f.facilityId IS UNIQUE;
CREATE CONSTRAINT incident_id IF NOT EXISTS
  FOR (i:Incident) REQUIRE i.incidentId IS UNIQUE;
CREATE CONSTRAINT document_id IF NOT EXISTS
  FOR (d:Document) REQUIRE d.docId IS UNIQUE;
CREATE CONSTRAINT voyage_id IF NOT EXISTS
  FOR (v:Voyage) REQUIRE v.voyageId IS UNIQUE;

-- RBAC (역할 기반 접근 제어) 관련
CREATE CONSTRAINT user_id IF NOT EXISTS
  FOR (u:User) REQUIRE u.userId IS UNIQUE;
CREATE CONSTRAINT role_id IF NOT EXISTS
  FOR (r:Role) REQUIRE r.roleId IS UNIQUE;

-- ... 총 24개
```

[SCREEN: "IF NOT EXISTS" 부분에 빨간 밑줄]

여기서 `IF NOT EXISTS`가 중요합니다.
이 스크립트를 10번 실행해도 에러가 안 나요. **멱등성(idempotency)**입니다.
처음 실행하면 제약조건을 만들고, 두 번째부터는 "이미 있네" 하고 넘어갑니다.

이게 왜 중요하냐면, CI/CD 파이프라인에서 배포할 때마다 이 스크립트를 실행하거든요. 멱등성이 없으면 매번 "이미 존재합니다" 에러가 터집니다.

#### 인덱스 (Indexes): 빨리 찾겠다는 약속

[SCREEN: `kg/schema/indexes.cypher` 파일로 전환]

인덱스는 "검색을 빠르게 하겠다"는 약속입니다.
44개 인덱스. 네 종류로 나뉩니다.

[SCREEN: 4종 인덱스가 색깔별로 분류]

**1. 벡터 인덱스 (4개) -- AI 의미 검색**

```cypher
-- 텍스트 임베딩: 768차원 (논문, 보고서의 의미를 벡터로)
CREATE VECTOR INDEX text_embedding IF NOT EXISTS
  FOR (n:Document) ON (n.textEmbedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }};

-- 시각 임베딩: 512차원 (CCTV, 위성영상을 벡터로)
CREATE VECTOR INDEX visual_embedding IF NOT EXISTS
  FOR (n:Observation) ON (n.visualEmbedding)
  OPTIONS {indexConfig: {`vector.dimensions`: 512, ...}};

-- 궤적 임베딩: 256차원 (AIS 항적 데이터를 벡터로)
CREATE VECTOR INDEX trajectory_embedding IF NOT EXISTS
  FOR (n:TrackSegment) ON (n.trajectoryEmbedding)
  OPTIONS {indexConfig: {`vector.dimensions`: 256, ...}};

-- 융합 임베딩: 1024차원 (텍스트+이미지+궤적 합친 벡터)
CREATE VECTOR INDEX fused_embedding IF NOT EXISTS
  FOR (n:Observation) ON (n.fusedEmbedding)
  OPTIONS {indexConfig: {`vector.dimensions`: 1024, ...}};
```

[SCREEN: 4개 벡터 차원을 비교하는 바 차트 -- 256, 512, 768, 1024]

왜 차원이 다를까요?
항적 데이터는 본질적으로 위도-경도 시퀀스라서 256차원이면 충분하고, 논문 텍스트는 의미가 훨씬 복잡하니까 768차원이 필요합니다.

이 벡터 인덱스 덕분에 "선박 저항 성능 관련 연구"라고 검색하면, 단어가 정확히 일치하지 않아도 **의미적으로 유사한** 문서를 찾아줍니다.

**2. 공간 인덱스 (5개) -- 지도 검색**

```cypher
-- 선박 위치 (GPS 좌표)
CREATE POINT INDEX vessel_location IF NOT EXISTS
  FOR (v:Vessel) ON (v.currentLocation);

-- 항구 위치
CREATE POINT INDEX port_location IF NOT EXISTS
  FOR (p:Port) ON (p.location);

-- 사고 위치
CREATE POINT INDEX incident_location IF NOT EXISTS
  FOR (i:Incident) ON (i.location);
```

공간 인덱스가 있으면, "부산항에서 반경 50km 이내 선박"이라는 쿼리를 O(log n)으로 처리할 수 있어요.
인덱스가 없으면 전체 선박을 하나하나 거리 계산해야 합니다.

**3. 풀텍스트 인덱스 (8개) -- 한국어 텍스트 검색**

```cypher
-- 논문/보고서 제목+본문+요약 통합 검색
CREATE FULLTEXT INDEX document_search IF NOT EXISTS
  FOR (d:Document) ON EACH [d.title, d.content, d.summary];

-- 규정 검색
CREATE FULLTEXT INDEX regulation_search IF NOT EXISTS
  FOR (r:Regulation) ON EACH [r.title, r.description, r.code];

-- 선박명 + 호출부호 검색
CREATE FULLTEXT INDEX vessel_search IF NOT EXISTS
  FOR (v:Vessel) ON EACH [v.name, v.callSign];
```

**4. 범위 인덱스 (19개) + RBAC 인덱스 (8개) -- 필터링**

```cypher
CREATE INDEX vessel_type IF NOT EXISTS FOR (v:Vessel) ON (v.vesselType);
CREATE INDEX incident_date IF NOT EXISTS FOR (i:Incident) ON (i.date);
CREATE INDEX experiment_status IF NOT EXISTS FOR (e:Experiment) ON (e.status);
CREATE INDEX user_email IF NOT EXISTS FOR (u:User) ON (u.email);
CREATE INDEX role_level IF NOT EXISTS FOR (r:Role) ON (r.level);
-- ...
```

[SCREEN: 인덱스 44개 종합 카드]

| 인덱스 종류 | 개수 | 용도 |
|-------------|------|------|
| 벡터 | 4 | AI 의미 유사도 검색 |
| 공간 | 5 | GPS 기반 거리/범위 검색 |
| 풀텍스트 | 8 | 한국어 텍스트 검색 |
| 범위 | 19 | 속성 필터링 (날짜, 타입, 상태) |
| RBAC | 8 | 사용자/역할/권한 조회 |
| **합계** | **44** | |

이 제약조건 24개와 인덱스 44개가 그래프의 "법"입니다.
법이 있으니까 데이터를 안전하게, 빠르게 넣고 뺄 수 있어요.

---

### [15:00] STEP 3: 그래프에 생명을 불어넣는다 -- 데이터 적재

[SCREEN: 큰 숫자 "STEP 3" + "데이터 적재" + 부제: "빈 그래프에 현실을 채운다"]

**일론:**
온톨로지 설계하고, 스키마 세우고, 이제 드디어 데이터를 넣습니다.

빈 그래프에 현실 세계를 채워넣는 과정이에요.
이 파트가 시각적으로 가장 재미있습니다.

[SCREEN: `kg/schema/load_sample_data.py` 파일 열림]

적재에는 핵심 패턴이 딱 하나 있어요.

[SCREEN: 큰 글씨 -- "MERGE = 있으면 업데이트, 없으면 생성"]

#### 핵심 패턴: MERGE

```cypher
MERGE (port:Port {unlocode: 'KRPUS'})
  ON CREATE SET
    port.name     = '부산항',
    port.location = point({latitude: 35.1028, longitude: 129.0403}),
    port.portType = 'TradePort',
    port.berthCount = 169
```

`MERGE`는 "이 조건에 맞는 노드가 있으면 그걸 쓰고, 없으면 새로 만들어라"입니다.
`ON CREATE SET`은 "새로 만들 때만 이 속성을 넣어라"입니다.

이것도 멱등성이에요. 10번 실행해도 부산항은 딱 하나만 존재합니다.
만약 `CREATE`를 썼다면? 10번 실행하면 부산항이 10개 생겨요. 혼돈.

자, 실제로 넣는 데이터를 카테고리별로 보겠습니다.

[SCREEN: 12개 카테고리가 숫자와 함께 나열]

#### 카테고리 1: 기관 7개

```python
# 실제 한국 해사 관련 기관들
orgs = [
    {"orgId": "ORG-KRISO", "name": "한국해양과학기술원 부설 선박해양플랜트연구소",
     "orgType": "ResearchInstitute"},
    {"orgId": "ORG-MOF",   "name": "해양수산부",
     "orgType": "GovernmentAgency"},
    {"orgId": "ORG-BPA",   "name": "부산항만공사",
     "orgType": "GovernmentAgency"},
    {"orgId": "ORG-KR",    "name": "한국선급",
     "orgType": "ClassificationSociety"},
    {"orgId": "ORG-HMM",   "name": "HMM (현대상선)",
     "orgType": "ShippingCompany"},
    {"orgId": "ORG-PANOCEAN", "name": "팬오션",
     "orgType": "ShippingCompany"},
    {"orgId": "ORG-KCG",   "name": "해양경찰청",
     "orgType": "GovernmentAgency"},
]
```

각 기관에는 `Organization` 레이블 외에 `ResearchInstitute`, `GovernmentAgency`, `ShippingCompany` 같은 하위 레이블도 추가됩니다. 아까 말한 멀티 레이블이에요.

#### 카테고리 2: 항구 5개

```python
ports = [
    {"unlocode": "KRPUS", "name": "부산항",
     "lat": 35.1028, "lon": 129.0403,
     "portType": "TradePort", "berthCount": 169},
    {"unlocode": "KRICN", "name": "인천항",
     "lat": 37.4563, "lon": 126.5922,
     "portType": "TradePort", "berthCount": 73},
    {"unlocode": "KRULS", "name": "울산항",
     "lat": 35.5007, "lon": 129.3855, ...},
    {"unlocode": "KRYOS", "name": "여수광양항", ...},
    {"unlocode": "KRPTK", "name": "평택당진항", ...},
]
```

[SCREEN: 한국 지도 위에 5개 항구 핀이 찍히는 애니메이션]

주목할 점: GPS 좌표가 들어갑니다.
`point({latitude: 35.1028, longitude: 129.0403})` -- 이게 아까 공간 인덱스가 걸리는 그 `POINT` 타입이에요.

#### 카테고리 3: 선박 5척

```python
vessels = [
    {"mmsi": 440123001, "imo": 9863297,
     "name": "HMM 알헤시라스", "vesselType": "ContainerShip",
     "grossTonnage": 228283.0, "length": 399.9, "beam": 61.0,
     "currentStatus": "UNDERWAY", "ownerOrgId": "ORG-HMM"},
    {"mmsi": 440234002, "imo": 9786543,
     "name": "팬오션 드림", "vesselType": "BulkCarrier",
     "grossTonnage": 81000.0, "length": 292.0, ...},
    {"mmsi": 440345003, "name": "한라",
     "vesselType": "Tanker", "grossTonnage": 160000.0, ...},
    {"mmsi": 440456004, "name": "새마을호",
     "vesselType": "PassengerShip", ...},
    {"mmsi": 440567005, "name": "무궁화 10호",
     "vesselType": "FishingVessel", "grossTonnage": 350.0, ...},
]
```

[SCREEN: HMM 알헤시라스 실제 사진 -- 세계 최대급 컨테이너선 24000TEU급]

HMM 알헤시라스. 399.9미터. 축구장 4개 길이. 세계 최대급 컨테이너선이에요. 총톤수 228,283톤.
이 배의 MMSI가 440123001, IMO가 9863297 -- 아까 설계한 두 개의 고유 식별자가 여기 쓰입니다.

그리고 바로 관계를 연결합니다.

```python
# 선박 -> 해역 위치 관계
# HMM 알헤시라스는 대한해협에 있다
tx.run("""
    MATCH (v:Vessel {mmsi: $mmsi})
    MATCH (sa:SeaArea {name: $seaName})
    MERGE (v)-[:LOCATED_AT {timestamp: datetime(), source: 'AIS'}]->(sa)
""", mmsi=440123001, seaName="대한해협")

# 선박 -> 소유 기관 관계
# HMM 알헤시라스는 HMM이 소유한다
tx.run("""
    MATCH (vessel:Vessel {mmsi: $mmsi})
    MATCH (org:Organization {orgId: $orgId})
    MERGE (vessel)-[:OWNED_BY]->(org)
""", mmsi=440123001, orgId="ORG-HMM")
```

[SCREEN: 그래프가 시각적으로 확장 -- Vessel 노드에서 SeaArea와 Organization으로 엣지가 뻗어나감]

#### 카테고리 5: 항해 2건

여기가 관계의 매력이 극대화되는 부분입니다.

```cypher
-- 항해: 부산 -> 인천, HMM 알헤시라스
MERGE (v:Voyage {voyageId: 'VOY-HMM-2024-001'})
  ON CREATE SET
    v.status    = 'IN_PROGRESS',
    v.cargoDesc = '컨테이너 화물 (TEU 23,964)'
WITH v
MATCH (dep:Port {unlocode: 'KRPUS'})     -- 출발: 부산
MATCH (arr:Port {unlocode: 'KRICN'})     -- 도착: 인천
MERGE (v)-[:FROM_PORT {departureTime: datetime('2024-12-01T08:00:00+09:00')}]->(dep)
MERGE (v)-[:TO_PORT   {eta: datetime('2024-12-02T14:00:00+09:00')}]->(arr)
WITH v
MATCH (vessel:Vessel {mmsi: 440123001})  -- HMM 알헤시라스
MERGE (vessel)-[:ON_VOYAGE]->(v)
```

[SCREEN: 이 코드의 결과로 생기는 그래프 구조가 다이어그램으로]

```
Vessel(HMM 알헤시라스) --ON_VOYAGE--> Voyage(VOY-HMM-2024-001)
                                       |
                                       +--FROM_PORT--> Port(부산항)
                                       |
                                       +--TO_PORT---> Port(인천항)
```

한 줄의 Cypher 쿼리 안에서 4개 노드와 3개 관계가 한 번에 만들어집니다.
이게 그래프의 힘이에요.

#### 카테고리 6: KRISO 시험시설 10종 + 실험 3건

[SCREEN: KRISO 시험시설 목록이 카드 형태로 나타남]

```python
facilities = [
    {"facilityId": "TF-LTT",  "name": "대형 예인수조",
     "facilityType": "TowingTank",
     "length": 200.0, "width": 16.0, "depth": 7.0, "maxSpeed": 6.0},
    {"facilityId": "TF-OEB",  "name": "해양공학수조",
     "facilityType": "OceanEngineeringBasin",
     "length": 56.0, "width": 30.0, "depth": 4.5},
    {"facilityId": "TF-ICE",  "name": "빙해수조",
     "facilityType": "IceTank",
     "length": 42.0, "width": 32.0, "depth": 2.5},
    {"facilityId": "TF-DOB",  "name": "심해공학수조",
     "length": 100.0, "width": 50.0, "depth": 15.0},
    {"facilityId": "TF-LCT",  "name": "대형 캐비테이션터널",
     "facilityType": "LargeCavitationTunnel",
     "maxSpeed": 16.0},
    # ... 총 10종
]
```

시험시설도 하위 타입이 있어요.
캐비테이션터널은 대형, 중형, 고속 3종류인데, `CavitationTunnel` 상위 레이블과 각각의 하위 레이블을 동시에 가집니다.

```python
# 캐비테이션터널 3종에 상위 레이블 추가
for fid in ["TF-LCT", "TF-MCT", "TF-HSCT"]:
    tx.run("MATCH (tf:TestFacility {facilityId: $fid}) SET tf:CavitationTunnel", fid=fid)
```

그리고 실험 데이터:

```cypher
-- KVLCC2 저항성능 시험
MERGE (exp:Experiment {experimentId: 'EXP-2024-001'})
  ON CREATE SET
    exp.title = 'KVLCC2 저항성능 시험',
    exp.objective = 'KVLCC2 선형의 저항 성능 평가 및 CFD 검증 데이터 확보',
    exp.date = date('2024-06-15'),
    exp.principalInvestigator = '김해양'
WITH exp
MATCH (tf:TestFacility {facilityId: 'TF-LTT'})  -- 대형 예인수조에서
MERGE (exp)-[:CONDUCTED_AT]->(tf)
```

모형선, 데이터셋, 측정값까지 전부 연결하면 이런 그래프가 됩니다:

[SCREEN: KRISO 연구 그래프 구조 다이어그램]

```
Organization(KRISO) --HAS_FACILITY--> TestFacility(대형 예인수조)
                                       ^
                                       |
                            CONDUCTED_AT
                                       |
                                  Experiment(KVLCC2 저항성능 시험)
                                       |
                          +------------+------------+
                          |            |            |
                       TESTED       PRODUCED    HAS_CONDITION
                          |            |            |
                     ModelShip    ExpDataset    TestCondition
                    (KVLCC2 1/58)    |
                          |       CONTAINS
                       MODEL_OF      |
                          |      Measurement
                       Vessel     (12.45N, 28.73N, 52.18N ...)
                      (한라호)
```

[SCREEN: 이 다이어그램이 완성되는 애니메이션 -- 노드가 하나씩 나타나고 관계가 연결됨]

**6홉(hop).**
KRISO에서 출발해서, 시험시설을 거쳐, 실험, 모형선, 실제 선박까지.
그리고 실험에서 나온 데이터셋, 그 안의 측정값까지.

관계형 DB였으면 JOIN 6개. 여기서는 화살표를 따라가면 됩니다.

#### 전체 적재 데이터 요약

[SCREEN: 12개 카테고리 종합 카드]

| # | 카테고리 | 건수 | 핵심 관계 |
|---|----------|------|-----------|
| 1 | 기관 | 7 | Organization --> SubLabel |
| 2 | 항구 | 5 | Port + GPS POINT |
| 3 | 해역/수로 | 4+2 | Waterway --CONNECTS--> SeaArea |
| 4 | 선박 | 5 | Vessel --OWNED_BY--> Organization |
| 5 | 항해 | 2 | Vessel --ON_VOYAGE--> Voyage --FROM/TO_PORT--> Port |
| 6 | KRISO 시설 | 10 | Organization --HAS_FACILITY--> TestFacility |
| 7 | 실험 | 3 | Experiment --CONDUCTED_AT--> TestFacility |
| 8 | 규정 | 3 | Regulation --ENFORCED_BY--> Organization |
| 9 | 기상 | 1 | WeatherCondition --AFFECTS--> SeaArea |
| 10 | 사고 | 1 | Incident --INVOLVES--> Vessel, --VIOLATED--> Regulation |
| 11 | 센서 | 2 | Port --HAS_FACILITY--> Sensor |
| 12 | 실험 데이터 | 다수 | Experiment --PRODUCED--> Dataset --CONTAINS--> Measurement |

이 모든 게 하나의 연결된 그래프입니다.
부산항의 센서가 선박을 감지하고, 그 선박은 항해 중이고, 그 항해는 두 항구를 연결하고, 사고가 났으면 규정 위반이 기록되고, KRISO에서 그 선종의 모형선 실험이 있었다면 그 데이터까지 이어져 있어요.

---

### [19:30] STEP 4: 그래프에 질문한다 -- Cypher 쿼리

[SCREEN: 큰 숫자 "STEP 4" + "Cypher 쿼리" + 부제: "만든 그래프를 써먹는 순간"]

**일론:**
드디어 마지막 단계. 그래프를 만들었으니, 이제 질문합니다.

Cypher 쿼리를 쉬운 것부터 어려운 것까지 단계별로 보겠습니다.

#### Level 1: 단순 조회 -- "뭐가 있지?"

[SCREEN: Neo4j Browser에서 쿼리 실행]

```cypher
-- 모든 선박의 이름과 선종
MATCH (v:Vessel)
RETURN v.name AS 선박명, v.vesselType AS 선종, v.grossTonnage AS 총톤수
```

```
| 선박명         | 선종           | 총톤수     |
|---------------|---------------|-----------|
| HMM 알헤시라스 | ContainerShip | 228283.0  |
| 팬오션 드림    | BulkCarrier   | 81000.0   |
| 한라          | Tanker        | 160000.0  |
| 새마을호       | PassengerShip | 10500.0   |
| 무궁화 10호    | FishingVessel | 350.0     |
```

기본이죠. `MATCH`로 노드를 찾고 `RETURN`으로 결과를 돌려줍니다.

#### Level 2: 관계 따라가기 -- "누가 누구와 연결되어 있지?"

[SCREEN: 쿼리가 점점 복잡해지는 것을 시각적으로]

```cypher
-- 항해 중인 선박과 출발/도착 항구
MATCH (vessel:Vessel)-[:ON_VOYAGE]->(v:Voyage)
MATCH (v)-[:FROM_PORT]->(dep:Port)
MATCH (v)-[:TO_PORT]->(arr:Port)
RETURN vessel.name AS 선박명,
       dep.name AS 출발항,
       arr.name AS 도착항,
       v.cargoDesc AS 화물
```

```
| 선박명         | 출발항 | 도착항     | 화물                        |
|---------------|--------|-----------|----------------------------|
| HMM 알헤시라스 | 부산항 | 인천항     | 컨테이너 화물 (TEU 23,964) |
| 팬오션 드림    | 울산항 | 여수광양항 | 철광석 (iron ore) 80,000 MT |
```

화살표가 곧 질문입니다.
"선박이 항해 중이고, 그 항해의 출발/도착이 어디인지" -- 이 질문을 화살표로 따라가면 됩니다.

#### Level 3: 멀티홉 탐색 -- "관계의 관계의 관계"

[SCREEN: 큰 자막 -- "이게 그래프의 진짜 힘"]

```cypher
-- KRISO의 시험시설에서 수행된 실험과 그 측정 데이터
MATCH (org:Organization {name: 'KRISO'})          -- 1홉
      -[:HAS_FACILITY]->(tf:TestFacility)          -- 2홉
      <-[:CONDUCTED_AT]-(exp:Experiment)           -- 3홉
      -[:PRODUCED]->(ds:ExperimentalDataset)       -- 4홉
OPTIONAL MATCH (ds)-[:CONTAINS]->(m:Measurement)   -- 5홉
RETURN org.name AS 기관,
       tf.name AS 시설,
       exp.title AS 실험명,
       ds.title AS 데이터셋,
       collect(m.value) AS 측정값
```

[SCREEN: 결과 테이블]

```
| 기관   | 시설          | 실험명                    | 데이터셋              | 측정값                        |
|-------|-------------|--------------------------|----------------------|------------------------------|
| KRISO | 대형 예인수조 | KVLCC2 저항성능 시험       | KVLCC2 저항시험 데이터셋| [12.45, 28.73, 52.18, 0.72..] |
| KRISO | 해양공학수조  | 컨테이너선 내항성능 시험   | 컨테이너선 내항성능 데이터셋 | []                       |
| KRISO | 빙해수조     | 쇄빙 상선 빙해 저항성능 시험| 쇄빙 상선 빙해저항 데이터셋 | []                         |
```

**5홉.**
기관에서 출발해서 시험시설, 실험, 데이터셋, 측정값까지 한 번의 쿼리로 도달합니다.

[SCREEN: 같은 질문을 SQL로 쓰면 어떻게 되는지 -- 매우 긴 JOIN 쿼리]

이걸 SQL로 쓰면?

```sql
SELECT o.name, tf.name, e.title, ds.title, m.value
FROM organizations o
JOIN org_facilities of ON o.id = of.org_id
JOIN test_facilities tf ON of.facility_id = tf.id
JOIN experiments e ON e.facility_id = tf.id
JOIN experimental_datasets ds ON ds.experiment_id = e.id
LEFT JOIN measurements m ON m.dataset_id = ds.id
WHERE o.name = 'KRISO'
```

JOIN 5개. 그리고 각 테이블에 외래 키와 인덱스를 미리 설계해야 합니다.
Cypher에서는 화살표를 따라가면 끝이에요. 읽히는 대로 데이터가 나옵니다.

#### Level 4: 공간 쿼리 -- "여기 근처에 뭐가 있지?"

[SCREEN: 지도 시각화 -- 부산항 중심으로 50km 원이 그려짐]

```cypher
-- 부산항에서 반경 50km 이내 선박
MATCH (v:Vessel)
WHERE point.distance(
    v.currentLocation,
    point({latitude: 35.1028, longitude: 129.0403})  -- 부산항 좌표
) < 50000  -- 50km = 50,000미터
RETURN v.name AS 선박명,
       v.vesselType AS 선종,
       v.grossTonnage AS 총톤수,
       round(point.distance(
           v.currentLocation,
           point({latitude: 35.1028, longitude: 129.0403})
       ) / 1000) AS 거리_km
```

이 쿼리는 아까 만든 공간 인덱스(`vessel_location`) 덕분에 빠르게 실행됩니다.
GPS 좌표가 `POINT` 타입으로 저장되어 있기 때문에 가능한 거예요.

#### Level 5: 사고 분석 -- "관계의 사슬을 따라가기"

```cypher
-- 사고와 관련된 모든 정보를 한 번에
MATCH (inc:Incident {incidentId: 'INC-2024-0042'})
OPTIONAL MATCH (inc)-[:INVOLVES]->(v:Vessel)
OPTIONAL MATCH (inc)-[:VIOLATED]->(reg:Regulation)
OPTIONAL MATCH (doc:Document)-[:DESCRIBES]->(inc)
OPTIONAL MATCH (doc)-[:ISSUED_BY]->(org:Organization)
RETURN inc.description AS 사고내용,
       inc.severity AS 심각도,
       v.name AS 관련선박,
       reg.title AS 위반규정,
       doc.title AS 보고서,
       org.name AS 발행기관
```

```
| 사고내용              | 심각도   | 관련선박        | 위반규정              | 보고서                    | 발행기관   |
|----------------------|---------|----------------|----------------------|--------------------------|-----------|
| 부산항 접근 수역에서   | MODERATE| HMM 알헤시라스  | 국제해상충돌예방규칙    | 부산항 접근수역 충돌사고   | 해양경찰청 |
| 컨테이너선과 소형 어선 |         |                |                      | 보고서                    |           |
| 간 접촉 사고 발생...   |         |                |                      |                          |           |
```

[SCREEN: 이 쿼리의 결과를 그래프 시각화로 -- Incident 노드를 중심으로 관련 노드들이 연결]

사고 하나를 중심으로, 관련 선박, 위반된 규정, 보고서, 발행 기관이 전부 한 번의 쿼리로 나옵니다.

이게 지식그래프의 진짜 가치입니다.
"사고가 났다. 어떤 배가 관련됐지? 무슨 규정을 위반했지? 보고서는 누가 냈지?" -- 연쇄 질문을 화살표를 따라가면서 답할 수 있어요.

---

### [22:00] 마무리 -- 전체 구조 복습

[SCREEN: 4단계가 왼쪽에서 오른쪽으로 플로우 다이어그램]

**일론:**
정리하겠습니다.

[SCREEN: 전체 구조 다이어그램 -- 각 단계가 하나씩 하이라이트]

**STEP 1: 세상을 정의한다 -- 온톨로지**
- 해사 세계에 뭐가 있는지 나열 (127개 엔티티)
- 11개 그룹으로 분류
- 속성 정의 (29종), 관계 정의 (83개)
- Python = Single Source of Truth

**STEP 2: 법을 세운다 -- Neo4j 스키마**
- 제약조건 24개 (고유성 보장)
- 인덱스 44개 (벡터 4, 공간 5, 풀텍스트 8, 범위 27)
- 전부 멱등성 (IF NOT EXISTS)

**STEP 3: 생명을 불어넣는다 -- 데이터 적재**
- MERGE 패턴으로 안전하게 적재
- 12개 카테고리: 기관, 항구, 해역, 선박, 항해, 시험시설, 실험, 규정, 기상, 사고, 센서, 실험데이터
- 모든 노드가 관계로 연결

**STEP 4: 질문한다 -- Cypher 쿼리**
- 단순 조회부터 5홉 탐색까지
- 공간 쿼리 (GPS 범위 검색)
- 사고 분석 (관계의 사슬 따라가기)

[SCREEN: 최종 그래프 구조 -- 전체 연결 관계 요약 다이어그램]

```
Organization(KRISO) ----HAS_FACILITY---> TestFacility(대형 예인수조)
     |                                         ^
     |                                    CONDUCTED_AT
     v                                         |
Organization(HMM) <--OWNED_BY-- Vessel(HMM 알헤시라스) --ON_VOYAGE--> Voyage
                                    |              |                    |
                                 LOCATED_AT     INVOLVES          FROM/TO_PORT
                                    |              |                    |
                                 SeaArea       Incident             Port(부산항)
                                (대한해협)        |                    |
                                             VIOLATED            ACCESSIBLE_FROM
                                                |                    |
                                            Regulation            SeaArea
                                           (COLREG)              (대한해협)
```

이 다이어그램이 오늘 만든 그래프의 핵심입니다.
선박, 항구, 항해, 사고, 규정, 연구시설 -- 전부가 하나의 연결된 지식 네트워크예요.

[SCREEN: 핵심 교훈 3가지]

**교훈 1: 온톨로지 설계에 시간을 투자하라.**
나머지는 기계적입니다. 첫 단계를 잘하면 나머지가 자연스럽게 따라옵니다.

**교훈 2: 멱등성을 습관화하라.**
MERGE, IF NOT EXISTS. 같은 코드를 몇 번 실행해도 안전해야 합니다. 프로덕션에서 이게 생명을 구합니다.

**교훈 3: 관계가 데이터 자체인 도메인에서 그래프가 빛난다.**
선박이 항구에 정박하고, 항구는 해역에 있고, 해역에는 기상이 있고, 기상은 사고에 영향을 미친다. 이런 관계의 사슬이 많은 도메인이라면, 그래프를 진지하게 고려해보세요.

[SCREEN: 기술 스택 카드]

| 기술 | 역할 |
|------|------|
| Neo4j 5.26 CE | 그래프 데이터베이스 |
| Python 3.10+ | 온톨로지 정의 + 전체 백엔드 |
| Cypher | 그래프 쿼리 언어 |

오늘은 여기까지. 지식그래프를 **어떻게 만드는지**, 4단계의 과정을 코드와 함께 보셨습니다.

[SCREEN: "다음 영상 예고" 카드]

다음 영상에서는 이 그래프 위에 **한국어로 질문하면 자동으로 Cypher를 생성하는 파이프라인** -- 룰 기반 NLP부터 GraphRAG Agentic 모드까지 보여드리겠습니다.

이 영상이 도움이 됐다면 좋아요 부탁드리고요, 지식그래프 구축에 관심 있으시면 구독해주세요.

댓글로 "저는 이런 도메인에 KG를 만들어보고 싶다" 남겨주시면, 도메인별 설계 팁도 다뤄보겠습니다.

그럼, 다음 영상에서 뵙겠습니다.

[SCREEN: 엔드카드 -- 구독 버튼 + 이전 영상]

[B-ROLL: Neo4j 그래프 시각화가 회전하며 페이드아웃]

---

## 썸네일 디자인 아이디어

### 안 1 (추천): "4단계 구축법" 프로세스형

```
+-----------------------------------------------+
|                                               |
|  [상단 큰 글씨]                               |
|  "지식그래프"                                  |
|  "4단계 구축법"                                |
|                                               |
|  [중앙: 4단계 아이콘이 화살표로 연결]          |
|  정의 --> 스키마 --> 적재 --> 쿼리              |
|  (뇌)    (자물쇠)  (데이터)  (돋보기)          |
|                                               |
|  [하단 서브타이틀]                             |
|  "127개 엔티티 해사 KG 실전 구축기"            |
|                                               |
|  [배경: 다크 네이비 + 노드 그래프 오버레이]    |
|  [얼굴: 일론, 설명하는 포즈, 좌측]            |
+-----------------------------------------------+
```

- 색상: 다크 네이비 배경 + 하얀 글씨 + 시안 포인트
- 핵심: "4단계"가 가장 크게
- 태그: "Neo4j" "Python" "튜토리얼"

### 안 2: "127개 엔티티" 스케일형

```
+-----------------------------------------------+
|                                               |
|  [배경: 실제 Neo4j 그래프 시각화 스크린샷]     |
|  노드 수십 개가 연결된 그래프 (블러 처리)      |
|                                               |
|  [중앙 큰 글씨]                               |
|  "127개 엔티티"                                |
|  "83개 관계"                                   |
|                                               |
|  [하단 강조]                                   |
|  "처음부터 만들기"                              |
|                                               |
|  [화살표 느낌의 플로우 오버레이]               |
+-----------------------------------------------+
```

- 색상: 다크 그레이 배경 + 밝은 시안 노드 + 흰 텍스트
- 숫자에 글로우 효과
- "처음부터 만들기"에 노란 밑줄

---

## 제작 노트

### 필요한 화면 녹화/캡처

1. VS Code에서 `kg/ontology/maritime_ontology.py` 파일 스크롤 (ENTITY_LABELS, RELATIONSHIP_TYPES, PROPERTY_DEFINITIONS)
2. VS Code에서 `kg/ontology/core.py` 파일 (ObjectTypeDefinition, LinkTypeDefinition)
3. VS Code에서 `kg/schema/constraints.cypher` 파일
4. VS Code에서 `kg/schema/indexes.cypher` 파일
5. VS Code에서 `kg/schema/load_sample_data.py` 파일 (각 _create_* 함수)
6. Neo4j Browser에서 각 Level 쿼리 실행 결과
7. Neo4j Browser에서 그래프 시각화 (특히 KRISO 연구 그래프 부분)
8. 터미널에서 `python -m kg.schema.init_schema` 실행 + `python -m kg.schema.load_sample_data` 실행

### B-Roll 소스

- 컨테이너선 항공 촬영 (Pexels/Pixabay 무료)
- 한국 지도 + 5대 항구 핀 애니메이션
- HMM 알헤시라스호 실제 사진 (언론 공개 이미지)
- KRISO 시험수조 영상 (공개 홍보 영상 있으면)
- 화이트보드에 다이어그램 그리는 타임랩스 (또는 애니메이션)
- Neo4j 그래프 줌인/줌아웃/회전

### 편집 포인트

- 인트로: 차분하게 시작, "어렵게 느껴지는" 공감
- STEP 1 (온톨로지): 가장 길고 상세하게. 코드와 다이어그램 교차 편집. 설계 결정 이유를 강조
- STEP 2 (스키마): 코드 중심. "법을 세운다"는 비유를 시각적으로
- STEP 3 (적재): 가장 시각적으로. 그래프가 확장되는 애니메이션 효과. 에너지 약간 올림
- STEP 4 (쿼리): "와 이게 한 번에 된다"는 임팩트. SQL 대비 Cypher 비교할 때 에너지 최고
- 마무리: 차분하게 복습. 핵심 교훈 텍스트 오버레이

### 톤앤매너

- 선생님이 아니라 같이 만들어보는 동료 개발자 느낌
- "이거 어려운 것 같지만 사실 단순해요" 반복 강조
- 기술 용어 나올 때마다 한국어로 풀어서 설명
- 코드를 보여줄 때 항상 "왜 이렇게 했는지" 이유를 먼저 설명
