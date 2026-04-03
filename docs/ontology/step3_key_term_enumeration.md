# Step 3: 핵심 용어 열거 (Key Term Enumeration)

> **Stanford 7-Step Ontology Design Methodology** | DevKG 구축
>
> 작성일: 2026-04-03 | 프로젝트: DevKG (`X-KG-Project: DevKG`)

---

## 3.1 용어 수집 소스 종합

6개 소스에서 수집한 용어를 3계층(P0 Core / P1 Extended / P2 Future)으로 분류한다. **1차년도 DevKG는 P0+P1 범위**로 구축한다.

| 소스 | 엔티티 | 관계 | 활용 |
|------|-------|------|------|
| **maritime_ontology.py** | 155개 | 93개 | 기존 정의 기반, 3계층 재분류 |
| **CQ1-CQ5 Cypher** | +4 신규 | +7 신규 | TestScenario, MeasurementRecord, VoyageEvent, AISRecord |
| **논문 4편** | +5 신규 | +8 신규 | VHFRecord, CCTVRecord, VTSOperator, MaritimeEvent 등 |
| **Neo4j 스키마** | 검증용 | +1 (OWNED_BY) | 제약조건·인덱스 속성 보완 |
| **샘플 데이터** | 검증용 | — | 누락 속성 보완 (nameEn, seaAreaType 등) |
| **프로젝트 시스템** | — | — | _kg_project 속성 + KG_ 레이블 자동 부여 |

### 3계층 규모 요약

| 계층 | 엔티티 수 | 시기 | 기준 |
|------|----------|------|------|
| **P0 Core** | ~27개 | 즉시 구현 | CQ1-CQ5 필수 |
| **P1 Extended** | ~47개 | 1차년도 후반 | VHF/CCTV 포함 |
| **P2 Future** | ~55개 | 2차년도 이후 | RBAC, 멀티모달 표현 |

---

## 3.2 P0 Core 엔티티 (CQ 필수, 즉시 구현)

CQ1~CQ5 검증 질의를 통과하기 위해 반드시 필요한 엔티티. DevKG PoC 적재 대상.

### 물리 엔티티 (8개) — 선박, 항만, 해역, 센서

| 엔티티 | 설명 | CQ 참조 | 출처 |
|-------|------|--------|------|
| **Vessel** | 모든 수상 선박 (상선, 어선, 군함, 자율운항선) | CQ1-5 | 기존 |
| **Port** | 항만 시설 (무역항, 연안항, 어항) | CQ1,3 | 기존 |
| **Berth** | 항만 내 접안 위치 | CQ1 | 기존+오재용 |
| **Anchorage** | 지정 정박 구역 | CQ1 | 기존+오재용 |
| **SeaArea** | 명명/규제 해역 (VTS, TSS, EEZ) | CQ1,3 | 기존 |
| **Waterway** | 항로, 해협, 수로 | CQ1 | 기존 |
| **GeoPoint** | 단일 위경도 좌표 | CQ1,2 | 기존 |
| **Sensor** | 관측 장비 (AIS, 레이더, 기상) | CQ4 | 기존 |

### 시간 엔티티 (6개) — 항해, 이벤트, 기상

| 엔티티 | 설명 | CQ 참조 | 출처 |
|-------|------|--------|------|
| **Voyage** | 출발항 → 도착항 완전 항해 | CQ2,4 | 기존 |
| **VoyageEvent** _(NEW)_ | 항해 중 이산 이벤트 (속력변화, 침로변화, 시운전) | CQ2 | CQ2+Li et al. |
| **TrackSegment** | 연속 AIS 궤적 구간 | CQ1,2 | 기존 |
| **AISRecord** _(NEW)_ | 단일 AIS 위치 보고 (위치, 속력, 침로, 선수각) | CQ1,2 | 오재용+IMO AIS |
| **WeatherCondition** | 관측/예보 기상 상태 | CQ4 | 기존+Li et al. |
| **SensorReading** | 시계열 센서 측정값 | CQ4 | 기존 |

### KRISO 시험시설 (7개) — 시험 4단계 체인

| 엔티티 | 설명 | CQ 참조 | 출처 |
|-------|------|--------|------|
| **TestFacility** | KRISO 물리적 시험시설 (8종) | CQ2,4,5 | 기존 |
| **Experiment** | 시험 캠페인 (1회 실험 단위) | CQ2,4,5 | 기존 |
| **TestScenario** _(NEW)_ | 실험 내 시험 시나리오 | CQ1,2,5 | CQ 도출 |
| **TestCondition** | 환경/운영 시험 조건 | CQ4,5 | 기존 |
| **MeasurementRecord** _(NEW)_ | 타입별 계측 결과 (저항, 추진, 캐비테이션) | CQ1,2,4 | CQ 도출 |
| **ModelShip** | 축척 모형선 | CQ2,4 | 기존 |
| **ExperimentalDataset** | 실험 산출 데이터셋 | CQ4 | 기존 |

**4단계 체인:**

```
TestFacility →[HOSTS]→ TestScenario →[APPLIES]→ TestCondition →[PRODUCES]→ MeasurementRecord
  (시험시설)             (시험시나리오)            (시험조건)                   (계측결과)
```

### 정보/규정 (6개) — 규정, 문서, 조직

| 엔티티 | 설명 | CQ 참조 | 출처 |
|-------|------|--------|------|
| **Regulation** | 해사 규정/협약 (COLREGS, SOLAS, MARPOL) | CQ3 | 기존+MAKG |
| **Document** | 문서 (보고서, 통지, 매니페스트) | CQ3 | 기존 |
| **Organization** | 법인/기관 (해운사, 정부, 연구소) | CQ5 | 기존+MAKG |
| **AIModel** | ML/AI 추론 모델 | CQ5 | 기존 |
| **Workflow** | 데이터 처리/분석 워크플로우 | CQ5 | 기존 |
| **WorkflowNode** | 워크플로우 내 개별 처리 단계 | — | 기존 |

> **P0 Core 합계: 27개 엔티티** — CQ1~CQ5 전체 통과에 필요한 최소 집합

---

## 3.3 P1 Extended 엔티티 (1차년도 후반)

CQ 검증 후 1차년도 내 확장 대상. VHF/CCTV 멀티모달, 사고/이벤트, 하위 타입 세분화.

### 멀티모달 데이터 (8개) — 오재용·김혜진 논문 기반

| 엔티티 | 설명 | 출처 |
|-------|------|------|
| **VHFRecord** _(NEW)_ | VHF 교신 기록 (송신자, 수신자, 내용) | 오재용 Table 2 |
| **CCTVRecord** _(NEW)_ | CCTV 관측 기록 (위치, 장비, 시간) | 오재용 Table 2 |
| **VTSOperator** _(NEW)_ | VTS 관제사 (교신 주체) | 오재용 Table 2 |
| **AISData** | AIS 위치 보고 시계열 배치 | 기존 |
| **SatelliteImage** | 위성 영상 (광학/SAR) | 기존 |
| **RadarImage** | 육상/선박 레이더 영상 | 기존 |
| **VideoClip** | CCTV/드론 영상 클립 | 기존 |
| **MaritimeChart** | 전자해도 (ENC) 데이터 | 기존 |

### 이벤트/사고 (8개) — MaritimeEvent 계층

| 엔티티 | 설명 | 출처 |
|-------|------|------|
| **MaritimeEvent** _(NEW)_ | 해사 이벤트 통합 (사고+입출항+VTS) | MAKG 매핑 |
| **Incident** | 해양 사건/사고 | 기존 |
| **Collision** | 선박 충돌 | 기존 |
| **Grounding** | 좌초 | 기존 |
| **Pollution** | 해양 오염 (유출) | 기존 |
| **Distress** | 조난 (SAR 필요) | 기존 |
| **PortCall** | 선박의 항만 방문 | 기존 |
| **Activity** | 선박 운영 활동 (양하, 급유 등) | 기존 |

### 선박 하위 타입 (6개) — AIS 선종코드 기반

| 엔티티 | AIS 코드 | 설명 |
|-------|---------|------|
| **CargoShip** | 70-79 | 화물선 |
| **Tanker** | 80-89 | 유조선 |
| **PassengerShip** | 60-69 | 여객선 (페리, 크루즈) |
| **FishingVessel** | 30 | 어선 |
| **NavalVessel** | 35 | 군함/해경선 |
| **AutonomousVessel** | — | 자율운항선 (MASS) |

### 시험시설 하위 타입 (8개) — KRISO 8종

| 엔티티 | 설명 |
|-------|------|
| **TowingTank** | 예인수조 (저항/추진 시험) |
| **OceanEngineeringBasin** | 해양공학수조 (내항성능 시험) |
| **IceTank** | 빙해수조 (빙해 성능 시험) |
| **DeepOceanBasin** | 심해공학수조 |
| **CavitationTunnel** | 캐비테이션 터널 (대형/중형/고속) |
| **WaveEnergyTestSite** | 파력발전 실해역 시험장 |
| **HyperbaricChamber** | 고압 챔버 |
| **BridgeSimulator** | 선교 시뮬레이터 |

### 규정 하위 타입 + 데이터소스 (11개)

| 엔티티 | 설명 |
|-------|------|
| **COLREG** | COLREGS(국제해상충돌예방규칙) 조문 |
| **SOLAS** | 해상인명안전협약 |
| **MARPOL** | 선박오염방지협약 |
| **IMDGCode** | 위험물운송규칙 |
| **AccidentReport** | 사고조사보고서 |
| **InspectionReport** | PSC/FSC 검사보고서 |
| **NavigationalWarning** | 항행경보 (NAVTEX) |
| **DataSource** | 외부 데이터 제공원/피드 |
| **APIEndpoint** | REST/gRPC 수집 엔드포인트 |
| **StreamSource** | 실시간 스트림 (Kafka, MQTT) |
| **FileSource** | 배치 파일 소스 |

> **P1 Extended 합계: ~47개 엔티티** — 1차년도 후반 확장 (VHF/CCTV + 하위 타입 + 이벤트 계층)

---

## 3.4 P2 Future 엔티티 (2차년도 이후)

2차년도(2029-2030) 플랫폼 고도화 시 추가. 관측 융합, 서비스 레이어, RBAC, 멀티모달 표현.

| 그룹 | 엔티티 | 수량 | 비고 |
|------|-------|------|------|
| **Observation 계층** | Observation, SARObservation, OpticalObservation, CCTVObservation, AISObservation, RadarObservation, WeatherObservation | 7 | 관측 데이터 통합 타입 |
| **Agent 확장** | Person, CrewMember, Inspector, GovernmentAgency, ShippingCompany, ResearchInstitute, ClassificationSociety | 7 | Crew/Person은 MaritimeAccidentKG에서 우선 구현 |
| **플랫폼 리소스** | WorkflowExecution, DataPipeline, AIAgent, MCPTool, MCPResource, Service, QueryService, AnalysisService, AlertService, PredictionService | 10 | 플랫폼 자체 메타데이터 |
| **물리 확장** | Terminal, PortFacility, TSS, Channel, EEZ, TerritorialSea, CoastalRegion, AISTransceiver, Radar, CCTVCamera, WeatherStation, Cargo, DangerousGoods, BulkCargo, ContainerCargo | 15 | Cargo는 제외 결정 → P2로 이동 |
| **멀티모달 표현** | VisualEmbedding, TrajectoryEmbedding, TextEmbedding, FusedEmbedding | 4 | 벡터 임베딩 엔티티 |
| **RBAC** | User, Role, DataClass, Permission | 4 | Keycloak 전환 후 통합 |
| **기타** | IllegalFishing, Loitering, Loading, Unloading, Bunkering, Anchoring, OceanEnvironment, CargoManifest | 8 | 세부 활동/환경 타입 |

> **P2 Future 합계: ~55개 엔티티** — 2차년도 플랫폼 고도화 시 점진적 추가

---

## 3.5 관계 타입 목록 (3계층)

108개 관계 타입을 3계층으로 분류. P0 관계는 CQ Cypher 질의에 직접 사용된다.

### P0 CORE 관계 — CQ 필수 (28개)

| 관계 | From | To | CQ | 출처 |
|------|------|-----|-----|------|
| `LOCATED_AT` (위치) | Vessel | SeaArea | CQ1 | 기존 |
| `DOCKED_AT` (접안) | Vessel | Berth | CQ1 | 기존 |
| `ANCHORED_AT` (정박) | Vessel | Anchorage | CQ1 | 기존+오재용 |
| `BERTH_TO` (접안-오재용) | Vessel | Berth | — | 오재용 |
| `HAS_FACILITY` (시설보유) | Port | PortFacility | CQ1 | 기존 |
| `CONNECTED_VIA` (항로연결) | Port | Waterway | CQ1 | 기존 |
| `CONNECTS` (해역연결) | Waterway | SeaArea | CQ1 | 기존 |
| `ON_VOYAGE` (항해중) | Vessel | Voyage | CQ2 | 기존 |
| `FROM_PORT` (출발항) | Voyage | Port | CQ2 | 기존 |
| `TO_PORT` (도착항) | Voyage | Port | CQ2 | 기존 |
| `CONSISTS_OF` (구간구성) | Voyage | TrackSegment | CQ2 | 기존 |
| `PARTICIPATED_IN` (이벤트참여) _(NEW)_ | Vessel | VoyageEvent | CQ2 | CQ 도출 |
| `PRODUCES` (산출) | Sensor / TestScenario | SensorReading / MeasurementRecord | CQ4,5 | 기존+확장 |
| `APPLIES_TO` (적용대상) | Regulation | Vessel / SeaArea | CQ3 | 기존+확장 |
| `HAS_VTS_ZONE` (VTS관할) _(NEW)_ | Port | SeaArea | CQ3 | CQ 도출 |
| `TESTED_IN` (시험대상) _(NEW)_ | Vessel | TestScenario | CQ1,2 | CQ 도출 |
| `HOSTS` (시험수행) _(NEW)_ | TestFacility | TestScenario | CQ5 | CQ 도출 |
| `APPLIES` (조건적용) _(NEW)_ | TestScenario | TestCondition | CQ5 | CQ 도출 |
| `CONDUCTED_AT` (실험장소) | Experiment | TestFacility | CQ2,5 | 기존 |
| `TESTED` (모형시험) | Experiment | ModelShip | CQ2 | 기존 |
| `PRODUCED` (데이터산출) | Experiment | ExperimentalDataset | CQ4 | 기존 |
| `UNDER_CONDITION` (시험조건) | Experiment | TestCondition | CQ4 | 기존 |
| `MODEL_OF` (모형대응) | ModelShip | Vessel | CQ2 | 기존 |
| `OWNED_BY` (소유) _(NEW)_ | Vessel | Organization | — | 샘플 데이터 |
| `USES_MODEL` (모델사용) | WorkflowNode | AIModel | CQ5 | 기존 |
| `CONTAINS_NODE` (노드포함) | Workflow | WorkflowNode | CQ5 | 기존 |
| `AFFECTS` (영향) | WeatherCondition | SeaArea | CQ4 | 기존 |

### P1 EXTENDED 관계 — 1차년도 후반 (18개)

| 관계 | From | To | 출처 |
|------|------|-----|------|
| `TRANSMITTED_BY` (송신선박) _(NEW)_ | VHFRecord | Vessel | 오재용 |
| `INTENDED_FOR` (수신대상) _(NEW)_ | VHFRecord | Vessel / VTS | 오재용 |
| `ARRIVED_AT` (입항) _(NEW)_ | Vessel | Port | 오재용 |
| `DEPARTED_FROM` (출항) _(NEW)_ | Vessel | Port | 오재용 |
| `COMMUNICATE_WITH` (교신) _(NEW)_ | VTSOperator | Vessel | 오재용 |
| `BELONG_TO` (상위해역) _(NEW)_ | SeaArea | SeaArea | PIKG |
| `INVOLVES` (관련선박) | Incident | Vessel | 기존 |
| `CAUSED_BY` (원인기상) | Incident | WeatherCondition | 기존 |
| `OCCURRED_AT` (발생위치) | Incident | GeoPoint | 기존 |
| `VIOLATED` (규정위반) | Incident | Regulation | 기존 |
| `DESCRIBES` (사고기술) | Document | Incident | 기존 |
| `ISSUED_BY` (발행기관) | Document | Organization | 기존 |
| `ENFORCED_BY` (집행기관) | Regulation | Organization | 기존 |
| `CARRIES` (화물적재) | Vessel | Cargo | 기존 |
| `PERFORMS` (활동수행) | Vessel | Activity | 기존 |
| `PROVIDED_BY` (제공기관) | DataSource | Organization | 기존 |
| `AIS_TRACK_OF` (AIS궤적) | AISData | Vessel | 기존 |
| `OBSERVED_IN_AREA` (관측해역) | AISData | SeaArea | 기존 |

### P2 FUTURE 관계 — 2차년도 (62개)

관측(Observation) 8개, 크로스모달 2개, 서비스/리니지 8개, 플랫폼 15개, 멀티모달 14개, KRISO 실험 확장 8개, RBAC 5개, 기타 2개 — 상세 목록은 `maritime_ontology.py` 참조

> **관계 합계**: P0: 28개 + P1: 18개 + P2: 62개 = **108개**

---

## 3.6 P0 핵심 속성 목록 (신규/확장)

기존 속성 외에 CQ와 논문에서 도출된 **신규/확장 속성 25개**. 기존 속성은 Step 5에서 전체 정의.

| 엔티티 | 속성 | 타입 | 출처 | 설명 |
|-------|------|------|------|------|
| **AISRecord** | location | POINT | IMO AIS | 위경도 좌표 |
| | speed | FLOAT | IMO AIS | 대지속력 (knots) |
| | course | FLOAT | IMO AIS | 대지침로 (degrees) |
| | heading | FLOAT | IMO AIS | 선수각 (degrees) |
| | navStatus | STRING | IMO AIS | 항해 상태 코드 |
| **MeasurementRecord** | resistanceCoefficient | FLOAT | CQ1 | 저항 계수 |
| | parameterType | STRING | CQ2 | 계측 파라미터 유형 |
| | resistanceIncrease | FLOAT | CQ4 | 저항 증가량 (%) |
| **VoyageEvent** | eventType | STRING | Li et al. | 이벤트 유형 (속력변화/침로변화/정지) |
| | actualEHP | FLOAT | CQ2 | 실측 유효마력 |
| | hasPerformanceData | BOOLEAN | CQ2 | 성능 데이터 보유 여부 |
| **Regulation** | framework | STRING | CQ3 | 규정 체계 (COLREGS/SOLAS/MARPOL) |
| | articleNumber | STRING | CQ3 | 조문 번호 |
| **TestCondition** | cavitationType | STRING | CQ5 | 캐비테이션 유형 |
| | pressure | FLOAT | CQ5 | 압력 (Pa) |
| | propellerRPM | FLOAT | CQ5 | 프로펠러 회전수 |
| **TestScenario** | scenarioId | STRING | CQ5 | 시나리오 고유 식별자 |
| **TrackSegment** | startPoint | POINT | 샘플 데이터 | 구간 시작점 |
| | endPoint | POINT | 샘플 데이터 | 구간 종료점 |
| | distance | FLOAT | 샘플 데이터 | 구간 거리 (NM) |
| | avgSpeed | FLOAT | 샘플 데이터 | 구간 평균 속력 |
| | anomaly | BOOLEAN | 인덱스 | 이상행동 감지 플래그 |
| **SeaArea** | seaAreaType | STRING | 샘플 데이터 | 해역 유형 (coastal_sea, strait 등) |
| **Organization** | orgType | STRING | 샘플 데이터 | 기관 유형 (정부, 해운사, 연구소) |

---

## Step 3 검증 CQ — 용어 완전성

열거된 엔티티/관계가 마스터 CQ Cypher를 실행하기에 충분한지 검증한다.

| ID | 검증 질문 | 검증 대상 |
|----|---------|---------|
| **S3-CQ1** | P0 엔티티 27개 + 관계 28개만으로 CQ1~CQ5 Cypher가 문법적으로 유효한가? | 용어 완전성 — 각 CQ 검증 Cypher의 노드 라벨과 관계 타입이 P0 목록에 모두 존재하는지 매칭 |
| **S3-CQ2** | P1 확장 없이 누락되는 CQ 경로(패턴)가 있는가? | P0/P1 경계 검증 — P0만으로 답할 수 없는 CQ가 있다면 해당 엔티티를 P0로 승격해야 하는지 판단 |
| **S3-CQ3** | 신규 엔티티 4개(VoyageEvent, AISRecord, TestScenario, MeasurementRecord)가 없으면 어떤 CQ가 깨지는가? | 신규 엔티티 필요성 — 4개 NEW 엔티티 각각이 커버하는 CQ를 역추적하여 추가 근거 확인 |

---

## Step 3 설계 결정 기록

Step 3 진행 중 확정된 설계 결정 사항.

| # | 결정 사항 | 선택 | 근거 |
|---|---------|------|------|
| D1 | 엔티티 분류 방식 | **3계층 (P0/P1/P2)** | 전체 155+ 엔티티를 보존하되 구현 우선순위 명시 |
| D2 | VHF/CCTV 엔티티 시기 | **P1 (1차년도 포함)** | 오재용·김혜진 KRISO 책임연구원 논문 기반, 직접 연계 가능 |
| D3 | MAKG Crew/Cargo 포함 여부 | **둘 다 제외** | 1차년도는 해상교통+시험시설 집중. 사고 분석은 MaritimeAccidentKG에서 별도 |
| D4 | 신규 엔티티 | **9개 추가** | TestScenario, MeasurementRecord, VoyageEvent, AISRecord (P0) + VHFRecord, CCTVRecord, VTSOperator, MaritimeEvent, OceanEnvironment (P1/P2) |
| D5 | 신규 관계 | **15개 추가** | CQ 도출 7개 + 오재용 논문 6개 + PIKG 1개 + 샘플 데이터 1개 |

---

## 다음 단계

**Step 4: 클래스 계층 정의** (Class Hierarchy)
- 8개 핵심 클래스 계층 구조 (L1~L5)
- URN 식별 체계: `urn:kriso:kg:{type}:{subtype}:{id}`
- 클래스 간 상속/구현 관계
- Neo4j 레이블 매핑 전략

---

## 참조

| 문서 | 내용 |
|------|------|
| `domains/maritime/ontology/maritime_ontology.py` | 155개 엔티티 + 93개 관계 원본 정의 |
| Step 1: 목적 정의 (`step1_purpose_definition.md`) | CQ1-CQ5 정의, 도메인 범위 |
| Step 2: 재사용 분석 (`step2_reuse_evaluation.md`) | 10개 온톨로지/표준 분석 결과 |
| KRISO 제안서 S14-S19 | Step 3-7 핵심 용어~인스턴스, L1-L5 계층 |
| KRISO 제안서 S24 | 14개 핵심 관계 카탈로그 |
