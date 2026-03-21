# 4. 데이터 아키텍처

[← 컴포넌트 아키텍처](./03-component-architecture.md) | [다음: 배포 아키텍처 →](./05-deployment-architecture.md)

## 개요

IMSP의 데이터 아키텍처는 용도별로 최적화된 5개 저장소(Neo4j, Object Storage, PostgreSQL, TimescaleDB, Redis)를 중심으로 구성된다. 이 문서는 데이터베이스 선정 근거, Neo4j 3계층 온톨로지 아키텍처, 온톨로지 재설계 계획, 멀티모달 저장 전략, ELT 파이프라인, 시계열 데이터 통합, 그리고 W3C PROV-O 기반 데이터 리니지를 기술한다.

---

## 4.1 데이터베이스 선정 및 역할

| Database | Version | License | 역할 | 선정 근거 |
|----------|---------|---------|------|----------|
| **Neo4j** | 5.x CE | GPLv3 | KG (graph + vector + spatial) | Cypher, LLM 통합, 통합 인덱스 |
| **Object Storage** | Ceph RGW | Apache 2.0 | Object Storage (원천 데이터) | S3 호환, 분산 파일시스템, PB급 확장, 온프레미스 |
| **PostgreSQL** | 14 | PostgreSQL | 메타데이터/인증 백엔드 | Keycloak 백엔드, Argo 메타 |
| **TimescaleDB** | TBD | Apache 2.0 | 시계열 (AIS 궤적, 기상) | AIS 쿼리 성능 (벤치마크 후 확정) |
| **Redis** | 7 | BSD | 잡 큐, 세션 캐싱 | BullMQ 호환, 저지연 캐시 |

TimescaleDB vs. InfluxDB 선택은 2차년도 착수 전 벤치마크로 확정한다. 평가 기준: AIS 궤적 시간 범위 쿼리 응답 시간, 압축률, PostgreSQL 호환성(TimescaleDB 유리).

> **Object Storage 선정:** Suredata Lab 인프라 표준에 따라 Ceph RGW를 기본 Object Storage로 사용한다.
> S3 호환 API를 사용하므로 개발 환경에서는 MinIO를 대체 사용할 수 있다.
> 코드에서는 boto3 S3 클라이언트를 사용하며, 엔드포인트 URL만 환경변수로 전환한다.

---

## 4.2 Neo4j 스키마 -- 3계층 온톨로지 아키텍처

```
+----------------------------------------------------------+
|  Conceptual Layer (도메인 독립, DB 비의존)                 |
|  kg/ontology/core.py                                     |
|                                                          |
|  - ObjectTypeDefinition (엔티티 정의)                    |
|  - LinkTypeDefinition (관계 정의)                        |
|  - PropertyDefinition (속성 정의)                        |
|  - FunctionRegistry (함수 등록)                          |
|                                                          |
|  ※ Neo4j 없이 pytest 단위 테스트 가능                    |
|  ※ DB 교체 시 이 레이어 불변                              |
+----------------------------------------------------------+
                           |
                           | generate_constraints()
                           | generate_indexes()
                           v
+----------------------------------------------------------+
|  Mapping Layer (DDL 생성)                                |
|  kg/ontology/maritime_loader.py                          |
|                                                          |
|  - UNIQUE 제약 생성 Cypher 출력                           |
|  - 인덱스 생성 Cypher 출력                               |
|    (vector / spatial / fulltext / range / RBAC)          |
|                                                          |
|  ※ DB 교체 시 이 레이어만 교체                            |
|    (예: Neo4j -> Apache AGE)                             |
+----------------------------------------------------------+
                           |
                           | 실행
                           v
+----------------------------------------------------------+
|  Physical Layer (Neo4j 전용 DDL)                         |
|  domains/maritime/schema/                                |
|                                                          |
|  constraints.cypher  (24 UNIQUE 제약)                    |
|  indexes.cypher      (44 인덱스)                         |
|    - Vector:    256d (궤적) / 512d (시각) / 768d (텍스트) / 1024d (융합) 임베딩 |
|    - Spatial:   point() 좌표                             |
|    - Fulltext:  한국어/영어 전문 검색                     |
|    - Range:     시간 범위 쿼리                            |
|    - RBAC:      접근 제어 필터용                          |
+----------------------------------------------------------+
```

---

## 4.3 온톨로지 재설계 (v1 목표: ~40 엔티티)

기존 127 엔티티는 데이터 소스 확인 없이 정의된 이론적 구조로, 실제 수집 가능한 데이터와 불일치한다. KRISO 요구 기반으로 완전 재설계한다.

### 4.3.1 설계 원칙 6가지

1. **Data-Driven** -- 확인된 데이터 소스가 있는 엔티티만 정의
2. **Maritime Traffic First** -- AIS 기반 해상교통 우선 구현
3. **Temporal** -- 모든 동적 엔티티에 validFrom / validTo 적용
4. **ELT-Friendly** -- Raw -> Metadata -> Entity 3단계 리니지 추적
5. **S-100 Compatible** -- IHO S-100 표준과 1:1 매핑 경로 확보
6. **Multi-Layer** -- 정적 지식 / 동적 관측 / 파생 인사이트 분리

### 4.3.2 온톨로지 v1 구조

```
IMSP Ontology v1 (Maritime Traffic, ~40 types)
|
+-- StaticKnowledge (정적 지식, ~12 types)
|   +-- Infrastructure
|   |   +-- Port, Berth, Terminal, Anchorage
|   |   +-- Waterway, TSS, NavigationAid
|   +-- Regulation
|   |   +-- TrafficRule, RestrictedArea, TemporalConstraint
|   +-- GeospatialReference
|       +-- SeaArea, EEZ, ChartFeature (S-100)
|
+-- DynamicObservation (동적 관측, ~10 types)
|   +-- VesselTracking
|   |   +-- Vessel, VesselPosition, TrackSegment, AISMessage
|   +-- EnvironmentalCondition
|   |   +-- WeatherObservation, OceanCurrent, TidalData
|   +-- SensorData
|       +-- RadarContact, CCTVFrame, LiDARPoint
|
+-- DerivedInsight (파생 인사이트, ~6 types)
|   +-- AnomalyDetection
|   |   +-- RouteDeviation, SpeedAnomaly, UnauthorizedEntry
|   +-- RiskAssessment
|   |   +-- CollisionRisk, GroundingRisk
|   +-- TrafficPattern
|       +-- TrafficDensity, RouteStatistics
|
+-- DataLineage (데이터 리니지, ~4 types)
    +-- RawAsset, ProcessedAsset
    +-- TransformActivity, ProvenanceChain
```

### 4.3.3 온톨로지 마이그레이션 절차

기존 127 엔티티에서 ~40 엔티티로의 전환은 다음 4단계로 수행한다.

```
단계 1: 기존 스키마 백업
     |  - Neo4j 전체 덤프 (neo4j-admin dump)
     |  - 기존 온톨로지 정의 파일 아카이브 (domains/maritime/ontology/)
     |  - 기존 constraints.cypher, indexes.cypher 보존
     v
단계 2: 새 온톨로지 정의
     |  - Conceptual Layer에서 ~40 ObjectTypeDefinition 정의
     |  - KRISO 요구사항 기반 엔티티/관계/속성 확정
     |  - SHACL 제약 조건 정의 (flux-ontology-local 참조)
     v
단계 3: 데이터 매핑 스크립트
     |  - 기존 엔티티 → 신규 엔티티 매핑 테이블 작성
     |  - Cypher MATCH-MERGE 기반 마이그레이션 스크립트 생성
     |  - 매핑 불가 엔티티 → 아카이브 레이블 부착 (:Archived)
     |  - 리니지 기록: 마이그레이션 자체를 PROV-O Activity로 추적
     v
단계 4: 검증
     - QualityGate 실행 (NodeCoverage, RelationCoverage, PropertyCompleteness)
     - 기존 테스트 케이스 재실행 (19개 maritime 테스트 파일)
     - S-100 매핑 경로 검증 (ChartFeature ↔ S-101 Feature 1:1 확인)
     - Rollback 절차 확인 (백업에서 복원 가능 여부)
```

### 4.3.4 S-100 호환성 매핑 계획

S-100 통합 레이어 (~33 엔티티, 2차년도 추가):

| 표준 | 내용 | 엔티티 수 | IMSP 매핑 대상 |
|------|------|-----------|---------------|
| S-101 ENC | Electronic Navigational Chart | 10 | ChartFeature, NavigationAid, Waterway |
| S-104 | Water Level | 4 | TidalData, Port |
| S-111 | Surface Currents | 4 | OceanCurrent, SeaArea |
| S-127 | VTS (Vessel Traffic Service) | 8 | TSS, RestrictedArea, TrafficRule |
| S-411 | Sea Ice | 4 | WeatherObservation (확장) |
| S-412 | Weather Forecast | 3 | WeatherObservation (확장) |

**S-100 매핑 원칙:**
- IMSP 엔티티와 S-100 Feature 간 `[:MAPS_TO_S100]` 관계로 연결
- S-100 Feature Code를 IMSP 노드의 `s100FeatureCode` 속성에 저장
- GML 속성은 IMSP 속성명으로 정규화, 원본 GML 경로는 `storagePath`로 참조
- 매핑 메타데이터: S-100 버전, 매핑 일자, 검증 상태

### 4.3.5 연차별 온톨로지 확장 경로

```
Y1 (2026): ~40 types  [Maritime Traffic Core]
     |
     v
Y2 (2027): ~70 types  [+ S-100 Standards, Environmental]
     |
     v
Y3 (2028): ~100 types [+ Research/Experiment, Port Operations]
     |
     v
Y4 (2029): ~130 types [+ Advanced Analytics, Regulatory]
     |
     v
Y5 (2030): ~150 types [+ Cross-domain, International Standards]
```

---

## 4.4 멀티모달 데이터 저장 전략

**원칙: Neo4j는 메타데이터만 저장. 원천 데이터(바이너리/대용량)는 Object Storage(Ceph)에 보관하고 `storagePath` 속성으로 참조한다.**

```
+-------------------+       storagePath       +-------------------+
|      Neo4j        | <---------------------- |  Object Storage    |
|                   |                         |                   |
| (:AISData {       |                         | raw/ais/          |
|   mmsi: "123",    |                         |   2026-03-20/     |
|   timestamp: ..., |                         |   batch_001.json  |
|   lat: 35.1,      |                         |                   |
|   lon: 129.0,     |                         | raw/satellite/    |
|   storagePath:    |                         |   2026-03-20/     |
|     "raw/ais/..." |                         |   scene_001.tif   |
| })                |                         |                   |
|                   |                         | raw/video/        |
| (:SatImage {      |                         |   cam_01/         |
|   resolution: ...,|                         |   2026-03-20/     |
|   bbox: [...],    |                         |   clip_001.mp4    |
|   storagePath:    |                         |                   |
|     "raw/sat/..." |                         | processed/        |
| })                |                         |   ocr/            |
+-------------------+                         |   embeddings/     |
                                              +-------------------+
```

| 데이터 유형 | Neo4j 역할 | 외부 저장소 | 연간 데이터량(예상) |
|------------|-----------|-----------|------------------|
| AIS 데이터 | 메타 + 관계 | TimescaleDB (시계열) | 10-100 GB |
| 위성 영상 | 메타 + 공간 인덱스 | Ceph RGW (GeoTIFF/SAFE) | 100-500 GB |
| 레이더 영상 | 메타 | Ceph RGW | 10-100 GB |
| 센서 데이터 | 메타 | TimescaleDB | 10-50 GB |
| 해도 (S-100) | 메타 + 공간 | Ceph RGW (S-101 GML) | 1-10 GB |
| 영상 클립 | 메타 | Ceph RGW (MP4/HLS) | 500 GB - 5 TB |
| **합계** | | | **~1-6 TB/년** |

---

## 4.5 ELT 파이프라인

### 4.5.1 ETL에서 ELT로의 전환

**왜 ETL → ELT 전환인가?**

기존 ETL(Extract-Transform-Load) 방식은 데이터를 추출한 후 스키마에 맞게 변환하고 적재한다. 이 방식은 온톨로지가 안정적일 때 효과적이지만, IMSP처럼 온톨로지가 연차별로 확장되고 재설계되는 환경에서는 다음과 같은 문제가 발생한다.

| 문제 | ETL 방식 | ELT 방식 |
|------|---------|---------|
| 온톨로지 변경 시 | 원본 데이터 유실 위험, 재수집 필요 | 원본 보존, 새 스키마로 재변환 가능 |
| 스키마 미확정 시 | 변환 로직 선행 개발 필요 | 원본 적재 후 스키마 확정 시 변환 |
| 대용량 데이터 | 변환 병목 (적재 전 전처리) | 적재 후 분산 변환 (Argo Workflow) |
| 디버깅 | 변환 중간 결과 추적 어려움 | 원본 항상 접근 가능 |

**전환 계획:**

| 연차 | 전략 | 상세 |
|------|------|------|
| Y1 (2026) | ETL 기반 유지 | 기존 flux-n8n에서 이식된 ETL 코드 활용. Extract → Transform → Load 순서 유지 |
| Y2 (2027) | ELT 전환 착수 | Object Storage(Ceph) 기반 Raw 적재 우선. 변환 로직을 Argo Workflow DAG로 분리 |
| Y3 (2028) | ELT 완전 전환 | 모든 파이프라인이 ELT 기반. ETL 레거시 코드 제거. 온톨로지 변경 시 재변환 자동화 |

### 4.5.2 ELT 파이프라인 상세

ETL(변환 후 적재) 대신 ELT(적재 후 변환) 방식을 채택한다. 원천 데이터를 먼저 Object Storage(Ceph RGW)에 원본 그대로 보존하고, 이후 필요에 따라 분석, 변환, KG 적재를 수행한다. 원본이 항상 보존되므로 온톨로지 변경 시 재처리가 가능하다.

```
Phase 1: Extract (수집)
  AIS 수신기 | 기상 API | S-100 해도 | 법규 DB | 위성 | CCTV | 레이더
     |
     v  Collection Adapters
     |  (NMEA / GRIB2 / S-100 / RTSP / REST / Kafka)
     |
Phase 2: Load (적재 -- "일단 올려라, 처리는 나중에")
     |
     v  Object Storage (Ceph RGW)
     |  raw/{source}/{yyyy-mm-dd}/
     |
Phase 3: Metadata Extraction (메타데이터 자동 추출)
     |
     v  Auto Metadata Extractor
     |  EXIF | GPS 좌표 | 파일 속성 | 타임스탬프
     |
Phase 4: Content Analysis (콘텐츠 분석)
     |
     +-- PaddleOCR (한국어 OCR, 문서/해도)
     +-- NER (엔티티 추출, BERT-based)
     +-- Relation Extraction (관계 추출)
     +-- Embedding Generation (nomic-embed-text, 768d)
     |
Phase 5: KG Loading (그래프 적재)
     |
     v  Neo4jBatchLoader
     |  UNWIND MERGE | batch=500 | 리니지 자동 기록
     v
  Neo4j (엔티티 + 관계 + 속성 + 인덱스 + 리니지)
```

### 4.5.3 Dual-Mode 처리

| 모드 | 대상 데이터 | 주기 | 기술 스택 |
|------|-----------|------|----------|
| **Batch** | 논문, 실험 결과, 사고 DB, 위성 영상, 시설 정보 | 시간/일/주 | Argo Workflow + Python |
| **Streaming** | AIS 위치, 기상 센서, VTS 레이더, CCTV 스트림 | 실시간 (ms~s) | Kafka + Python Consumer |

### 4.5.4 7개 CronJob 스케줄

| 파이프라인 | 스케줄 (cron) | 적재 엔티티 |
|----------|-------------|-----------|
| 논문 크롤링 | `0 2 * * 6` (매주 토 02:00) | Document, Author |
| 기상 수집 | `0 */3 * * *` (매 3시간) | WeatherObservation |
| 해양사고 | `0 4 * * *` (매일 04:00) | Incident, Vessel |
| 시설 데이터 | `0 3 1 * *` (매월 1일 03:00) | TestFacility |
| 관계 추출 | `0 5 * * 1` (매주 월 05:00) | Relationship (다형) |
| S-100 동기화 | `0 6 * * 3` (매주 수 06:00) | ChartFeature |
| 시설 실험 데이터 | 수동 트리거 | Experiment, Measurement |

---

## 4.6 시계열 데이터 통합 전략 (TimescaleDB)

> **현재 상태:** TimescaleDB vs InfluxDB 벤치마크 미완료 (TBD). 아래는 TimescaleDB 기준 설계안이며, 벤치마크 결과에 따라 조정될 수 있다.

### 4.6.1 시계열 데이터 유형

IMSP에서 시계열 저장이 필요한 데이터 유형은 다음과 같다.

| 데이터 유형 | 수집 주기 | 레코드/일 (예상) | 주요 쿼리 패턴 |
|------------|----------|----------------|---------------|
| **AIS 위치** | 2-30초 | 10M - 100M | 특정 선박의 시간 범위 궤적, 특정 영역 내 선박 집계 |
| **기상 관측** | 1-3시간 | 10K - 50K | 특정 해역 시간대별 기상 조건, 이상치 감지 |
| **센서 데이터** | 100ms - 1s | 1M - 10M | 센서별 시계열 트렌드, 이상 패턴 감지 |
| **조류/해류** | 10분 - 1시간 | 50K - 200K | 특정 항로 시간대별 해류 변화 |
| **수위** | 1분 - 10분 | 100K - 500K | 항구별 조위 예측, 선박 입출항 가능 시간 |

### 4.6.2 PostgreSQL 확장 기반 통합

TimescaleDB는 PostgreSQL 확장(Extension)으로 동작하므로, IMSP의 기존 PostgreSQL 14 인스턴스와 논리적으로 공존할 수 있다. 단, 운영 환경에서는 부하 격리를 위해 별도 인스턴스를 권장한다.

```
PostgreSQL 14 (기존)                    PostgreSQL 14 + TimescaleDB (신규)
+------------------+                    +---------------------------+
| keycloak DB      |                    | timeseries DB             |
| argo_workflows DB|                    |                           |
| imsp_metadata DB |                    | - hypertable: ais_positions |
+------------------+                    | - hypertable: weather_obs   |
       |                                | - hypertable: sensor_data   |
       | JDBC (5432)                    | - hypertable: ocean_current |
       |                                +---------------------------+
       |                                       |
       +---------- K8s Service ----------------+
                   (별도 인스턴스, 포트 분리)
```

**연차별 배포 전략:**

| 연차 | 구성 | 비고 |
|------|------|------|
| Y1 | 단일 PostgreSQL 인스턴스에 TimescaleDB 확장 | 개발/검증 환경, 데이터량 소규모 |
| Y2 | 전용 TimescaleDB 인스턴스 분리 | 프로덕션 부하 격리 |
| Y3+ | TimescaleDB HA (Patroni) | 고가용성 구성 |

### 4.6.3 데이터 보존 정책

시계열 데이터는 시간 경과에 따라 접근 빈도가 급격히 감소한다. 3-Tier 보존 정책으로 저장 비용을 최적화한다.

| Tier | 보존 기간 | 저장소 | 해상도 | 접근 지연 | 용도 |
|------|----------|--------|--------|----------|------|
| **Hot** | 7일 | TimescaleDB (SSD) | 원본 (Full resolution) | < 10ms | 실시간 모니터링, 최근 궤적 조회 |
| **Warm** | 90일 | TimescaleDB (HDD) + 압축 | 다운샘플링 (1분 평균) | < 100ms | 단기 분석, 트렌드 조회 |
| **Cold** | 1년+ | Object Storage (Ceph) 아카이브 | 시간별 집계 | < 10s | 장기 통계, 규정 준수용 보존 |

**자동 Tier 전환 정책:**

```sql
-- TimescaleDB Continuous Aggregate (Warm tier 자동 생성)
CREATE MATERIALIZED VIEW ais_positions_1min
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 minute', timestamp) AS bucket,
       mmsi,
       AVG(latitude) as avg_lat,
       AVG(longitude) as avg_lon,
       AVG(speed) as avg_speed,
       MAX(speed) as max_speed
FROM ais_positions
GROUP BY bucket, mmsi;

-- 7일 이후 원본 데이터 압축 (Warm 전환)
SELECT add_compression_policy('ais_positions', INTERVAL '7 days');

-- 90일 이후 Object Storage 이동 (Cold 전환, 외부 스크립트)
-- Argo CronWorkflow로 실행: 0 1 * * * (매일 01:00)
```

**Neo4j 연동:**
- TimescaleDB의 시계열 데이터는 Neo4j에 직접 저장하지 않음
- Neo4j에는 시계열 데이터의 메타 노드만 생성 (예: `(:AISTrack {mmsi, startTime, endTime, pointCount})`)
- 상세 시계열 조회 시 API가 TimescaleDB에 직접 쿼리
- 그래프 질의와 시계열 질의 결합이 필요한 경우, API 레이어에서 Join

---

## 4.7 데이터 리니지 (W3C PROV-O)

모든 데이터 변환 과정은 W3C PROV-O 표준으로 Neo4j에 기록된다. 8가지 이벤트 타입과 5단계 기록 레벨로 세밀도를 조정할 수 있다.

```
RawAsset (Object Storage)
  |
  | [:DERIVED_FROM]
  v
ProcessedAsset (변환 결과)
  |
  | [:GENERATED_BY]
  v
TransformActivity (Argo Task)
  |
  | [:USED]
  v
ProvenanceChain (전체 리니지 체인)
```

**8 EventTypes:** `INGEST`, `TRANSFORM`, `VALIDATE`, `MERGE`, `SPLIT`, `ENRICH`, `EXPORT`, `DELETE`

**5 RecordingLevels:** `NONE` / `MINIMAL` / `STANDARD` / `DETAILED` / `FULL`

---

> **다음 문서:** [5. 배포 아키텍처](./05-deployment-architecture.md)에서 Kubernetes 클러스터 구성, Helm/Kustomize 배포 전략, GitOps(ArgoCD) 운영을 상세히 기술한다.
