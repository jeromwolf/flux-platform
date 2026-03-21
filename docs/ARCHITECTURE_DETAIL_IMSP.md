# IMSP 상세 아키텍처 설계서

> 작성일: 2026-03-20 | 버전: v1.0
> 기준: strategy_5year_IMSP.md, architecture_flux_platform.md, RFP-보강_K8S_S100_전략.md

---

## 목차

1. [시스템 컨텍스트](#1-시스템-컨텍스트-system-context)
2. [시스템 아키텍처 개요 (5-Tier)](#2-시스템-아키텍처-개요-5-tier)
3. [컴포넌트 아키텍처](#3-컴포넌트-아키텍처)
4. [데이터 아키텍처](#4-데이터-아키텍처)
5. 배포 아키텍처 (Kubernetes) — 별도 파일
6. 보안 아키텍처 — 별도 파일
7. 데이터 흐름도 — 별도 파일
8. Suredata Lab 연동 아키텍처 — 별도 파일
9. 기술 스택 매트릭스 — 별도 파일
10. 관측성 아키텍처 — 별도 파일
11. AI/LLM 아키텍처 — 별도 파일
12. 설계 원칙 및 패턴 — 별도 파일
13. 연차별 아키텍처 진화 — 별도 파일
14. 디렉토리 구조 — 별도 파일

---

## 0. 용어 정의

IMSP 플랫폼에서 사용하는 핵심 용어를 아래와 같이 정의한다. 본 문서 전체에서 이 정의를 따른다.

| 용어 | 영문 | 정의 | 자산 관리 구분 |
|------|------|------|--------------|
| **자원** | Resource | 원천 데이터, 소스 코드, 서버 등 물리/논리적 개체 | 인프라 및 데이터 저장소 등 물리적 환경을 논리화한 것 |
| **자산** | Asset | 플랫폼에 등록되어 메타데이터가 관리되는 모든 유무형 자산 | 워크플로우 저작도구에서 사용 및 생산한 모든 항목 |
| **응용** | App | 워크플로우 내에서 호출되는 독립적 실행 프로그램/컨테이너. 1회성 실행 후 결과를 반환 | 실행 가능한 기능 자산 |
| **컴포넌트** | Component | 특정 기능을 수행하는 노드들의 논리적 묶음 | 재사용 가능한 모듈 |
| **어댑터** | Adapter | 외부 데이터/시스템 연동을 위한 전용 컴포넌트 | 데이터 수집 및 변환 자산 |
| **워크플로우** | Workflow | 서비스를 개발하기 위해 노드들을 연결하여 구성한 비즈니스 로직 | 저작도구에서 생산된 자산 |
| **서비스** | Service | 완성된 워크플로우를 통해 사용자에게 제공되는 최종 기능. 지속적으로 운용됨 | 배포 및 운영 가능한 상태의 최종 형태 |

> **응용 vs 서비스 구분:** 응용(App)은 1회성 실행(K8s Job)으로 결과를 반환하고 종료된다. 서비스(Service)는 K8s Deployment로 지속 운용되며, 서비스 포털을 통해 외부 사용자에게 공개된다.

### MDT-Ops (Maritime Digital Twin Operations)

IMSP는 해사 분야의 **DevOps/MLOps 개념을 적용한 MDT-Ops (Maritime Digital Twin Operations)** 프레임워크를 구현하는 플랫폼이다. MDT-Ops는 해사 서비스의 설계-개발-배포-운영 전체 라이프사이클을 자동화하고, 데이터/모델/워크플로우의 리니지를 통합 추적한다.

```
MDT-Ops 프레임워크
|
+-- Dev (개발)
|   +-- VueFlow 워크플로우 저작도구
|   +-- 커스텀 노드 개발 SDK (Antigravity/VS Code Extension)
|   +-- 지식그래프 기반 자산 라이브러리
|
+-- Data (데이터)
|   +-- ELT 파이프라인 (원본 보존 → AI 분석 → KG 적재)
|   +-- 멀티모달 자원 저장소 (Object Storage + Neo4j + TimescaleDB)
|   +-- W3C PROV-O 통합 리니지
|
+-- ML (모델)
|   +-- 도메인 특화 모델 레지스트리 (매년 5종)
|   +-- GPU 서빙 (Ollama → vLLM → Ray)
|   +-- 모델 리니지 (학습 → 배포 → 버전 추적)
|
+-- Ops (운영)
    +-- K8s 컨테이너 오케스트레이션
    +-- Argo Workflow DAG 실행
    +-- Prometheus/Grafana/Zipkin 관측성
    +-- 서비스 Pool 등록/공개 관리
```

## 1. 시스템 컨텍스트 (System Context)

IMSP는 해사 연구 및 서비스 개발을 지원하는 대화형 플랫폼으로, KRISO 내부 연구자, 민간 이용자(해운사/연구기관/공공), 외부 데이터 소스, Suredata Lab과 상호작용한다.

```
                          +------------------+
                          |  KRISO 내부 연구자  |
                          | (Internal Users)  |
                          +--------+---------+
                                   |
                          OIDC (Keycloak) / HTTPS
                                   |
                                   v
+----------------+        +------------------------------------------+        +------------------+
| 외부 데이터 소스  |        |              IMSP Platform               |        | 2차 이용자         |
|                |        |                                          |        | (External Users)  |
| - AIS 수신기    | -Raw-> | +----------+  +----------+  +--------+  | <-OIDC-| - 해운사           |
| - 기상 API     |        | | Gateway  |->| Service  |->| Data   |  |        | - 연구기관         |
| - S-100 해도   |        | |  Layer   |  |  Layer   |  |  Layer |  |        | - 공공기관         |
| - 법규 DB      |        | +----------+  +----------+  +--------+  |        +------------------+
| - 위성 영상    |        |                                          |
| - CCTV        |        |  [VueFlow Canvas] [Chat UI] [Portal]     |
| - 레이더       |        |  [Observability Dashboard] [Auth]        |
+----------------+        +-------------------+----------------------+
                                              |
                                     REST API (OpenAPI 3.0)
                                     + Webhook / Kafka
                                              |
                                              v
                          +----------------------------------+
                          |          Suredata Lab            |
                          |  - 데이터 수집/크롤링              |
                          |  - 데이터 마트 (PostgreSQL DW)    |
                          |  - AI 모델 서빙 (vLLM / Ray)     |
                          |  - DW 파이프라인 (Kafka + Spark)  |
                          +----------------------------------+
```

### 1.1 액터 설명

**KRISO 내부 연구자** — 플랫폼의 1차 이용자. VueFlow 워크플로우 캔버스를 통해 해사 서비스를 설계하고, 대화 인터페이스로 KG 탐색·질의를 수행한다. Keycloak OIDC로 인증하며, RBAC 정책에 따라 데이터 접근 권한이 제한된다.

**외부 데이터 소스** — AIS 수신기(NMEA 0183/2000), 기상 API(GRIB2), IHO S-100 해도, 법규 DB, 위성 영상(GeoTIFF), CCTV 스트림(RTSP), 레이더 영상이 포함된다. 각 소스는 Collection Adapter를 통해 MinIO에 Raw 적재된 후 ELT 파이프라인으로 처리된다.

**데이터 제공 기관 매핑:**

| 제공 기관 | 데이터 유형 | 연동 방식 | 주기 |
|----------|-----------|---------|------|
| 해수부 | 해사 법규, 항만 정보 | REST API | 일/주 |
| 해양조사원 | 조석·해류, 해저지형 | 파일 다운로드 (GML/HDF5) | 일/월 |
| 국립해양측위정보원 | GNSS 보정, 측위 데이터 | REST API | 실시간 |
| 기상청 | 기상 관측·예보 (GRIB2) | REST API | 매 3시간 |
| 해경 | 해양사고, VTS 레이더 | REST API / Kafka | 실시간/일 |
| 자율운항선박 실증센터 | AIS, 센서, CCTV | Kafka 스트림 | 실시간 |
| KRISO | 실험 데이터, 시설 정보 | 파일 업로드 / API | 수동/일 |

**Suredata Lab** — 협력사. 데이터 수집/크롤링, PostgreSQL DW, AI 모델 서빙, 파이프라인 인프라를 담당한다. IMSP와는 REST API(OpenAPI 3.0) + Webhook + Kafka로 연동한다. IMSP는 KG 질의·리니지·온톨로지 스키마 API를 제공하고, Suredata는 추출 엔티티·모델 자산·원천 데이터를 IMSP에 등록한다.

**2차 이용자 (서비스 사용자)** — 5가지 유형으로 세분화된다:
- **해양 공무원**: 해사 정책 수립·집행을 위한 데이터 분석 및 시각화 활용
- **해운사**: 해상교통 분석, 항로 최적화, 안전 관리 서비스 이용
- **어민**: 어장 정보, 기상·해상 상태 조회 서비스 이용
- **해양레저 사용자**: 해양 안전 정보, 기상 예보 서비스 이용
- **해사 연구자**: 해사 데이터 탐색, 분석 모델 개발, 워크플로우 활용

서비스 포털을 통해 승인된 기능에 접근하며, Keycloak OIDC + 멀티테넌트 RBAC로 격리된다.

### 1.2 주요 인터페이스

| 인터페이스 | 프로토콜 | 포트 | 인증 |
|-----------|---------|------|------|
| 내부 연구자 → IMSP | HTTPS / WebSocket | 443 | Keycloak OIDC |
| 2차 이용자 → IMSP | HTTPS | 443 | Keycloak OIDC (별도 Realm) |
| 외부 소스 → IMSP | HTTPS / NMEA / RTSP | 443 / 8001 | API Key |
| IMSP → Suredata Lab | HTTPS / Kafka | 443 / 9092 | mTLS + API Key |
| IMSP → Suredata Lab (AI 서빙) | HTTPS (gRPC) | 443 | JWT Bearer |

---

## 2. 시스템 아키텍처 개요 (5-Tier)

IMSP는 Presentation → Gateway → Service → Data → Infrastructure의 5계층 구조로 설계된다. 각 계층은 독립 배포 단위(Kubernetes Deployment/StatefulSet)로 수평 확장 가능하다.

```
+-----------------------------------------------------------------------------+
|                          PRESENTATION TIER                                  |
|                                                                             |
|  +--------------+  +-------------+  +--------------+  +------------------+ |
|  | VueFlow       |  | 서비스 포털   |  | 관측성         |  | 대화 인터페이스    | |
|  | 워크플로우     |  | (2차 이용자)  |  | 대시보드        |  | (글로벌 + 노드별)  | |
|  | 캔버스         |  |              |  | (Grafana)     |  |                  | |
|  +--------------+  +-------------+  +--------------+  +------------------+ |
|                                                                             |
|  Vue 3 + VueFlow + TypeScript | Keycloak JS Adapter | WebSocket Client     |
+-----------------------------------------------------------------------------+
|                          API GATEWAY TIER                                   |
|                                                                             |
|  +---------+  +----------------+  +----------+  +-----------+  +--------+  |
|  | FastAPI  |  | Keycloak       |  | Rate     |  | WebSocket |  | CORS   |  |
|  | Router   |  | OIDC Middleware|  | Limiter  |  | Handler   |  |        |  |
|  +---------+  +----------------+  +----------+  +-----------+  +--------+  |
|                                                                             |
|  OpenAPI 3.0 | JWT Validation | Reverse Proxy (Nginx Ingress)               |
+-----------------------------------------------------------------------------+
|                          SERVICE TIER                                       |
|                                                                             |
|  +------------------+ +---------------+ +--------------+ +--------------+  |
|  |   KG Engine       | | Agent Runtime | | Workflow     | | Domain       |  |
|  |   (core/kg/)      | | (agent/)      | | Engine       | | Plugins      |  |
|  |                   | |               | | (Argo)       | | (maritime/)  |  |
|  | - Text2Cypher     | | - Orchestrator| | - DAG 실행    | | - Ontology   |  |
|  | - GraphRAG        | | - A2A / MCP   | | - 노드 실행   | | - NLP 사전   |  |
|  | - QualityGate     | | - Sub-agents  | | - 스케줄링    | | - 크롤러     |  |
|  | - ELT Pipeline    | | - Skills      | |              | | - S-100      |  |
|  | - Lineage (PROV-O)| | - Memory      | |              | |              |  |
|  | - RBAC            | | - LLM Failover| |              | |              |  |
|  +------------------+ +---------------+ +--------------+ +--------------+  |
|                                                                             |
|  FastAPI + Python 3.10+ | Async / await | Dependency Injection              |
+-----------------------------------------------------------------------------+
|                          DATA TIER                                          |
|                                                                             |
|  +---------+  +-------+  +------------+  +-------------+  +----------+     |
|  | Neo4j   |  | MinIO |  | PostgreSQL |  | TimescaleDB |  | Redis    |     |
|  | 5.x CE  |  | (S3)  |  |    14      |  | / InfluxDB  |  |   7      |     |
|  |         |  |       |  |            |  |             |  |          |     |
|  | - Graph |  | - Raw |  | - Auth     |  | - AIS 궤적   |  | - 캐시   |     |
|  | - Vector|  | - S100|  | - Workflow |  | - 기상 시계열 |  | - Queue  |     |
|  | - Spatial|  | - 영상|  | - Metadata |  |             |  |          |     |
|  +---------+  +-------+  +------------+  +-------------+  +----------+     |
|                                                                             |
|  Bolt (7687) | S3 API (9000) | JDBC (5432) | SQL (5432) | RESP (6379)      |
+-----------------------------------------------------------------------------+
|                          INFRASTRUCTURE TIER                                |
|                                                                             |
|  +-----------+  +------------+  +--------+  +----------+  +--------------+ |
|  | Kubernetes |  | Prometheus |  | Zipkin |  | Keycloak |  | ArgoCD       | |
|  | (K8s)      |  | + Grafana  |  |        |  |   SSO    |  | (GitOps)     | |
|  +-----------+  +------------+  +--------+  +----------+  +--------------+ |
|                                                                             |
|  Helm + Kustomize | Nginx Ingress | cert-manager (TLS) | Harbor (Registry)  |
+-----------------------------------------------------------------------------+
```

### 2.1 Presentation Tier

Presentation Tier는 Vue 3 기반 SPA(Single Page Application)로 구성된다. **VueFlow 워크플로우 캔버스**는 6종 노드(Trigger, Action, Connector, Control, Transform, Special)를 드래그앤드롭으로 조합해 해사 서비스 워크플로우를 시각적으로 저작하는 핵심 UI다. 노드별 대화창이 우측 패널로 열려, 해당 노드의 실행 결과를 LLM과 대화하며 검토할 수 있다.

**서비스 포털**은 2차 이용자(해운사, 민간 연구기관)가 접근하는 별도 라우트로, 승인된 서비스 목록 조회·이용 신청·데이터 탐색 기능을 제공한다. **관측성 대시보드**는 Grafana iframe을 임베드해 시스템 상태, KG 파이프라인 처리량, 에이전트 호출 지연 등을 실시간 모니터링한다.

**대화 인터페이스**는 글로벌(플랫폼 전체)과 노드별(워크플로우 노드 컨텍스트) 두 가지 모드로 동작한다. WebSocket을 통해 Server-Sent Events 방식으로 LLM 스트리밍 응답을 수신하며, 대화 히스토리는 Agent Memory에 영속화된다.

### 2.2 API Gateway Tier

Gateway Tier는 모든 외부 트래픽의 진입점이다. **Nginx Ingress**가 TLS 종단 및 경로 기반 라우팅을 담당하고, **FastAPI Router**가 OpenAPI 3.0 명세로 REST 엔드포인트를 노출한다. **Keycloak OIDC Middleware**는 모든 요청의 JWT를 검증하고 사용자 역할(role)을 추출해 서비스 계층으로 전달한다.

**Rate Limiter**는 Redis를 백엔드로 사용하며, 테넌트·사용자·엔드포인트 단위로 요청 횟수를 제한한다. **WebSocket Handler**는 대화 인터페이스와 실시간 파이프라인 진행 상황을 위한 양방향 채널을 유지한다. 모든 요청은 Zipkin으로 분산 추적된다.

### 2.3 Service Tier

Service Tier는 플랫폼의 핵심 비즈니스 로직을 담는 계층이다. **KG Engine**은 자연어 질의를 Cypher로 변환하고, ELT 파이프라인으로 데이터를 적재하며, W3C PROV-O 기반 리니지를 추적한다. **Agent Runtime**은 Orchestrator-SubAgent 구조로 복합 질의를 분해·실행하며, MCP(Model Context Protocol)와 A2A(Agent-to-Agent) 프로토콜을 지원한다.

**Workflow Engine(Argo)**은 VueFlow에서 저작된 워크플로우를 DAG로 변환·실행한다. **Domain Plugins**는 해사 도메인 특화 기능(온톨로지, NLP 용어 사전, 크롤러, S-100 파서)을 플러그인 형태로 제공해, 향후 항만·선박·해양환경 등 도메인 확장 시 플러그인 추가만으로 대응할 수 있다.

### 2.4 Data Tier

Data Tier는 용도별로 최적화된 5개 저장소로 구성된다. **Neo4j**가 KG(그래프+벡터+공간 인덱스)의 중심이며, **MinIO**가 원천 데이터 원본을 S3 호환 API로 보존한다. **PostgreSQL**은 Keycloak 인증 백엔드와 워크플로우 메타데이터를 담당하고, **TimescaleDB**(또는 InfluxDB, 벤치마크 후 확정)가 AIS 궤적·기상 시계열 데이터의 시간 범위 쿼리를 최적화한다. **Redis**는 잡 큐(BullMQ 호환)와 세션 캐시로 활용된다.

### 2.5 Infrastructure Tier

Infrastructure Tier는 플랫폼 운영 기반이다. **Kubernetes**가 모든 서비스를 컨테이너로 오케스트레이션하며, **Helm + Kustomize**로 환경별(dev/staging/prod) 배포 구성을 관리한다. **Prometheus + Grafana**가 메트릭 수집·시각화를, **Zipkin**이 분산 추적을 담당한다. **Keycloak**은 SSO 서버로 모든 Realm의 인증·인가를 처리하고, **ArgoCD**가 GitOps 방식으로 배포 상태를 Git 저장소와 동기화한다.

---

## 3. 컴포넌트 아키텍처

### 3.1 KG Engine (core/kg/) — 모듈 의존성

```
TextToCypherPipeline
  |
  +-- NLParser ---------> TermDictionary (Protocol)
  |                           +-- maritime_terms (도메인 구현)
  |
  +-- QueryGenerator -------> StructuredQuery -> GeneratedQuery
  |       |
  |       +-- CypherBuilder (Fluent API)
  |               +-- SecureCypherBuilder (RBAC WHERE 주입)
  |                       +-- RBACPolicy ---------> Neo4j RBAC 그래프
  |
  +-- CypherValidator (6가지 검증)
  |     - syntax: 파서 기반 구문 검증
  |     - injection: SQL/Cypher 인젝션 패턴 탐지
  |     - schema: 레이블/관계 타입 존재 여부
  |     - param: $param 사용 강제
  |     - complexity: 노드 수 상한 (default: 10000)
  |     - readonly: 읽기 전용 모드 enforce
  |
  +-- CypherCorrector (규칙 기반 교정)
  |     - 오타 수정, 레이블 대소문자, 파라미터 변환
  |
  +-- HallucinationDetector (온톨로지 기반)
        - 존재하지 않는 레이블/관계 탐지

Ontology Framework (kg/ontology/core.py)
  +-- ObjectTypeDefinition (엔티티 정의)
  +-- LinkTypeDefinition (관계 정의)
  +-- PropertyDefinition (속성 정의)
  +-- FunctionRegistry (함수 등록)

ELT Pipeline (kg/etl/)
  +-- RecordValidator -------> ValidationRule
  +-- TransformStep
  |     - TextNormalizer (한국어 정규화)
  |     - DateTimeNormalizer (ISO 8601)
  |     - IdentifierNormalizer (IMO/MMSI)
  +-- Neo4jBatchLoader (UNWIND MERGE, batch=500)
  +-- DLQManager (Dead Letter Queue -> MinIO)
  +-- LineageRecorder -------> LineagePolicy
        +-- LineageNode / LineageEdge / LineageGraph (W3C PROV-O)
        +-- 8 EventTypes, 5 RecordingLevels

EntityResolution (kg/entity_resolution/)
  +-- ExactMatcher (정규화 문자열 비교)
  +-- FuzzyMatcher (Jaro-Winkler, threshold=0.80)
  +-- EmbeddingMatcher (cosine similarity, threshold=0.85)

n10s / Neosemantics (kg/n10s/)
  +-- N10sImporter (OWL -> Neo4j)
  +-- OWLExporter (Neo4j -> OWL)

Embeddings (kg/embeddings/)
  +-- OllamaEmbedder (nomic-embed-text, 768d)

QualityGate (kg/quality_gate.py)
  +-- NodeCoverage, RelationCoverage, PropertyCompleteness
  +-- DuplicateRate, VectorIndexCoverage, IsolatedNodeRate
```

### 3.2 API 엔드포인트 (현재 구현 + 계획)

**현재 구현 (core/kg/api/):**

```
GET  /metrics                                 [no auth]  Prometheus 텍스트 포맷
GET  /api/v1/health                           [no auth]  Neo4j 연결 확인
GET  /api/v1/subgraph?label=&limit=           [auth]     서브그래프 조회
GET  /api/v1/neighbors?nodeId=               [auth]     이웃 노드 탐색
GET  /api/v1/search?q=&limit=                [auth]     풀텍스트 검색
GET  /api/v1/schema                           [auth]     레이블/관계타입 + 개수
POST /api/v1/query                            [auth]     한국어 NL -> Cypher -> 실행
GET  /api/v1/lineage/{type}/{id}              [auth]     전체 리니지 그래프
GET  /api/v1/lineage/{type}/{id}/ancestors    [auth]     상위 리니지
GET  /api/v1/lineage/{type}/{id}/descendants  [auth]     하위 리니지
GET  /api/v1/lineage/{type}/{id}/timeline     [auth]     시간순 이벤트
POST /api/v1/etl/trigger                      [auth]     ETL 파이프라인 실행
POST /api/v1/etl/webhook/{source}             [auth]     외부 웹훅 트리거
GET  /api/v1/etl/status/{run_id}              [auth]     실행 상태 조회
GET  /api/v1/etl/history?limit=              [auth]     실행 이력
GET  /api/v1/etl/pipelines                    [auth]     등록된 파이프라인 목록
```

**계획 (Suredata Lab 연동 API v1):**

```
POST /api/v1/ingest/raw                    원천 데이터 등록 (-> MinIO)
POST /api/v1/ingest/metadata               메타데이터 노드 생성/수정
POST /api/v1/ingest/entities               추출 엔티티 KG 로딩
POST /api/v1/ingest/model-registry         AI 모델 자산 등록
GET  /api/v1/query/nl?q={query}            자연어 -> Text2Cypher -> 응답
GET  /api/v1/query/cypher                  Cypher 직접 실행
GET  /api/v1/lineage/{assetId}             리니지 체인 조회
GET  /api/v1/ontology/schema               온톨로지 스키마 조회
GET  /api/v1/ontology/search?q=            온톨로지 시맨틱 검색
POST /api/v1/model/invoke                  Suredata 모델 서빙 프록시
```

### 3.3 Agent Runtime (agent/ — 이식 예정)

```
+-----------------------------------------------+
|             Orchestrator Agent                 |
|       (글로벌 대화 통합, 의도 분류)               |
+----------------+------------------+------------+
                 |  A2A Protocol    |
     +-----------v--+  +-----------v--+  +-------v-------+
     | KG Agent      |  | Workflow     |  | Analytics     |
     |               |  | Agent        |  | Agent         |
     | - Text2Cypher |  | - 노드 추천   |  | - 시각화 생성  |
     | - GraphRAG    |  | - 자동 생성   |  | - 대시보드     |
     +---------------+  +--------------+  +---------------+
                 |  MCP Protocol    |
     +-----------v------------------v------------------v---+
     |                    Agent Tools                      |
     |  KG Query | Workflow CRUD | File System             |
     |  Data Ingest | Visualization | External API         |
     +------------------------------------------------------+
                 |                  |
     +-----------v--+  +-----------v--+  +---------------+
     |  Memory       |  |  Skills      |  | LLM Provider  |
     |  - 단기 (Redis)|  |  - 스킬팩    |  | - Ollama      |
     |  - 장기 (Neo4j)|  |  - Registry  |  | - vLLM        |
     +---------------+  +--------------+  | + Failover     |
                                          +---------------+
```

에이전트 런타임은 ReAct(Reasoning + Acting), Pipeline, Batch 세 가지 실행 모드를 지원한다. **Orchestrator**는 사용자 의도를 분류해 적합한 Sub-agent로 라우팅하고, Sub-agent 간 A2A 프로토콜로 컨텍스트를 전달한다. MCP는 표준 도구 호출 인터페이스로, 외부 MCP 서버(파일 시스템, 데이터베이스, 외부 API)를 동적으로 연결한다. LLM Provider는 Ollama(온프레미스) 우선, OpenAI/Anthropic(폴백) 3단계 Failover를 지원한다.

### 3.4 Workflow Engine — 6 노드 타입

| # | 노드 타입 | 역할 | 예시 |
|---|-----------|------|------|
| 1 | **Trigger** | 워크플로우 실행 시점 정의 | Manual, Cron, Webhook, App Event, Error Event |
| 2 | **Action** | 외부 시스템 조작 및 부수효과 | HTTP/GraphQL, Messaging, File I/O, DB CRUD, Docker |
| 3 | **Connector** | 외부 시스템 연동 | SaaS/API, SFTP, SQL DB, OAuth2/OIDC |
| 4 | **Control** | 흐름 제어 | If/Switch, Merge, Split in Batches, Wait, Error |
| 5 | **Transform** | 해사 데이터 변환 | AIS NMEA, Radar, S-100, GRIB2, PDF/OCR, VHF/STT |
| 6 | **Special** | AI/LLM 고급 기능 | Skills, MCP, LLM Calls, YOLO/OCR/NER 모델 |

VueFlow 캔버스에서 저작된 워크플로우 JSON은 Argo Workflow DAG YAML로 변환되어 Kubernetes에서 실행된다. 각 노드는 독립 Pod로 실행되며 노드 간 데이터는 Argo Artifact(MinIO)로 전달된다.

#### 3.4.1 1차년도 노드 5종 개발 목록

RFP 1차년도 결과물로 아래 5종 노드를 개발한다 (해사서비스 특화 2종 포함).

| # | 노드명 | 카테고리 | 해사 특화 | 입력 | 출력 | 설명 |
|---|--------|---------|:--------:|------|------|------|
| 1 | **AIS 데이터 수집** | Connector | **Yes** | AIS 수신기 주소, 필터 조건 | AIS 메시지 스트림 (NMEA → JSON) | NMEA 0183/2000 프로토콜 AIS 데이터 수집·파싱·저장. 실시간 스트림 및 배치 모드 지원 |
| 2 | **S-100 해도 파서** | Transform | **Yes** | S-100 GML 파일 경로 | 파싱된 해도 피처 (GeoJSON) | IHO S-101 ENC, S-111 해류, S-127 VTS 등 S-100 표준 파일 파싱 및 KG 적재 |
| 3 | **데이터 변환** | Transform | No | 원천 데이터 (CSV/JSON/XML) | 정규화된 레코드 | 텍스트 정규화, 날짜 표준화(ISO 8601), 식별자 변환(IMO/MMSI), 임베딩 생성 |
| 4 | **KG 질의** | Action | No | 자연어 질문 또는 Cypher | 쿼리 결과 (JSON) | Text2Cypher 파이프라인 호출, 결과 반환. 파라미터로 실행 모드(parse_only/execute) 선택 |
| 5 | **시각화 출력** | Action | No | 데이터셋 (JSON/GeoJSON) | 차트/지도/테이블 렌더링 | ECharts 기반 차트, Leaflet 기반 지도, AG Grid 테이블. 대시보드 패널로 임베드 가능 |

> **2차년도 추가 예정 노드:** 기상 수집(GRIB2), OCR 문서 처리, 관계 추출(NER+RE), 이상 탐지, 워크플로우 트리거(Cron/Webhook)

### 3.5 RAG Engine (rag/ — 이식 예정) — 5 GraphRAG Retriever

| # | Retriever | 전략 | 적합한 질문 유형 |
|---|-----------|------|----------------|
| 1 | **Vector Retriever** | 임베딩 유사도 검색 | "선박 충돌 관련 논문" |
| 2 | **VectorCypher Retriever** | 벡터 검색 + 그래프 순회 | "부산항 관련 연구 및 주변 시설" |
| 3 | **Text2Cypher Retriever** | NL -> Cypher -> KG 직접 조회 | "2024년 해양사고 건수는?" |
| 4 | **Hybrid Retriever** | 벡터 + 그래프 점수 결합 | "울산항 위험물 운반선 규정" |
| 5 | **ToolsRetriever (Agentic)** | LLM이 전략 자동 선택 | 복합 질문 (자동 라우팅) |

---

## 4. 데이터 아키텍처

### 4.1 데이터베이스 선정 및 역할

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

### 4.2 Neo4j 스키마 — 3계층 온톨로지 아키텍처

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
|    - Vector:    768d / 512d / 1024d 임베딩               |
|    - Spatial:   point() 좌표                             |
|    - Fulltext:  한국어/영어 전문 검색                     |
|    - Range:     시간 범위 쿼리                            |
|    - RBAC:      접근 제어 필터용                          |
+----------------------------------------------------------+
```

### 4.3 온톨로지 재설계 (v1 목표: ~40 엔티티)

기존 127 엔티티는 데이터 소스 확인 없이 정의된 이론적 구조로, 실제 수집 가능한 데이터와 불일치한다. KRISO 요구 기반으로 완전 재설계한다.

**설계 원칙 6가지:**

1. **Data-Driven** — 확인된 데이터 소스가 있는 엔티티만 정의
2. **Maritime Traffic First** — AIS 기반 해상교통 우선 구현
3. **Temporal** — 모든 동적 엔티티에 validFrom / validTo 적용
4. **ELT-Friendly** — Raw -> Metadata -> Entity 3단계 리니지 추적
5. **S-100 Compatible** — IHO S-100 표준과 1:1 매핑 경로 확보
6. **Multi-Layer** — 정적 지식 / 동적 관측 / 파생 인사이트 분리

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

**S-100 통합 레이어 (~33 엔티티, 2차년도 추가):**

| 표준 | 내용 | 엔티티 수 |
|------|------|-----------|
| S-101 ENC | Electronic Navigational Chart | 10 |
| S-104 | Water Level | 4 |
| S-111 | Surface Currents | 4 |
| S-127 | VTS (Vessel Traffic Service) | 8 |
| S-411 | Sea Ice | 4 |
| S-412 | Weather Forecast | 3 |

**연차별 온톨로지 확장 경로:**

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

### 4.4 멀티모달 데이터 저장 전략

**원칙: Neo4j는 메타데이터만 저장. 원천 데이터(바이너리/대용량)는 Object Storage (Ceph)에 보관하고 `storagePath` 속성으로 참조한다.**

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

### 4.5 ELT 파이프라인

ETL(변환 후 적재) 대신 ELT(적재 후 변환) 방식을 채택한다. 원천 데이터를 먼저 Object Storage (Ceph RGW)에 원본 그대로 보존하고, 이후 필요에 따라 분석·변환·KG 적재를 수행한다. 원본이 항상 보존되므로 온톨로지 변경 시 재처리가 가능하다.

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

**Dual-Mode 처리:**

| 모드 | 대상 데이터 | 주기 | 기술 스택 |
|------|-----------|------|----------|
| **Batch** | 논문, 실험 결과, 사고 DB, 위성 영상, 시설 정보 | 시간/일/주 | Argo Workflow + Python |
| **Streaming** | AIS 위치, 기상 센서, VTS 레이더, CCTV 스트림 | 실시간 (ms~s) | Kafka + Python Consumer |

**7개 CronJob 스케줄:**

| 파이프라인 | 스케줄 (cron) | 적재 엔티티 |
|----------|-------------|-----------|
| 논문 크롤링 | `0 2 * * 6` (매주 토 02:00) | Document, Author |
| 기상 수집 | `0 */3 * * *` (매 3시간) | WeatherObservation |
| 해양사고 | `0 4 * * *` (매일 04:00) | Incident, Vessel |
| 시설 데이터 | `0 3 1 * *` (매월 1일 03:00) | TestFacility |
| 관계 추출 | `0 5 * * 1` (매주 월 05:00) | Relationship (다형) |
| S-100 동기화 | `0 6 * * 3` (매주 수 06:00) | ChartFeature |
| 시설 실험 데이터 | 수동 트리거 | Experiment, Measurement |

### 4.6 데이터 리니지 (W3C PROV-O)

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

> **이 문서는 섹션 1-4를 다룹니다. 섹션 5-14는 `ARCHITECTURE_DETAIL_IMSP_PART2.md`에 계속됩니다.**

# IMSP 아키텍처 상세 설계서 - Part 2

**문서 버전:** 1.0
**작성일:** 2026-03-20
**작성자:** InsightMining
**대상:** IMSP 플랫폼 개발 팀, Suredata Lab 협력 팀, KRISO 담당자

> 이 문서는 IMSP 아키텍처 설계서의 Part 2로, 배포·보안·데이터 흐름·협력 연동·기술 스택을 다룹니다.
> Part 1 (Core KG Engine, Ontology, NLP, ETL, API)은 별도 문서를 참조하십시오.

---

## 목차

- [5. 배포 아키텍처 (Kubernetes)](#5-배포-아키텍처-kubernetes)
- [6. 보안 아키텍처](#6-보안-아키텍처)
- [7. 데이터 흐름도](#7-데이터-흐름도)
- [8. Suredata Lab 연동 아키텍처](#8-suredata-lab-연동-아키텍처)
- [9. 기술 스택 매트릭스](#9-기술-스택-매트릭스)

---

## 5. 배포 아키텍처 (Kubernetes)

### 5.1 클러스터 토폴로지

1차년도는 Docker Compose 기반 로컬 개발 환경으로 시작하고, 2차년도부터 Helm-managed Kubernetes로
전환한다. 아래는 목표 K8s 클러스터 토폴로지다.

```
KRISO K8s Cluster
|
+-- Namespace: maritime-platform -----------------------------------------------
|   |
|   +-- Deployment: maritime-api (FastAPI)
|   |   +-- Replicas: 2~5 (HPA, CPU threshold 70%)
|   |   +-- Resources: 512Mi~2Gi mem, 0.5~2 CPU
|   |   +-- Probes: /api/health (liveness + readiness)
|   |   +-- ConfigMap: NEO4J_URI, APP_API_KEY, JWT_SECRET
|   |   \-- SecretRef: Vault (DB 패스워드, LLM API 키)
|   |
|   +-- Deployment: maritime-frontend (Vue 3 + VueFlow)
|   |   +-- Replicas: 2~3 (HPA)
|   |   +-- Nginx static serving (gzip, cache-control)
|   |   \-- ConfigMap: API_BASE_URL, KEYCLOAK_URL
|   |
|   +-- StatefulSet: neo4j (Neo4j 5.26 CE)
|   |   +-- Replicas: 1 (CE 단일 인스턴스 제한)
|   |   +-- PVC: 500Gi (StorageClass: ssd-fast)
|   |   +-- Resources: 4~8Gi mem, 2~4 CPU
|   |   +-- Plugins: APOC, n10s (Neosemantics)
|   |   \-- Probes: bolt://7687 TCP check
|   |
|   +-- Deployment: ollama-server (LLM Serving)
|   |   +-- nodeSelector: gpu-type=a100
|   |   +-- tolerations: nvidia.com/gpu NoSchedule
|   |   +-- Resources: 16Gi mem, 4 CPU, 1x nvidia.com/gpu
|   |   +-- InitContainer: model-init (모델 다운로드 및 캐시)
|   |   \-- Volume: nfs-shared (모델 파일 공유)
|   |
|   \-- CronJob: etl-pipelines (7개)
|       +-- papers-crawler     (Sat 02:00 KST)
|       +-- weather-collector  (매 3시간)
|       +-- accident-crawler   (Daily 04:00 KST)
|       +-- facility-sync      (매월 1일)
|       +-- relation-extractor (Mon 05:00 KST)
|       +-- s100-sync          (Wed 06:00 KST)
|       \-- experiment-loader  (Manual trigger, Argo Workflow)
|
|   +-- Istio Sidecar Injection: enabled (2차년도)
|   |   +-- mTLS: STRICT mode
|   |   +-- VirtualService / DestinationRule per service
|
+-- Namespace: monitoring ------------------------------------------------------
|   |
|   +-- Deployment: prometheus
|   |   \-- Scrape targets: maritime-api, neo4j-exporter, node-exporter,
|   |                       kube-state-metrics, ollama-exporter
|   |
|   +-- Deployment: grafana
|   |   \-- Dashboards: K8s health, Neo4j performance, API latency, ETL status
|   |
|   +-- Deployment: alertmanager
|   |   \-- Rules: disk > 80%, P99 > 5s, ETL failure, GPU utilization
|   |
|   +-- DaemonSet: node-exporter
|   +-- Deployment: kube-state-metrics
|   +-- Deployment: neo4j-exporter (neo4j-prometheus-exporter)
|   \-- Deployment: zipkin (분산 추적 수집기)
|
\-- Namespace: auth -------------------------------------------------------------
    |
    \-- Deployment: keycloak
        +-- PostgreSQL backend (별도 PVC 10Gi)
        +-- Realm: maritime-platform
        +-- Clients: maritime-api, maritime-frontend, argo-workflow
        \-- Roles: Admin, InternalResearcher, ExternalResearcher, Developer, Public
```

### 5.2 Storage Classes

| StorageClass | 용도 | 성능 특성 | 대표 PVC |
|-------------|------|----------|---------|
| `ssd-fast` | Neo4j 데이터, 벡터 인덱스 | IOPS 보장, 지연 < 1ms | 500Gi |
| `hdd-bulk` | S-100 원본, HDF5, OCR 원문 | 대용량, 순차 읽기 최적화 | 2Ti |
| `nfs-shared` | 모델 파일, 공유 설정 | ReadWriteMany, 멀티 Pod 공유 | 100Gi |

Neo4j Community Edition은 단일 인스턴스 제한으로 읽기 복제본(Read Replica)을 지원하지 않는다.
고가용성 요구가 발생하면 Enterprise Edition으로 업그레이드하거나 Neo4j Aura 검토가 필요하다.

### 5.3 Helm 차트 구조

```
helm/maritime-platform/
|-- Chart.yaml                    # 차트 메타데이터 (버전, 의존성)
|-- values.yaml                   # 기본값 (전체 환경 공통)
|-- values-dev.yaml               # 개발: 샘플 데이터, GPU 미사용
|-- values-staging.yaml           # 스테이징: 운영 데이터 복사본
|-- values-prod.yaml              # 운영: A100 GPU, 실 데이터
|-- values-kriso.yaml             # KRISO 인프라 전용 오버라이드
\-- templates/
    |-- neo4j/
    |   |-- statefulset.yaml      # Neo4j StatefulSet + PVC claim
    |   |-- service.yaml          # Bolt 7687 + HTTP 7474
    |   |-- configmap.yaml        # neo4j.conf 커스텀 설정
    |   \-- pvc.yaml              # 데이터 볼륨 선언
    |-- api/
    |   |-- deployment.yaml       # FastAPI Deployment
    |   |-- hpa.yaml              # CPU 70% 기반 오토스케일링
    |   \-- configmap.yaml        # 환경변수 및 앱 설정
    |-- ollama/
    |   |-- deployment.yaml       # GPU Deployment + InitContainer
    |   \-- service.yaml          # 11434 포트 (내부 통신만)
    |-- etl/
    |   \-- cronjobs.yaml         # 7개 CronJob 정의 (스케줄/리소스 포함)
    |-- monitoring/
    |   |-- prometheus.yaml       # Prometheus + ServiceMonitor CRD
    |   \-- grafana.yaml          # 대시보드 ConfigMap (JSON)
    |-- ingress.yaml              # Kong/Nginx Ingress + TLS 설정
    |-- networkpolicy.yaml        # Pod 간 통신 제어 (최소 권한)
    \-- external-secrets.yaml     # External Secrets Operator (Vault 연동)
```

배포 명령:

```bash
# KRISO 환경 최초 설치
helm install maritime . -f values-kriso.yaml --namespace maritime-platform

# 업그레이드 (새 이미지 태그 배포)
helm upgrade maritime . -f values-kriso.yaml --set api.image.tag=1.2.3

# 롤백
helm rollback maritime 2
```

### 5.4 CI/CD 파이프라인

```
+---- CI (GitLab CI) ---------------------------------------------------------+
|                                                                               |
|  +------+  +----------+  +-------------+  +------------+  +------+  +-----+ |
|  | Lint |->|Unit Tests|->|Integration  |->|Docker Build|->| Helm |->|Trivy| |
|  | ruff |  | pytest   |  | Tests       |  | multi-stage|  | Lint |  | CVE | |
|  | mypy |  | 1,095+건 |  | Neo4j Pod   |  | Python3.11 |  | Test |  |Scan | |
|  +------+  +----------+  +-------------+  +------------+  +------+  +--+--+ |
|                                                                        |      |
|                                                              +---------v----+ |
|                                                              |GitLab Registry| |
|                                                              |Push           | |
|                                                              |(KRISO 내부)   | |
|                                                              +---------------+ |
+-------------------------------------------------------------------------------+

+---- CD (ArgoCD / GitOps) ----------------------------------------------------+
|                                                                               |
|  +----------+      +----------+      +---------------------+                 |
|  |   dev    |      | staging  |      |        prod         |                 |
|  |          |      |          |      |                     |                 |
|  | 자동배포  +----->| 수동     +----->| PM 승인 게이트       |                 |
|  | (main)   |      | 프로모션  |      | (approval required) |                 |
|  | 샘플데이터|      | (dev lead|      | 실 데이터, A100 GPU  |                 |
|  | GPU 없음  |      |  승인)   |      |                     |                 |
|  +----------+      +----------+      +---------------------+                 |
|                                                                               |
|  Rollback: ArgoCD 헬스체크 실패 시 자동 롤백 (5분 이내)                       |
|  GitOps: Helm values 변경 -> Git commit -> ArgoCD 자동 동기화                 |
+-------------------------------------------------------------------------------+
```

**브랜치 전략:**

| 브랜치 | 환경 | 배포 방식 | 승인 |
|--------|------|----------|------|
| `feature/*` | 없음 | PR 빌드만 | 자동 |
| `develop` | dev | 자동 배포 | 없음 |
| `main` | staging | 수동 프로모션 | Dev Lead |
| `release/*` | prod | 수동 프로모션 | PM + Dev Lead |

### 5.5 GPU 서빙 진화 경로

| Phase | 시기 | 서빙 엔진 | GPU | 처리량 | 비고 |
|-------|------|-----------|-----|--------|------|
| Phase 0 | Y1 | Ollama (CPU) | 없음 | ~5 req/min | GPU 조달 대기, 프로토타입 |
| Phase 1 | Y2 Q1-Q2 | Ollama | 1x A100 80G | ~30 req/min | 기본 서빙, 단일 요청 |
| Phase 2 | Y2 Q3 | vLLM | 1x A100 80G | ~100 req/min | Continuous Batching |
| Phase 3 | Y2 Q4 | vLLM + TP | 2x A100 80G | ~200 req/min | Tensor Parallelism |
| Phase 4 | Y3 | Ray + vLLM | A100/H200 클러스터 | ~500+ req/min | 분산 추론, 멀티 모델 |

### 5.6 Docker Compose -> K8s 전환 전략

**현재 (1차년도):** Docker Compose 5 서비스

```
infra/docker-compose.yml
+-- maritime-neo4j        (Neo4j 5.26 CE + APOC + n10s)
+-- maritime-api          (FastAPI/uvicorn, hot-reload)
+-- maritime-activepieces (워크플로우 -> Argo 전환 예정)
+-- maritime-postgres     (Activepieces 백엔드 + 로컬 DW)
\-- maritime-redis        (BullMQ 잡 큐, 세션 캐시)
```

**목표 (2차년도):** Helm-managed K8s

- 아키텍처 변경 없이 배포 환경만 마이그레이션 (Lift & Shift)
- 12-Factor App 준수: 환경변수 외부화, Stateless API 서버
- Named Volume -> PVC 전환 (ssd-fast 스토리지 클래스 적용)
- docker-compose.yml 로컬 개발 환경으로 유지 (개발자 DX 보존)

---

## 6. 보안 아키텍처

### 6.1 인증/인가 3계층 모델

IMSP는 이용자 유형에 따라 3개 보안 계층을 적용한다. 외부 이용자일수록 더 강한 격리와 제한을 받는다.

```
+----------------------------------------------------------------------+
|                     보안 아키텍처 3계층 모델                           |
|                                                                      |
|  Layer 2: 2차 이용자 (External Researcher / Public)                  |
|  +------------------------------------------------------------------+ |
|  | Authentication : Keycloak OIDC (소셜 로그인 허용)                  | |
|  | Authorization  : Read-only, 공개 데이터 + 서비스 포털 접근만        | |
|  | Isolation      : 공유 환경, Rate Limit 100 req/min                | |
|  | Data Access    : PUBLIC, INTERNAL 등급만                          | |
|  +------------------------------------------------------------------+ |
|                                                                      |
|  Layer 1: KRISO 내부 연구자 (Internal Researcher / Developer)        |
|  +------------------------------------------------------------------+ |
|  | Authentication : Keycloak OIDC + MFA (TOTP 또는 WebAuthn)        | |
|  | Authorization  : Read/Write/Execute (팀/프로젝트 RBAC)             | |
|  | Isolation      : 팀별 K8s Namespace, 전용 KG 접근 범위            | |
|  | Data Access    : PUBLIC ~ CONFIDENTIAL 등급                       | |
|  +------------------------------------------------------------------+ |
|                                                                      |
|  Layer 0: 데이터 제공자 (Suredata Lab / 외부 기관)                   |
|  +------------------------------------------------------------------+ |
|  | Authentication : API Key + IP Whitelist (CIDR 화이트리스트)        | |
|  | Authorization  : Write-only, Ingest API (/api/v1/ingest/*) 한정   | |
|  | Isolation      : 기관별 Object Storage 버킷 + KG 네임스페이스 분리          | |
|  | Data Access    : 쓰기 전용, 자기 기관 데이터만                     | |
|  +------------------------------------------------------------------+ |
+----------------------------------------------------------------------+
```

### 6.2 이중 RBAC 시스템

Keycloak SSO가 통합 인증 허브 역할을 하며, K8s RBAC와 Application RBAC가 병렬로 동작한다.

```
                    +---------------------------+
                    |     Keycloak SSO          |
                    |  (OIDC 토큰 발급 허브)     |
                    +------+----------+---------+
                           |          |
               +-----------+          +-----------+
               |                                  |
  +--------------------+            +-----------------------------+
  |   K8s RBAC          |            |   Application RBAC          |
  |   (인프라 접근 제어) |            |   (데이터 접근 제어)         |
  |                     |            |                             |
  | ServiceAccount      |            |  5 Roles:                   |
  | ClusterRole         |            |  - Admin (전체 접근)         |
  | RoleBinding         |            |  - InternalResearcher (R/W) |
  |                     |            |  - ExternalResearcher (R)   |
  | Pod / Service /     |            |  - Developer (API + Execute)|
  | Secret 접근 제어     |            |  - Public (공개 데이터만)   |
  |                     |            |                             |
  |                     |            |  5 Data Classifications:    |
  |                     |            |  1. PUBLIC                  |
  |                     |            |  2. INTERNAL                |
  |                     |            |  3. CONFIDENTIAL            |
  |                     |            |  4. RESTRICTED              |
  |                     |            |  5. TOP_SECRET              |
  +--------------------+            +-----------------------------+
```

**RBAC 강제 3개 지점 (Defense in Depth):**

```
HTTP Request
    |
    v [1] RBACPolicy.check_access()
    |      binary allow/deny
    |      Neo4j 그래프 순회: User->Role->DataClass
    |      실패 시 403 즉시 반환
    |
    v [2] augment_cypher_with_access()
    |      생성된 Cypher에 WHERE 절 주입
    |      WHERE dc.level <= user.maxAccessLevel
    |      데이터 등급 필터링 자동화
    |
    v [3] SecureCypherBuilder (쿼리 생성 단계)
    |      EXISTS 서브쿼리 구조 주입
    |      MATCH (u:User)-[:HAS_ROLE]->(r:Role)-[:CAN_ACCESS]->(dc:DataClass)
    |      SQL Injection 유사 패턴 사전 차단
    |
    v Neo4j 실행 (3중 필터링된 결과 반환)
```

### 6.3 네트워크 보안

| 보안 계층 | 기술 | 설명 |
|----------|------|------|
| NetworkPolicy | K8s NetworkPolicy | Neo4j는 maritime-api, etl-pipeline만 접근 허용 (Bolt 7687) |
| Service Mesh | Istio | mTLS 자동 적용, 트래픽 관리, Circuit Breaking, 서비스 간 인증 (2차년도 도입) |
| Pod Security | PodSecurityStandards `restricted` | root 실행 금지, 특권 컨테이너 금지, capability 제한 |
| TLS | cert-manager | Let's Encrypt (외부) 또는 KRISO 내부 CA (내부망) |
| Secret 관리 | External Secrets Operator | HashiCorp Vault 연동, GitOps 시크릿 관리 |
| 이미지 보안 | Trivy (CI 파이프라인) | CVE 자동 검출, CRITICAL 취약점 시 빌드 실패 |
| GitOps Secret | SOPS + age | 암호화된 시크릿을 Git에 안전하게 커밋 |
| Ingress | Kong Gateway / Nginx | TLS Termination, Rate Limiting, WAF 규칙 |

**NetworkPolicy 예시 (Neo4j 격리):**

```
Neo4j Pod (7687)
  |
  +-- ALLOW: maritime-api (label: app=maritime-api)
  +-- ALLOW: etl-pipeline (label: app=etl-pipeline)
  \-- DENY: 기타 모든 Pod 및 외부 접근
```

### 6.4 감사 로깅 (Dual Audit)

| 감사 계층 | 대상 이벤트 | 저장소 | 보존 기간 |
|----------|-----------|--------|---------|
| K8s Audit Log | API 서버 요청, Pod 생성/삭제, RBAC 변경 | 파일 (EFK 연동 예정) | 90일 |
| Application Lineage | KG 데이터 변경, Cypher 쿼리 실행, 데이터 출처 | Neo4j (LineageNode) | 영구 |
| Access Log | HTTP 요청/응답 (사용자, IP, 경로, 상태코드) | 구조화 JSON (stdout) | 30일 |
| ETL Audit | 수집 건수, 오류율, 데이터 품질 점수 | PostgreSQL (etl_audit 테이블) | 180일 |

4차년도 이후 EFK(Elasticsearch + Fluentd + Kibana) 스택으로 중앙 집중 로그 관리 전환 예정.

---

## 7. 데이터 흐름도

### 7.1 자연어 쿼리 흐름 (Text2Cypher Pipeline)

```
사용자: "부산항 근처에 정박 중인 대형 선박을 알려줘"
    |
    v HTTP POST /api/v1/query/nl
    |
    +-- Auth Middleware    (API Key 또는 JWT 검증)
    +-- Metrics Middleware (요청 시간 측정, Zipkin Span 시작)
    |
    v TextToCypherPipeline.process()
    |
    +-- Stage 1: NLParser.parse()
    |   |  규칙 기반 한국어 토큰화 (KoNLPy 또는 커스텀 토크나이저)
    |   |  TermDictionary 조회:
    |   |    "부산항" -> Port (신뢰도 0.99)
    |   |    "선박"   -> Vessel (신뢰도 0.97)
    |   |    "정박"   -> DOCKED_AT (신뢰도 0.93)
    |   |    "대형"   -> tonnage > threshold (필터)
    |   \-> StructuredQuery {
    |         entities: [Port("부산항"), Vessel],
    |         relationships: [DOCKED_AT],
    |         filters: [{field: tonnage, op: >, value: 50000}]
    |       }
    |
    +-- Stage 2: QueryGenerator.generate_cypher()
    |   \-> MATCH (p:Port {name: '부산항'})<-[:DOCKED_AT]-(v:Vessel)
    |        WHERE v.tonnage > 50000
    |        RETURN v.name, v.type, v.tonnage
    |        ORDER BY v.tonnage DESC LIMIT 20
    |
    +-- Stage 3: CypherValidator.validate()
    |   |  [1] 구문 검증  : Cypher 파서 AST 검증
    |   |  [2] 스키마 검증: Port, Vessel, DOCKED_AT 존재 여부
    |   |  [3] 속성 검증  : name, tonnage 유효한 속성
    |   |  [4] 타입 검증  : tonnage -> 숫자형 비교 적합
    |   |  [5] 보안 검증  : Injection 패턴 없음
    |   |  [6] 성능 검증  : Port.name 인덱스 활용 가능
    |   \-> ValidationResult { valid: true, score: 0.95, checks_passed: 6/6 }
    |
    +-- Stage 4: CypherCorrector.correct()  [Stage 3 실패 시에만 실행]
    |   \-> 규칙 기반 교정 (속성명 오타, 레이블 케이스 등) 적용
    |
    +-- Stage 5: HallucinationDetector.validate()
    |   |  "부산항" 실제 존재? -> Neo4j MATCH 확인 -> FOUND
    |   |  "DOCKED_AT" 관계 타입 존재? -> 온톨로지 확인 -> VALID
    |   \-> DetectionResult { hallucinated: [], confidence: 0.98 }
    |
    v Neo4j Driver.run(cypher, params)
    |
    v 결과 직렬화
    |   +-- spatial: Point(latitude, longitude) -> {"lat": ..., "lng": ...}
    |   +-- temporal: datetime -> ISO 8601 문자열
    |   \-- 페이지네이션: cursor 기반 (skip/limit)
    |
    v NLQueryResponse {
        cypher: "MATCH ...",
        results: [...],
        confidence: 0.95,
        execution_time_ms: 42,
        trace_id: "abc-123"
      }
```

**Dual-Path Query Router (3차년도 계획):**

```
사용자 질문
    |
    v Intent Classifier (LLM 기반 분류)
    |
    +-- "Structured Query" -----> Direct Path
    |   (엔티티/관계 명확)         CypherBuilder
    |                              빠름, 확정적
    |
    +-- "Complex Reasoning" ---> LLM Path
    |   (자연어 추론 필요)          Text2Cypher (LLM)
    |                              유연, 오류 가능성
    |
    \-- "Knowledge Search" ----> RAG Path
        (배경 지식 필요)            GraphRAG
                                   풍부한 컨텍스트
    |
    v 라우팅된 결과 수집
    |
    v 응답 합성 (LLM 기반 자연어 생성)
    |
    v 최종 응답 반환
```

### 7.2 ELT 데이터 흐름

```
외부 데이터 소스                     IMSP Platform
+-------------------+
| AIS 수신기         |--NMEA--+
| 기상 API (KMA)    |--REST--+
| S-100 해도 (IHO)  |--GML---+
| 해양 법규 DB       |--REST--+     +--------------+        +----------+
| 위성 영상 (KOMPSAT)|--SFTP--+---> | Collection   |--Raw-->|  Object  |
| CCTV / 항만 카메라 |--RTSP--+     | Adapters     |        | Storage  |
| 레이더 데이터       |--Kafka-+     | (어댑터 패턴) |        | (Ceph)   |
| 사고 DB (MSC)     |--REST--+     +--------------+        +----+-----+
+-------------------+                                           |
                                                                v
                                                    +-------------------+
                                                    | Metadata          |
                                                    | Extraction        |
                                                    | EXIF, GPS,        |
                                                    | 파일 해시, 수집 시각|
                                                    +--------+----------+
                                                             |
                                                             v
                                               +-------------------------+
                                               |  AI Content Analysis    |
                                               |                         |
                                               | PaddleOCR  -> 텍스트    |
                                               | NER Model  -> 엔티티    |
                                               | RE Model   -> 관계      |
                                               | Embedding  -> 768d 벡터 |
                                               | S-100 Parser -> 해도    |
                                               +------------+------------+
                                                            |
                                              +-------------+-------------+
                                              |             |             |
                                              v             v             v
                                         +--------+   +--------+   +----------+
                                         | Neo4j  |   | Object |   | Postgres |
                                         | KG     |   |Storage |   | 마트/DW  |
                                         | 엔티티 |   | 보존   |   | (Suredata|
                                         | 관계   |   |        |   |  Lab)    |
                                         | 벡터   |   |        |   |          |
                                         | 리니지 |   |        |   |          |
                                         +--------+   +--------+   +----------+
```

**ETL -> ELT 전환 전략 (2차년도):**

| 현재 (ETL) | 목표 (ELT) | 이유 |
|-----------|-----------|------|
| 수집 시 변환 | 원본 저장 후 변환 | 재처리 가능성, 스키마 변경 대응 |
| 파이프라인 내 변환 로직 | KG 구축 시 변환 | 분리된 관심사, 테스트 용이 |
| 단일 파이프라인 | 원본 보존 + 다중 뷰 | 다양한 분석 요구 대응 |

### 7.3 워크플로우 실행 흐름

```
사용자 (VueFlow 캔버스)
    |
    +-- 노드 드래그 & 드롭 (사전 정의된 노드 팔레트)
    +-- 엣지 연결 (데이터 흐름 정의)
    +-- 속성 패널 입력 (파라미터, 조건, 리소스)
    |
    v JSON Workflow Definition 저장
      { nodes: [...], edges: [...], metadata: {...} }
    |
    v VueFlow -> Argo DAG 변환기 (Python)
    |   +-- 노드 -> Argo Template 매핑 (노드 타입별 컨테이너)
    |   +-- 엣지 -> DAG dependencies 매핑
    |   +-- 속성 -> Argo Parameters / Artifacts 매핑
    |   +-- 조건 엣지 -> Argo when 표현식
    |   \-- 루프 노드 -> Argo withItems / withParam
    |
    v Argo Workflow API 제출
      kubectl apply -f workflow.yaml  또는  argo submit
    |
    v K8s Pod 스케줄링
    |   +-- 데이터 전달: Artifact (Object Storage 경유) / Parameter (인라인)
    |   +-- GPU 노드: nodeSelector gpu-type=a100 적용
    |   +-- 리소스 제한: resources.limits (OOM 방지)
    |   \-- 재시도 정책: retryStrategy (최대 3회, 지수 백오프)
    |
    v 실행 모니터링 (Argo UI + Grafana 대시보드)
    |   +-- 실시간 노드 상태: Pending/Running/Succeeded/Failed
    |   +-- 로그 스트리밍: kubectl logs -f
    |   +-- 이벤트 알림: Slack/이메일 (Alertmanager 연동)
    |   \-- 오류 핸들링: onExit handler, exitCode 기반 분기
    |
    v 결과 반영
        +-- KG 업데이트 (신규 엔티티/관계 추가)
        +-- 리니지 기록 (W3C PROV-O 형식)
        \-- 대시보드 갱신 (WebSocket 푸시)
```

### 7.4 OWL <-> Neo4j 동기화 흐름

온톨로지 설계 도구(Protege)와 Neo4j KG 사이의 단방향 동기화 파이프라인이다.
변경 사항은 Protege -> OWL -> Neo4j 방향으로만 흐른다 (Neo4j -> OWL 역방향 동기화 없음).

```
Protege (OWL 2 DL 설계)
    |
    v maritime.ttl (Turtle 형식)
      해상교통 온톨로지: Class, Property, Restriction, SHACL Shape
    |
    v OWL Exporter (owl_exporter.py)
      Python owlready2 -> Turtle/OWL 직렬화
    |
    v n10s Importer (importer.py)
      Neosemantics: n10s.onto.import()
      OWL Class     -> Neo4j (:OntologyClass) 노드
      OWL Property  -> Neo4j (:Relationship) 메타데이터
      OWL Instance  -> Neo4j 도메인 노드
    |
    v CI/CD Auto-Sync (Git Push 트리거)
    |   +-- OWL 파일 변경 감지 (git diff *.ttl)
    |   +-- 의존성 분석 (변경된 클래스 영향 범위)
    |   +-- Python 도메인 모델 자동 생성 (pydantic 스키마)
    |   +-- Neo4j 스키마 마이그레이션 (인덱스/제약조건 업데이트)
    |   +-- 단위 테스트 실행 (온톨로지 일관성 검증)
    |   \-- 불일치 알림: Python 모델 <-> OWL 스키마 드리프트 감지
    |
    v 배포 완료
      Neo4j에 최신 온톨로지 반영, API 서버 재시작 없이 스키마 갱신
```

---

## 8. Suredata Lab 연동 아키텍처

IMSP 플랫폼 전체는 InsightMining이 개발하나, 데이터 수집/마트/AI 서빙/DW 파이프라인은
Suredata Lab이 전담한다. 두 시스템은 REST API로 연동된다.

```
+----------------------------+              +--------------------------------------+
|       Suredata Lab          |              |        IMSP (InsightMining)           |
|                             |              |                                      |
| +------------------+        |  REST API    | +--------------------------------+   |
| | Data Collector   |--------+------------->| POST /api/v1/ingest/raw         |   |
| | AIS 수신기        |        |              | POST /api/v1/ingest/metadata     |   |
| | 기상 수집기       |        |              | POST /api/v1/ingest/entities     |   |
| | 크롤러 (논문 등)  |        |              +----------------+---------------+   |   |
| +------------------+        |              |                |                   |   |
|                             |              |                v                   |   |
| +------------------+        |  REST API    | +--------------------------------+   |
| | Data Mart        |--------+------------->| KG Engine                        |   |
| | PostgreSQL 마트  |        |              | - Ontology Mapping               |   |
| | 집계 / 통계 뷰   |        |              | - Entity Resolution              |   |
| | 실시간 피드      |        |              | - Lineage Tracking               |   |
| +------------------+        |              +--------------------------------+   |   |
|                             |              |                                      |
| +------------------+        |  REST API    | +--------------------------------+   |
| | AI Model Serving |<-------+------------- | POST /api/v1/model/invoke       |   |
| | vLLM / Ray       |        |              | (모델 호출 -> 결과 KG 반영)      |   |
| | Model Registry   |        |              +--------------------------------+   |   |
| +------------------+        |              |                                      |
|                             |              | +--------------------------------+   |
| +------------------+        |  REST API    | | GET  /api/v1/query/nl         |   |
| | DW Pipeline      |<-------+------------- | GET  /api/v1/query/cypher      |   |
| | ETL 관리          |        |              | GET  /api/v1/lineage/{id}       |   |
| | 품질 관리         |        |              | GET  /api/v1/ontology/schema    |   |
| +------------------+        |              +--------------------------------+   |   |
+----------------------------+              +--------------------------------------+
```

### 8.1 역할 분담 매트릭스

| 기능 영역 | Suredata Lab | InsightMining (우리) | 연동 경계 |
|----------|-------------|---------------------|----------|
| 데이터 수집 | 크롤러/수집기 운영, 스케줄 관리 | 수집 어댑터 표준 인터페이스 정의 | Suredata 수집 -> REST API 전달 |
| 원천 저장 | DW (PostgreSQL), Data Lake | Object Storage (Ceph RGW) + Neo4j KG | REST API로 이중 저장 |
| 데이터 마트 | 마트 설계/구축/관리 | 마트 -> KG 통합 파이프라인 | GET API로 마트 데이터 조회 |
| AI 모델 서빙 | 모델 레지스트리, 서빙 인프라 | 모델 호출 인터페이스, 결과 KG 반영 | POST API로 모델 호출 |
| **KG 구축/검색** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |
| **온톨로지 설계** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |
| **Text2Cypher** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |
| **데이터 리니지** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |
| **VueFlow 캔버스** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |

### 8.2 공동 협력 영역

| 협력 항목 | InsightMining 역할 | Suredata Lab 역할 |
|----------|------------------|------------------|
| API 명세 | OpenAPI 3.0 정의 및 게이트웨이 운영 | 명세 기반 구현 및 통합 테스트 |
| 데이터 품질 | KG 품질 게이트 (QualityGate 모듈) | DW 품질 규칙, 교차 검증 |
| 보안 정책 | Keycloak Realm 설계, API Key 발급 | DW 접근 제어, 통합 보안 정책 참여 |
| 모니터링 | K8s + KG 메트릭 (Prometheus) | DW + 모델 메트릭 수집, Prometheus 통합 |
| 장애 대응 | API 계층, KG, 워크플로우 장애 | 데이터 수집 중단, 마트 이상 대응 |

### 8.3 API 연동 표준

**인증:** API Key (헤더: `X-API-Key`) + IP 화이트리스트
**형식:** JSON (Content-Type: application/json)
**버전:** `/api/v1/` 경로 접두사, 하위 호환 보장
**오류:** RFC 7807 Problem Details 형식

```
POST /api/v1/ingest/raw
Authorization: X-API-Key {suredata_api_key}
Content-Type: application/json

{
  "source": "suredata-ais",
  "collected_at": "2026-03-20T10:00:00Z",
  "data_type": "ais_position",
  "records": [...]
}

Response 202 Accepted:
{
  "job_id": "ingest-20260320-001",
  "status": "queued",
  "estimated_processing_time_sec": 30
}
```

---

## 9. 기술 스택 매트릭스

### 9.1 확정 기술

| 영역 | 기술 | 버전 | 라이선스 | 역할 | 선정 근거 |
|------|------|------|---------|------|----------|
| 프론트엔드 프레임워크 | Vue 3 + VueFlow | 3.x / 0.x | MIT | 워크플로우 캔버스, SPA | KRISO 미팅 확정, n8n 스타일 노드 에디터 최적 |
| KG Database | Neo4j CE | 5.26 | GPLv3 | Knowledge Graph 저장/조회 | Cypher, 그래프+벡터+공간 통합 인덱스 |
| 온톨로지 도구 | Protege + n10s | 5.6 / 5.x | BSD/Apache 2.0 | OWL 2 설계 -> Neo4j 변환 | W3C 표준, 자동화된 OWL-KG 변환 |
| 인증/인가 | Keycloak | 24.x | Apache 2.0 | OIDC SSO, RBAC 허브 | 공공기관 통합 인증, SAML/OIDC 지원 |
| 컨테이너 오케스트레이션 | Kubernetes | 1.28+ | Apache 2.0 | 프로덕션 인프라 관리 | GPU 워크로드, 멀티테넌트, HPA |
| 메트릭 모니터링 | Prometheus + Grafana | - | Apache 2.0 | 메트릭 수집 + 시각화 | K8s 네이티브, CNCF 표준 |
| 분산 추적 | Zipkin | 2.x | Apache 2.0 | 서비스 간 추적 | 경량, OpenTracing 호환 |
| 분산 추론 | Ray | 2.x | Apache 2.0 | A100+ GPU 분산 서빙 | 스케일아웃, vLLM 통합 |
| RDBMS | PostgreSQL | 14 | PostgreSQL | Keycloak/워크플로우 백엔드 | 안정성, 오픈소스, 라이선스 무료 |
| LLM 런타임 (초기) | Ollama | Latest | MIT | 온프레미스 LLM 서빙 | 간편한 모델 관리, CPU/GPU 지원 |
| LLM 런타임 (성장) | vLLM | 0.4+ | Apache 2.0 | 고성능 GPU 서빙 | Continuous Batching, 처리량 극대화 |
| 워크플로우 실행 | Argo Workflow | 3.x | Apache 2.0 | DAG 기반 파이프라인 실행 | K8s 네이티브, 스케줄링, UI 제공 |
| 객체 저장소 | Ceph RGW | Latest | Apache 2.0 | S3 호환 원천 데이터 보존 | 분산 파일시스템, PB급 확장, 온프레미스, ELT 패턴 지원 |
| 백엔드 언어 | Python | 3.10+ | PSF | KG 엔진, API, 파이프라인 | 데이터 과학 생태계, 팀 역량 |
| 프론트엔드 언어 | TypeScript | 5.x | Apache 2.0 | Vue 3 컴포넌트 | 타입 안전성, 대규모 유지보수 |
| API 프레임워크 | FastAPI | 0.100+ | MIT | REST API 서버 | async, OpenAPI 자동 생성, 성능 |
| Helm | Helm | 3.x | Apache 2.0 | K8s 패키지 관리 | values 기반 환경별 배포 |

### 9.2 미결정 기술 (벤치마크 예정)

| 결정 항목 | 후보 A | 후보 B | 결정 기준 | 결정 시점 |
|----------|--------|--------|----------|----------|
| 시계열 DB | TimescaleDB (PostgreSQL 확장) | InfluxDB v3 | AIS 궤적 쿼리 성능, 팀 역량 | Y1 Q2 |
| Vector DB 확장 | Neo4j 내장 벡터 인덱스 | Milvus 2.x | 1M+ 임베딩 스케일, 지연 | Y2 Q1 |
| K8s 배포 도구 | Helm (현재 후보) | Kustomize | 인프라팀 선호도, 환경 복잡도 | Y1 Q1 |
| 기본 LLM 모델 | Qwen2.5 VL 72B | Llama 3.3 70B | 한국어 해사 도메인 30문항 벤치마크 | Y1 Q3 |
| OCR 엔진 | PaddleOCR (현재 사용) | Tesseract 5 | 한국어 해사 문서 정확도 | Y1 Q2 |
| 메시지 큐 | Redis (BullMQ, 현재) | Kafka | 처리량 요구사항, 운영 복잡도 | Y2 |

### 9.3 기술 의존성 그래프

```
                           +-------------------+
                           |   Vue 3 + VueFlow  |
                           |   (프론트엔드)      |
                           +--------+----------+
                                    |
                                    v
+-------------+          +-------------------+          +-------------+
| Keycloak    |<-------->|   FastAPI          |<-------->| Prometheus  |
| (OIDC/RBAC) |          |   (API Gateway)   |          | + Grafana   |
+-------------+          +--------+----------+          +-------------+
                                  |
                    +-------------+-------------+
                    |             |             |
                    v             v             v
             +----------+  +---------+  +----------+
             |  Neo4j   |  |  Ceph   |  |  Ollama  |
             |  KG + 벡터|  | 원본저장|  |  vLLM   |
             +----------+  +---------+  +----------+
                    |
                    v
             +------------------+
             |  Argo Workflow   |
             |  (DAG 실행)      |
             +------------------+
                    |
                    v
             +------------------+
             |  Suredata Lab    |
             |  REST API 연동   |
             +------------------+
```

### 9.4 연차별 기술 도입 계획

| 기술 | Y1 (2026) | Y2 (2027) | Y3 (2028) | Y4 (2029) | Y5 (2030) |
|------|-----------|-----------|-----------|-----------|-----------|
| Neo4j CE | 도입 + KG 구축 | 성능 튜닝 | 스케일 검토 | EE 전환 검토 | 안정 운영 |
| Kubernetes | 없음 (Compose) | 전환 | 고도화 | 멀티테넌트 | 안정 운영 |
| Keycloak | JWT (임시) | 전환 완료 | MFA 강화 | 외부 IdP 연동 | 안정 운영 |
| Argo Workflow | Activepieces | 전환 완료 | 고도화 | 표준화 | 안정 운영 |
| vLLM | Ollama (CPU) | GPU 전환 | Tensor Parallel | Ray 분산 | 멀티 모델 |
| VueFlow 캔버스 | 기획/설계 | 프로토타입 | MVP | 고도화 | 안정 운영 |
| S-100 해도 | 표준 분석 | 파서 개발 | 렌더러 개발 | 실시간 통합 | 안정 운영 |
| GraphRAG | 없음 | 연구/설계 | 프로토타입 | 통합 | 안정 운영 |

---

*문서 끝 - Part 2 / 섹션 5-9*

*다음 갱신 예정: Y1 Q2 (2026-06) - GPU 서빙 진화, Keycloak 전환, K8s 마이그레이션 설계 반영*

# IMSP 상세 아키텍처 문서 - Part 3 (섹션 10~14)

> **대상 독자:** 플랫폼 개발팀, 인프라팀, KRISO 기술 검토자
> **최종 수정:** 2026-03-20
> **관련 문서:** strategy_5year_IMSP.md, architecture_flux_platform.md, DES-001~005

---

## 10. 관측성 아키텍처 (Observability)

### 10.1 3대 관측 축

```
┌─────────────────────────────────────────────────────────────┐
│                    Observability 3 Pillars                    │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   Metrics   │  │    Traces    │  │       Logs         │  │
│  │ (Prometheus)│  │   (Zipkin)   │  │ (JSON structured)  │  │
│  │             │  │              │  │                    │  │
│  │ • API 응답시간│ │ • 요청 추적   │  │ • 구조화된 로그     │  │
│  │ • Neo4j 성능 │ │ • 서비스 간   │  │ • 에러 스택트레이스  │  │
│  │ • K8s 리소스 │ │   호출 체인   │  │ • ETL 실행 이력     │  │
│  │ • ETL 처리량 │ │ • 지연 분석   │  │ • 인증 감사         │  │
│  │ • GPU 사용률 │ │              │  │                    │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│             │              │                │                │
│             ▼              ▼                ▼                │
│       ┌─────────────────────────────────────────────┐       │
│       │              Grafana Dashboard               │       │
│       │  K8s Health │ Neo4j │ API │ ETL │ Text2Cypher│       │
│       └─────────────────────────────────────────────┘       │
│                           │                                  │
│                           ▼                                  │
│                    AlertManager                              │
│                    (Slack / Email 알림)                       │
└─────────────────────────────────────────────────────────────┘
```

관측성은 단순한 로그 수집을 넘어 플랫폼 전반의 상태를 실시간으로 파악하고
이상 징후를 선제적으로 감지하는 것을 목표로 한다. Prometheus(메트릭),
Zipkin(분산 추적), 구조화 JSON 로그(감사/운영)의 세 축이 Grafana를
허브로 통합된다.

### 10.2 메트릭 수집 (Prometheus)

**Scrape Target 목록:**

| Target | 주요 메트릭 | 수집 주기 |
|--------|-----------|----------|
| maritime-api | API 요청 수, 응답 시간, 에러율 | 15s |
| neo4j-exporter | 트랜잭션 수, 쿼리 지연, 캐시 히트율, 볼륨 사용량 | 30s |
| node-exporter | CPU, 메모리, 디스크 I/O, 네트워크 | 15s |
| kube-state-metrics | Pod 상태, HPA 메트릭, CronJob 성공/실패 | 30s |
| ollama-server | GPU 사용률, 추론 지연, 모델 메모리 | 30s |

**커스텀 API 메트릭 (MetricsMiddleware 자동 기록):**

```
# API 요청 카운터/지연/활성 요청
maritime_api_requests_total{method, path, status}
maritime_api_request_duration_seconds{method, path}
maritime_api_active_requests

# Text2Cypher 품질
maritime_text2cypher_accuracy{confidence_bucket}

# ETL 파이프라인 처리량
maritime_etl_records_processed_total{pipeline}
maritime_etl_records_failed_total{pipeline}

# KG 규모 추이
maritime_kg_nodes_total
maritime_kg_relationships_total
```

**Prometheus 설정 예시 (`infra/prometheus/prometheus.yml`):**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  - job_name: maritime-api
    static_configs:
      - targets: ["maritime-api:8000"]
    metrics_path: /metrics

  - job_name: neo4j
    static_configs:
      - targets: ["neo4j-exporter:9474"]
    scrape_interval: 30s

  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: "true"
```

### 10.3 분산 추적 (Zipkin)

요청 흐름 추적 경로:

```
Browser
  │
  ▼
API Gateway  ─── [Span: gateway]
  │
  ├──► TextToCypherPipeline  ─── [Span: text2cypher]
  │         │
  │         ├──► NLParser          [Span: nlp.parse]
  │         ├──► QueryGenerator    [Span: query.generate]
  │         ├──► CypherValidator   [Span: cypher.validate]
  │         ├──► CypherCorrector   [Span: cypher.correct]
  │         ├──► HallucinationDet  [Span: hallucination.detect]
  │         └──► Neo4j Execute     [Span: neo4j.execute]
  │
  ├──► ETL Pipeline  ─── [Span: etl]
  │         │
  │         ├──► Object Storage Fetch [Span: s3.fetch]
  │         ├──► Transform          [Span: etl.transform]
  │         └──► Neo4j BatchLoad    [Span: neo4j.batch_load]
  │
  └──► Agent Runtime  ─── [Span: agent]
            │
            ├──► LLM Inference      [Span: llm.infer]
            └──► Neo4j Query        [Span: neo4j.query]
```

각 Span에 `trace_id`, `span_id`, `parent_span_id`, 시작/종료 타임스탬프,
태그(`db.type=neo4j`, `llm.model=qwen2.5-vl-7b` 등)가 기록된다.
P99 지연이 임계치를 초과하면 Zipkin UI에서 병목 Span을 즉시 식별 가능하다.

### 10.4 Grafana 대시보드 (5개)

| 대시보드 | 주요 패널 | 갱신 주기 |
|---------|----------|----------|
| K8s Cluster Health | CPU/메모리 사용률, Pod 상태, HPA 활동, 노드 Ready 여부 | 30s |
| Neo4j Performance | 쿼리 지연 P50/P95/P99, 트랜잭션 수, 캐시 히트율, 볼륨 사용량 | 30s |
| API Monitoring | 요청 수, 응답 시간, 에러율, 엔드포인트별 트래픽, DLQ 크기 | 15s |
| ETL Pipeline | 파이프라인별 처리량, 실패율, 마지막 실행 시간, 누적 레코드 | 1m |
| Text2Cypher Quality | 정확도 분포, 검증 통과율, 교정 빈도, 환각 감지율, 신뢰도 히스토그램 | 5m |

모든 대시보드는 `infra/prometheus/grafana/` 아래 JSON으로 관리되며
ArgoCD가 배포 시 자동 import한다.

### 10.5 알림 규칙 (AlertManager)

| 규칙 이름 | 조건 | 심각도 | 알림 채널 |
|----------|------|--------|----------|
| Neo4jDiskHigh | 사용률 > 80% (5분간) | WARNING | Slack #ops |
| Neo4jDiskCritical | 사용률 > 90% (5분간) | CRITICAL | Slack #ops + Email |
| APILatencyHigh | P99 응답 > 5s (5분간) | WARNING | Slack #ops |
| APIErrorRateHigh | 5xx 비율 > 5% (5분간) | CRITICAL | Slack #ops + Email |
| ETLPipelineFailed | 연속 3회 실패 | WARNING | Slack #etl |
| GPUUtilizationHigh | GPU 사용률 > 95% (10분간) | WARNING | Slack #ml |
| PodRestartLoop | Pod 재시작 > 3회 (1시간) | WARNING | Slack #ops |
| CronJobMissed | 스케줄 미실행 (지연 > 1시간) | WARNING | Slack #etl |
| KGNodeGrowthStall | KG 노드 증가 없음 (24시간) | INFO | Slack #data |

**AlertManager 라우팅 설정:**

```yaml
route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: slack-default
  routes:
    - match:
        severity: critical
      receiver: pagerduty-critical
    - match:
        team: etl
      receiver: slack-etl

receivers:
  - name: slack-default
    slack_configs:
      - api_url: "${SLACK_WEBHOOK_URL}"
        channel: "#ops"
        title: "[{{ .Status | toUpper }}] {{ .GroupLabels.alertname }}"
  - name: pagerduty-critical
    pagerduty_configs:
      - routing_key: "${PAGERDUTY_KEY}"
```

---

## 11. AI/LLM 아키텍처

### 11.1 모델 스택

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Model Stack                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 1: Language Models (대화, 추론, OCR)               │   │
│  │                                                          │   │
│  │  ┌──────────────────┐   ┌───────────────────┐           │   │
│  │  │  Qwen 2.5 VL 7B  │   │   MiniCPM-V 4.5   │           │   │
│  │  │  (Primary)        │   │   (Backup/Batch)   │           │   │
│  │  │                   │   │                   │           │   │
│  │  │ • 한국어 대화     │   │ • 경량 폴백        │           │   │
│  │  │ • 이미지 이해     │   │ • 배치 처리        │           │   │
│  │  │ • OCR             │   │ • CPU 가능         │           │   │
│  │  │ • A100 GPU 필요   │   │ • 소규모 GPU       │           │   │
│  │  └──────────────────┘   └───────────────────┘           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 2: Vision Models (객체 탐지, 다중 추적)             │   │
│  │                                                          │   │
│  │  ┌──────────────────┐   ┌───────────────────┐           │   │
│  │  │ YOLOv8 / RT-DETR │   │    DeepSORT        │           │   │
│  │  │ (Detection)       │   │    (Tracking)      │           │   │
│  │  │                   │   │                   │           │   │
│  │  │ • 위성 선박 탐지  │   │ • CCTV 다중 추적  │           │   │
│  │  │ • CCTV 선박 인식  │   │ • 궤적 연결        │           │   │
│  │  └──────────────────┘   └───────────────────┘           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 3: Embedding Models (의미 벡터 검색)               │   │
│  │                                                          │   │
│  │  ┌──────────────────┐                                   │   │
│  │  │ nomic-embed-text │  768-dim, Ollama serving           │   │
│  │  └──────────────────┘                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Serving Engine (연차별 전환)                             │   │
│  │                                                          │   │
│  │  Y1: Ollama (CPU/경량) ──► Y2: Ollama (GPU, 1x A100)    │   │
│  │                        ──► Y3: vLLM + Ray 분산 추론       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 LLM Provider 추상화 및 Failover

```python
# agent/llm/provider.py (이식 예정)
class LLMProvider(Protocol):
    async def complete(self, prompt: str, **kwargs) -> LLMResponse: ...
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]: ...

class OllamaProvider(LLMProvider):    # 온프레미스 기본
    model: str = "qwen2.5-vl:7b"
    base_url: str = "http://ollama:11434"

class OpenAIProvider(LLMProvider):    # 클라우드 폴백 (규정 검토 후)
    model: str = "gpt-4o"

class AnthropicProvider(LLMProvider): # 백업 (규정 검토 후)
    model: str = "claude-opus-4-6"

class FailoverProvider(LLMProvider):
    """순서대로 시도, 실패 시 다음으로"""
    providers: list[LLMProvider]

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        for provider in self.providers:
            try:
                return await provider.complete(prompt, **kwargs)
            except LLMUnavailableError:
                continue
        raise AllProvidersFailedError()
```

**기본 구성:** Ollama(primary) → OpenAI(fallback) → Anthropic(backup)
온프레미스 보안 요구사항에 따라 클라우드 Provider 활성화 여부를
환경변수(`LLM_ALLOW_CLOUD=false`)로 제어한다.

### 11.3 Agentic AI 시스템

```
┌──────────────────────────────────────────────────────────────────┐
│                     Orchestrator Agent                             │
│            (글로벌 대화 통합 / 의도 분류 / 라우팅)                   │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                A2A Protocol (Agent-to-Agent)                │   │
│  │                                                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │   │
│  │  │  KG Agent   │  │  Workflow   │  │  Analytics  │       │   │
│  │  │             │  │  Agent      │  │  Agent      │       │   │
│  │  │• Text2Cypher│  │• 노드 추천  │  │• 시각화 생성│       │   │
│  │  │• GraphRAG   │  │• 자동 생성  │  │• 대시보드   │       │   │
│  │  │• 스키마 탐색│  │• 실행 관리  │  │• 차트 구성  │       │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │   │
│  └─────────┼────────────────┼────────────────┼──────────────┘   │
│            │                │                │                    │
│  ┌─────────▼────────────────▼────────────────▼──────────────┐   │
│  │                    MCP Protocol                            │   │
│  │               (Model Context Protocol)                     │   │
│  │                                                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │   │
│  │  │KG Query  │ │Workflow  │ │File      │ │External  │    │   │
│  │  │Tool      │ │CRUD Tool │ │System    │ │API Tool  │    │   │
│  │  │          │ │          │ │Tool      │ │          │    │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐     │
│  │   Memory    │  │   Skills    │  │   LLM Provider       │     │
│  │             │  │             │  │                      │     │
│  │ • 단기 메모리│  │ • 스킬 팩   │  │ • Ollama (primary)   │     │
│  │   (대화)    │  │ • 워크플로우 │  │ • OpenAI (fallback)  │     │
│  │ • 장기 메모리│  │   스킬      │  │ • Anthropic (backup) │     │
│  │   (KG 기반) │  │ • 데이터 스킬│  │ • Auto failover      │     │
│  └─────────────┘  └─────────────┘  └──────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

**에이전트 런타임 유형:**

| 런타임 | 사용 목적 | 특징 |
|--------|---------|------|
| ReAct Runtime | 대화형 KG 탐색 | Reason → Act → Observe 반복, 동적 도구 선택 |
| Pipeline Runtime | 정형 ETL 후처리 | 고정 단계 순서, 병렬 실행 지원 |
| Batch Runtime | 주기적 평가/리포트 | CronJob 연동, 대량 데이터 처리 |

### 11.4 Agent VM 모델

```
Agent Configuration (YAML 정의)
├── id: kg-agent-v1
├── core_system_prompt
│   ├── 해사 도메인 온톨로지 요약 (압축 JSON)
│   ├── 사용 가능 도구 목록 + 시그니처
│   └── 역할별 권한 범위 (RBAC Role 매핑)
├── skills:
│   - workflow_create
│   - workflow_execute
│   - kg_query
│   - data_ingest
└── mcp_servers:
    - uri: mcp://kg-query-server:3000
    - uri: mcp://workflow-crud-server:3001

Agent VM (격리 실행 환경, K8s Pod 단위)
├── /skills/          # 등록된 스킬 정의 (YAML)
├── /workspace/       # 작업 공간 (임시 데이터, Pod 수명 동안)
├── /context/         # 대화 컨텍스트 (Redis 백업)
└── Tool Access (RBAC 적용)
    ├── KG Query     (Text2Cypher 경유, 역할별 데이터 분류 필터)
    ├── Workflow CRUD(생성/수정/실행/삭제, 소유자 검증)
    ├── Data Ingest  (Object Storage 업로드 + KG 등록, 용량 쿼터)
    └── Visualization(차트/지도/그래프 생성, 읽기 전용)
```

**메모리 아키텍처:**

```
단기 메모리 (Short-term)
└── Redis List (TTL 24h)
    └── 최근 N 턴의 대화 내용 (요약 압축)

장기 메모리 (Long-term)
└── Neo4j KG
    └── (:MemoryNode {content, embedding, timestamp})
        -[:RELATED_TO]->(:Concept)
    (nomic-embed-text 벡터 인덱스로 유사 기억 검색)
```

### 11.5 Text2Cypher 5단계 파이프라인 (상세)

```
입력: "부산항에서 출항한 컨테이너 선박 목록"
  │
  ▼
[1단계: NLParser]
  • 한국어 형태소 분석
  • 해사 용어 사전 매핑 (부산항 → PORT_BUSAN)
  • 의도 분류 (QUERY_LIST)
  출력: StructuredQuery {entity: Vessel, filter: {type: container},
                         relation: DEPARTED_FROM, target: PORT_BUSAN}
  │
  ▼
[2단계: QueryGenerator]
  • Direct Path: CypherBuilder (확정적, 80% 커버)
  • LLM Path: Few-shot Prompt + LLM (20% 복잡 쿼리)
  • RAG Path: GraphRAG (스키마 탐색 후 생성)
  출력: MATCH (v:Vessel)-[:DEPARTED_FROM]->(p:Port {name:"부산항"})
         WHERE v.type = "container" RETURN v
  │
  ▼
[3단계: CypherValidator]
  • 구문 검증 (Cypher 파서)
  • 스키마 정합성 (존재하는 레이블/관계 타입인지)
  • RBAC 레이블 허용 여부
  • 위험 패턴 감지 (DELETE/MERGE 무제한)
  • 파라미터 주입 검사
  • 복잡도 상한 (Hop 수 <= 5)
  │
  ▼
[4단계: CypherCorrector]
  • 규칙 기반 교정 (오탈자 레이블, 잘못된 방향)
  • 스키마 기반 자동 제안 (Vessel → :Vessel)
  • 교정 불가 시 LLM 재생성 요청
  │
  ▼
[5단계: HallucinationDetector]
  • 존재하지 않는 노드 ID 참조 감지
  • 스키마에 없는 프로퍼티 사용 감지
  • 신뢰도 점수 산출 (0.0 ~ 1.0)
  • 임계값(0.7) 미달 시 사람 검토 요청
  │
  ▼
출력: ValidatedQuery {cypher, confidence: 0.92, corrections: [...]}
```

---

## 12. 설계 원칙 및 패턴

### 12.1 핵심 설계 패턴 10가지

| # | 패턴 | 적용 위치 | 설명 |
|---|------|----------|------|
| 1 | **Palantir Foundry-style Ontology** | `kg/ontology/core.py` | ObjectType / LinkType / PropertyDefinition 삼중 구조. DB 독립적 엔티티 모델링 프레임워크 |
| 2 | **Plugin Architecture** | `core/` + `domains/` | 도메인 독립 엔진(core) + 도메인 플러그인(maritime). TermDictionary Protocol 기반 DI로 새 도메인 확장 가능 |
| 3 | **3-Layer Ontology-Schema** | 온톨로지 전체 | Conceptual(DB 무관) → Mapping(DDL 생성) → Physical(Neo4j 전용). DB 교체 시 Mapping 레이어만 교체 |
| 4 | **ELT over ETL** | `kg/etl/` | "일단 올려라, 처리는 나중에". Object Storage (Ceph)에 원천 보존 후 AI 분석. 데이터 무결성 보장 + 재처리 가능 |
| 5 | **Dual-Path Query Routing** | TextToCypherPipeline | Direct Path(CypherBuilder) / LLM Path(Text2Cypher) / RAG Path(GraphRAG). 의도 기반 자동 라우팅 |
| 6 | **5-Stage Quality Pipeline** | Pipeline 5단계 | Parse → Generate → Validate → Correct → HallucinationDetect. 각 단계 독립 품질 검증 및 Span 추적 |
| 7 | **Metadata-First Graph** | 멀티모달 저장 | Neo4j는 메타데이터만 저장. 바이너리(영상/센서)는 Object Storage (Ceph)에 저장, `storagePath` 속성으로 참조 |
| 8 | **Multi-Agent Architecture** | Agent Runtime | Orchestrator → A2A Protocol → Sub-agents → MCP Protocol → Tools. 역할 분리 + 도구 추상화 |
| 9 | **GitOps Deployment** | CI/CD 전체 | ArgoCD + Flux. 모든 인프라 변경이 Git commit. `values-{env}.yaml`로 환경 분리 |
| 10 | **Temporal Knowledge Reasoning** | 온톨로지, RBAC | `validFrom` / `validTo` 속성. "3월에만 제한된 구역을 4월에 쿼리" 같은 시간 조건부 추론 지원 |

### 12.2 소프트웨어 아키텍처 원칙

| 원칙 | 설명 | 적용 위치 |
|------|------|----------|
| **12-Factor App** | 환경변수 외부화, Stateless 서비스, Port binding | FastAPI, Docker, K8s ConfigMap/Secret |
| **Domain-Driven Design** | 핵심 도메인(KG) + 지원 도메인(인프라/인증) 명확히 분리 | `core/` vs `infra/` vs `gateway/` |
| **CQRS 경향** | 데이터 주입(Write) / 쿼리(Read) 경로 분리. 향후 본격 CQRS 전환 검토 | Ingest API vs Query API |
| **Hexagonal Architecture** | Port & Adapter. 외부 의존성을 Protocol/Interface로 추상화 | TermDictionary Protocol, LLM Provider 추상화 |
| **Principle of Least Privilege** | 최소 권한 원칙. 컴포넌트별 필요 권한만 부여 | K8s RBAC, NetworkPolicy, Pod Security Standards |
| **Fail Fast** | 조기 오류 발견. 파이프라인 각 단계에서 명시적 예외 발생 | CypherValidator, RecordValidator |

### 12.3 모듈 의존성 원칙

```
허용되는 의존 방향:
  domains/maritime/ ──► core/kg/          (도메인 → 엔진)
  core/kg/api/      ──► core/kg/          (API → 엔진)
  gateway/          ──► core/kg/api/      (게이트웨이 → API)
  agent/            ──► core/kg/          (에이전트 → 엔진)
  ui/               ──► gateway/          (프론트 → 게이트웨이)

금지되는 의존 방향:
  core/kg/          ──► domains/maritime/ (엔진은 도메인을 몰라야 함)
  core/kg/          ──► agent/            (순환 의존 금지)
  ui/               ──► core/kg/          (직접 DB 접근 금지)
```

### 12.4 알려진 안티 패턴 및 대응

| 안티 패턴 | 현재 상태 | 대응 방안 |
|----------|----------|----------|
| PRD/전략서 프론트엔드 불일치 | PRD: Next.js+React Flow vs 전략: Vue 3+VueFlow | **Vue 3 + VueFlow 확정** (KRISO 미팅 후 결정, 2026-03-18) |
| Neo4j CE 클러스터링 제한 | CE는 단일 인스턴스만 지원 | 애플리케이션 레벨 Redis 캐싱 + Y4에서 EE 전환 검토 |
| Agent A2A 프로토콜 미성숙 | 멀티 에이전트 조율 복잡도 높음 | Y1~Y2: 단일 에이전트로 시작, Y3+ A2A 점진적 도입 |
| 온톨로지 규모 vs LLM 정확도 | 150 엔티티에서 Text2Cypher 정확도 저하 우려 | Few-shot Exemplar DB + 도메인 특화 프롬프트 + Direct Path 우선 |
| Lineage 비영속성 | LineageRecorder가 in-memory only | ETL 완료 후 Neo4j flush 단계 추가 (Y1 Q3 목표) |
| 테스트 DB 격리 부족 | 현재 통합 테스트가 공유 Neo4j 사용 | Test DB Container + Fixture 기반 격리 (진행 중) |

---

## 13. 연차별 아키텍처 진화

### 13.1 컴포넌트별 진화 로드맵

| 컴포넌트 | Y1 (2026) | Y2 (2027) | Y3 (2028) | Y4 (2029) | Y5 (2030) |
|----------|-----------|-----------|-----------|-----------|-----------|
| **인증** | JWT → Keycloak PoC | Keycloak OIDC 전환 완료 | SSO 완성 + MFA | ISMS-P 인증 준비 | 안정 운영 |
| **워크플로우** | Activepieces (현행 유지) | VueFlow 캔버스 + Argo v1 | Argo DAG 완성 | 자동화 + 최적화 | 안정 운영 |
| **LLM 서빙** | CPU PoC (Ollama) | GPU (vLLM, 1x A100) | Ray 분산 클러스터 | Quantization 최적화 | SLA 관리 |
| **KG 규모** | 10K nodes, 50K rels | 100K nodes, 500K rels | 500K nodes, 2M rels | 1M nodes, 5M rels | 2M+ nodes, 10M+ rels |
| **온톨로지** | 40 types (재설계 완료) | 70 types (+S-100 매핑) | 100 types (통합) | 130 types (고도화) | 150 types (안정) |
| **동시 사용자** | 5명 | 10명 | 30명 | 50명 | 100+명 |
| **모니터링** | Prometheus + Grafana 기본 | AlertManager + EFK 도입 | 자동 스케일링 연동 | SLA 대시보드 | SLA 99.5% 관리 |
| **K8s** | dev/staging 클러스터 | prod 클러스터, Helm v1 | GPU 클러스터 통합 | HA (Multi-AZ 검토) | 자동 복구 |
| **데이터 처리** | Batch (CronJob) | Batch + Kafka 스트리밍 | 실시간 AIS 스트리밍 | Ray 분산 처리 | 글로벌 데이터 통합 |
| **보안** | API Key + JWT | Keycloak RBAC | 감사 로그 자동화 | ISMS-P | 보안 자동화 |
| **프론트엔드** | 없음 (API only) | VueFlow 캔버스 v1 | 전자해도 + 3D 렌더러 | 대시보드 고도화 | 서비스 포털 완성 |
| **SLA** | N/A (개발 환경) | 95% (내부 검증) | 99% (파일럿) | 99.5% (확장) | 99.5%+ (안정) |

### 13.2 정량 목표 추이

| 지표 | Y1 | Y2 | Y3 | Y4 | Y5 |
|------|-----|-----|-----|-----|-----|
| Text2Cypher 정확도 | 70% | 85% | 90% | 93% | 95% |
| 도메인 모델 종수 (누적) | 5종 | 10종 | 15종 | 20종 | 25종 |
| 워크플로우 노드 종류 | 10종 | 30종 | 50종 | 70종 | 80+종 |
| 민간 연구 지원 (누적) | 3건 | 7건 | 12건 | 19건 | 29건 |
| 논문/특허 (누적) | 1건 | 4건 | 9건 | 16건 | 25건 |
| 테스트 커버리지 | 80% | 85% | 90% | 90% | 90% |
| API P99 응답 (목표) | 5s | 3s | 2s | 1.5s | 1s |
| 평가 데이터셋 문항 | 30개 | 100개 | 200개 | 300개 | 500개 |

### 13.3 마일스톤 타임라인

```
2026 (Y1) - 운영 개념 정의 및 설계
  │
  ├── Q1: [M1] 코드 마이그레이션 (flux-n8n → flux-platform)
  │         - 기존 테스트 전체 통과 확인
  │         - core/kg/ 구조 안정화
  │
  ├── Q2: [M2] K8s + Keycloak 기본 환경 구축
  │         - dev/staging 클러스터 구성
  │         - Keycloak realm 설정 (PoC)
  │
  │   [M3] 온톨로지 v1 확정
  │         - OWL 파일 작성 + Neo4j 스키마 DDL 생성
  │         - 40 ObjectType / 60 LinkType 정의
  │
  ├── Q3: [M4] Text2Cypher PoC
  │         - 30문항 평가 데이터셋 구축
  │         - "부산항 근처 선박" 수준 쿼리 70% 정확도
  │
  │   [M5] VueFlow 캔버스 PoC
  │         - 노드 CRUD (생성/이동/연결/삭제)
  │         - 워크플로우 JSON 저장/불러오기
  │
  └── Q4: [M6] 통합 PoC 데모 (KRISO 발표)
            - KG 탑재 + 대화형 쿼리 + 시각화

2027 (Y2) - 데이터·모델 의미 체계화 + 구성 요소 개발
  │
  ├── Q1: [M7] ELT 파이프라인 가동 (AIS 실시간 수신)
  │         - Kafka → ETLPipeline → Neo4j
  │
  ├── Q2: [M8] 워크플로우 저작도구 v1
  │         - 5개 이상 해사 시나리오 노드
  │         - Argo Workflow 연동 v1
  │
  ├── Q3: [M9] Text2Cypher v2 (100문항 85% 정확도)
  │         - Few-shot Exemplar DB 구축
  │
  │   [M10] 전자해도 시각화
  │         - S-100 데이터 + AIS 오버레이 (Leaflet/MapLibre)
  │
  └── Q4: [M11] 멀티테넌트 검증 (3팀 동시)

2028 (Y3) - 통합 연계 및 플랫폼 MVP
  │
  ├── Q1: [M12] MVP 알파 (핵심 기능 통합 완료)
  ├── Q2: [M13] GPU 클러스터 통합 (Ray + A100)
  ├── Q3: [M14] 표준 개발 프로세스 수립 (문서화)
  └── Q4: [M15] MVP 베타 + 1단계 완료 보고

2029 (Y4) - 플랫폼 고도화 + 표준 개발 프로세스
  │
  ├── Q2: [M17] 플랫폼 v2 (API P99 < 2s 달성)
  ├── Q3: [M18] 표준 개발 프로세스 (외부 공개)
  └── Q4: [M19] 3D 시각화 통합 (Three.js 기반)

2030 (Y5) - 안정화 + 민간 연구개발 지원
  │
  ├── Q2: [M21] SLA 99.5%+ 달성
  └── Q3~Q4: 최종 보고서 / 논문 / 특허 / 기술 이전
```

### 13.4 위험 관리

| 위험 요소 | 가능성 | 영향도 | 대응 전략 |
|----------|--------|--------|----------|
| Neo4j CE 성능 한계 도달 | 중 | 높음 | Y3 이전 EE 전환 예산 확보, 애플리케이션 캐싱 강화 |
| 온프레미스 GPU 조달 지연 | 중 | 중간 | Y1: CPU 기반 PoC, Y2 초 GPU 우선 확보 계획 |
| 한국어 해사 LLM 성능 미달 | 높음 | 높음 | Qwen 2.5 VL 파인튜닝 데이터셋 Y1부터 구축 시작 |
| Keycloak 전환 복잡도 | 중 | 중간 | 기존 JWT 코드와 병행 운영, 점진적 마이그레이션 |
| KRISO 요구사항 변경 | 높음 | 중간 | 플러그인 아키텍처로 도메인 모델 교체 용이하게 설계 |

---

## 14. 디렉토리 구조 (최종 목표 - Y5 기준)

```
flux-platform/
│
├── core/                              ← 도메인 독립 KG 엔진 (20,000+ lines)
│   └── kg/
│       ├── __init__.py                # 공개 API surface (40+ exports)
│       ├── cypher_builder.py          # Fluent Cypher 쿼리 빌더
│       ├── query_generator.py         # StructuredQuery → Cypher 변환
│       ├── pipeline.py                # TextToCypherPipeline (5단계)
│       ├── cypher_validator.py        # 6가지 구문/스키마/보안 검증
│       ├── cypher_corrector.py        # 규칙 기반 자동 교정
│       ├── hallucination_detector.py  # 환각 감지 + 신뢰도 점수
│       ├── quality_gate.py            # CI/CD 품질 게이트
│       ├── ontology_bridge.py         # 온톨로지 → KG 브릿지
│       ├── maritime_factories.py      # 해사 팩토리 (→ domains/ 이동 예정)
│       ├── config.py                  # Neo4j + App 설정 (싱글톤)
│       ├── types.py                   # 공통 Enum / 타입 정의
│       ├── exceptions.py              # KGError 계층 구조
│       │
│       ├── ontology/                  # Palantir Foundry 패턴 온톨로지
│       │   ├── core.py                # Ontology, ObjectType, LinkType, PropertyDef
│       │   └── maritime_loader.py     # 해사 온톨로지 로더
│       │
│       ├── nlp/                       # 자연어 파서
│       │   ├── nl_parser.py           # NLParser (규칙 기반 한국어)
│       │   ├── term_dictionary.py     # TermDictionary Protocol (DI)
│       │   └── maritime_terms.py      # 해사 용어 사전 (3,000+ 항목)
│       │
│       ├── entity_resolution/         # 3단계 엔티티 해석기
│       │   ├── resolver.py            # EntityResolver (정확/퍼지/LLM)
│       │   ├── fuzzy_matcher.py       # Jaro-Winkler 유사도
│       │   └── models.py              # ERCandidate, ERResult
│       │
│       ├── embeddings/                # 벡터 임베딩
│       │   └── ollama_embedder.py     # nomic-embed-text 768-dim
│       │
│       ├── etl/                       # ELT 파이프라인
│       │   ├── pipeline.py            # ETLPipeline (5단계)
│       │   ├── loader.py              # Neo4jBatchLoader (UNWIND MERGE)
│       │   ├── transforms.py          # Text/DateTime/Identifier Normalizer
│       │   ├── validator.py           # RecordValidator
│       │   ├── dlq.py                 # Dead Letter Queue
│       │   └── models.py              # PipelineConfig, RecordEnvelope
│       │
│       ├── lineage/                   # W3C PROV-O 데이터 리니지
│       │   ├── recorder.py            # LineageRecorder (in-memory + Neo4j flush)
│       │   ├── policy.py              # LineagePolicy (5 레벨: NONE ~ FULL)
│       │   ├── models.py              # LineageNode, LineageEdge, LineageGraph
│       │   └── queries.py             # MERGE_LINEAGE_NODE, GET_ANCESTORS Cypher
│       │
│       ├── rbac/                      # RBAC 정책
│       │   ├── policy.py              # RBACPolicy (Neo4j 그래프 기반)
│       │   ├── secure_builder.py      # SecureCypherBuilder (자동 필터 주입)
│       │   ├── models.py              # RBACUser, Role, DataClassification
│       │   └── schema.py              # RBAC 스키마 DDL
│       │
│       ├── n10s/                      # Neosemantics OWL 통합
│       │   ├── importer.py            # N10sImporter (OWL → Neo4j)
│       │   └── owl_exporter.py        # OWLExporter (Neo4j → OWL)
│       │
│       ├── evaluation/                # 평가 프레임워크
│       │   ├── runner.py              # EvaluationRunner
│       │   ├── metrics.py             # CypherAccuracy, QueryRelevancy
│       │   └── dataset.py             # 평가 데이터셋 (Y1: 30문항, Y5: 500문항)
│       │
│       ├── api/                       # FastAPI 애플리케이션
│       │   ├── app.py                 # create_app() 팩토리
│       │   ├── deps.py                # DI (Neo4j session, AppConfig)
│       │   ├── models.py              # Pydantic 요청/응답 모델
│       │   ├── serializers.py         # Neo4j 값 → JSON 직렬화
│       │   ├── routes/                # 라우트 핸들러
│       │   │   ├── query.py           # POST /api/v1/query/text
│       │   │   ├── ingest.py          # POST /api/v1/ingest
│       │   │   ├── ontology.py        # GET  /api/v1/ontology
│       │   │   ├── lineage.py         # GET  /api/v1/lineage/{node_id}
│       │   │   └── health.py          # GET  /health, /metrics
│       │   └── middleware/            # 미들웨어
│       │       ├── auth.py            # JWT → Keycloak 전환 예정
│       │       ├── metrics.py         # Prometheus 메트릭 기록
│       │       └── logging.py         # 구조화 JSON 로그
│       │
│       ├── crawlers/                  # 데이터 크롤러 (공통)
│       ├── schema/                    # Neo4j DDL (공통)
│       └── utils/                     # 유틸리티 (날짜, 문자열, 해시)
│
├── domains/                           ← 도메인 플러그인
│   └── maritime/
│       ├── ontology/                  # 해사 교통 온톨로지 (KRISO 기반 재설계)
│       │   ├── maritime_ontology.py   # 엔티티/관계 Python 정의
│       │   ├── maritime_loader.py     # 온톨로지 로더 (TermDictionary 구현)
│       │   └── maritime.ttl           # OWL/Turtle 파일 (Neosemantics 입력)
│       ├── nlp/                       # 해사 용어 사전
│       ├── crawlers/                  # AIS, 기상, 항만 데이터 크롤러
│       ├── schema/                    # Neo4j 스키마 DDL (해사 전용)
│       ├── s100/                      # IHO S-100 매핑 레이어 (Y2 신규)
│       │   ├── s101_mapper.py         # S-101 (전자해도) → KG 매핑
│       │   └── s124_mapper.py         # S-124 (항해 경고) → KG 매핑
│       ├── evaluation/                # 해사 도메인 평가 데이터셋
│       ├── poc/                       # 해사 PoC 데모
│       └── workflows/                 # 워크플로우 노드 정의 (→ Argo 전환 예정)
│
├── agent/                             ← 에이전트 런타임 (flux-agent-builder 이식 예정)
│   ├── runtime/                       # ReAct, Pipeline, Batch 런타임
│   │   ├── react.py                   # ReAct 에이전트 루프
│   │   ├── pipeline.py                # 고정 파이프라인 런타임
│   │   └── batch.py                   # 배치 처리 런타임
│   ├── tools/                         # 도구 레지스트리
│   │   ├── registry.py                # ToolRegistry (동적 등록)
│   │   ├── kg_query.py                # KG 쿼리 도구
│   │   ├── workflow_crud.py           # 워크플로우 CRUD 도구
│   │   └── file_system.py             # 파일 시스템 도구
│   ├── memory/                        # 대화 메모리
│   │   ├── short_term.py              # Redis 기반 단기 메모리
│   │   └── long_term.py               # Neo4j 기반 장기 메모리
│   ├── llm/                           # LLM 프로바이더 추상화
│   │   ├── provider.py                # LLMProvider Protocol
│   │   ├── ollama.py                  # Ollama 구현체
│   │   ├── openai.py                  # OpenAI 구현체 (규정 검토 후 활성화)
│   │   ├── anthropic.py               # Anthropic 구현체 (규정 검토 후 활성화)
│   │   └── failover.py                # FailoverProvider
│   ├── mcp/                           # MCP 클라이언트/서버
│   │   ├── client.py                  # MCP 클라이언트
│   │   └── server.py                  # MCP 서버 (도구 노출)
│   └── skills/                        # 스킬팩 레지스트리
│       ├── registry.py                # SkillRegistry
│       └── maritime/                  # 해사 전용 스킬팩
│
├── rag/                               ← RAG 엔진 (flux-rag 이식 예정)
│   ├── engines/                       # GraphRAG 검색 엔진 5종
│   │   ├── vector.py                  # 순수 벡터 검색
│   │   ├── graph.py                   # 그래프 구조 탐색
│   │   ├── hybrid.py                  # 벡터 + 그래프 혼합
│   │   ├── semantic.py                # 의미론적 검색
│   │   └── temporal.py                # 시간 조건부 검색
│   ├── documents/                     # 문서 파이프라인
│   │   ├── pdf_parser.py              # PDF 파싱 (pdfplumber)
│   │   ├── hwp_parser.py              # HWP 파싱 (한글 문서)
│   │   └── ocr_pipeline.py            # OCR (Tesseract + Qwen VL)
│   └── embeddings/                    # 벡터 검색 인터페이스
│       └── vector_store.py            # Milvus / Weaviate 추상화
│
├── ui/                                ← 프론트엔드 (Vue 3 + VueFlow, 신규)
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── canvas/                    # VueFlow 워크플로우 캔버스
│       │   ├── nodes/                 # 6 노드 타입 Vue 컴포넌트
│       │   │   ├── DataSourceNode.vue # 데이터 소스 노드
│       │   │   ├── TransformNode.vue  # 변환 노드
│       │   │   ├── KGQueryNode.vue    # KG 쿼리 노드
│       │   │   ├── LLMNode.vue        # LLM 추론 노드
│       │   │   ├── VisualizationNode.vue # 시각화 노드
│       │   │   └── OutputNode.vue     # 출력 노드
│       │   ├── edges/                 # 엣지 컴포넌트
│       │   └── panels/                # 속성 편집/리소스 패널
│       ├── chat/                      # 대화 인터페이스
│       │   ├── global/                # 글로벌 어시스턴트 대화창
│       │   └── node/                  # 노드별 컨텍스트 대화창
│       ├── auth/                      # Keycloak OIDC 연동
│       │   ├── keycloak.ts            # Keycloak 초기화
│       │   └── guards.ts              # Vue Router 인증 가드
│       ├── monitor/                   # 관측성 대시보드 임베드
│       ├── portal/                    # 서비스 포털 (2차 이용자용)
│       └── map/                       # 전자해도 뷰어
│           ├── ChartViewer.vue        # Leaflet / MapLibre GL JS
│           ├── AISOverlay.vue         # AIS 실시간 선박 위치
│           └── S100Layer.vue          # S-100 레이어 렌더러
│
├── gateway/                           ← API Gateway (신규)
│   ├── routes/                        # REST API 엔드포인트 정의
│   │   ├── v1/                        # v1 API
│   │   └── v2/                        # v2 API (Y3+)
│   ├── ws/                            # WebSocket (실시간 스트리밍)
│   │   ├── ais_stream.py              # AIS 데이터 스트리밍
│   │   └── etl_progress.py            # ETL 진행 상황 스트리밍
│   └── middleware/                    # 미들웨어
│       ├── keycloak.py                # Keycloak 토큰 검증
│       ├── rate_limit.py              # Rate Limiter (Redis 기반)
│       └── cors.py                    # CORS 설정
│
├── infra/                             ← 인프라
│   ├── helm/                          # Helm 차트
│   │   └── maritime-platform/
│   │       ├── Chart.yaml
│   │       ├── templates/             # K8s 리소스 템플릿
│   │       │   ├── deployment.yaml
│   │       │   ├── service.yaml
│   │       │   ├── hpa.yaml
│   │       │   ├── networkpolicy.yaml
│   │       │   └── pdb.yaml
│   │       ├── values.yaml            # 공통 기본값
│   │       ├── values-dev.yaml        # 개발 환경 오버라이드
│   │       ├── values-staging.yaml    # 스테이징 환경 오버라이드
│   │       └── values-prod.yaml       # 프로덕션 환경 오버라이드
│   ├── k8s/                           # Helm 미사용 시 직접 매니페스트
│   ├── docker/                        # Dockerfiles
│   │   ├── Dockerfile.core            # KG 엔진 API 이미지
│   │   ├── Dockerfile.frontend        # Vue 3 SPA Nginx 이미지
│   │   ├── Dockerfile.agent           # Agent Runtime 이미지
│   │   └── Dockerfile.gateway         # API Gateway 이미지
│   ├── keycloak/                      # Keycloak 설정
│   │   ├── realm-maritime.json        # Realm 정의 (클라이언트, 역할, 정책)
│   │   └── themes/                    # 커스텀 로그인 테마
│   ├── prometheus/                    # 모니터링 설정
│   │   ├── prometheus.yml             # Scrape 설정
│   │   ├── alert_rules.yml            # 알림 규칙 정의
│   │   ├── alertmanager.yml           # AlertManager 라우팅
│   │   └── grafana/                   # Grafana 대시보드 JSON (5개)
│   ├── argo/                          # Argo Workflow 템플릿
│   │   ├── templates/                 # 재사용 가능한 Workflow 템플릿
│   │   └── workflows/                 # 실행 워크플로우 정의
│   └── docker-compose.yml             # 로컬 개발용 (Neo4j+Redis+MinIO/Ceph+Keycloak)
│
├── tests/                             ← 테스트 스위트
│   ├── core/                          # KG 엔진 테스트 (19+ 파일)
│   │   ├── test_cypher_builder.py
│   │   ├── test_query_generator.py
│   │   ├── test_pipeline.py
│   │   ├── test_cypher_validator.py
│   │   ├── test_cypher_corrector.py
│   │   ├── test_hallucination_detector.py
│   │   ├── test_quality_gate.py
│   │   ├── test_ontology.py
│   │   ├── test_nl_parser.py
│   │   ├── test_entity_resolution.py
│   │   ├── test_embeddings.py
│   │   ├── test_etl_pipeline.py
│   │   ├── test_etl_loader.py
│   │   ├── test_lineage.py
│   │   ├── test_rbac.py
│   │   ├── test_n10s.py
│   │   ├── test_evaluation.py
│   │   ├── test_api_routes.py
│   │   └── test_api_middleware.py
│   ├── maritime/                      # 해사 도메인 테스트 (19+ 파일)
│   ├── agent/                         # 에이전트 테스트
│   ├── rag/                           # RAG 엔진 테스트
│   ├── e2e/                           # E2E 시나리오 테스트
│   │   ├── test_text2cypher_e2e.py    # "부산항 선박 목록" 전체 흐름
│   │   ├── test_etl_e2e.py            # AIS 수신 → KG 적재 전체 흐름
│   │   └── test_agent_e2e.py          # 에이전트 대화 전체 흐름
│   └── conftest.py                    # 공통 pytest 픽스처
│
├── docs/                              ← 문서
│   ├── strategy_5year_IMSP.md         # 5개년 전략서 (1,479줄)
│   ├── ARCHITECTURE_DETAIL_IMSP_part1.md  # 아키텍처 상세 (섹션 1~5)
│   ├── ARCHITECTURE_DETAIL_IMSP_part2.md  # 아키텍처 상세 (섹션 6~9)
│   ├── ARCHITECTURE_DETAIL_IMSP_part3.md  # 아키텍처 상세 (섹션 10~14) ← 이 파일
│   ├── DES-001_ontology_design.md     # 온톨로지 설계
│   ├── DES-002_kg_engine.md           # KG 엔진 설계
│   ├── DES-003_etl_pipeline.md        # ETL 파이프라인 설계
│   ├── DES-004_agent_runtime.md       # 에이전트 런타임 설계
│   ├── DES-005_ui_canvas.md           # UI 캔버스 설계
│   ├── REQ-001_functional.md          # 기능 요구사항
│   ├── REQ-002_nonfunctional.md       # 비기능 요구사항
│   ├── REQ-003_data.md                # 데이터 요구사항
│   ├── REQ-004_security.md            # 보안 요구사항
│   └── meeting_20260318_KRISO.md      # KRISO 미팅 정리
│
├── examples/                          ← 사용 예제
│   ├── text2cypher_basic.py           # 기본 Text2Cypher 사용법
│   ├── etl_ais_ingest.py              # AIS 데이터 수집 예제
│   └── agent_kg_query.py              # 에이전트 KG 쿼리 예제
│
├── scripts/                           ← 운영 스크립트
│   ├── migrate_schema.py              # Neo4j 스키마 마이그레이션
│   ├── load_evaluation_dataset.py     # 평가 데이터셋 로드
│   ├── export_ontology.py             # 온톨로지 OWL 내보내기
│   └── seed_demo_data.py              # 데모 데이터 시드
│
├── pyproject.toml                     # Python 프로젝트 설정 (Poetry)
├── CLAUDE.md                          # AI 어시스턴트 지침
└── AGENTS.md                          # 에이전트 코드 인덱스 (deepinit 생성)
```

---

*이 문서(Part 3)는 `strategy_5year_IMSP.md`, `architecture_flux_platform.md`,*
*`RFP-보강_K8S_S100_전략.md`, `DES-001~005` 설계 문서, `PRD.md`,*
*`meeting_20260318_KRISO.md`를 기반으로 작성되었습니다.*

*Part 1 (섹션 1~5): 시스템 개요, 핵심 구성 요소, KG 엔진 상세, 온톨로지, ETL*
*Part 2 (섹션 6~9): API, 인증/보안, 인프라, 워크플로우*
*Part 3 (섹션 10~14): 관측성, AI/LLM, 설계 원칙, 연차별 진화, 디렉토리 구조*
*Part 4 (섹션 16): 플랫폼 운영 기능 아키텍처 (Gap 보완)*

---

## 16. 플랫폼 운영 기능 아키텍처 (Gap 보완)

> **추가 배경:** Suredata Lab 사전착수회의(2026-03-18) 및 RFP 요구사항 점검 결과, KG 엔진 외 플랫폼 운영 계층 기능이 미설계로 확인되어 본 섹션을 추가한다.

### 16.1 통합 리니지 설계 (4종)

RFP는 데이터·모델·노드·워크플로우 4가지 대상에 대한 리니지를 요구한다. 기존 Section 4.6의 데이터 리니지(W3C PROV-O)를 기반으로 4종 통합 리니지를 설계한다.

```
통합 리니지 (W3C PROV-O 확장)
|
+-- 데이터 리니지 (Section 4.6 기존 설계)
|   RawAsset -> ProcessedAsset -> TransformActivity -> ProvenanceChain
|   추적 대상: 원천 데이터 수집 → 변환 → KG 적재 → 파생 분석
|
+-- 모델 리니지 (신규)
|   ModelVersion -> TrainingRun -> Dataset -> DeploymentRecord
|   추적 대상: 학습 데이터 → 하이퍼파라미터 → 모델 버전 → 배포 이력 → 성능 메트릭
|   저장: Neo4j (:ModelVersion)-[:TRAINED_ON]->(:Dataset)
|         (:ModelVersion)-[:DEPLOYED_AS]->(:DeploymentRecord)
|
+-- 노드 리니지 (신규)
|   NodeExecution -> InputArtifact -> OutputArtifact -> ErrorLog
|   추적 대상: 노드 실행 시각 → 입력/출력 데이터 → 실행 시간 → 오류 이력
|   저장: Neo4j (:NodeExecution)-[:CONSUMED]->(:Artifact)
|         (:NodeExecution)-[:PRODUCED]->(:Artifact)
|
+-- 워크플로우 리니지 (신규)
    WorkflowRun -> NodeExecution[] -> ServiceVersion -> ChangeLog
    추적 대상: 워크플로우 실행 DAG → 노드별 실행 결과 → 버전 변경 이력
    저장: Neo4j (:WorkflowRun)-[:EXECUTED]->(:NodeExecution)
          (:WorkflowRun)-[:VERSION_OF]->(:WorkflowDefinition)
    연동: Argo Workflow 실행 이벤트 → Webhook → 리니지 자동 기록
```

**통합 리니지 Neo4j 스키마 (추가 엔티티):**

| 엔티티 | 속성 | 관계 |
|--------|------|------|
| ModelVersion | modelId, version, framework, metrics, createdAt | TRAINED_ON, DEPLOYED_AS |
| TrainingRun | runId, hyperparams, duration, gpuHours | USED_DATASET, PRODUCED_MODEL |
| DeploymentRecord | deployId, endpoint, replicas, status | SERVES_MODEL |
| NodeExecution | execId, nodeType, startTime, endTime, status | CONSUMED, PRODUCED, PART_OF |
| WorkflowRun | runId, workflowId, trigger, status, duration | EXECUTED, VERSION_OF |
| WorkflowDefinition | workflowId, version, author, updatedAt | CONTAINS_NODE, DERIVED_FROM |

### 16.2 자산 관리 체계 (Asset Management)

플랫폼에 등록되는 모든 유무형 자산을 통합 관리하는 체계이다. 자산은 KG 노드로 메타데이터가 관리되며, W3C PROV-O 리니지로 이력이 추적된다.

```
자산 라이프사이클
|
+-- 등록 (Register)
|   자산 메타데이터 생성, KG 노드 생성, 버전 v1.0 할당
|
+-- 개발 (Develop)
|   버전 관리 (Git 기반), 변경 이력 추적
|
+-- 검증 (Validate)
|   단위 테스트, 통합 테스트, 품질 게이트 통과
|
+-- 배포 (Deploy)
|   컨테이너 빌드, K8s Deployment/Job 생성
|
+-- 운영 (Operate)
|   모니터링, 성능 메트릭 수집, 사용 통계
|
+-- 폐기 (Deprecate)
    사용 중지 알림, 의존성 분석, 아카이브
```

**자산 유형별 메타데이터:**

| 자산 유형 | 저장소 | 메타데이터 (Neo4j) | 원본 (Object Storage) |
|----------|--------|-------------------|---------------------|
| 데이터 자산 | Object Storage | 스키마, 크기, 포맷, 소유자, 접근 등급 | raw/{source}/{date}/ |
| 모델 자산 | Model Registry | 프레임워크, 버전, 메트릭, 입출력 스펙 | models/{name}/{version}/ |
| 노드 자산 | GitLab | 노드 타입, 입출력 스펙, 의존성, 컨테이너 이미지 | 소스코드 (Git) |
| 워크플로우 자산 | PostgreSQL + KG | DAG 구조, 노드 목록, 파라미터 스키마 | JSON 정의 |
| 서비스 자산 | K8s + KG | 엔드포인트, SLA, 접근 정책, 사용 통계 | Deployment YAML |

**API 엔드포인트 (계획):**

```
POST   /api/v1/assets                    자산 등록
GET    /api/v1/assets?type=&owner=       자산 목록 조회 (필터/검색)
GET    /api/v1/assets/{id}               자산 상세 조회
PUT    /api/v1/assets/{id}               자산 메타데이터 수정
DELETE /api/v1/assets/{id}               자산 폐기 (soft delete)
GET    /api/v1/assets/{id}/versions      자산 버전 이력
GET    /api/v1/assets/{id}/lineage       자산 리니지 그래프
POST   /api/v1/assets/{id}/deploy        자산 배포 (서비스화)
GET    /api/v1/assets/search?q=          자연어 기반 자산 검색 (KG + 벡터)
```

### 16.3 서비스 Pool 및 공개 관리

워크플로우를 개발한 후 "서비스"로 등록하고 외부에 공개하는 라이프사이클을 관리한다.

```
워크플로우 → 서비스 전환 라이프사이클

[워크플로우 저작]
     |
     v 기능 테스트 통과
[응용(App) 등록]  ← 1회성 실행, K8s Job
     |
     v 안정성 검증 (3회 이상 성공 실행)
[서비스(Service) 승격]  ← 지속 운용, K8s Deployment
     |
     v 관리자 심사/승인
[서비스 Pool 등록]  ← 카탈로그에 노출
     |
     v 접근 정책 설정
[서비스 공개]  ← 서비스 포털에서 이용 가능
     |
     v 사용 통계 수집
[서비스 운영/모니터링]
```

**워크플로우 서비스 GW:**

API Gateway(내부 개발자용)와 별도로, 등록된 서비스를 외부 사용자가 호출하는 전용 Gateway를 운영한다.

| Gateway | 대상 | 경로 Prefix | 인증 | Rate Limit |
|---------|------|-----------|------|-----------|
| Internal API GW | 개발자/연구자 | `/api/v1/` | Keycloak OIDC (JWT) | 1000 req/min |
| Service GW | 서비스 사용자 | `/service/v1/` | Keycloak OIDC 또는 API Key | 100 req/min (테넌트별) |

**서비스 Pool 관리 API (계획):**

```
POST   /api/v1/services                  서비스 등록 (워크플로우 → 서비스 전환)
GET    /api/v1/services                   서비스 카탈로그 조회
GET    /api/v1/services/{id}              서비스 상세 정보
PUT    /api/v1/services/{id}/publish      서비스 공개 (심사 후)
PUT    /api/v1/services/{id}/unpublish    서비스 비공개 전환
GET    /api/v1/services/{id}/stats        서비스 사용 통계
GET    /service/v1/{serviceId}/invoke     서비스 호출 (Service GW 경유)
```

### 16.4 협업 및 작업 공유 관리

멀티 연구자가 프로젝트 단위로 워크플로우·데이터·모델을 공유하고 협업하는 기능이다.

**프로젝트 작업 공간 (Project Workspace):**

```
프로젝트 (Project)
  |
  +-- 멤버 관리 (RBAC: Owner / Editor / Viewer)
  +-- 공유 자산 (데이터, 모델, 워크플로우)
  +-- 공유 KG 네임스페이스 (Neo4j 라벨 프리픽스 격리)
  +-- 활동 로그 (변경 이력, 댓글)
  +-- 환경 설정 (GPU 할당, 저장소 쿼터)
```

| 기능 | 설명 | K8s 구현 |
|------|------|---------|
| 프로젝트 생성 | 격리된 작업 공간 생성 | Namespace 또는 라벨 기반 격리 |
| 멤버 초대 | Keycloak 그룹 + RBAC 매핑 | Keycloak Group → K8s RoleBinding |
| 자산 공유 | 프로젝트 내 자산 공유 레벨 설정 | KG 접근 정책 (SecureCypherBuilder) |
| 워크플로우 공유 | 워크플로우 복제/포크/공동 편집 | PostgreSQL workflow_share 테이블 |
| 실시간 알림 | 변경/실행/오류 알림 | WebSocket + Redis Pub/Sub |

### 16.5 커스텀 노드 개발 SDK 및 Antigravity 연계

외부 개발자(연구자)가 자체 워크플로우 노드를 개발하고 플랫폼에 등록할 수 있는 도구 체인이다.

**노드 개발 프로시저 (Antigravity 연계):**

```
1. VS Code + Antigravity Extension 설치
     |
     v
2. 새 자산 프로젝트 생성 (IMSP 플랫폼 연계용 Extension)
   ├── 자산 개발 가이드.md (자동 생성)
   ├── 자산 개발 계획.md (AI Prompting으로 작성)
   ├── Dockerfile.default (자동 생성)
   └── src/ (소스 코드)
     |
     v AI Prompting (Antigravity)
3. 소스 코드 작성 (Python 또는 Node.js)
   ├── node_spec.yaml   # 노드 입출력 스펙 정의
   ├── main.py          # 노드 실행 로직
   ├── requirements.txt # 의존성
   └── test_node.py     # 단위 테스트
     |
     v
4. 자산 빌드 (Docker 이미지)
   docker build -t registry.kriso.re.kr/nodes/{node-name}:{version} .
     |
     v
5. 자산 등록 (IMSP 플랫폼 업로드)
   imsp-cli asset register --type node --spec node_spec.yaml --image ...
     |
     v
6. 노드 팔레트에 노출 (VueFlow 캔버스에서 사용 가능)
```

**노드 스펙 YAML 예시:**

```yaml
name: ais-anomaly-detector
version: 1.0.0
category: Transform
maritime_specific: true
description: AIS 데이터에서 항로 이탈 및 속도 이상을 탐지
inputs:
  - name: ais_data
    type: json_array
    description: AIS 메시지 배열
  - name: threshold
    type: float
    default: 2.0
    description: 이상 탐지 임계값 (표준편차 배수)
outputs:
  - name: anomalies
    type: json_array
    description: 탐지된 이상 항목
  - name: statistics
    type: json_object
    description: 탐지 통계
container:
  image: registry.kriso.re.kr/nodes/ais-anomaly-detector:1.0.0
  resources:
    memory: 512Mi
    cpu: "0.5"
```

---

## 15. 아키텍처 리뷰 및 개선 계획

> 리뷰일: 2026-03-20 | 리뷰어: Architect Agent (Opus)

### 15.1 식별된 문제 요약

| 구분 | 건수 | 주요 항목 |
|------|:---:|----------|
| CRITICAL (즉시 수정) | 6 | 역방향 의존, API Key 보안, Lineage 비영속, Dev 보안 우회, DB 마이그레이션 전략 부재, timezone |
| HIGH (빠른 대응) | 10 | Neo4j CE 한계, Entity Resolution O(n²), ETL 동기 전용, RBAC regex, Batch Loader 트랜잭션, JWT→Keycloak 경로, Gateway 분리, Circuit Breaker, 데이터 보존, 재해 복구 |
| MEDIUM (계획 수립) | 6 | Coverage 60%, API 버전, 멀티테넌시, 부하 테스트, LangChain 의존, 문서 현재/미래 혼용 |

### 15.2 CRITICAL 수정 계획

#### C-1. core/kg/ → maritime/ 역방향 의존 제거

**문제:** 15+ 파일에서 `from maritime.* import *` — Plugin Architecture 무효화

**수정 방안:**
```
Before: core/kg/maritime_factories.py  →  from maritime.factories import *
After:  core/kg/maritime_factories.py  →  삭제 (maritime/factories.py만 존재)

Before: core/kg/nlp/maritime_terms.py  →  from maritime.nlp.maritime_terms import *
After:  core/kg/nlp/nl_parser.py       →  TermDictionary Protocol로 DI

Before: core/kg/api/entity_groups.py   →  from maritime.entity_groups import *
After:  core/kg/api/entity_groups.py   →  Registry Pattern (런타임 등록)
```

**원칙:** `core/kg/`는 `maritime.*` import 0건이 되어야 함

#### C-2. API Key 인증 보안 강화

**문제:** 모든 API Key 보유자에게 admin 역할 자동 부여

**수정:**
```python
# Before
return {"sub": "api-key-user", "role": "admin"}

# After
API_KEY_ROLES = {
    "suredata-ingest-key": {"sub": "suredata", "role": "data_provider", "scope": ["ingest"]},
    "internal-api-key":    {"sub": "internal", "role": "developer",     "scope": ["query", "schema"]},
}
```

#### C-3. Lineage Neo4j 영속화

**문제:** LineageRecorder가 in-memory only, 크래시 시 데이터 소실

**수정:**
- `LineageRecorder.flush(session)` 메서드 추가
- `ETLPipeline.run()` 완료 시 자동 flush 호출
- `lineage/queries.py`의 MERGE_LINEAGE_NODE/EDGE 활용

#### C-4. Development 모드 보안 개선

**수정:**
- dev 모드 시 `logger.critical("⚠️ SECURITY: Running in development mode - ALL AUTH BYPASSED")` 경고
- `APP_API_KEY` 또는 `JWT_SECRET_KEY` 설정 시 dev 모드 자동 거부
- 프로덕션 환경 감지 시 dev 모드 진입 차단

#### C-5. ETL datetime timezone 통일

**수정:** `datetime.now()` → `datetime.now(timezone.utc)` 전체 치환

#### C-6. DB 마이그레이션 프레임워크 설계

**설계:**
```
infra/migrations/
├── 001_initial_schema.cypher
├── 002_add_lineage_indexes.cypher
├── 003_ontology_v1_redesign.cypher
└── migrate.py   # (:Migration {version, applied_at}) 노드 기반 추적
```

### 15.3 확장성 대응 계획

#### S-1. Neo4j CE 한계 대응

| 연차 | 전략 |
|------|------|
| Y1-Y2 | CE 단일 인스턴스 + 애플리케이션 캐싱 + 읽기 최적화 |
| Y2 | EE 라이선스 예산 요청 (또는 Apache AGE 벤치마크) |
| Y3 | EE 전환 또는 AGE 전환 (3계층 온톨로지로 매핑만 교체) |
| Y4-Y5 | Causal Clustering + Read Replica + Online Backup |

#### S-2. Entity Resolution 성능 개선

```
현재: O(n²) 전수 비교
목표: O(n log n) Blocking + Canopy

Phase 1 (Y1): Blocking by entity type + first character
Phase 2 (Y2): MinHash LSH for fuzzy tier
Phase 3 (Y3): HNSW approximate NN for embedding tier
```

#### S-3. ETL 비동기 경로 추가

```
현재: 동기 ETLPipeline.run() (Batch CronJob 전용)
추가: AsyncETLPipeline.run_async() (Streaming 전용, Y2)

Batch (현행 유지):  CronJob → ETLPipeline.run() → Neo4jBatchLoader
Streaming (Y2 신규): Kafka → AsyncETLPipeline → async Neo4j driver
```

#### S-4. RBAC 강화

```
현재: regex 기반 WHERE 주입 (단순 쿼리만)
목표: SecureCypherBuilder 전용 경로

1. LLM 생성 Cypher → 반드시 SecureCypherBuilder 래핑
2. 직접 Cypher 실행 금지 (Query API에서 차단)
3. RBAC bypass detection 로직 추가
```

#### S-5. Batch Loader 트랜잭션 관리

```python
# Before: session.run() 직접 호출, partial commit 위험
session.run(cypher, {"batch": batch})

# After: execute_write() + 재시도
session.execute_write(
    lambda tx: tx.run(cypher, {"batch": batch}),
    max_retry_time=30
)
```

### 15.4 누락 항목 보완 계획

| 항목 | 대응 | 시점 |
|------|------|------|
| DB 마이그레이션 | Migration runner + versioned .cypher 파일 | Y1 Q1 |
| Circuit Breaker | pybreaker + connection pool 모니터링 | Y1 Q2 |
| 데이터 보존 정책 | Object Storage lifecycle + Neo4j archival CronJob | Y1 Q2 |
| 재해 복구 | neo4j-admin dump CronJob + Object Storage 복제 | Y1 Q2 |
| 부하 테스트 | k6/Locust + tests/perf/ | Y1 Q3 |
| 멀티테넌시 | tenantId 속성 기반 격리 + BatchLoader 강제 | Y2 Q1 |
| LangChain 격리 | 얇은 래퍼 인터페이스 뒤에 격리 | Y1 Q1 |

### 15.5 API 버전 전략

```
현재: /api/health, /api/query, /api/schema (무버전)
목표: /api/v1/health, /api/v1/query, /api/v1/schema

전환 전략:
1. 모든 라우트를 /api/v1/ prefix로 이동
2. 기존 /api/ 경로는 301 Redirect (하위 호환, 3개월 유지)
3. Suredata 연동 API도 /api/v1/ 통일
```

### 15.6 확장성이 잘 설계된 부분 (유지)

| 설계 | 근거 |
|------|------|
| **3계층 온톨로지 분리** | DB 교체 시 Mapping만 교체. 5년 생존력 확보 |
| **ELT 전략 (Object Storage 원천 보존)** | 온톨로지 변경 시 원천 재처리 가능. 최고의 설계 결정 |
| **Text2Cypher 5단계 파이프라인** | 각 단계 독립 교체 가능. 70%→95% 경로 열림 |
| **Frozen Config** | 런타임 설정 변경 방지. 장기 운영 안정 |
| **DLQ 패턴** | 실패 레코드 보존. 정부 과제 추적성 충족 |
| **PEP 562 하위 호환** | DeprecationWarning 점진적 마이그레이션 |
