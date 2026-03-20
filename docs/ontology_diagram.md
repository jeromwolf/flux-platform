# 해사 지식그래프 온톨로지 다이어그램

## 개요

해사(Maritime) 도메인 지식그래프는 **103개 엔티티**와 **45개 이상의 관계타입**으로 구성된 포괄적인 해양 정보 모델입니다.

### 11개 엔티티 그룹

1. **PhysicalEntity** (18개): 선박, 항만, 항로, 화물, 센서 등 물리적 인프라
2. **SpatialEntity** (5개): 해역, EEZ, 영해, 지역, 지점 등 공간정보
3. **TemporalEntity** (18개): 항해, 사건, 활동, 기상 등 시간기반 데이터
4. **InformationEntity** (18개): 규정, 문서, 데이터소스, 서비스 등 정보자산
5. **Observation** (6개): SAR, 광학, CCTV, AIS, 레이더, 기상 관측
6. **Agent** (8개): 기관, 회사, 연구소, 개인 등 행위자
7. **PlatformResource** (8개): 워크플로우, AI모델, 데이터파이프라인, MCP
8. **MultimodalData** (6개): AIS, 위성영상, 레이더, 센서, 해도, 영상
9. **MultimodalRepresentation** (4개): 임베딩 벡터 (영상, 궤적, 텍스트, 융합)
10. **KRISO** (20개): 실험, 시설, 측정 데이터 (해양과학 전용)
11. **RBAC** (4개): 사용자, 역할, 데이터분류, 권한 (접근제어)

---

## 1. 고수준 개요 - 11개 그룹 관계도

```mermaid
graph LR
    PE["<b>PhysicalEntity</b><br/>선박·항만·센서<br/>(18)"]
    SE["<b>SpatialEntity</b><br/>해역·EEZ·지점<br/>(5)"]
    TE["<b>TemporalEntity</b><br/>항해·사건·활동<br/>(18)"]
    IE["<b>InformationEntity</b><br/>규정·문서·서비스<br/>(18)"]
    OBS["<b>Observation</b><br/>위성·CCTV·AIS<br/>(6)"]
    AGT["<b>Agent</b><br/>기관·회사·개인<br/>(8)"]
    PR["<b>PlatformResource</b><br/>워크플로우·AI모델<br/>(8)"]
    MD["<b>MultimodalData</b><br/>AIS·위성·비디오<br/>(6)"]
    MR["<b>MultimodalRep</b><br/>임베딩 벡터<br/>(4)"]
    KR["<b>KRISO</b><br/>실험·시설·측정<br/>(20)"]
    RB["<b>RBAC</b><br/>사용자·역할<br/>(4)"]

    PE -->|위치| SE
    PE -->|화물 운송| TE
    TE -->|규정 준수| IE
    PE -->|센서 데이터| OBS
    OBS -->|임베딩| MR
    OBS -->|저장| MD
    MD -->|융합| MR
    PE -->|관리| AGT
    IE -->|파이프라인| PR
    PR -->|실행| TE
    KR -->|실험| PE
    AGT -->|접근| RB
    PR -->|배포| RB

    style PE fill:#e8f4f8
    style SE fill:#e8f8e8
    style TE fill:#f8f0e8
    style IE fill:#f0e8f8
    style OBS fill:#f8e8e8
    style AGT fill:#f8f8e8
    style PR fill:#e8f0f8
    style MD fill:#f0f8e8
    style MR fill:#f8e8f0
    style KR fill:#e8e8f8
    style RB fill:#f8f0e8
```

---

## 2. PhysicalEntity 그룹 (물리적 인프라)

18개 엔티티: 선박 6종, 항만 4종, 수로 3종, 화물 3종, 센서 5종

```mermaid
graph TD
    V["Vessel<br/>선박"]
    V --> CS["CargoShip<br/>화물선"]
    V --> TK["Tanker<br/>유조선"]
    V --> FV["FishingVessel<br/>어선"]
    V --> PS["PassengerShip<br/>여객선"]
    V --> NV["NavalVessel<br/>군함"]
    V --> AV["AutonomousVessel<br/>무인선"]

    P["Port<br/>항만"]
    P --> TP["TradePort<br/>무역항"]
    P --> CP["CoastalPort<br/>연안항"]
    P --> FP["FishingPort<br/>어항"]
    P --> PF["PortFacility<br/>항만시설"]

    W["Waterway<br/>수로"]
    W --> TSS["TSS<br/>분리통항방식"]
    W --> CH["Channel<br/>항로"]

    C["Cargo<br/>화물"]
    C --> DG["DangerousGoods<br/>위험물"]
    C --> BC["BulkCargo<br/>산적화물"]
    C --> CC["ContainerCargo<br/>컨테이너"]

    S["Sensor<br/>센서"]
    S --> AIS["AISTransceiver<br/>AIS"]
    S --> RD["Radar<br/>레이더"]
    S --> CCTV["CCTVCamera<br/>CCTV"]
    S --> WS["WeatherStation<br/>기상관측"]

    B["Berth<br/>선석"]
    A["Anchorage<br/>투묘지"]

    V -->|DOCKED_AT| B
    V -->|ANCHORED_AT| A
    V -->|CARRIES| C
    V -->|LOCATED_AT| W
    P -->|HAS_FACILITY| PF
    P -->|CONNECTED_VIA| W
    S -->|PRODUCES| OBS["Observation"]

    style V fill:#e8f4f8
    style CS fill:#d0e8f0
    style TK fill:#d0e8f0
    style FV fill:#d0e8f0
    style PS fill:#d0e8f0
    style NV fill:#d0e8f0
    style AV fill:#d0e8f0
    style P fill:#c0e0e8
    style TP fill:#b0d8e0
    style CP fill:#b0d8e0
    style FP fill:#b0d8e0
    style PF fill:#b0d8e0
    style W fill:#a0d0d8
    style TSS fill:#90c8d0
    style CH fill:#90c8d0
    style C fill:#d0e0f0
    style DG fill:#b8d0e8
    style BC fill:#b8d0e8
    style CC fill:#b8d0e8
    style S fill:#e0d0f0
    style AIS fill:#d0c0e8
    style RD fill:#d0c0e8
    style CCTV fill:#d0c0e8
    style WS fill:#d0c0e8
    style B fill:#a0c0d8
    style A fill:#a0c0d8
```

---

## 3. TemporalEntity 그룹 (시간기반 데이터)

18개 엔티티: 항해 2종, 사건 5종, 활동 4종, 기상 1종, 기타 6종

```mermaid
graph TD
    VYG["Voyage<br/>항해"]
    VYG --> PC["PortCall<br/>입항"]
    VYG --> TS["TrackSegment<br/>궤적"]

    INC["Incident<br/>사건"]
    INC --> COL["Collision<br/>충돌"]
    INC --> GND["Grounding<br/>좌초"]
    INC --> POL["Pollution<br/>오염"]
    INC --> DST["Distress<br/>조난"]
    INC --> IF["IllegalFishing<br/>불법어업"]

    ACT["Activity<br/>활동"]
    ACT --> LD["Loading<br/>적하"]
    ACT --> ULD["Unloading<br/>하역"]
    ACT --> BNK["Bunkering<br/>연료주유"]
    ACT --> ANC["Anchoring<br/>투묘"]

    WC["WeatherCondition<br/>기상"]
    LTR["Loitering<br/>배회"]

    V["Vessel"]
    P["Port"]
    SA["SeaArea"]

    V -->|ON_VOYAGE| VYG
    VYG -->|FROM_PORT| P
    VYG -->|TO_PORT| P
    VYG -->|CONSISTS_OF| TS
    V -->|PERFORMS| ACT
    INC -->|INVOLVES| V
    INC -->|OCCURRED_AT| SA
    WC -->|AFFECTS| SA
    INC -->|CAUSED_BY| WC

    style VYG fill:#f8f0e8
    style PC fill:#f0e8d8
    style TS fill:#f0e8d8
    style INC fill:#f8d0d0
    style COL fill:#f0b8b8
    style GND fill:#f0b8b8
    style POL fill:#f0b8b8
    style DST fill:#f0b8b8
    style IF fill:#f0b8b8
    style ACT fill:#f8e8d0
    style LD fill:#f0d8b8
    style ULD fill:#f0d8b8
    style BNK fill:#f0d8b8
    style ANC fill:#f0d8b8
    style WC fill:#f0e0e8
    style LTR fill:#f0e0e8
```

---

## 4. KRISO 그룹 (해양과학 실험)

20개 엔티티: 실험 1종, 시설 10종, 측정 6종, 기타 3종

```mermaid
graph TD
    EXP["Experiment<br/>실험"]

    TF["TestFacility<br/>시험시설"]
    TF --> TT["TowingTank<br/>예인수로"]
    TF --> OEB["OceanEngBasin<br/>해양공학수조"]
    TF --> IT["IceTank<br/>빙해수조"]
    TF --> DOB["DeepOceanBasin<br/>심해수조"]
    TF --> WETS["WaveEnergySite<br/>파력발전"]
    TF --> HC["HyperbaricChamber<br/>고압실"]
    TF --> CT["CavitationTunnel<br/>캐비테이션터널"]
    CT --> LCT["LargeCavTunnel<br/>대형"]
    CT --> MCT["MediumCavTunnel<br/>중형"]
    CT --> HCT["HighSpeedCavTunnel<br/>고속"]
    TF --> BS["BridgeSimulator<br/>선박운항시뮬레이터"]

    MS["ModelShip<br/>모형선"]
    TC["TestCondition<br/>시험조건"]
    ED["ExperimentalDataset<br/>실험데이터"]

    MEA["Measurement<br/>측정"]
    MEA --> RES["Resistance<br/>저항"]
    MEA --> PROP["Propulsion<br/>추진"]
    MEA --> MAN["Maneuvering<br/>조종"]
    MEA --> SEA["Seakeeping<br/>내항성"]
    MEA --> ICE["IcePerformance<br/>빙해성능"]
    MEA --> SR["StructuralResp<br/>구조응답"]

    V["Vessel"]

    EXP -->|CONDUCTED_AT| TF
    EXP -->|TESTED| MS
    EXP -->|PRODUCED| ED
    EXP -->|UNDER_CONDITION| TC
    MS -->|MODEL_OF| V
    ED -->|HAS_RAW_DATA| MEA
    EXP -->|RECORDED_VIDEO| VC["VideoClip"]
    EXP -->|MEASURED_DATA| SR2["SensorReading"]

    style EXP fill:#e8e8f8
    style TF fill:#d8d8f0
    style TT fill:#c0c0e8
    style OEB fill:#c0c0e8
    style IT fill:#c0c0e8
    style DOB fill:#c0c0e8
    style WETS fill:#c0c0e8
    style HC fill:#c0c0e8
    style CT fill:#c0c0e8
    style LCT fill:#b0b0e0
    style MCT fill:#b0b0e0
    style HCT fill:#b0b0e0
    style BS fill:#c0c0e8
    style MS fill:#d0d0e8
    style TC fill:#d0d0e8
    style ED fill:#d0d0e8
    style MEA fill:#c8c8f0
    style RES fill:#b8b8e8
    style PROP fill:#b8b8e8
    style MAN fill:#b8b8e8
    style SEA fill:#b8b8e8
    style ICE fill:#b8b8e8
    style SR fill:#b8b8e8
```

---

## 5. Observation 그룹 (다중모달 관측)

6개 엔티티: 위성 2종, 영상기반 3종, 기상 1종

```mermaid
graph TD
    OBS["Observation<br/>관측"]
    OBS --> SAR["SARObservation<br/>합성개구레이더"]
    OBS --> OPT["OpticalObservation<br/>광학위성"]
    OBS --> CCTV["CCTVObservation<br/>CCTV"]
    OBS --> AIS["AISObservation<br/>AIS위치"]
    OBS --> RAD["RadarObservation<br/>레이더"]
    OBS --> WEA["WeatherObservation<br/>기상"]

    S["Sensor"]
    V["Vessel"]
    T["TrackSegment"]
    G["GeoPoint"]
    EMB["VisualEmbedding<br/>임베딩"]
    MD["MultimodalData<br/>데이터"]

    S -->|PRODUCES| OBS
    OBS -->|DEPICTS| V
    OBS -->|IDENTIFIED| V
    OBS -->|DETECTED| V
    OBS -->|TRACKED| T
    OBS -->|OBSERVED_AT| G
    OBS -->|HAS_EMBEDDING| EMB
    OBS -->|STORED_AT| MD
    OBS -->|MATCHED_WITH| OBS
    OBS -->|SAME_ENTITY| OBS

    style OBS fill:#f8e8e8
    style SAR fill:#f0d0d0
    style OPT fill:#f0d0d0
    style CCTV fill:#f0d0d0
    style AIS fill:#f0d0d0
    style RAD fill:#f0d0d0
    style WEA fill:#f0d0d0
    style EMB fill:#f8e8d8
    style MD fill:#f0d8d0
```

---

## 6. RBAC 그룹 (접근제어)

4개 엔티티: 사용자, 역할, 데이터분류, 권한

```mermaid
graph LR
    U["User<br/>사용자"]
    R["Role<br/>역할"]
    DC["DataClass<br/>데이터분류"]
    P["Permission<br/>권한"]
    ORG["Organization<br/>조직"]

    U -->|HAS_ROLE| R
    U -->|BELONGS_TO| ORG
    R -->|CAN_ACCESS| DC
    R -->|GRANTS| P

    ED["ExperimentalDataset"]
    ED -->|CLASSIFIED_AS| DC

    style U fill:#f8f0e8
    style R fill:#f0e8d8
    style DC fill:#e8f0d8
    style P fill:#d8e8d0
    style ORG fill:#e0f0d0
    style ED fill:#d0e8d8
```

---

## 7. InformationEntity 그룹 (규정 및 서비스)

18개 엔티티: 규정 4종, 문서 4종, 데이터소스 4종, 서비스 4종

```mermaid
graph TD
    REG["Regulation<br/>규정"]
    REG --> COL["COLREG<br/>해충법"]
    REG --> SOL["SOLAS<br/>해안법"]
    REG --> MAR["MARPOL<br/>해양오염"]
    REG --> IMDG["IMDGCode<br/>위험물"]

    DOC["Document<br/>문서"]
    DOC --> AR["AccidentReport<br/>사건보고"]
    DOC --> IR["InspectionReport<br/>검사보고"]
    DOC --> NW["NavigationalWarning<br/>항행경고"]
    DOC --> CM["CargoManifest<br/>화물명세"]

    DS["DataSource<br/>데이터소스"]
    DS --> API["APIEndpoint<br/>REST API"]
    DS --> SS["StreamSource<br/>스트림"]
    DS --> FS["FileSource<br/>파일"]
    DS --> MCP["(MCP 노드)"]

    SVC["Service<br/>서비스"]
    SVC --> QS["QueryService<br/>쿼리"]
    SVC --> AS["AnalysisService<br/>분석"]
    SVC --> ALS["AlertService<br/>알림"]
    SVC --> PS["PredictionService<br/>예측"]

    V["Vessel"]
    INC["Incident"]
    ORG["Organization"]

    REG -->|APPLIES_TO| V
    REG -->|ENFORCED_BY| ORG
    INC -->|VIOLATED| REG
    DOC -->|DESCRIBES| INC
    DOC -->|ISSUED_BY| ORG
    SVC -->|USES_DATA| DS
    SVC -->|PRODUCES_OUTPUT| DS
    SVC -->|FEEDS| SVC
    SVC -->|GENERATES| DOC

    style REG fill:#f0e8f8
    style COL fill:#e0d8f0
    style SOL fill:#e0d8f0
    style MAR fill:#e0d8f0
    style IMDG fill:#e0d8f0
    style DOC fill:#e8e0f8
    style AR fill:#d8d0f0
    style IR fill:#d8d0f0
    style NW fill:#d8d0f0
    style CM fill:#d8d0f0
    style DS fill:#e0e8f8
    style API fill:#d0d8f0
    style SS fill:#d0d8f0
    style FS fill:#d0d8f0
    style SVC fill:#d8e0f8
    style QS fill:#c8d0f0
    style AS fill:#c8d0f0
    style ALS fill:#c8d0f0
    style PS fill:#c8d0f0
```

---

## 8. PlatformResource 그룹 (플랫폼 자산)

8개 엔티티: 워크플로우 3종, AI자산 2종, 파이프라인 1종, MCP 2종

```mermaid
graph TD
    WF["Workflow<br/>워크플로우"]
    WF --> WN["WorkflowNode<br/>노드"]
    WF --> WE["WorkflowExecution<br/>실행인스턴스"]

    WN -->|CONTAINS_NODE| WN
    WN -->|CONNECTS_TO| WN
    WN -->|USES_MODEL| AM["AIModel<br/>AI모델"]
    WN -->|READS_FROM| DS["DataSource"]
    WN -->|WRITES_TO| DS

    WE -->|EXECUTION_OF| WF

    DP["DataPipeline<br/>파이프라인"]
    DP -->|PIPELINE_READS| DS
    DP -->|PIPELINE_FEEDS| DS

    AG["AIAgent<br/>AI에이전트"]
    AG -->|EXECUTES| WF
    AG -->|MANAGES| DS

    MCPTool["MCPTool<br/>MCP도구"]
    MCPRes["MCPResource<br/>MCP리소스"]
    SVC["Service"]

    SVC -->|EXPOSES_TOOL| MCPTool
    SVC -->|EXPOSES_RESOURCE| MCPRes
    AG -->|INVOKES| MCPTool
    AG -->|ACCESSES| MCPRes

    style WF fill:#e8f0f8
    style WN fill:#d0e0f0
    style WE fill:#d0e0f0
    style DP fill:#d8e8f0
    style AM fill:#c0d8e8
    style AG fill:#c8e0f0
    style MCPTool fill:#b8d0e8
    style MCPRes fill:#b8d0e8
    style SVC fill:#b0c8e0
    style DS fill:#d0d8e0
```

---

## 9. MultimodalData & Representation 그룹

**MultimodalData (6개)**: AIS, 위성영상, 레이더, 센서, 해도, 비디오

**MultimodalRepresentation (4개)**: 영상, 궤적, 텍스트, 융합 임베딩

```mermaid
graph TD
    MD["MultimodalData"]
    MD --> AIS["AISData<br/>AIS데이터"]
    MD --> SAT["SatelliteImage<br/>위성영상"]
    MD --> RAD["RadarImage<br/>레이더영상"]
    MD --> SR["SensorReading<br/>센서데이터"]
    MD --> MC["MaritimeChart<br/>해도"]
    MD --> VC["VideoClip<br/>영상클립"]

    AIS -->|AIS_TRACK_OF| V["Vessel"]
    AIS -->|OBSERVED_IN_AREA| SA["SeaArea"]
    SAT -->|CAPTURED_OVER| SA
    SAT -->|SAT_DEPICTS| P["Port"]
    SAT -->|SAT_DETECTED| V
    RAD -->|RADAR_COVERS| SA
    SR -->|READING_FROM_SENSOR| S["Sensor"]
    SR -->|READING_AT| G["GeoPoint"]
    MC -->|CHART_COVERS| SA
    VC -->|VIDEO_FROM| S
    VC -->|VIDEO_DEPICTS| V

    EMBD["MultimodalRepresentation"]
    EMBD --> VE["VisualEmbedding<br/>영상"]
    EMBD --> TE["TrajectoryEmbedding<br/>궤적"]
    EMBD --> TXE["TextEmbedding<br/>텍스트"]
    EMBD --> FE["FusedEmbedding<br/>융합"]

    FE -->|FUSED_FROM| AIS
    FE -->|FUSED_FROM_IMAGE| SAT
    OBS["Observation"]
    OBS -->|HAS_EMBEDDING| VE

    style MD fill:#f0f8e8
    style AIS fill:#d8f0d0
    style SAT fill:#d8f0d0
    style RAD fill:#d8f0d0
    style SR fill:#d8f0d0
    style MC fill:#d8f0d0
    style VC fill:#d8f0d0
    style EMBD fill:#e8f0d8
    style VE fill:#d0e8c0
    style TE fill:#d0e8c0
    style TXE fill:#d0e8c0
    style FE fill:#d0e8c0
```

---

## 10. SpatialEntity 그룹 (공간정보)

5개 엔티티: 해역, EEZ, 영해, 지역, 지점

```mermaid
graph TD
    SA["SeaArea<br/>해역"]
    SA --> EEZ["EEZ<br/>배타적경제수역"]
    SA --> TS["TerritorialSea<br/>영해"]
    SA --> CR["CoastalRegion<br/>연안지역"]

    GP["GeoPoint<br/>지점"]

    style SA fill:#e8f8e8
    style EEZ fill:#d0f0d0
    style TS fill:#d0f0d0
    style CR fill:#d0f0d0
    style GP fill:#c0e8c0
```

---

## 요약 테이블

| 그룹 | 엔티티 수 | 주요 엔티티 | 설명 |
|------|----------|----------|------|
| **PhysicalEntity** | 18 | Vessel, Port, Waterway, Cargo, Sensor | 선박, 항만, 항로, 화물, 센서 등 물리적 해양 인프라 |
| **SpatialEntity** | 5 | SeaArea, EEZ, TerritorialSea, GeoPoint | 해역, EEZ, 영해, 지점 등 공간좌표 정보 |
| **TemporalEntity** | 18 | Voyage, Incident, Activity, WeatherCondition | 항해, 사건, 활동, 기상 등 시간기반 이벤트 |
| **InformationEntity** | 18 | Regulation, Document, DataSource, Service | 규정(COLREG/SOLAS/MARPOL), 문서, 데이터소스, 서비스 |
| **Observation** | 6 | SARObservation, OpticalObservation, AISObservation, CCTVObservation | SAR, 광학, AIS, CCTV 관측 데이터 |
| **Agent** | 8 | Organization, GovernmentAgency, ShippingCompany, ResearchInstitute, Person | 해양 관련 기관, 회사, 개인 |
| **PlatformResource** | 8 | Workflow, WorkflowNode, AIModel, DataPipeline, AIAgent, MCPTool | 플랫폼 워크플로우, AI모델, 데이터파이프라인, MCP |
| **MultimodalData** | 6 | AISData, SatelliteImage, RadarImage, SensorReading, MaritimeChart, VideoClip | AIS, 위성영상, 레이더, 센서, 해도, 비디오 |
| **MultimodalRepresentation** | 4 | VisualEmbedding, TrajectoryEmbedding, TextEmbedding, FusedEmbedding | 임베딩 벡터 (영상, 궤적, 텍스트, 융합) |
| **KRISO** | 20 | Experiment, TestFacility, TowingTank, Measurement, ModelShip | KRISO 실험, 시설(수로/수조), 측정, 모형선 |
| **RBAC** | 4 | User, Role, DataClass, Permission | 사용자, 역할, 데이터분류, 권한 (접근제어) |
| **TOTAL** | **103** | - | 해사 도메인 포괄적 온톨로지 |

---

## 주요 관계 패턴

### 1. 물리적 위치 관계 (Physical Location)
```
Vessel -[LOCATED_AT]-> SeaArea
Vessel -[DOCKED_AT]-> Berth
Vessel -[ANCHORED_AT]-> Anchorage
Port -[CONNECTED_VIA]-> Waterway
Waterway -[CONNECTS]-> SeaArea
```

### 2. 운영 항해 관계 (Operational Voyage)
```
Vessel -[ON_VOYAGE]-> Voyage
Voyage -[FROM_PORT]-> Port
Voyage -[TO_PORT]-> Port
Voyage -[CONSISTS_OF]-> TrackSegment
Vessel -[CARRIES]-> Cargo
Vessel -[PERFORMS]-> Activity
```

### 3. 관측 및 감지 관계 (Observation & Detection)
```
Sensor -[PRODUCES]-> Observation
Observation -[DEPICTS|IDENTIFIED|DETECTED]-> Vessel
Observation -[TRACKED]-> TrackSegment
Observation -[HAS_EMBEDDING]-> VisualEmbedding
Observation -[MATCHED_WITH]-> Observation (크로스모달)
```

### 4. 환경 및 사건 관계 (Environmental & Incident)
```
WeatherCondition -[AFFECTS]-> SeaArea
Incident -[CAUSED_BY]-> WeatherCondition
Incident -[INVOLVES]-> Vessel
Incident -[OCCURRED_AT]-> GeoPoint
Incident -[VIOLATED]-> Regulation
```

### 5. KRISO 실험 관계 (KRISO Experiment)
```
Experiment -[CONDUCTED_AT]-> TestFacility
Experiment -[TESTED]-> ModelShip
Experiment -[PRODUCED]-> ExperimentalDataset
Experiment -[UNDER_CONDITION]-> TestCondition
Experiment -[RECORDED_VIDEO|MEASURED_DATA]-> MultimodalData
ExperimentalDataset -[HAS_RAW_DATA]-> Measurement
```

### 6. 플랫폼 서비스 관계 (Platform & Service)
```
Service -[USES_DATA]-> DataSource
Service -[PRODUCES_OUTPUT]-> DataSource
Service -[FEEDS]-> Service (파이프라인)
Service -[EXPOSES_TOOL|EXPOSES_RESOURCE]-> MCP*
AIAgent -[EXECUTES]-> Workflow
Workflow -[CONTAINS_NODE]-> WorkflowNode
WorkflowNode -[CONNECTS_TO]-> WorkflowNode
```

### 7. 접근제어 관계 (RBAC)
```
User -[HAS_ROLE]-> Role
User -[BELONGS_TO]-> Organization
Role -[CAN_ACCESS]-> DataClass
Role -[GRANTS]-> Permission
ExperimentalDataset -[CLASSIFIED_AS]-> DataClass
```

---

## 마지막 수정일: 2026-02-09
