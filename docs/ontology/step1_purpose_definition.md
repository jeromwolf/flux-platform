# Step 1: 목적 정의 (Purpose Definition)

> **Stanford 7-Step Ontology Design Methodology** | DevKG 구축
>
> 작성일: 2026-03-30 | 프로젝트: DevKG (`X-KG-Project: DevKG`)

---

## 1.1 온톨로지 설계 목적

**대화형 해사서비스 플랫폼(IMSP)의 자원 의미 연결**을 위한 지식그래프 온톨로지를 설계한다.

### 핵심 목적

| # | 목적 | 설명 |
|---|------|------|
| P1 | **멀티모달 해사 데이터 통합** | AIS, GPS, RADAR, VHF, Port-MIS, CCTV, 기상, 시험시설 등 이질적 데이터를 하나의 의미 체계로 연결 |
| P2 | **자연어 기반 지식 탐색** | Text-to-Cypher 파이프라인을 통해 비전문가도 자연어로 KG를 질의할 수 있도록 지원 |
| P3 | **KRISO 시험시설 데이터 구조화** | 선형수조, 캐비테이션터널 등 시험시설의 시험 이력/결과/보고서를 체계적으로 관리 |
| P4 | **국제 표준 정합성 확보** | IHO S-100, IMO AIS 표준 기반 온톨로지로 국제 해사 데이터와의 상호운용성 보장 |
| P5 | **2차년도 LLM 연계 기반 마련** | GraphRAG + LLM 대화형 인터페이스와 즉시 연계 가능한 스키마 설계 |

### 설계 원칙

- **LPG(Labeled Property Graph) 기반**: Neo4j Community Edition 사용 (S21 기술 비교 결과)
- **Schema-optional**: 유연한 확장성 + SHACL 사전 품질 검증으로 무결성 보장
- **Cypher 최적화**: Text-to-Cypher 변환 시 직관적인 노드/관계 명명 규칙 적용
- **URN 식별 체계**: `urn:kriso:kg:{type}:{subtype}:{id}` 형식의 글로벌 고유 식별자

---

## 1.2 도메인 범위 (Scope)

### 포함 도메인 (In Scope)

```
                    ┌─────────────────────────────┐
                    │    IMSP 해사 지식그래프       │
                    │                             │
          ┌─────────┼──────┬──────┬──────┐        │
          │         │      │      │      │        │
     ┌────▼───┐ ┌──▼───┐ ┌▼────┐ ┌▼────┐ ┌▼─────┐│
     │해상교통│ │항만  │ │해양 │ │선박 │ │시험  ││
     │        │ │물류  │ │환경 │ │안전 │ │시설  ││
     └────────┘ └──────┘ └─────┘ └─────┘ └──────┘│
                    └─────────────────────────────┘
```

| 서브도메인 | 핵심 데이터 | 우선순위 |
|-----------|-----------|---------|
| **해상교통** | AIS, RADAR, VHF, 항로 | Core |
| **항만물류** | Port-MIS, 선석, 화물 | Core |
| **해양환경** | 기상, 환경, ENC(전자해도) | Core |
| **선박안전** | 시험시설, 인증, 법규 | Core (KRISO 특화) |
| 시계열 분석 | InfluxDB 연계 (2차년도) | Extended |
| 영상/음성 | CCTV(YOLO), VHF(STT) | Extended |
| 외부 KG 연계 | MAKG, DBpedia, Wikidata | Future |

### 제외 도메인 (Out of Scope)

- 상업 항만 운영 시스템 (ERP, TOS)
- 군사/보안 해역 정보 (CLASSIFIED)
- 실시간 스트리밍 처리 (별도 InfluxDB로 분리, KG는 메타만 보관)
- 선박 설계/건조 프로세스 (조선 도메인)

---

## 1.3 대상 사용자 (Target Users)

| 사용자 유형 | 역할 | KG 활용 시나리오 |
|-----------|------|---------------|
| **KRISO 연구원** | 시험시설 운영, 실험 수행 | 시험 이력 조회, 유사 실험 검색, 결과 비교 분석 |
| **해양안전 분석관** | VTS 관제, 사고 분석 | 항로 위험도 평가, COLREGS 적용 조문 확인 |
| **해사 데이터 과학자** | 데이터 분석, 모델 개발 | Multi-hop 질의, 그래프 패턴 탐색, 데이터 품질 분석 |
| **플랫폼 개발자** | API/파이프라인 개발 | Cypher 쿼리 빌더, ETL 파이프라인, GraphRAG |
| **민간 해사 서비스** | 2단계 R&D 활용 (2029~) | 해사 데이터 조회, 서비스 연동 |

---

## 1.4 Competency Questions (CQ) - 핵심 5개

> Stanford 7-Step에서 CQ는 온톨로지가 반드시 답할 수 있어야 하는 질문이다.
> 이 질문들이 Step 3(핵심 용어), Step 4(클래스 계층), Step 5(속성)를 이끈다.

### CQ1: 시험 조회 (1-hop, Direct)

> **"VLCC 모형선의 14노트 저항계수(Ct)는?"**

- **추론 유형**: Direct (단순 조회)
- **관련 엔티티**: `Vessel`, `TestScenario`, `MeasurementRecord`
- **필요 관계**: `Vessel -[TESTED_IN]-> TestScenario -[PRODUCES]-> MeasurementRecord`
- **필요 속성**: `Vessel.vesselType`, `MeasurementRecord.speed`, `MeasurementRecord.resistanceCoefficient`
- **검증 Cypher**:
  ```cypher
  MATCH (v:Vessel {vesselType: "VLCC"})-[:TESTED_IN]->(ts:TestScenario)
        -[:PRODUCES]->(mr:MeasurementRecord {speed: 14})
  RETURN mr.resistanceCoefficient AS Ct
  ```

### CQ2: 선형/운항 비교 (2-hop, Bridge)

> **"설계 EHP(유효마력)와 실해역 연시(Sea Trial) 결과의 차이는?"**

- **추론 유형**: Bridge (순차 이동 A->B->C)
- **관련 엔티티**: `Vessel`, `TestScenario`, `MeasurementRecord`, `VoyageEvent`
- **필요 관계**: 시험 결과 → 설계 EHP, 운항 데이터 → 실해역 성능
- **필요 속성**: `MeasurementRecord.effectiveHorsePower`, `VoyageEvent.actualPerformance`
- **검증 Cypher**:
  ```cypher
  MATCH (v:Vessel)-[:TESTED_IN]->(ts:TestScenario)-[:PRODUCES]->(mr:MeasurementRecord)
  MATCH (v)-[:PARTICIPATED_IN]->(ve:VoyageEvent)
  WHERE mr.parameterType = "EHP" AND ve.hasPerformanceData = true
  RETURN mr.value AS designEHP, ve.actualEHP AS seaTrialEHP,
         abs(mr.value - ve.actualEHP) AS difference
  ```

### CQ3: 해역/규정 연계 (2-hop, Bridge)

> **"부산항 VTS 관제구역에 적용되는 COLREGS 조문은?"**

- **추론 유형**: Bridge (해역 → 규정)
- **관련 엔티티**: `Port`, `SeaArea`, `Regulation`
- **필요 관계**: `Port -[HAS_VTS_ZONE]-> SeaArea -[APPLIES_TO]<- Regulation`
- **필요 속성**: `Port.name`, `SeaArea.areaType`, `Regulation.articleNumber`, `Regulation.title`
- **검증 Cypher**:
  ```cypher
  MATCH (p:Port {name: "부산항"})-[:HAS_VTS_ZONE]->(sa:SeaArea)
  MATCH (r:Regulation)-[:APPLIES_TO]->(sa)
  WHERE r.framework = "COLREGS"
  RETURN r.articleNumber, r.title, sa.name
  ```

### CQ4: 환경/성능 상관 (2-hop, Composition)

> **"파고 3m 이상 조건에서 선박 저항 증가율은?"**

- **추론 유형**: Composition (환경 조건 + 성능 데이터 결합)
- **관련 엔티티**: `SeaArea`, `OceanEnvironment`, `MeasurementRecord`, `TestCondition`
- **필요 관계**: `SeaArea -[HAS_CONDITION]-> OceanEnvironment`, `TestCondition -[PRODUCES]-> MeasurementRecord`
- **필요 속성**: `OceanEnvironment.waveHeight`, `MeasurementRecord.resistanceIncrease`
- **검증 Cypher**:
  ```cypher
  MATCH (tc:TestCondition)-[:PRODUCES]->(mr:MeasurementRecord)
  WHERE tc.waveHeight >= 3.0
  RETURN tc.waveHeight, mr.resistanceCoefficient,
         mr.resistanceIncrease AS increaseRate
  ORDER BY tc.waveHeight
  ```

### CQ5: 시설 추론 (Multi-hop, Intersection)

> **"캐비테이션터널에서 프로펠러 공동 조건이 유사한 시험 목록은?"**

- **추론 유형**: Intersection (시설 + 조건 교집합 탐색)
- **관련 엔티티**: `TestFacility`, `TestScenario`, `TestCondition`, `Sensor`
- **필요 관계**:
  - `TestFacility -[HOSTS]-> TestScenario`
  - `TestScenario -[APPLIES]-> TestCondition`
  - `TestScenario -[USES_INSTRUMENT]-> Sensor`
- **필요 속성**: `TestFacility.facilityType`, `TestCondition.cavitationType`, `TestCondition.propellerRPM`
- **검증 Cypher**:
  ```cypher
  MATCH (tf:TestFacility {facilityType: "캐비테이션터널"})-[:HOSTS]->(ts:TestScenario)
        -[:APPLIES]->(tc:TestCondition)
  WHERE tc.cavitationType IS NOT NULL
  WITH tc.pressure AS pressure, tc.propellerRPM AS rpm, collect(ts) AS scenarios
  WHERE size(scenarios) > 1
  RETURN pressure, rpm, size(scenarios) AS similarCount,
         [s IN scenarios | s.scenarioId] AS scenarioIds
  ```

---

## 1.5 확장 검증 질문 (Q6~Q10) - PoC 심화

> 제안서 S29 기반: Q1~Q5는 기본 탐색, Q6~Q10은 KRISO 특화 심화 탐색

| # | 질문 | Hop | 유형 |
|---|------|-----|------|
| Q6 | VLCC 모형선 14노트 저항 계수는? | 2-hop | Direct → TT 저항시험 계측값 직접 반환 |
| Q7 | 캐비테이션터널 시험 중 프로펠러 공동 조건이 유사한 시험 목록은? | Multi-hop | 압력·회전수·공동수 속성값 비교 기반 Multi-hop 탐색 |
| Q8 | 부산항 입항 선박 중 VLCC 유형은? | 2-hop | 선박 유형 필터링 기반 목록 반환 — 항만+선박 연계 검증 |
| Q9 | 해사안전법 TSS 관련 조문은? | 2-hop | 법규 그래프 탐색 → 관련 조문 목록 — 해역·법규 연계 검증 |
| Q10 | 이 선박의 어제 이동 경로는? | Hybrid | AIS 요약 데이터 + InfluxDB 세부 데이터 참조 — 하이브리드 탐색 검증 |

### 성능 합격 기준 (S26)

| 항목 | 기준 |
|------|------|
| 단순 쿼리 (1-hop) | < 1초 |
| 복합 쿼리 (2+ hop) | < 5초 |
| 시각화 렌더링 | 100노드 1초 이내 |
| 관계 정확도 | 90% 이상 |
| Multi-hop 탐색 | 3-hop 이상 |
| Cypher 쿼리 | 10개 이상 검증 |

---

## 1.6 데이터 연결 키 (Join Keys)

> 멀티모달 데이터를 하나의 KG로 통합하기 위한 6대 조인 키 (S11)

| # | 조인 키 | 식별자 | 연결 대상 |
|---|--------|-------|---------|
| 1 | **선박(Vessel)** | MMSI, IMO | AIS ↔ Port-MIS ↔ 시험 ↔ 인증 |
| 2 | **시간(Time)** | UTC timestamp | AIS ↔ 기상 ↔ VHF ↔ CCTV |
| 3 | **위치(Location)** | WGS-84 (lat/lon), LOCODE | AIS ↔ 항만 ↔ 해역 ↔ 전자해도 |
| 4 | **시설(Facility)** | facilityId | 시험시설 ↔ 장비 ↔ 시험 ↔ 보고서 |
| 5 | **문서(Document)** | documentId | 보고서 ↔ 분석결과 ↔ 시험시나리오 |
| 6 | **이벤트(Event)** | eventId | 항해 ↔ 사고 ↔ 계측 ↔ 입출항 |

---

## 1.7 데이터 품질 등급 (Quality Grades)

> 데이터 소스별 사전 품질 등급 (S17 기준) — 적재 전 평가

| 등급 | 기준 | 결측률 | 활용 |
|------|------|-------|------|
| **A (상)** | 즉시 활용 가능 | < 5% | Core KG 직접 적재 |
| **B (중)** | 보정 후 활용 | 5~30% | ETL 정제 후 적재 |
| **C (하)** | 향후 검토 | > 30% | Future 카테고리로 분류 |

---

## 1.8 KG 자원 우선순위 (Resource Priority)

> 구축 순서: Core → Extended → Future (S19)

### Core (1차년도 즉시 구축)

| 자원 | 데이터 소스 | 품질 | PoC 규모 |
|------|-----------|------|---------|
| AIS 동적정보 | 해양수산부 GICOMS | A | 500척 × 1주일 |
| GPS 항적 | AIS 파생 | A | 상동 |
| Port-MIS | 해양수산부 | A | 부산·인천·울산 3개 항만 |
| RADAR | KRISO VTS | B | 부산항 VTS 관제구역 |
| 시험시설 | KRISO 내부 | A | 선형수조(TT) 1개 시설 |
| 기상 데이터 | 기상청 API | A | 부산 인근 |

### Extended (1차년도 말~2차년도 초)

| 자원 | 데이터 소스 | 품질 | 비고 |
|------|-----------|------|------|
| CCTV 영상 | KRISO/항만 | B | YOLO 객체인식 → JSON → KG |
| VHF 음성 | VTS 교신 | C | STT(Whisper) → NER(KoELECTRA) → KG |
| 전자해도 (ENC) | IHO S-57/S-101 | A | gdal/ogr → GeoJSON → Cypher |

### Future (2차년도 이후)

| 자원 | 비고 |
|------|------|
| 외부 KG (MAKG, DBpedia) | LINKED_TO 관계로 연계 |
| 시계열 상세 (InfluxDB) | KG는 메타만, 상세는 InfluxDB |
| 실시간 스트리밍 | Kafka → InfluxDB → KG 메타 갱신 |

---

## 1.9 기존 온톨로지 재사용 계획 (Step 2 연계)

> Step 1에서 식별, Step 2에서 상세 분석

| 기존 온톨로지 | 활용 범위 | 재사용 방법 |
|-------------|---------|-----------|
| **IHO S-100** | 전자해도, 해역 분류 | Feature Catalogue 속성 매핑 |
| **IMO AIS 메시지** | 선박 동적/정적 정보 | Message Type 1/5/18/24 필드 매핑 |
| **MAKG** (Maritime Academic KG) | 해사 학술 엔티티 비교 | 8개 공통 엔티티 정렬 (S18 비교표) |
| **오재용 논문** (해상교통 온톨로지) | 선박-항만-해역 관계 | 관계 타입 + 속성 참고 |

---

## 1.10 DevKG 구축 목표

| 항목 | 목표 |
|------|------|
| **프로젝트 이름** | `DevKG` (X-KG-Project: DevKG) |
| **Neo4j 네임스페이스** | `:KG_DevKG` 레이블 자동 부여 |
| **목적** | 온톨로지 설계 검증 + PoC 데이터 적재 테스트 |
| **핵심 엔티티** | 8종: Vessel, Port, SeaArea, Event, Regulation, Facility, AIModel, Workflow |
| **핵심 관계** | 14종 (S24 카탈로그 기반) |
| **샘플 데이터 규모** | S26 기준 — Vessel 500, Port 3, TestDataset 100, Regulation 10 |
| **검증 기준** | CQ 5개 + Q6~Q10 심화 = 총 10개 질의 통과 |

---

## 다음 단계

**Step 2: 기존 온톨로지 재사용 분석** (Reuse Evaluation)
- IHO S-100 Feature Catalogue 상세 분석
- MAKG 8개 엔티티 매핑 테이블 작성
- IMO AIS 메시지 타입별 속성 추출
- 재사용 가능 속성/관계 목록 도출

---

## 참조

| 문서 | 슬라이드 | 내용 |
|------|---------|------|
| KRISO 제안서 | S07-S08 | 연구 배경, 3단계 프레임워크 |
| KRISO 제안서 | S09-S11 | 데이터 생태계, 멀티모달 유형, 조인 키 |
| KRISO 제안서 | S12-S13 | Stanford 7-Step 개요, CQ 5개 |
| KRISO 제안서 | S14-S19 | Step 3-7 핵심 용어~인스턴스, L1-L5 계층 |
| KRISO 제안서 | S20-S21 | LPG vs RDF 비교, 공간 관계 |
| KRISO 제안서 | S24 | 14개 핵심 관계 카탈로그 |
| KRISO 제안서 | S26 | PoC 데이터 7종 + 성능 합격 기준 |
| KRISO 제안서 | S29 | Q1~Q10 검증 질문 |
| DES-001 | - | 지식그래프 모델 설계서 |
| REQ-002 | - | KG 구축 대상 자원 선정 |
