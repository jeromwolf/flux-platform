# 3. 컴포넌트 아키텍처

[← 시스템 아키텍처](./02-system-architecture.md) | [다음: 데이터 아키텍처 →](./04-data-architecture.md)

## 개요

IMSP Service Tier를 구성하는 핵심 컴포넌트(KG Engine, API, Agent Runtime, Workflow Engine, RAG Engine)의 내부 구조와 모듈 간 의존성을 기술한다. 각 컴포넌트는 독립적으로 배포 가능한 마이크로서비스 단위로 설계되며, FastAPI + Python 3.10+ 기반 비동기 처리를 공통 런타임으로 사용한다.

---

## 3.1 KG Engine (core/kg/) -- 모듈 의존성

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
  +-- DLQManager (Dead Letter Queue → Object Storage)
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

---

## 3.2 API 엔드포인트 (현재 구현 + 계획)

### 3.2.1 현재 구현 (core/kg/api/)

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

### 3.2.2 계획 (Suredata Lab 연동 API v1)

```
POST /api/v1/ingest/raw                    원천 데이터 등록 (→ Ceph RGW)
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

---

## 3.3 Agent Runtime (agent/ -- 이식 예정)

> :hourglass_flowing_sand: **이식 예정** -- flux-agent-builder에서 이식 예정. 현재 설계만 존재.

### 3.3.1 아키텍처 다이어그램

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

### 3.3.2 ReAct 루프 구조

flux-agent-builder에서 이식될 핵심 실행 모델은 **ReAct(Reason + Act)** 패턴이다. LLM이 사고 과정(Reasoning)과 행동(Acting)을 교대로 수행하며, 관찰 결과(Observation)를 다음 사고에 반영하는 루프 구조를 따른다.

```
사용자 질의 입력
     |
     v
+-----------------------------+
|  Reason (사고)               |
|  - 현재 상태 분석            |
|  - 다음 행동 결정            |
|  - 필요한 도구 선택          |
+-----------------------------+
     |
     v
+-----------------------------+
|  Act (행동)                  |
|  - 선택된 Tool 호출          |
|  - KG 질의 / API 호출 /     |
|    파일 읽기 등               |
+-----------------------------+
     |
     v
+-----------------------------+
|  Observe (관찰)              |
|  - Tool 실행 결과 수신       |
|  - 결과 해석 및 평가         |
|  - 충분한 정보 확보 여부 판단 |
+-----------------------------+
     |
     +---> 정보 부족 → Reason으로 복귀 (최대 N회 반복)
     |
     +---> 충분 → 최종 응답 생성
```

**실행 모드 비교:**

| 모드 | 용도 | 특성 | 최대 반복 |
|------|------|------|----------|
| **ReAct** | 대화형 질의응답 | 사고-행동-관찰 루프, 단일 질의 처리 | 10회 |
| **Pipeline** | 다단계 처리 | 순차적 단계 실행, 단계 간 데이터 전달 | 단계 수 |
| **Batch** | 대량 처리 | 동일 작업 반복, 병렬 처리 가능 | 무제한 |

### 3.3.3 Tool Registry 패턴

에이전트가 사용할 수 있는 도구는 **Tool Registry**에 등록되며, LLM이 Function Calling을 통해 동적으로 선택한다.

| 도구 카테고리 | 도구 목록 | 설명 |
|--------------|----------|------|
| **KG 질의** | `kg_query`, `kg_schema`, `kg_search` | Text2Cypher, 스키마 조회, 풀텍스트 검색 |
| **워크플로우** | `workflow_list`, `workflow_create`, `workflow_execute` | 워크플로우 CRUD 및 실행 |
| **데이터** | `data_ingest`, `data_status`, `data_lineage` | 데이터 수집, 상태 확인, 리니지 추적 |
| **파일** | `file_read`, `file_write`, `file_list` | Object Storage 파일 접근 |
| **시각화** | `chart_create`, `map_render`, `table_format` | ECharts, Leaflet, AG Grid |
| **외부 API** | `web_search`, `api_call`, `weather_fetch` | 웹 검색, REST API 호출, 기상 데이터 |
| **계산** | `math_eval`, `statistics`, `geo_distance` | 수학 연산, 통계, 지리 계산 |

### 3.3.4 대화 메모리

| 메모리 유형 | 저장소 | TTL | 용도 |
|------------|--------|-----|------|
| **Short-term (단기)** | Redis | 세션 종료 시 | 현재 대화 컨텍스트, 최근 N턴 히스토리 |
| **Long-term (장기)** | Neo4j | 영구 | 사용자별 대화 요약, 선호도, 학습된 패턴 |
| **Working (작업)** | In-memory | 요청 단위 | ReAct 루프 내 중간 결과, Tool 호출 이력 |

단기 메모리는 Redis에 세션 ID 기반으로 저장되어 빠른 읽기/쓰기를 보장하고, 장기 메모리는 Neo4j 그래프에 `(:User)-[:HAD_CONVERSATION]->(:ConversationSummary)` 형태로 영속화된다. 장기 메모리에서 사용자 패턴을 학습해 향후 질의에 대한 응답 품질을 점진적으로 개선한다.

### 3.3.5 LLM Provider 추상화 및 Failover

```
LLMProvider (추상 인터페이스)
  |
  +-- OllamaProvider (1순위, 온프레미스)
  |     - 모델: llama3, codellama, mistral 등
  |     - GPU: A100 (KRISO 인프라)
  |     - 지연: ~1-3s (로컬 네트워크)
  |
  +-- OpenAIProvider (2순위, 클라우드 폴백)
  |     - 모델: gpt-4o, gpt-4o-mini
  |     - API Key 기반
  |     - 지연: ~2-5s (네트워크 포함)
  |
  +-- AnthropicProvider (3순위, 최종 폴백)
        - 모델: claude-sonnet-4-20250514
        - API Key 기반
        - 지연: ~2-5s (네트워크 포함)
```

**Failover 전략:**
1. Ollama(온프레미스) 호출 시도 → 3회 연속 실패 시 Circuit Breaker Open
2. OpenAI로 자동 전환 → 실패 시 Anthropic으로 전환
3. 모든 Provider 실패 시 사용자에게 오류 반환 + 관리자 알림
4. Circuit Breaker Half-Open(60초 후) 시 Ollama 재시도

### 3.3.6 MCP (Model Context Protocol) 통합

MCP는 에이전트가 외부 시스템과 상호작용하기 위한 표준 프로토콜이다. 에이전트는 MCP 클라이언트로서 동적으로 MCP 서버를 발견하고 연결한다.

| MCP 서버 | 제공 기능 | 연결 방식 |
|----------|----------|----------|
| **파일 시스템** | Object Storage(Ceph) 파일 읽기/쓰기 | stdio (동일 Pod) |
| **Neo4j** | Cypher 실행, 스키마 조회 | SSE (내부 네트워크) |
| **외부 API** | 기상청, 해양수산부, AIS 수신기 | SSE (인터넷) |
| **Argo Workflow** | 워크플로우 제출, 상태 조회 | SSE (K8s 내부) |
| **시각화** | 차트/지도 렌더링 요청 | stdio (동일 Pod) |

---

## 3.4 Workflow Engine -- 6 노드 타입

| # | 노드 타입 | 역할 | 예시 |
|---|-----------|------|------|
| 1 | **Trigger** | 워크플로우 실행 시점 정의 | Manual, Cron, Webhook, App Event, Error Event |
| 2 | **Action** | 외부 시스템 조작 및 부수효과 | HTTP/GraphQL, Messaging, File I/O, DB CRUD, Docker |
| 3 | **Connector** | 외부 시스템 연동 | SaaS/API, SFTP, SQL DB, OAuth2/OIDC |
| 4 | **Control** | 흐름 제어 | If/Switch, Merge, Split in Batches, Wait, Error |
| 5 | **Transform** | 해사 데이터 변환 | AIS NMEA, Radar, S-100, GRIB2, PDF/OCR, VHF/STT |
| 6 | **Special** | AI/LLM 고급 기능 | Skills, MCP, LLM Calls, YOLO/OCR/NER 모델 |

VueFlow 캔버스에서 저작된 워크플로우 JSON은 Argo Workflow DAG YAML로 변환되어 Kubernetes에서 실행된다. 각 노드는 독립 Pod로 실행되며 노드 간 데이터는 Argo Artifact(Object Storage)로 전달된다.

### VueFlow → Argo 변환 상세

#### 노드 타입별 Argo 템플릿 매핑

VueFlow JSON의 6종 노드 타입은 아래 규칙에 따라 Argo Workflow 템플릿으로 변환된다.

| VueFlow 노드 타입 | Argo 템플릿 타입 | 실행 방식 | 비고 |
|-------------------|-----------------|----------|------|
| **Trigger** (Manual) | `Event` (수동 제출) | Argo Events → Workflow 트리거 | 수동 실행 시 Argo API 직접 호출 |
| **Trigger** (Cron/Webhook) | `CronWorkflow` / `Event` | 스케줄 기반 또는 HTTP Webhook 수신 | Cron 표현식은 VueFlow 설정에서 그대로 전달 |
| **Action** | `Container` 템플릿 | K8s Job (1회 실행 후 종료) | HTTP/DB/File 등 부수효과 수행 컨테이너 |
| **Connector** | `Container` 템플릿 + `Retry` 정책 | K8s Job + 재시도 (최대 3회) | 외부 시스템 연동 시 네트워크 오류 대비 Retry 적용 |
| **Control** (If/Switch) | DAG 분기 (`when` 조건) | Argo DAG `dependencies` + `when` 표현식 | VueFlow 조건식을 Argo 표현식으로 변환 |
| **Transform** | `Container` 템플릿 | K8s Job (데이터 변환) | 입출력은 Argo Artifact로 전달 |
| **Special** (AI/LLM) | `Container` 템플릿 + GPU `nodeSelector` | GPU Pod에서 실행 | `nvidia.com/gpu: 1` 리소스 요청 자동 추가 |

#### 변환 시 오류 처리

변환 엔진은 VueFlow JSON을 Argo DAG YAML로 변환하기 전 다음 검증을 수행한다.

| 검증 항목 | 오류 유형 | 처리 방식 |
|-----------|----------|----------|
| **연결 무결성** | 끊어진 엣지 (소스/타겟 노드 누락) | 변환 거부 + 오류 노드 하이라이트 반환 |
| **필수 파라미터** | 노드 설정 값 누락 (예: AIS 수신기 주소 미입력) | 변환 거부 + 누락 파라미터 목록 반환 |
| **순환 참조** | DAG에 사이클 존재 | 토폴로지 정렬(Kahn's Algorithm) 시 탐지, 변환 거부 |
| **타입 불일치** | 출력 포트 타입과 입력 포트 타입 불일치 | 경고 반환 (자동 변환 가능 시 Transform 노드 자동 삽입) |
| **리소스 초과** | GPU 노드 3개 이상 동시 요청 | 경고 반환 (관리자 승인 필요) |

#### 부분 실행 및 재시작

Argo Workflow의 `--from` 옵션을 활용하여 실패한 노드부터 재실행(Resume)을 지원한다.

```
실행 흐름: A → B → C(실패) → D → E
                       |
                 재시작 시 C부터 재실행
                 A, B의 Artifact는 Object Storage에 보존되어 재사용
```

- **재시작 조건**: 사용자가 VueFlow UI에서 실패 노드를 우클릭 → "여기서 재실행" 선택
- **Artifact 보존**: 성공한 노드의 출력 Artifact는 Object Storage에 7일간 보존 (TTL 설정 가능)
- **파라미터 수정**: 재실행 전 실패 노드의 파라미터를 수정할 수 있음 (VueFlow UI에서 인라인 편집)
- **실패 알림**: 노드 실패 시 Grafana Alert → Webhook으로 담당자에게 즉시 알림

### 3.4.1 1차년도 노드 5종 개발 목록

RFP 1차년도 결과물로 아래 5종 노드를 개발한다 (해사서비스 특화 2종 포함).

| # | 노드명 | 카테고리 | 해사 특화 | 입력 | 출력 | 설명 |
|---|--------|---------|:--------:|------|------|------|
| 1 | **AIS 데이터 수집** | Connector | **Yes** | AIS 수신기 주소, 필터 조건 | AIS 메시지 스트림 (NMEA -> JSON) | NMEA 0183/2000 프로토콜 AIS 데이터 수집, 파싱, 저장. 실시간 스트림 및 배치 모드 지원 |
| 2 | **S-100 해도 파서** | Transform | **Yes** | S-100 GML 파일 경로 | 파싱된 해도 피처 (GeoJSON) | IHO S-101 ENC, S-111 해류, S-127 VTS 등 S-100 표준 파일 파싱 및 KG 적재 |
| 3 | **데이터 변환** | Transform | No | 원천 데이터 (CSV/JSON/XML) | 정규화된 레코드 | 텍스트 정규화, 날짜 표준화(ISO 8601), 식별자 변환(IMO/MMSI), 임베딩 생성 |
| 4 | **KG 질의** | Action | No | 자연어 질문 또는 Cypher | 쿼리 결과 (JSON) | Text2Cypher 파이프라인 호출, 결과 반환. 파라미터로 실행 모드(parse_only/execute) 선택 |
| 5 | **시각화 출력** | Action | No | 데이터셋 (JSON/GeoJSON) | 차트/지도/테이블 렌더링 | ECharts 기반 차트, Leaflet 기반 지도, AG Grid 테이블. 대시보드 패널로 임베드 가능 |

> **2차년도 추가 예정 노드:** 기상 수집(GRIB2), OCR 문서 처리, 관계 추출(NER+RE), 이상 탐지, 워크플로우 트리거(Cron/Webhook)

---

## 3.4.2 Crawlers 모듈 (core/kg/crawlers/)

ELT 파이프라인의 Extract 단계에서 외부 데이터 소스를 수집하는 크롤러 모듈이다. 현재 8개 파일로 구성되며, `BaseCrawler` 추상 클래스를 상속해 도메인별 크롤러를 구현하는 구조를 따른다.

```
BaseCrawler (ABC)
  +-- fetch()          # 데이터 수집 (추상 메서드)
  +-- parse()          # 응답 파싱 (추상 메서드)
  +-- validate()       # 수집 데이터 검증
  +-- store()          # Object Storage 적재
  |
  +-- AISCrawler           # AIS 수신기 NMEA 데이터 수집
  +-- WeatherCrawler       # 기상청 GRIB2/JSON 수집
  +-- RegulationCrawler    # 해사 법규 DB 수집
  +-- S100Crawler          # IHO S-100 해도 파일 동기화
  +-- CCTVCrawler          # RTSP 스트림 프레임 캡처

CrawlerRegistry
  +-- register()       # 크롤러 등록
  +-- get_crawler()    # 이름으로 크롤러 조회
  +-- list_crawlers()  # 등록된 크롤러 목록
```

| 파일 | 역할 |
|------|------|
| `base.py` | `BaseCrawler` ABC 정의 (fetch/parse/validate/store 인터페이스) |
| `registry.py` | `CrawlerRegistry` -- 크롤러 등록/조회/목록 관리 |
| `ais_crawler.py` | AIS NMEA 0183/2000 TCP 소켓 수집 |
| `weather_crawler.py` | 기상청 API GRIB2/JSON 주기적 수집 |
| `regulation_crawler.py` | 해수부/해경 법규 REST API 수집 |
| `s100_crawler.py` | S-100 해도 파일 HTTPS/FTP 동기화 |
| `cctv_crawler.py` | CCTV RTSP 스트림 프레임 캡처 |

> **역방향 의존성 주의:** 현재 이 모듈은 `domains/maritime/`의 도메인 스키마에 직접 의존하고 있다 (해사 용어 사전, NMEA 파서 등). 이는 `core/`가 `domains/`에 의존하는 역방향 의존성(reverse dependency)으로, 향후 Plugin Architecture를 통해 해결할 예정이다. 크롤러가 도메인 로직을 플러그인 인터페이스(`CrawlerPlugin`)로 주입받는 구조로 전환하여 `core/`의 도메인 독립성을 회복한다.

---

## 3.5 RAG Engine (rag/ -- 이식 예정)

> :hourglass_flowing_sand: **이식 예정** -- flux-rag에서 이식 예정. 현재 설계만 존재.

### 3.5.1 5 GraphRAG Retriever

| # | Retriever | 전략 | 적합한 질문 유형 |
|---|-----------|------|----------------|
| 1 | **Vector Retriever** | 임베딩 유사도 검색 | "선박 충돌 관련 논문" |
| 2 | **VectorCypher Retriever** | 벡터 검색 + 그래프 순회 | "부산항 관련 연구 및 주변 시설" |
| 3 | **Text2Cypher Retriever** | NL -> Cypher -> KG 직접 조회 | "2024년 해양사고 건수는?" |
| 4 | **Hybrid Retriever** | 벡터 + 그래프 점수 결합 | "울산항 위험물 운반선 규정" |
| 5 | **ToolsRetriever (Agentic)** | LLM이 전략 자동 선택 | 복합 질문 (자동 라우팅) |

### 3.5.2 하이브리드 검색 아키텍처 (Sparse + Dense + KG)

RAG Engine은 단일 검색 전략이 아닌, 세 가지 검색 축을 결합하는 하이브리드 검색 아키텍처를 채택한다. 각 축의 검색 결과를 **Reciprocal Rank Fusion (RRF)** 또는 가중 합산으로 통합해 최종 문서를 선정한다.

```
사용자 질의
     |
     +---> [Sparse Retriever (BM25)]
     |       - Elasticsearch / Neo4j Fulltext Index
     |       - 키워드 기반 역색인 매칭
     |       - 정확한 용어 매칭에 강점 (IMO 번호, 항구명 등)
     |
     +---> [Dense Retriever (Vector)]
     |       - Neo4j Vector Index (nomic-embed-text, 768d)
     |       - 의미적 유사도 기반 검색
     |       - 동의어, 유사 표현 매칭에 강점
     |
     +---> [KG Traversal Retriever]
             - Cypher 패턴 매칭 + 그래프 순회
             - 관계 기반 연관 정보 탐색
             - 구조적 질문에 강점 ("A와 연결된 모든 B")
     |
     v
+-----------------------------+
|  Score Fusion               |
|  - RRF (Reciprocal Rank     |
|    Fusion)                  |
|  - 가중 합산 (w_sparse,    |
|    w_dense, w_kg)           |
+-----------------------------+
     |
     v
+-----------------------------+
|  Re-ranker                  |
|  (Cross-encoder)            |
|  질의-문서 쌍 점수 재계산     |
+-----------------------------+
     |
     v
  Top-K 문서 반환 → LLM 컨텍스트
```

### 3.5.3 문서 파이프라인

원천 문서(PDF, HWP, 스캔 이미지 등)를 검색 가능한 형태로 변환하는 파이프라인이다.

```
원천 문서 (Object Storage)
     |
Phase 1: 문서 로딩
     +-- PDF: PyPDF2 / pdfplumber
     +-- HWP: pyhwp / hwp5html
     +-- 이미지: PaddleOCR (한국어 OCR)
     +-- 웹: BeautifulSoup / Scrapy
     |
Phase 2: 청킹 (Chunking)
     +-- 전략: Recursive Character Splitter
     +-- 청크 크기: 512 tokens (overlap: 50)
     +-- 메타데이터 보존: 출처, 페이지, 섹션
     |
Phase 3: 임베딩 생성
     +-- 모델: nomic-embed-text (768d, Ollama)
     +-- 배치 크기: 32
     +-- 정규화: L2 normalize
     |
Phase 4: 인덱싱
     +-- Neo4j Vector Index (HNSW, cosine)
     +-- Neo4j Fulltext Index (BM25)
     +-- 메타데이터 노드 생성 + 리니지 기록
```

| 단계 | 입력 | 출력 | 처리량 목표 |
|------|------|------|-----------|
| 문서 로딩 | PDF/HWP/이미지 파일 | 순수 텍스트 | 100 pages/min |
| 청킹 | 순수 텍스트 | 512-token 청크 리스트 | 1,000 chunks/s |
| 임베딩 생성 | 텍스트 청크 | 768d float 벡터 | 200 chunks/s (GPU) |
| 인덱싱 | 벡터 + 메타데이터 | Neo4j 노드 + 인덱스 | 500 records/s |

### 3.5.4 Re-ranking 전략

초기 검색(Retrieval)에서 반환된 Top-K 문서를 **Cross-encoder**로 재정렬하여 정밀도를 높인다.

| 항목 | 설정 |
|------|------|
| 모델 | `cross-encoder/ms-marco-MiniLM-L-6-v2` (Y1, 경량) |
| 입력 | (질의, 문서) 쌍 |
| 출력 | 관련도 점수 (0.0 ~ 1.0) |
| Top-K | 초기 검색 50건 → Re-rank 후 상위 5건 선택 |
| Y2+ 계획 | 한국어 특화 Cross-encoder 파인튜닝 (해사 도메인 데이터) |

### 3.5.5 Retriever별 상세 설명

| Retriever | 검색 방식 | 반환 형태 | 지연 목표 | 주요 파라미터 |
|-----------|----------|----------|----------|-------------|
| **Vector** | 임베딩 cosine similarity | `(:Chunk {text, embedding})` | < 500ms | `top_k=20`, `threshold=0.7` |
| **VectorCypher** | Vector 검색 후 1-2 hop 그래프 확장 | Chunk + 연결 노드 | < 1s | `top_k=10`, `hops=2` |
| **Text2Cypher** | NL→Cypher 변환 후 KG 직접 조회 | 구조화된 그래프 결과 | < 5s | LLM 의존 |
| **Hybrid** | Sparse(BM25) + Dense(Vector) 결합 | 통합 점수 기반 문서 | < 1s | `alpha=0.5` (dense 가중치) |
| **ToolsRetriever** | LLM이 질문 유형 분석 후 적합한 Retriever 자동 선택 | 선택된 Retriever 결과 | < 5s | 자동 결정 |

---

> **다음 문서:** [4. 데이터 아키텍처](./04-data-architecture.md)에서 데이터베이스 선정, 온톨로지 설계, ELT 파이프라인, 데이터 리니지를 상세히 기술한다.
