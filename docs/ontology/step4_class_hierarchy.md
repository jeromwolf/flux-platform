# Step 4: 클래스 계층 정의 (Class Hierarchy)

> **Stanford 7-Step Ontology Design Methodology** | DevKG 구축
>
> 작성일: 2026-04-11 | 프로젝트: DevKG (`X-KG-Project: DevKG`)

---

## 4.1 계층 설계 원칙

Step 3에서 열거한 129개 엔티티(P0 27 + P1 47 + P2 55)를 **5단계 깊이(L1~L5)**의 IS_A 계층으로 구조화한다. Neo4j 멀티레이블 스태킹을 통해 구현하며, 별도의 `IS_A` 관계는 생성하지 않는다.

### 설계 규칙

| 규칙 | 설명 |
|------|------|
| **단일 상속** | 각 엔티티는 하나의 부모만 가짐 (다중 상속 금지) |
| **멀티레이블 스태킹** | 모든 상위 레이블을 Neo4j 노드에 포함 (`:L1:L2:...:Leaf`) |
| **추상 타입 비생성** | abstract 타입은 인스턴스를 직접 생성하지 않음 (질의용 레이블만 부여) |
| **속성 추가만 허용** | 하위 클래스는 속성을 추가할 수 있으나 오버라이드 불가 |
| **KG 프로젝트 레이블** | 모든 노드에 `KG_{project}` 레이블 추가 (멀티 KG 격리) |

### 계층 수준 정의

| Level | 의미 | 예시 | 수량 |
|-------|------|------|------|
| L1 | 온톨로지 범주 (추상) | PhysicalEntity, TemporalEntity | 6 |
| L2 | 핵심 도메인 클래스 | Vessel, Port, Voyage, Regulation | ~30 |
| L3 | 하위 타입 | CargoShip, TowingTank, Collision | ~80 |
| L4 | 세부 특화 | LargeCavitationTunnel, Resistance | ~20 |
| L5 | 최하위 (필요 시) | 현재 미사용 (확장 예약) | 0 |

### 추상 타입 (12개)

L1 6개 추상 루트와 L2 5개 추상 그룹, 그리고 ENTITY_LABELS에 포함되나 직접 인스턴스화하지 않는 Observation 1개로 구성한다. 추상 타입은 직접 인스턴스화하지 않고 다형성 질의를 위한 레이블로만 사용한다.

| 추상 타입 | Level | 목적 |
|----------|-------|------|
| **PhysicalEntity** | L1 | 물리적 개체 루트 (선박, 항만, 시설, 센서) |
| **SpatialEntity** | L1 | 공간 개체 루트 (해역, 좌표, 환경) |
| **TemporalEntity** | L1 | 시간 개체 루트 (항해, 이벤트, 실험) |
| **InformationEntity** | L1 | 정보 개체 루트 (규정, 문서, 서비스) |
| **ObservationEntity** | L1 | 관측 개체 루트 (센서 데이터, 계측, 임베딩) |
| **AgentEntity** | L1 | 행위자 루트 (기관, 인물, AI) |
| **PortInfrastructure** | L2 | Berth/Anchorage/Terminal/PortFacility 그룹 |
| **PlatformResource** | L2 | Workflow/AIModel/DataPipeline/MCP 그룹 |
| **MultimodalData** | L2 | 멀티모달 센서 데이터 그룹 |
| **MultimodalRepresentation** | L2 | 벡터 임베딩 그룹 |
| **AccessControl** | L2 | RBAC 그룹 |
| **Observation** | L2 | 관측 데이터 통합 기본 타입 (ENTITY_LABELS에 포함되나 직접 인스턴스화하지 않음) |

---

## 4.2 전체 계층 트리 (L1~L5)

모든 엔티티를 L1~L4 계층으로 배치한다. 각 노드에 `(Level, 우선순위)` 또는 `(Level, impl)` 표기.

```
PhysicalEntity (abstract, L1)
├── Vessel (L2, P0)
│   ├── CargoShip (L3, P1)
│   ├── Tanker (L3, P1)
│   ├── PassengerShip (L3, P1)
│   ├── FishingVessel (L3, P1)
│   ├── NavalVessel (L3, P1)
│   └── AutonomousVessel (L3, P1)
├── Port (L2, P0)
│   ├── TradePort (L3, P2)
│   ├── CoastalPort (L3, P2)
│   └── FishingPort (L3, P2)
├── PortInfrastructure (abstract, L2)
│   ├── PortFacility (L3, P2)
│   ├── Berth (L3, P0)
│   ├── Anchorage (L3, P0)
│   └── Terminal (L3, P2)
├── Waterway (L2, P0)
│   ├── TSS (L3, P2)
│   └── Channel (L3, P2)
├── Sensor (L2, P0)
│   ├── AISTransceiver (L3, P2)
│   ├── Radar (L3, P2)
│   ├── CCTVCamera (L3, P2)
│   └── WeatherStation (L3, P2)
├── Cargo (L2, P2)
│   ├── DangerousGoods (L3, P2)
│   ├── BulkCargo (L3, P2)
│   └── ContainerCargo (L3, P2)
├── TestFacility (L2, P0)
│   ├── TowingTank (L3, P1)
│   ├── OceanEngineeringBasin (L3, P1)
│   ├── IceTank (L3, P1)
│   ├── DeepOceanBasin (L3, P1)
│   ├── CavitationTunnel (L3, P1)
│   │   ├── LargeCavitationTunnel (L4, impl)
│   │   ├── MediumCavitationTunnel (L4, impl)
│   │   └── HighSpeedCavitationTunnel (L4, impl)
│   ├── WaveEnergyTestSite (L3, P1)
│   ├── HyperbaricChamber (L3, P1)
│   └── BridgeSimulator (L3, P1)
└── ModelShip (L2, P0)

SpatialEntity (abstract, L1)
├── SeaArea (L2, P0)
│   ├── EEZ (L3, P2)
│   ├── TerritorialSea (L3, P2)
│   └── CoastalRegion (L3, P2)
├── GeoPoint (L2, P0)
└── OceanEnvironment (L2, P2)

TemporalEntity (abstract, L1)
├── Voyage (L2, P0)
│   ├── VoyageEvent (L3, P0)
│   ├── TrackSegment (L3, P0)
│   └── PortCall (L3, P1)
├── MaritimeEvent (L2, P1)
│   └── Incident (L3, P1)
│       ├── Collision (L4, P1)
│       ├── Grounding (L4, P1)
│       ├── Pollution (L4, P1)
│       ├── Distress (L4, P1)
│       └── IllegalFishing (L4, P2)
├── Activity (L2, P1)
│   ├── Loading (L3, P2)
│   ├── Unloading (L3, P2)
│   ├── Bunkering (L3, P2)
│   ├── Anchoring (L3, P2)
│   └── Loitering (L3, P2)
├── WeatherCondition (L2, P0)
├── Experiment (L2, P0)
│   ├── TestScenario (L3, P0)
│   └── TestCondition (L3, P0)
├── ExperimentalDataset (L2, P0)
└── AISRecord (L2, P0)

InformationEntity (abstract, L1)
├── Regulation (L2, P0)
│   ├── COLREG (L3, P1)
│   ├── SOLAS (L3, P1)
│   ├── MARPOL (L3, P1)
│   └── IMDGCode (L3, P1)
├── Document (L2, P0)
│   ├── AccidentReport (L3, P1)
│   ├── InspectionReport (L3, P1)
│   ├── NavigationalWarning (L3, P1)
│   └── CargoManifest (L3, P2)
├── DataSource (L2, P1)
│   ├── APIEndpoint (L3, P1)
│   ├── StreamSource (L3, P1)
│   └── FileSource (L3, P1)
├── PlatformResource (abstract, L2)
│   ├── Workflow (L3, P0)
│   │   ├── WorkflowNode (L4, P0)
│   │   └── WorkflowExecution (L4, P2)
│   ├── AIModel (L3, P0)
│   ├── DataPipeline (L3, P2)
│   ├── MCPTool (L3, P2)
│   └── MCPResource (L3, P2)
└── Service (L2, P2)
    ├── QueryService (L3, P2)
    ├── AnalysisService (L3, P2)
    ├── AlertService (L3, P2)
    └── PredictionService (L3, P2)

ObservationEntity (abstract, L1)
├── Observation (L2, P2)
│   ├── SARObservation (L3, P2)
│   ├── OpticalObservation (L3, P2)
│   ├── CCTVObservation (L3, P2)
│   ├── AISObservation (L3, P2)
│   ├── RadarObservation (L3, P2)
│   └── WeatherObservation (L3, P2)
├── SensorReading (L2, P0)
├── MultimodalData (abstract, L2)
│   ├── AISData (L3, P1)
│   ├── VHFRecord (L3, P1)
│   ├── CCTVRecord (L3, P1)
│   ├── SatelliteImage (L3, P1)
│   ├── RadarImage (L3, P1)
│   ├── MaritimeChart (L3, P1)
│   └── VideoClip (L3, P1)
├── MeasurementRecord (L2, P0)
│   └── Measurement (L3, impl)
│       ├── Resistance (L4, impl)
│       ├── Propulsion (L4, impl)
│       ├── Maneuvering (L4, impl)
│       ├── Seakeeping (L4, impl)
│       ├── IcePerformance (L4, impl)
│       └── StructuralResponse (L4, impl)
└── MultimodalRepresentation (abstract, L2)
    ├── VisualEmbedding (L3, P2)
    ├── TrajectoryEmbedding (L3, P2)
    ├── TextEmbedding (L3, P2)
    └── FusedEmbedding (L3, P2)

AgentEntity (abstract, L1)
├── Organization (L2, P0)
│   ├── GovernmentAgency (L3, P2)
│   ├── ShippingCompany (L3, P2)
│   ├── ResearchInstitute (L3, P2)
│   └── ClassificationSociety (L3, P2)
├── Person (L2, P2)
│   ├── CrewMember (L3, P2)
│   └── Inspector (L3, P2)
├── VTSOperator (L2, P1)
├── AIAgent (L2, P2)
└── AccessControl (abstract, L2)
    ├── User (L3, P2)
    ├── Role (L3, P2)
    ├── DataClass (L3, P2)
    └── Permission (L3, P2)
```

### Level별 엔티티 수

| Level | 수량 | 설명 |
|-------|------|------|
| L1 | 6 | 추상 루트 (PhysicalEntity ~ AgentEntity) |
| L2 | 33 | 핵심 도메인 클래스 + 추상 그룹 5개 |
| L3 | 81 | 하위 타입 (P0~P2 혼합) |
| L4 | 17 | 세부 특화 (CavitationTunnel 3종 + Incident 5종 + Measurement 6종 + Workflow 2종 + WorkflowNode 1종) |
| **합계** | **147** | 기존 136개 + 계층 전용 추상 11개 (**=** Step 3 129 엔티티 + 구현 전용 10 + 계층 전용 추상 11) |

> **참고:** Step 3의 129개 P0/P1/P2 엔티티에 구현 전용(impl) 엔티티 10개(LargeCavitationTunnel, MediumCavitationTunnel, HighSpeedCavitationTunnel, Measurement, Resistance, Propulsion, Maneuvering, Seakeeping, IcePerformance, StructuralResponse)와 계층 전용 추상 11개(6 L1 + 5 L2)가 추가되어 ENTITY_LABELS 136개가 된다. ABSTRACT_TYPES 집합은 12개이며, 이 중 Observation은 ENTITY_LABELS에 포함(136 내)되나 직접 인스턴스화하지 않는 추상 타입이다.

---

## 4.3 URN 식별 체계

전역 고유 식별자(URN)를 도입하여 모든 KG 노드를 일관되게 참조할 수 있도록 한다.

### 형식

```
urn:kriso:kg:{l1}:{leaf_type}:{id}
```

| 구성 요소 | 설명 | 예시 |
|----------|------|------|
| `kriso` | 네임스페이스 발행 기관 | 고정값 |
| `kg` | Knowledge Graph 표시 | 고정값 |
| `{l1}` | L1 루트 약어 | `physical`, `spatial`, `temporal`, `info`, `obs`, `agent` |
| `{leaf_type}` | 최하위 엔티티명 (소문자) | `vessel`, `cargoship`, `collision` |
| `{id}` | 도메인 식별자 | MMSI, UNLOCODE, UUID 등 |

### Level별 예시

| Level | 엔티티 | URN 예시 |
|-------|--------|---------|
| L2 | Vessel | `urn:kriso:kg:physical:vessel:440123456` |
| L2 | Port | `urn:kriso:kg:physical:port:KRPUS` |
| L2 | SeaArea | `urn:kriso:kg:spatial:seaarea:KR-VTS-BUSAN` |
| L2 | Voyage | `urn:kriso:kg:temporal:voyage:VOY-2026-001234` |
| L2 | Organization | `urn:kriso:kg:agent:organization:KRISO` |
| L2 | Regulation | `urn:kriso:kg:info:regulation:COLREGS-1972` |
| L3 | CargoShip | `urn:kriso:kg:physical:cargoship:440987654` |
| L3 | TowingTank | `urn:kriso:kg:physical:towingtank:KRISO-TT-001` |
| L3 | Collision | `urn:kriso:kg:temporal:collision:INC-2026-0042` |
| L3 | COLREG | `urn:kriso:kg:info:colreg:COLREGS-1972-R15` |
| L3 | AISData | `urn:kriso:kg:obs:aisdata:BATCH-440123456-1680000000` |
| L4 | LargeCavitationTunnel | `urn:kriso:kg:physical:largecavitationtunnel:KRISO-LCT-001` |
| L4 | Resistance | `urn:kriso:kg:obs:resistance:MEAS-2026-RES-001` |

### 도메인별 ID 형식

| 엔티티 그룹 | ID 소스 | 형식 | 예시 |
|------------|---------|------|------|
| Vessel | MMSI | 9자리 숫자 | `440123456` |
| Port | UNLOCODE | 5자 알파벳 (CC+LLL) | `KRPUS` |
| SeaArea | 커스텀 | `{국가}-{타입}-{이름}` | `KR-VTS-BUSAN` |
| Voyage | 순번 | `VOY-{yyyy}-{seq:06d}` | `VOY-2026-001234` |
| Incident | 순번 | `INC-{yyyy}-{seq:04d}` | `INC-2026-0042` |
| TestFacility | KRISO 내부 | `KRISO-{약어}-{seq:03d}` | `KRISO-TT-001` |
| Experiment | 프로젝트 코드 | `EXP-{projectCode}-{seq:04d}` | `EXP-HULL-0001` |
| AISRecord | 복합 | `AIS-{mmsi}-{timestamp_epoch}` | `AIS-440123456-1680000000` |
| MeasurementRecord | 순번 | `MEAS-{yyyy}-{타입}-{seq:03d}` | `MEAS-2026-RES-001` |
| Document | 순번 | `DOC-{docType}-{yyyy}-{seq:04d}` | `DOC-ACC-2026-0001` |
| Organization | 슬러그 | 기관명 슬러그 | `KRISO` |
| User | Keycloak | Keycloak sub (UUID) | `550e8400-e29b-41d4-a716-446655440000` |

---

## 4.4 Neo4j 멀티레이블 매핑 전략

### 레이블 스태킹 규칙

모든 노드는 계층의 **모든 상위 레이블**을 포함하며, KG 프로젝트 레이블이 추가된다. 이를 통해 어떤 수준에서든 다형성 질의가 가능하다.

**패턴:** `:{KG_Project}:{L1}:{L2}:...:{Leaf}`

### 매핑 예시

| 엔티티 | Neo4j 레이블 |
|--------|-------------|
| Vessel (L2) | `:KG_DevKG:PhysicalEntity:Vessel` |
| CargoShip (L3) | `:KG_DevKG:PhysicalEntity:Vessel:CargoShip` |
| Berth (L3) | `:KG_DevKG:PhysicalEntity:PortInfrastructure:Berth` |
| TowingTank (L3) | `:KG_DevKG:PhysicalEntity:TestFacility:TowingTank` |
| LargeCavitationTunnel (L4) | `:KG_DevKG:PhysicalEntity:TestFacility:CavitationTunnel:LargeCavitationTunnel` |
| SeaArea (L2) | `:KG_DevKG:SpatialEntity:SeaArea` |
| EEZ (L3) | `:KG_DevKG:SpatialEntity:SeaArea:EEZ` |
| Voyage (L2) | `:KG_DevKG:TemporalEntity:Voyage` |
| VoyageEvent (L3) | `:KG_DevKG:TemporalEntity:Voyage:VoyageEvent` |
| Collision (L4) | `:KG_DevKG:TemporalEntity:MaritimeEvent:Incident:Collision` |
| AISRecord (L2) | `:KG_DevKG:TemporalEntity:AISRecord` |
| COLREG (L3) | `:KG_DevKG:InformationEntity:Regulation:COLREG` |
| AccidentReport (L3) | `:KG_DevKG:InformationEntity:Document:AccidentReport` |
| WorkflowNode (L4) | `:KG_DevKG:InformationEntity:PlatformResource:Workflow:WorkflowNode` |
| SensorReading (L2) | `:KG_DevKG:ObservationEntity:SensorReading` |
| AISData (L3) | `:KG_DevKG:ObservationEntity:MultimodalData:AISData` |
| Resistance (L4) | `:KG_DevKG:ObservationEntity:MeasurementRecord:Measurement:Resistance` |
| VisualEmbedding (L3) | `:KG_DevKG:ObservationEntity:MultimodalRepresentation:VisualEmbedding` |
| VTSOperator (L2) | `:KG_DevKG:AgentEntity:VTSOperator` |
| User (L3) | `:KG_DevKG:AgentEntity:AccessControl:User` |

### 다형성 질의 (Polymorphic Query) 패턴

```cypher
-- L1: 모든 물리 개체 (Vessel, Port, Sensor, TestFacility 등 전부)
MATCH (n:PhysicalEntity:KG_DevKG)
RETURN labels(n), count(*)

-- L2: 모든 선박 (CargoShip, Tanker, PassengerShip 등 포함)
MATCH (v:Vessel:KG_DevKG)
RETURN v

-- L3: 화물선만
MATCH (cs:CargoShip:KG_DevKG)
RETURN cs

-- L1: 모든 관측 (SensorReading, AISRecord, MeasurementRecord 등)
MATCH (o:ObservationEntity:KG_DevKG)
RETURN o

-- L3: 모든 사고 (Collision, Grounding, Pollution, Distress, IllegalFishing)
MATCH (i:Incident:KG_DevKG)
RETURN i

-- L2: 모든 멀티모달 데이터 (AISData, VHFRecord, CCTVRecord 등)
MATCH (md:MultimodalData:KG_DevKG)
RETURN md

-- L1+L2: 모든 정보 엔티티 중 플랫폼 리소스만
MATCH (pr:PlatformResource:KG_DevKG)
RETURN pr
```

### 인덱스 전략

```cypher
-- L1 레이블 인덱스 (광범위 질의)
CREATE INDEX idx_physical_name IF NOT EXISTS
  FOR (n:PhysicalEntity) ON (n.name)
CREATE INDEX idx_temporal_start IF NOT EXISTS
  FOR (n:TemporalEntity) ON (n.startTime)
CREATE INDEX idx_obs_timestamp IF NOT EXISTS
  FOR (n:ObservationEntity) ON (n.timestamp)
CREATE INDEX idx_info_title IF NOT EXISTS
  FOR (n:InformationEntity) ON (n.title)
CREATE INDEX idx_agent_name IF NOT EXISTS
  FOR (n:AgentEntity) ON (n.name)

-- L2 다형성 인덱스 (가장 빈번한 질의 수준)
CREATE INDEX idx_vessel_mmsi IF NOT EXISTS
  FOR (n:Vessel) ON (n.mmsi)
CREATE INDEX idx_port_unlocode IF NOT EXISTS
  FOR (n:Port) ON (n.unlocode)
CREATE INDEX idx_voyage_id IF NOT EXISTS
  FOR (n:Voyage) ON (n.voyageId)
CREATE INDEX idx_experiment_id IF NOT EXISTS
  FOR (n:Experiment) ON (n.experimentId)
CREATE INDEX idx_testfacility_id IF NOT EXISTS
  FOR (n:TestFacility) ON (n.facilityId)

-- URN 유니크 인덱스 (전역)
CREATE CONSTRAINT urn_unique IF NOT EXISTS
  FOR (n:KG_DevKG) REQUIRE n._urn IS UNIQUE
```

---

## 4.5 속성 상속 규칙

### 상속 모델

하위 클래스는 상위 클래스의 모든 속성을 **암묵적으로 상속**한다. Neo4j는 스키마리스 속성 모델이므로 실제 상속은 애플리케이션 레이어(`core/kg/ontology/core.py`의 `parent_type` 필드)에서 관리한다.

| 규칙 | 설명 |
|------|------|
| **상속** | 하위 클래스의 노드에 상위 속성이 존재할 수 있음 |
| **추가만 허용** | 하위 클래스는 새 속성을 추가할 수 있음 |
| **오버라이드 금지** | 동일 속성명이 부모/자식에 정의되면 타입이 반드시 일치 |
| **필수 속성 전파** | 상위의 필수 속성은 하위에서도 필수 |

### L1 루트 공통 속성

모든 노드는 L1 루트에 따라 다음 속성을 가진다.

| L1 루트 | 상속 속성 | 타입 | 설명 |
|---------|----------|------|------|
| **공통 (전체)** | `_urn` | STRING | URN 식별자 |
| **공통 (전체)** | `_kg_project` | STRING | 프로젝트 네임스페이스 |
| **공통 (전체)** | `createdAt` | DATETIME | 생성 시각 |
| **공통 (전체)** | `updatedAt` | DATETIME | 수정 시각 |
| PhysicalEntity | `name` | STRING | 이름 |
| PhysicalEntity | `location` | POINT | 위치 좌표 |
| SpatialEntity | `name` | STRING | 지역/좌표명 |
| SpatialEntity | `bounds` | STRING | 경계 (WKT 또는 GeoJSON) |
| TemporalEntity | `startTime` | DATETIME | 시작 시각 |
| TemporalEntity | `endTime` | DATETIME | 종료 시각 |
| TemporalEntity | `status` | STRING | 생명주기 상태 |
| InformationEntity | `title` | STRING | 문서/리소스 제목 |
| InformationEntity | `version` | STRING | 버전 식별자 |
| ObservationEntity | `timestamp` | DATETIME | 관측 시각 |
| ObservationEntity | `source` | STRING | 데이터 소스 식별자 |
| AgentEntity | `name` | STRING | 행위자 이름 |
| AgentEntity | `status` | STRING | 활성/비활성 |

### 상속 예시

| 엔티티 | 경로 | 상속받는 속성 | 자체 속성 (일부) |
|--------|------|-------------|-----------------|
| CargoShip | Physical > Vessel > CargoShip | `_urn`, `_kg_project`, `createdAt`, `updatedAt`, `name`, `location`, `mmsi`, `vesselType` ... | `cargoCapacity` |
| Collision | Temporal > MaritimeEvent > Incident > Collision | `_urn`, `_kg_project`, `createdAt`, `updatedAt`, `startTime`, `endTime`, `status`, `incidentId`, `severity` ... | `collisionType`, `impactAngle` |
| Resistance | Observation > MeasurementRecord > Measurement > Resistance | `_urn`, `_kg_project`, `createdAt`, `updatedAt`, `timestamp`, `source`, `recordId`, `measurementType` ... | `resistanceCoefficient`, `froudeNumber` |

> 상세 속성 정의는 **Step 5: 속성 정의**에서 엔티티별로 전체 수행

---

## 4.6 Step 4 검증 CQ (S4-CQ1~3)

### S4-CQ1: IS_A 계층이 다형성 CQ 필터링을 지원하는가?

**질문:** "모든 선박"(하위 타입 포함)과 "화물선만"을 동일 레이블 패턴으로 질의할 수 있는가?

```cypher
-- S4-CQ1a: 다형성 선박 질의 (Vessel + 모든 하위 타입)
MATCH (v:Vessel:KG_DevKG)
RETURN labels(v) AS labelStack, count(*) AS cnt
ORDER BY cnt DESC

-- S4-CQ1b: 특정 하위 타입 질의 (CargoShip만)
MATCH (cs:CargoShip:KG_DevKG)
WHERE NOT cs:Tanker AND NOT cs:PassengerShip
RETURN count(cs) AS cargoShipCount

-- S4-CQ1c: L1 전체 질의 (모든 도메인 엔티티 분류)
MATCH (n:KG_DevKG)
WHERE n:PhysicalEntity OR n:SpatialEntity OR n:TemporalEntity
   OR n:InformationEntity OR n:ObservationEntity OR n:AgentEntity
RETURN
  CASE
    WHEN n:PhysicalEntity THEN 'PhysicalEntity'
    WHEN n:SpatialEntity THEN 'SpatialEntity'
    WHEN n:TemporalEntity THEN 'TemporalEntity'
    WHEN n:InformationEntity THEN 'InformationEntity'
    WHEN n:ObservationEntity THEN 'ObservationEntity'
    WHEN n:AgentEntity THEN 'AgentEntity'
  END AS rootClass,
  count(*) AS cnt
```

**통과 기준:**

| 질의 | 기대 결과 |
|------|----------|
| S4-CQ1a | Vessel, CargoShip, Tanker, PassengerShip 등 모든 하위 타입 포함. `labelStack`에 `:PhysicalEntity:Vessel` 공통 |
| S4-CQ1b | CargoShip 레이블만 있는 노드 수 반환 (Tanker, PassengerShip 제외) |
| S4-CQ1c | 6개 L1 루트별 집계. 모든 KG 노드가 하나의 루트에 귀속 |

---

### S4-CQ2: KRISO 4단계 시험 체인을 계층과 함께 질의할 수 있는가?

**질문:** TestFacility -> TestScenario -> TestCondition -> MeasurementRecord 체인에서 각 노드의 L1 레이블이 정확한가?

```cypher
-- S4-CQ2a: 시험 체인 + 계층 레이블 검증
MATCH (tf:TestFacility:KG_DevKG)-[:HOSTS]->(ts:TestScenario)
      -[:APPLIES]->(tc:TestCondition)-[:PRODUCES]->(mr:MeasurementRecord)
WHERE tf:PhysicalEntity AND ts:TemporalEntity
  AND tc:TemporalEntity AND mr:ObservationEntity
RETURN tf.name, ts.scenarioId, mr.measurementType, labels(mr) AS mrLabels

-- S4-CQ2b: ObservationEntity 다형성 질의에 MeasurementRecord 포함 확인
MATCH (obs:ObservationEntity:KG_DevKG)
WHERE obs:MeasurementRecord OR obs:SensorReading OR obs:AISData
RETURN
  CASE
    WHEN obs:MeasurementRecord THEN 'MeasurementRecord'
    WHEN obs:SensorReading THEN 'SensorReading'
    WHEN obs:AISData THEN 'AISData'
    ELSE 'Other'
  END AS obsType,
  count(*) AS cnt
```

**통과 기준:**

| 질의 | 기대 결과 |
|------|----------|
| S4-CQ2a | MeasurementRecord가 `:ObservationEntity` 레이블 보유. TestFacility는 `:PhysicalEntity`, TestScenario/TestCondition은 `:TemporalEntity` |
| S4-CQ2b | 관측 집계에 MeasurementRecord 포함. 3가지 이상의 관측 타입 반환 |

---

### S4-CQ3: URN 식별 체계가 고유하고 역방향 검색 가능한가?

```cypher
-- S4-CQ3a: URN 정방향 검색
MATCH (n:KG_DevKG {_urn: 'urn:kriso:kg:physical:vessel:440123456'})
RETURN n, labels(n)

-- S4-CQ3b: URN 고유성 검증 (중복 0이어야 함)
MATCH (n:KG_DevKG)
WHERE n._urn IS NOT NULL
WITH n._urn AS urn, count(*) AS cnt
WHERE cnt > 1
RETURN urn, cnt

-- S4-CQ3c: URN 완전성 검증 (누락 0이어야 함)
MATCH (n:KG_DevKG)
WHERE n._urn IS NULL
RETURN labels(n) AS missingUrnLabels, count(*) AS cnt
```

**통과 기준:**

| 질의 | 기대 결과 |
|------|----------|
| S4-CQ3a | 정확히 1개 노드 반환. `labels(n)`에 `:PhysicalEntity:Vessel` 포함 |
| S4-CQ3b | 0행 (중복 URN 없음) |
| S4-CQ3c | 0행 (URN 누락 노드 없음) |

---

## 4.7 계층 배치 결정 기록

Step 4 진행 중 확정된 설계 결정 사항. (Step 3 D1~D5 이후 D6~D15)

| # | 결정 사항 | 선택 | 근거 |
|---|---------|------|------|
| D6 | L1 루트 수 | **6개 추상 루트** | 6개 근본적 온톨로지 범주. 각 레이블로 다형성 질의 지원. W3C BFO(Basic Formal Ontology) 상위 분류 참고 |
| D7 | L2 추상 그룹 | **5개** (PortInfrastructure, PlatformResource, MultimodalData, MultimodalRepresentation, AccessControl) | 의미적으로 관련된 엔티티의 논리적 그룹핑. L2 수준 관리 용이 |
| D8 | MeasurementRecord 배치 | **ObservationEntity** 하위 | 시간 이벤트가 아닌 계측 데이터. W3C SSN/SOSA의 `sosa:Result` 패턴에 부합 |
| D9 | 레이블 매핑 방식 | **전체 상위 레이블 스태킹** | 모든 수준에서 다형성 질의 가능. Neo4j 인덱스를 레이블별로 활용 가능 |
| D10 | 속성 상속 | **추가만 허용, 오버라이드 금지** | 타입 충돌 방지. `parent_type` 시맨틱스와 일치. 스키마 검증 단순화 |
| D11 | URN 체계 | `urn:kriso:kg:{l1}:{leaf}:{id}` | 전역 고유, 사람 판독 가능, 역방향 검색 가능. IETF RFC 8141 준수 |
| D12 | 구현 전용 엔티티 | **L4로 포함** (LargeCavitationTunnel, Resistance 등) | `maritime_ontology.py`에 속성 정의 존재. 제외 시 코드-온톨로지 불일치 발생 |
| D13 | MaritimeEvent 배치 | **TemporalEntity** 하위 | 이벤트는 시간적 개체. `maritime_ontology.py`의 InformationEntity 그룹 주석은 Step 4 계층으로 대체 |
| D14 | AISRecord 배치 | **TemporalEntity** 하위 | 시간 순서 위치 보고. ObservationEntity의 AISObservation과는 별도 엔티티 (P0 vs P2) |
| D15 | IS_A 관계 구현 방식 | **멀티레이블만 사용** | IS_A 관계를 별도 생성하지 않음. 레이블 스태킹으로 다형성 질의 충분. 저장 공간 및 질의 성능 최적화 |

---

## 다음 단계

**Step 5: 속성 정의** (Attribute Definition)
- L1 루트 공통 속성을 기반으로 각 엔티티별 상세 속성 정의
- Domain/Range 타입 지정, 필수(required)/선택(optional) 구분
- Cypher 명명 규칙 (camelCase) 적용
- 인덱스 대상 속성 식별
- `core/kg/ontology/core.py`의 `PropertyDefinition` 매핑

---

## 참조

| 문서 | 내용 |
|------|------|
| `domains/maritime/ontology/maritime_ontology.py` | 136개 엔티티 + 93개 관계 + PROPERTY_DEFINITIONS |
| `core/kg/ontology/core.py` | ObjectTypeDefinition (`parent_type`, `abstract` 필드) |
| Step 1: 목적 정의 (`step1_purpose_definition.md`) | CQ1-CQ5 정의, 도메인 범위 |
| Step 2: 재사용 분석 (`step2_reuse_evaluation.md`) | 10개 온톨로지/표준 분석 결과 |
| Step 3: 핵심 용어 열거 (`step3_key_term_enumeration.md`) | 129개 엔티티 + 108개 관계 (3계층) |
| KRISO 제안서 S14-S19 | L1-L5 계층 참조 |
