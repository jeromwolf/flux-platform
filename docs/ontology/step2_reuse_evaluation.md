# Step 2: 기존 온톨로지 재사용 분석 (Reuse Evaluation)

> **Stanford 7-Step Ontology Design Methodology** | DevKG 구축
>
> 작성일: 2026-04-03 | 프로젝트: DevKG (`X-KG-Project: DevKG`)

---

## 2.1 재사용 대상 온톨로지 식별

KRISO 해사 KG에 재사용 가능한 기존 온톨로지 4종과 표준 패턴 4종을 식별하고, 각각의 재사용 범위와 방법을 분석한다.

| 온톨로지/표준 | 유형 | 활용 범위 | 재사용 방법 | 우선순위 |
|-------------|------|---------|-----------|---------|
| **IHO S-100** | 해사 표준 | 전자해도, 해역 분류, 수위, 해류 | Feature Catalogue → Node Label/Property 매핑 | **P0** |
| **IMO AIS 메시지** | 해사 표준 | 선박 동적/정적 정보 | Message Type 1/5/18/24 필드 → Vessel Property | **P0** |
| **MAKG** (Maritime Accident KG) | 학술 온톨로지 | 해사 사고 KG 엔티티 비교 | 8개 사고 엔티티 vs KRISO 매핑 | P1 |
| **오재용·김혜진 논문** (멀티모달 해사 데이터) | 학술 논문 (KRISO) | 8종 멀티모달 데이터 + VHF/CCTV 그래프 모델 | 10개 관계 타입 + 아키텍처 패턴 참고 | P1 |
| **Li et al.** (AIS 해상교통 KG) | 학술 논문 | AIS 기반 시간적 KG + 이벤트 탐지 | 선종 코드 매핑, DCPA/TCPA, 이벤트 탐지 알고리즘 | P1 |
| **Kim & Lee** (긴급구조 PIKG) | 학술 논문 | Neo4j LPG 장소 식별자 KG | 시나리오 기반 CQ 설계 패턴, BELONG_TO 계층 | P2 |
| **W3C SSN/SOSA** | 범용 표준 | 센서/관측 패턴 | Sensor → Observation → Result 패턴 차용 | P1 |
| **OGC GeoSPARQL** | 범용 표준 | 공간 쿼리 패턴 | Neo4j `point()` + `point.distance()` 활용 | **P0** |
| **W3C OWL-Time** | 범용 표준 | 시간 표현 패턴 | Neo4j `datetime()` + `duration()` 활용 | **P0** |
| **W3C PROV-O** | 범용 표준 | 데이터 계보/리니지 | `DERIVED_FROM`, `PRODUCED_BY` 관계 패턴 | P1 |

---

## 2.2 IHO S-100 Feature Catalogue → Neo4j 매핑

S-100 Feature Catalogue(FC)는 본질적으로 온톨로지와 유사한 구조를 가진다. Feature Type → Node Label, Attribute → Property, Association → Relationship으로 직접 매핑된다.

### S-100 FC 구성요소 → Property Graph 대응

| S-100 FC 구성요소 | 설명 | Neo4j PG 매핑 | 예시 |
|------------------|------|-------------|------|
| **Feature Type** | 실세계 현상 분류 | Node Label | `(:Light)`, `(:Buoy)` |
| **Information Type** | 메타 정보 유형 | Node Label | `(:Authority)`, `(:Source)` |
| **Simple Attribute** | 단일 값 속성 | Node Property | `{height: 15.0}` |
| **Complex Attribute** | 복합 구조 속성 | 중첩 Property 또는 별도 Node | `featureName = lang + name` |
| **Feature Association** | Feature 간 관계 | Relationship | `-[:COMPONENT_OF]->` |
| **Role** | Association 역할 | Relationship Property | `{role: "parent"}` |
| **Enumeration** | 열거형 값 | `enum_values` | `colour: ["red","green"]` |
| **Spatial Attribute** | 공간 좌표 | `point()` / WKT | `point({lat:35.1, lon:129.0})` |

### KRISO 관련 S-100 Product Specification → KG 매핑

| S-100 PS | 주요 Feature | KG Node Label | 우선순위 | 비고 |
|---------|-------------|-------------|---------|------|
| **S-101** ENC | DepthArea, Anchorage, Fairway, TSS | `SeaArea`, `Anchorage`, `Waterway`, `TSS` | P0 | 공간 베이스맵 |
| **S-104** 수위 | WaterLevel, TidalStation | `SensorReading`, `Sensor` | P2 | 수조 연계 |
| **S-111** 해류 | SurfaceCurrent | `SensorReading` | P2 | HDF5 인코딩 |
| **S-127** 교통관리 | VTSArea, ReportingPoint | `SeaArea`, `GeoPoint` | P1 | VTS 연동 |
| **S-411** 빙하 | IceConcentration, IceType | `TestCondition` | P2 | 빙해수조 |
| **S-412** 기상 | WeatherOverlay | `OceanEnvironment` | P3 | 개발 중 (2027~) |

### S-100 데이터 교환 형식 → KG 변환 파이프라인

| 인코딩 | 기반 | 용도 | 파서 | 난이도 |
|-------|------|------|------|-------|
| **GML** | ISO 19136 (XML) | 벡터 데이터 (해도, 경계선) | GDAL/OGR | 중간 |
| **HDF5** | HDF Group | 격자 데이터 (수심, 해류, 기상) | h5py + xarray | 높음 |
| **ISO 8211** | ISO/IEC 8211 | 레거시 호환 (S-57) | OGR S-57 드라이버 | 높음 |

---

## 2.3 IMO AIS 메시지 필드 매핑

AIS(Automatic Identification System) 메시지에서 추출하는 필드를 KG의 `Vessel`, `AISRecord` 노드 속성으로 매핑한다.

### AIS 메시지 타입별 추출 필드

| 메시지 타입 | 용도 | 주요 필드 | KG 매핑 | 갱신 주기 |
|-----------|------|---------|---------|---------|
| **Type 1/2/3** | 동적 정보 (Class A) | MMSI, lat/lon, SOG, COG, heading, navStatus, timestamp | `AISRecord` 노드 속성 | 2~10초 |
| **Type 5** | 정적 정보 (Class A) | IMO, callSign, shipName, shipType, length, beam, draft, destination, ETA | `Vessel` 노드 속성 | 6분 |
| **Type 18** | 동적 정보 (Class B) | MMSI, lat/lon, SOG, COG, heading | `AISRecord` 노드 속성 | 30초~3분 |
| **Type 24** | 정적 정보 (Class B) | MMSI, shipName, shipType, vendorId, callSign | `Vessel` 노드 속성 | 6분 |

### AIS → KG 속성 매핑 상세

| AIS 필드 | KG Property | 타입 | 대상 노드 | 비고 |
|---------|------------|------|---------|------|
| MMSI | `mmsi` | STRING | Vessel | 고유 식별자 (9자리) |
| IMO Number | `imo` | STRING | Vessel | 7자리, Type 5에서만 |
| Ship Name | `name` | STRING | Vessel | 최대 20자 |
| Ship Type | `vesselType` | STRING | Vessel | AIS 선종코드 → 한글 변환 |
| Latitude/Longitude | `location` | POINT | AISRecord | `point({lat, lon})` |
| SOG | `speed` | FLOAT | AISRecord | 노트(knots) 단위 |
| COG | `course` | FLOAT | AISRecord | 0~360도 |
| Heading | `heading` | FLOAT | AISRecord | 선수 방향 |
| Navigation Status | `navStatus` | STRING | AISRecord | 정박/항해/예인 등 |
| Destination | `destination` | STRING | Vessel | Port → DEPARTED_FROM 관계 생성 |
| Draught | `draft` | FLOAT | Vessel | 미터 단위 (0.1m 해상도) |

---

## 2.4 MAKG 엔티티 비교 매핑

MAKG(Maritime Accident Knowledge Graph)는 **해사 사고 분석**에 특화된 지식그래프이다. Liu & Cheng(2024, Ocean Engineering)이 중국 MSA 사고조사 보고서 581건(2014-2023)을 기반으로 Stanford 7-step 방법론으로 구축하였다. (16,099 엔티티, 20,809 관계)

### MAKG 8개 엔티티 vs KRISO KG 매핑

| # | MAKG 엔티티 | MAKG 역할 | KRISO KG 매핑 | 비고 |
|---|-----------|---------|-------------|------|
| 1 | **Case (사고)** | 사고 사례 (핵심 엔티티) | `MaritimeEvent` | KRISO: 사고 외 입출항/VTS 이벤트 포함으로 범위 확장 |
| 2 | **Ship (선박)** | 사고 관련 선박 | `Vessel` | 공통 속성: name, type, IMO. KRISO: AIS 동적 데이터 추가 |
| 3 | **Crew (선원)** | 사고 관련 선원 | 해당 없음 (Phase 2 검토) | KRISO 1차년도 범위 외. MAKG 고유 엔티티 |
| 4 | **Cargo (화물)** | 적재 화물 정보 | 해당 없음 (Phase 2 검토) | 위험물 운송 시나리오에서 참조 가능 |
| 5 | **Organization (조직)** | 관련 조직/기관 | `TestFacility` (부분 매핑) | MAKG: MSA, 해운사 등. KRISO: 시험시설로 특화 |
| 6 | **Law (법률)** | 관련 법규/규정 | `Regulation` | 공통 개념. KRISO: COLREGS/SOLAS/MARPOL 조문 단위 모델링 |
| 7 | **Reason Analysis (원인 분석)** | 사고 원인 분석 결과 | 해당 없음 (KRISO 독자 설계 영역) | MAKG 고유: 사고 원인 체계적 분류 |
| 8 | **Manage Suggestion (관리 제안)** | 관리 개선 제안사항 | 해당 없음 | MAKG 고유: 사고 재발 방지 제안 |

### MAKG 핵심 기술 요소

- **NER 프레임워크**: MBERT-BiLSTM-CRF-SF (F1: 0.910). 사고 보고서에서 8개 엔티티 자동 추출
- **CRISPE 프롬프트**: LLM 기반 KG 질의 인터페이스. KRISO KG pipeline.py에서 동일 프레임워크 채택
- **사고 특화 도메인**: 중국 MSA 581건 기반. KRISO는 해상교통 + 시험시설로 범위 확장 필요
- **Stanford 7-Step 적용**: MAKG도 동일 방법론 사용. 엔티티 도출 과정 참고 가능

---

## 2.5 오재용·김혜진 논문 (멀티모달 해사 데이터 관리)

오재용, 김혜진(2024, KOSOMES) — "멀티 모달 해사 데이터 관리 체계 설계에 관한 연구". **KRISO 책임연구원**의 논문으로, 해사 멀티모달 데이터(AIS, GPS, RADAR, VHF, CCTV, Port-MIS 등 8종)를 Neo4j 그래프 모델로 통합 관리하는 체계를 제안한다.

### 8종 멀티모달 데이터 유형

| 데이터 유형 | 형태 | 주요 항목 | KRISO KG 반영 |
|-----------|------|---------|-------------|
| **AIS** | 정형 | MMSI, 위치, 속력, 침로, 선종 | `Vessel` + `AISRecord` 직접 매핑 |
| **GPS** | 정형 | 위도, 경도, 시각 | `point()` 속성으로 통합 |
| **Equipment** | 정형 | 장비 상태, 센서 데이터 | `Sensor` → `SensorReading` |
| **RADAR** | 비정형 | 레이더 영상, 탐지 객체 | Phase 2 검토 (영상 데이터) |
| **VHF** | 비정형 | 교신 내용, 송수신자 | `VHFRecord` 관계 모델 채택 |
| **Port-MIS** | 정형 | 입출항 신고, 선석 배정 | `Port`, `Berth` 엔티티 반영 |
| **CCTV** | 비정형 | 영상, 촬영 위치, 장비 | `CCTVRecord` 관계 모델 참조 |
| **Environment** | 정형 | 기상, 조류, 파고 | `WeatherCondition` 엔티티 |

### VHF/CCTV 그래프 모델 관계 (Table 2)

| From | 관계 | To | 설명 | KRISO KG 채택 |
|------|-----|-----|------|-------------|
| VHFRecord | `TRANSMITTED_BY` | Vessel | VHF 송신 선박 | 채택 |
| VHFRecord | `INTENDED_FOR` | Vessel / VTS | VHF 수신 대상 | 채택 |
| Vessel | `PORT_ENTRY` | Port | 입항 | 채택 → `ARRIVED_AT` |
| Vessel | `PORT_DEPARTURE` | Port | 출항 | 채택 → `DEPARTED_FROM` |
| Vessel | `ANCHORED_AT` | AnchorArea | 정박 | 채택 |
| Vessel | `HEAVE_AT` | AnchorArea | 양묘 | Phase 2 검토 |
| Vessel | `BERTH_TO` | Berth | 접안 | 채택 |
| CCTVRecord | `LOCATED_AT` | Port / SeaArea | 촬영 위치 | Phase 2 검토 |
| CCTVRecord | `PROVIDED_BY` | CCTVCamera | 촬영 장비 | Phase 2 검토 |
| VTSOperator | `COMMUNICATE_WITH` | Vessel | VTS-선박 교신 | 채택 |

### 시스템 아키텍처 참조

- **오재용 논문**: Kafka → Workflow Manager → Neo4j + MinIO → Cypher/REST API → Grafana
- **KRISO KG**: Kafka → ELT Pipeline → Neo4j + PostgreSQL + Qdrant → FastAPI → VueFlow UI
- Neo4j 중심 그래프 저장 + 객체저장소 보조 패턴 동일. KRISO는 벡터DB(Qdrant)와 FastAPI 추가

---

## 2.5a Li et al. AIS 기반 해상교통 시간적 KG

Li et al.(2024, J. Mar. Sci. Eng.) — "Maritime Traffic Knowledge Discovery via Knowledge Graph Theory". Long Beach 항만 AIS 데이터 기반 시간적 지식그래프 구축. 선박 이동 이벤트, 충돌 위험도, 정박지를 자동 추출한다.

### KG 엔티티 구조

| 엔티티 | 속성 | KRISO KG 매핑 |
|-------|------|-------------|
| **Ship** | MMSI, name, callsign, draft, length, beam, type | `Vessel` — AIS 정적 데이터 직접 매핑 |
| **Navigation Event** | eventType (속력변화/침로변화/정지), timestamp | `VoyageEvent` — 이벤트 유형 확장 |
| **Berth** | 위치(DBSCAN 클러스터), 용량 | `Berth` — Port 하위 엔티티 |
| **Weather** | 풍속, 파고, 시정, 조류 | `WeatherCondition` |
| **Time** | UTC timestamp, interval | `datetime()` 속성으로 통합 |

### AIS 선종 코드 매핑

| AIS 코드 | 선종 | KRISO vesselType |
|---------|------|-----------------|
| 50-59 | 특수작업선 (예인선, 준설선 등) | `SPECIAL` |
| 60-69 | 여객선 | `PASSENGER` |
| 70-79 | 화물선 | `CARGO` |
| 80-89 | 유조선 | `TANKER` |
| 90-99 | 기타 (어선, 범선 등) | `OTHER` |

### 핵심 알고리즘 참조

- **DCPA/TCPA 충돌 위험도**: 두 선박 간 최근접점 거리(DCPA)와 도달 시간(TCPA) 공식. KRISO: CollisionRisk 관계의 score 속성으로 반영
- **Sliding Window 이벤트 탐지**: 속력/침로 급변 시점을 탐지하여 Navigation Event 생성. KRISO: ELT 파이프라인 transform 단계에서 적용 가능
- **DBSCAN 정박지 식별**: AIS 위치 클러스터링으로 정박지/선석 자동 식별. KRISO: Berth 엔티티 자동 생성에 참조

---

## 2.5b 긴급구조 장소 식별자 KG (PIKG)

Kim & Lee(2024) — "긴급구조 접수 및 출동을 위한 장소 식별자 지식그래프 구축". Neo4j LPG 모델을 활용한 국내 장소 식별자 통합 KG. 시나리오 기반 Cypher 질의 설계 패턴을 참조한다.

### 장소 식별자 엔티티

| 엔티티 | 설명 | 관계 | KRISO KG 참조점 |
|-------|------|------|---------------|
| **국가지점번호** | 대한민국 격자 좌표 체계 | `BELONG_TO` (상위 장소 포함) | 해상 격자 좌표 → SeaArea 매핑 |
| **도로명주소** | 도로명 기반 주소 | `BELONG_TO` | 항만 시설 주소 → Port 속성 |
| **지번** | 필지 기반 주소 | `BELONG_TO` | 해안 시설 위치 참조 |
| **POI** | 관심 장소 (건물, 시설) | `BELONG_TO` | VTS 센터, 해경서 위치 |
| **해수욕장** | 해수욕장 이름/위치 | `BELONG_TO` | 해양 레저 구역 참조 |

### 참조 설계 패턴

- **시나리오 기반 질의 설계**: 7개 긴급구조 시나리오별 Cypher 질의 설계. KRISO CQ(Competency Question) 설계 패턴 참조
- **Neo4j LPG 실무 적용**: 한국 맥락 Neo4j LPG 실무 사례. BELONG_TO 계층 관계 패턴 → KRISO 해역 계층에 적용

---

## 2.6 범용 표준 패턴 재사용 전략

W3C/OGC 범용 온톨로지에서 패턴을 차용하여 Property Graph로 변환 적용한다.

| 표준 | 핵심 패턴 | KRISO KG 적용 | 예시 |
|------|---------|-------------|------|
| **SSN/SOSA** | Sensor → Observation → Result | Sensor → SensorReading 2단계로 단순화 | `(s:Sensor)-[:PRODUCES]->(r:SensorReading)` |
| **GeoSPARQL** | Feature → Geometry + spatial functions | `point()` 속성 + `point.distance()` 함수 | `WHERE point.distance(v.location, p) < 5000` |
| **OWL-Time** | Instant, Interval, Duration | `datetime()` + startTime/endTime 속성 쌍 | `WHERE voy.eta >= datetime("2024-01-01")` |
| **PROV-O** | Entity → Activity → Agent | `DERIVED_FROM`, `PRODUCED_BY` 관계 패턴 | `(result)-[:DERIVED_FROM]->(rawData)` |

---

## 2.7 온톨로지 재사용 4계층 스택

KRISO KG 온톨로지는 4개 계층의 기존 표준을 재사용하여 상호운용성을 확보한다.

```
┌──────────────────────────────────────────────────────────┐
│  Layer 4: KRISO 도메인 온톨로지                            │
│    8 Core Classes + 14 Relations + URN Scheme             │
├──────────────────────────────────────────────────────────┤
│  Layer 3: 해사 도메인 표준                                 │
│    IHO S-100 · IMO AIS · DCSA · IMO FAL                  │
├──────────────────────────────────────────────────────────┤
│  Layer 2: 범용 도메인 온톨로지                              │
│    W3C SSN/SOSA · OGC GeoSPARQL · W3C OWL-Time · PROV-O │
├──────────────────────────────────────────────────────────┤
│  Layer 1: 기반 표준                                       │
│    Schema.org · W3C SKOS · W3C DCAT                      │
└──────────────────────────────────────────────────────────┘
```

---

## 2.8 재사용 판정 결과 요약

| 온톨로지 | 판정 | 재사용 범위 | 비고 |
|---------|------|-----------|------|
| **IHO S-100** | **채택** | Feature Type → Label, Attribute → Property, `s100_featureCode` 메타데이터 보존 | S-101(ENC), S-127(VTS) 우선 매핑 |
| **IMO AIS** | **채택** | Type 1/5/18/24 전체 필드 → Vessel + AISRecord | 선종코드 한글 변환 테이블 필요 |
| **MAKG** | 참조 | Case·Ship·Law 3개 엔티티 개념 참고, CRISPE 프롬프트 프레임워크 채택 | 사고 도메인 특화 — 해상교통/시험시설은 KRISO 독자 설계 |
| **오재용·김혜진** | **부분 채택** | VHF/CCTV 그래프 모델 10개 관계 중 6개 채택, Kafka→Neo4j 아키텍처 참조 | KRISO 내부 논문 — 직접 연계 가능 |
| **Li et al.** | 참조 | AIS 선종 코드 매핑, DCPA/TCPA 충돌 위험도, Sliding Window 이벤트 탐지 | ELT transform 단계 알고리즘 참조 |
| **Kim & Lee** | 참조 | 시나리오 기반 Cypher 질의 설계 패턴, BELONG_TO 계층 관계 | CQ 설계 방법론 참고 |
| **SSN/SOSA** | **패턴 채택** | Sensor → Observation 패턴 → 2단계로 단순화 | PG 변환 시 3단계 → 2단계 |
| **GeoSPARQL** | **패턴 채택** | 공간 함수 패턴 → Neo4j `point()` | Neo4j 네이티브 공간 인덱스 활용 |
| **OWL-Time** | **패턴 채택** | 시간 표현 패턴 → Neo4j `datetime()` | UTC 기준 통일 |
| **PROV-O** | **패턴 채택** | 데이터 계보 관계 패턴 차용 | core/kg/lineage 모듈과 연계 |

---

## Step 2 검증 CQ — 재사용 완전성

재사용한 온톨로지 요소가 마스터 CQ를 실제로 커버하는지 검증한다.

| ID | 검증 질문 | 검증 대상 |
|----|---------|---------|
| **S2-CQ1** | S-100 Feature Catalogue 속성 중 P0 노드에 직접 매핑되는 것은 몇 개인가? | S-100 재사용률 — FC 구성요소(Feature Type, Attribute, Role) → KG Label/Property 대응 완전성 |
| **S2-CQ2** | AIS 메시지 타입 1/5/18/24의 필드가 Vessel·AISRecord 속성과 1:1 대응되는가? | AIS 매핑 완전성 — 누락 필드 없이 IMO 표준 필드가 KG 속성으로 변환되는지 확인 |
| **S2-CQ3** | MAKG 8개 엔티티 중 P0와 겹치는 것은? 차이나는 것의 제외 근거는? | MAKG 정합성 — Case/Ship/Law 채택, Crew/Cargo 제외 판정의 근거 추적성 |

---

## Step 2 결론

- **직접 채택**: S-100 FC 매핑, AIS 필드 매핑, 공간/시간/계보 패턴 — KG 스키마에 직접 반영
- **부분 채택**: 오재용·김혜진 VHF/CCTV 그래프 모델 10개 관계 중 6개 — KRISO 내부 연구 직접 연계
- **참조 활용**: MAKG 사고 엔티티 + CRISPE 프롬프트, Li et al. AIS 이벤트 탐지, PIKG CQ 설계 패턴
- **KRISO 독자 설계**: TestFacility → TestScenario → TestCondition → MeasurementRecord 4단계 체인, 시험시설 8종

---

## 다음 단계

**Step 3: 핵심 용어 열거** (Key Term Enumeration)
- P0/P1/P2 3계층 엔티티 분류
- 관계 타입 목록 도출
- 핵심 속성 목록 확정

---

## 참조

| 문서 | 내용 |
|------|------|
| IHO S-100 Universal Hydrographic Data Model | Feature Catalogue 구조, Product Specification |
| IMO AIS Message Types | Type 1/2/3/5/18/24 필드 정의 |
| Liu & Cheng (2024, Ocean Engineering) | MAKG 구축 — 581건 사고 보고서 |
| 오재용·김혜진 (2024, KOSOMES) | 멀티모달 해사 데이터 관리 체계 설계 |
| Li et al. (2024, J. Mar. Sci. Eng.) | AIS 기반 해상교통 시간적 KG |
| Kim & Lee (2024) | 긴급구조 장소 식별자 KG (PIKG) |
| W3C SSN/SOSA | Semantic Sensor Network / Sensor, Observation, Sample, Actuator |
| OGC GeoSPARQL | Geographic Query Language for RDF Data |
| W3C OWL-Time | Time Ontology in OWL |
| W3C PROV-O | Provenance Ontology |
