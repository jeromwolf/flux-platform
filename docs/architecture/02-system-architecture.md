# 2. 시스템 아키텍처 개요 (5-Tier)

[← 시스템 컨텍스트](./01-system-context.md) | [다음: 컴포넌트 아키텍처 →](./03-component-architecture.md)

## 개요

IMSP는 Presentation → Gateway → Service → Data → Infrastructure의 5계층 구조로 설계된다. 각 계층은 독립 배포 단위(Kubernetes Deployment/StatefulSet)로 수평 확장 가능하며, 계층 간 통신은 표준 프로토콜(REST, gRPC, WebSocket)을 통해 느슨하게 결합된다. 이 문서는 각 계층의 구성 요소, 계층 간 통신 규약, 그리고 비기능 요구사항 달성 전략을 기술한다.

---

## 2.0 5-Tier 아키텍처 다이어그램

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
|  | Neo4j   |  | Ceph  |  | PostgreSQL |  | TimescaleDB |  | Redis    |     |
|  | 5.x CE  |  | RGW   |  |    14      |  | / InfluxDB  |  |   7      |     |
|  |         |  |       |  |            |  |             |  |          |     |
|  | - Graph |  | - Raw |  | - Auth     |  | - AIS 궤적   |  | - 캐시   |     |
|  | - Vector|  | - S100|  | - Workflow |  | - 기상 시계열 |  | - Queue  |     |
|  | - Spatial|  | - 영상|  | - Metadata |  |             |  |          |     |
|  +---------+  +-------+  +------------+  +-------------+  +----------+     |
|                                                                             |
|  Bolt (7687) | S3 API (7480) | JDBC (5432) | SQL (5432) | RESP (6379)      |
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

---

## 2.1 Presentation Tier

Presentation Tier는 Vue 3 기반 SPA(Single Page Application)로 구성된다. **VueFlow 워크플로우 캔버스**는 6종 노드(Trigger, Action, Connector, Control, Transform, Special)를 드래그앤드롭으로 조합해 해사 서비스 워크플로우를 시각적으로 저작하는 핵심 UI다. 노드별 대화창이 우측 패널로 열려, 해당 노드의 실행 결과를 LLM과 대화하며 검토할 수 있다.

**서비스 포털**은 2차 이용자(해운사, 민간 연구기관)가 접근하는 별도 라우트로, 승인된 서비스 목록 조회, 이용 신청, 데이터 탐색 기능을 제공한다. **관측성 대시보드**는 Grafana iframe을 임베드해 시스템 상태, KG 파이프라인 처리량, 에이전트 호출 지연 등을 실시간 모니터링한다.

**대화 인터페이스**는 글로벌(플랫폼 전체)과 노드별(워크플로우 노드 컨텍스트) 두 가지 모드로 동작한다. WebSocket을 통해 Server-Sent Events 방식으로 LLM 스트리밍 응답을 수신하며, 대화 히스토리는 Agent Memory에 영속화된다.

## 2.2 API Gateway Tier

Gateway Tier는 모든 외부 트래픽의 진입점이다. **Nginx Ingress**가 TLS 종단 및 경로 기반 라우팅을 담당하고, **FastAPI Router**가 OpenAPI 3.0 명세로 REST 엔드포인트를 노출한다. **Keycloak OIDC Middleware**는 모든 요청의 JWT를 검증하고 사용자 역할(role)을 추출해 서비스 계층으로 전달한다.

**Rate Limiter**는 Redis를 백엔드로 사용하며, 테넌트, 사용자, 엔드포인트 단위로 요청 횟수를 제한한다. **WebSocket Handler**는 대화 인터페이스와 실시간 파이프라인 진행 상황을 위한 양방향 채널을 유지한다. 모든 요청은 Zipkin으로 분산 추적된다.

### 2.2.1 RBAC 역할별 Rate Limiting

Rate Limiter는 Keycloak에서 추출한 사용자 역할(role)에 따라 차등 제한을 적용한다.

| RBAC 역할 | 요청 제한 (req/min) | 버스트 허용 | 비고 |
|-----------|-------------------|-----------|------|
| `admin` | 무제한 | - | 플랫폼 관리자 |
| `researcher` | 300 | 50 | KRISO 내부 연구자 |
| `developer` | 200 | 30 | 워크플로우 개발자 |
| `viewer` | 60 | 10 | 2차 이용자 (읽기 전용) |
| `anonymous` | 10 | 5 | 미인증 (health/metrics만 허용) |

제한 초과 시 `429 Too Many Requests` 응답과 함께 `Retry-After` 헤더를 반환한다.

### 2.2.2 API 버전 라우팅

API 버전은 URL 경로 기반으로 라우팅되며, 하위 호환성을 유지한다.

```
/api/v1/*  →  현재 안정 버전 (Y1~)
/api/v2/*  →  차기 버전 (Y2~ 도입, gRPC Gateway 포함)
```

버전 간 전환 시 최소 6개월의 병행 운영 기간을 두어 클라이언트 마이그레이션을 보장한다. Deprecated 엔드포인트는 `Sunset` 헤더로 종료 일자를 고지한다.

### 2.2.3 요청/응답 변환 및 보안 정책

- **Request Validation**: OpenAPI 3.0 스키마 기반 요청 본문/파라미터 자동 검증
- **Request Size Limit**: 기본 10MB, 파일 업로드 엔드포인트(`/api/v1/ingest/raw`)는 100MB 허용
- **CORS 정책**: `Access-Control-Allow-Origin`을 허용된 도메인 목록(`ALLOWED_ORIGINS`)으로 제한. 와일드카드(`*`) 금지
- **Response Transform**: 내부 오류 상세(스택 트레이스 등)를 외부 응답에서 제거, 표준 오류 포맷(`{"error": {"code": "", "message": ""}}`)으로 통일
- **Security Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security` 적용

## 2.3 Service Tier

Service Tier는 플랫폼의 핵심 비즈니스 로직을 담는 계층이다. **KG Engine**은 자연어 질의를 Cypher로 변환하고, ELT 파이프라인으로 데이터를 적재하며, W3C PROV-O 기반 리니지를 추적한다. **Agent Runtime**은 Orchestrator-SubAgent 구조로 복합 질의를 분해, 실행하며, MCP(Model Context Protocol)와 A2A(Agent-to-Agent) 프로토콜을 지원한다.

**Workflow Engine(Argo)**은 VueFlow에서 저작된 워크플로우를 DAG로 변환, 실행한다. **Domain Plugins**는 해사 도메인 특화 기능(온톨로지, NLP 용어 사전, 크롤러, S-100 파서)을 플러그인 형태로 제공해, 향후 항만, 선박, 해양환경 등 도메인 확장 시 플러그인 추가만으로 대응할 수 있다.

## 2.4 Data Tier

Data Tier는 용도별로 최적화된 5개 저장소로 구성된다. **Neo4j**가 KG(그래프+벡터+공간 인덱스)의 중심이며, **Ceph RGW**가 원천 데이터 원본을 S3 호환 API로 보존한다. **PostgreSQL**은 Keycloak 인증 백엔드와 워크플로우 메타데이터를 담당하고, **TimescaleDB**(또는 InfluxDB, 벤치마크 후 확정)가 AIS 궤적, 기상 시계열 데이터의 시간 범위 쿼리를 최적화한다. **Redis**는 잡 큐(BullMQ 호환)와 세션 캐시로 활용된다.

## 2.5 Infrastructure Tier

Infrastructure Tier는 플랫폼 운영 기반이다. **Kubernetes**가 모든 서비스를 컨테이너로 오케스트레이션하며, **Helm + Kustomize**로 환경별(dev/staging/prod) 배포 구성을 관리한다. **Prometheus + Grafana**가 메트릭 수집, 시각화를, **Zipkin**이 분산 추적을 담당한다. **Keycloak**은 SSO 서버로 모든 Realm의 인증, 인가를 처리하고, **ArgoCD**가 GitOps 방식으로 배포 상태를 Git 저장소와 동기화한다.

---

## 2.6 계층 간 통신 규약

각 Tier 간 통신은 명확한 프로토콜과 데이터 직렬화 표준을 따르며, 장애 격리(fault isolation)를 위한 폴백 전략을 계층별로 정의한다.

### 2.6.1 데이터 직렬화 표준

| 통신 경로 | 1차년도 (Y1) | 2차년도~ (Y2+) | 비고 |
|-----------|-------------|---------------|------|
| Presentation → Gateway | JSON (REST) | JSON (REST) | OpenAPI 3.0 스키마 검증 |
| Gateway → Service | JSON (REST) | JSON + Protocol Buffers (gRPC) | gRPC는 내부 서비스 간 고성능 통신용 |
| Service → Service | JSON (REST) | Protocol Buffers (gRPC) | Agent ↔ KG Engine 등 내부 호출 |
| Service → Data | 각 DB 네이티브 프로토콜 | 동일 | Bolt, S3 API, JDBC, RESP |
| WebSocket (양방향) | JSON | JSON | 대화 스트리밍, 파이프라인 진행 상황 |
| Argo 노드 간 | Artifact (Object Storage JSON/Binary) | 동일 | 노드 간 데이터는 Argo Artifact로 전달 |

### 2.6.2 장애 격리 및 폴백 전략

**Circuit Breaker 패턴:**

각 서비스 호출 지점에 Circuit Breaker를 적용하여 연쇄 장애(cascading failure)를 방지한다.

```
[정상] ──(오류율 > 50%, 10회 이상)──> [Open] ──(30초 대기)──> [Half-Open]
                                         |                        |
                                    즉시 실패 반환          1회 시도 후 판정
                                                                  |
                                                    성공 → [정상] / 실패 → [Open]
```

| 대상 서비스 | 오류 임계값 | Open 유지 시간 | 폴백 동작 |
|------------|-----------|---------------|----------|
| Neo4j (KG 질의) | 5회 연속 실패 | 30초 | 캐시된 결과 반환 + 사용자 알림 |
| LLM Provider (Ollama) | 3회 연속 실패 | 60초 | 차순위 Provider로 Failover (OpenAI → Anthropic) |
| Object Storage (Ceph) | 5회 연속 실패 | 30초 | 업로드 큐잉 (Redis) 후 재시도 |
| 외부 API (기상/AIS) | 3회 연속 실패 | 120초 | 마지막 수집 데이터 유지 + DLQ 기록 |

**Dead Letter Queue (DLQ) 라우팅:**

처리 실패한 메시지는 DLQ로 라우팅되어 수동 검토 또는 자동 재시도 대상이 된다.

```
원본 메시지 → 처리 시도 (최대 3회) → 실패 → DLQ (Object Storage: dlq/{source}/{date}/)
                                                |
                                         메타데이터 기록: 실패 원인, 시도 횟수, 원본 경로
                                                |
                                         알림 발송 (Grafana Alert → Webhook)
```

### 2.6.3 계층 간 지연 시간 목표

| 통신 경로 | 지연 시간 목표 | 측정 지점 | 비고 |
|-----------|-------------|----------|------|
| Presentation → Gateway → Service (REST API) | p95 < 100ms | Nginx Ingress → FastAPI 응답 | 단순 CRUD, 캐시 히트 기준 |
| Text2Cypher 전체 파이프라인 | p95 < 5s | NL 입력 → Cypher 생성 → 실행 → 응답 | LLM 추론 시간 포함 |
| GraphRAG 검색 | p95 < 3s | 질의 입력 → Retriever 실행 → 결과 반환 | 벡터 검색 + 그래프 순회 |
| WebSocket 메시지 전달 | p95 < 50ms | Gateway → Client | 대화 스트리밍 토큰 단위 |
| ELT Batch 적재 (1,000건) | < 10s | Object Storage 읽기 → Neo4j MERGE 완료 | batch=500, 2회 라운드 |
| Argo Workflow 노드 기동 | < 15s | DAG 제출 → 첫 번째 Pod Running | Cold start 포함 |

---

## 2.7 비기능 요구사항 매트릭스

| 항목 | 목표 | 측정 방법 | 비고 |
|------|------|----------|------|
| API 응답 시간 | p95 < 200ms | Prometheus histogram (`http_request_duration_seconds`) | 캐시 미스 포함 전체 평균 |
| Text2Cypher 지연 | p95 < 5s | Zipkin trace (`text2cypher.pipeline.duration`) | LLM 추론 시간이 지배적 |
| 가용성 | 99.5% (Y1) → 99.9% (Y5) | Uptime probe (Kubernetes liveness/readiness) | Y1은 단일 클러스터, Y3~ HA 구성 |
| 동시 사용자 | 5 (Y1) → 10 (Y2) → 30 (Y3) → 50 (Y4) → 100+ (Y5) | Load test (k6/Locust) | WebSocket 연결 수 기준 |
| KG 질의 처리량 | 100 req/s (Y1) → 1,000 req/s (Y5) | Prometheus counter (`kg_query_total`) | Neo4j 클러스터링(Y3~)으로 확장 |
| ELT 일일 처리량 | 100K records (Y1) → 10M records (Y5) | Prometheus counter (`elt_records_processed_total`) | Batch 병렬화로 확장 |
| 데이터 내구성 | 99.99% | Object Storage 복제 팩터 (3x) | Ceph RGW 기본 설정 |
| 장애 복구 시간 (RTO) | < 30분 (Y1) → < 5분 (Y5) | 장애 시나리오 훈련 | Y1은 수동 복구, Y3~ 자동 Failover |
| 백업 복구 시점 (RPO) | < 1시간 (Y1) → < 5분 (Y5) | Neo4j 백업 주기 | Y1 시간별, Y3~ 실시간 복제 |
| 보안 인증 지연 | p95 < 50ms | Keycloak token validation 소요 시간 | JWT 로컬 검증 (공개키 캐시) |

### 연차별 확장 로드맵

```
Y1 (2026):  Docker Compose (단일 호스트) | Neo4j CE 단일 인스턴스 | 5 사용자 | 99.5% 가용성
     |
     v
Y2 (2027):  Neo4j Read Replica 추가 | Redis Cluster | gRPC 내부 통신 도입
     |
     v
Y3 (2028):  Multi-AZ K8s | Neo4j Causal Cluster (3노드) | 30 사용자 | 99.9% 가용성
     |
     v
Y4 (2029):  GPU 노드풀 추가 (A100) | 분산 추론 (Ray/vLLM) | 50 사용자
     |
     v
Y5 (2030):  멀티 클러스터 Federation | 100+ 사용자 | 99.9% 가용성 | DR 사이트
```

---

> **다음 문서:** [3. 컴포넌트 아키텍처](./03-component-architecture.md)에서 각 서비스 계층 모듈의 내부 구조와 의존성을 상세히 기술한다.
