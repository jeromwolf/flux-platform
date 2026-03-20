# Flux Platform 아키텍처 설계 (초안)

> 2026.03.18 KRISO 미팅 기반 아키텍처 방향 정리
> 상태: 초안 — 계약 및 상세 문서 수령 후 확정 예정

## 1. 프로젝트 전환 배경

### 기존 (flux-n8n + flux-agent-builder)

```
flux-n8n/           → KG 엔진 + 해사 도메인 플러그인 (1,148 테스트, 성숙)
flux-agent-builder/ → 에이전트 빌더 백엔드 (ReAct 런타임, MCP, 도구 8종)
```

### 신규 (flux-platform 모노레포)

KRISO 미팅에서 확인된 요구사항을 반영하여 통합 플랫폼으로 전환.
기존 코드는 모듈 단위로 이식 (git history 없이 복사, 원본은 아카이브 보존).

## 2. 목표 디렉토리 구조

```
flux-platform/
├── core/                    ← KG 엔진 (flux-n8n의 kg/ 이식)
│   ├── kg/                  # CypherBuilder, QueryGenerator, Pipeline, Validator 등
│   ├── ontology/            # Ontology 프레임워크 (도메인 독립)
│   ├── nlp/                 # NL Parser + TermDictionary Protocol
│   ├── etl/                 # ELT 파이프라인 (ETL→ELT 전환 반영)
│   ├── lineage/             # W3C PROV-O 리니지 (시간조건부 확장)
│   ├── rbac/                # RBAC 정책 엔진
│   └── entity_resolution/   # 엔티티 해석기
│
├── domains/
│   └── maritime/            ← 해사 도메인 플러그인 (flux-n8n의 maritime/ 이식)
│       ├── ontology/        # 해상교통 온톨로지 (AIS 중심 축소판)
│       ├── nlp/             # 해사 용어 사전
│       ├── crawlers/        # 데이터 크롤러 6종
│       ├── schema/          # Neo4j 스키마
│       └── s100/            # IHO S-100 매핑
│
├── agent/                   ← 에이전트 런타임 (flux-agent-builder 이식)
│   ├── runtime/             # ReAct, Pipeline, Batch
│   ├── tools/               # 도구 레지스트리 + 빌트인 8종
│   ├── memory/              # 대화 메모리
│   ├── llm/                 # LLM 프로바이더 (Ollama/OpenAI/Anthropic + Failover)
│   ├── mcp/                 # MCP 클라이언트/서버
│   └── skills/              # 스킬팩 레지스트리
│
├── ui/                      ← 프론트엔드 (신규)
│   ├── package.json         # Vue 3 + TypeScript
│   ├── src/
│   │   ├── canvas/          # VueFlow 워크플로우 캔버스
│   │   ├── chat/
│   │   │   ├── global/      # 전역 대화창 (워크플로우 생성)
│   │   │   └── node/        # 노드별 대화창 (설정/디버깅)
│   │   ├── auth/            # Keycloak 연동
│   │   ├── monitor/         # 옵저버빌리티 대시보드
│   │   └── portal/          # 서비스 포털 (2차 사용자용)
│   └── vite.config.ts
│
├── gateway/                 ← API Gateway
│   ├── app.py               # FastAPI 앱 팩토리
│   ├── routes/              # REST API 라우트
│   ├── ws/                  # WebSocket (실시간 스트리밍)
│   └── middleware/
│       ├── keycloak.py      # Keycloak 인증 (JWT→Keycloak 전환)
│       └── rate_limit.py    # Rate limiting
│
├── infra/
│   ├── k8s/                 # Kubernetes manifests
│   │   ├── base/            # 공통 리소스
│   │   ├── dev/             # 개발 환경
│   │   └── prod/            # 운영 환경
│   ├── docker/
│   │   ├── Dockerfile.core  # KG 엔진
│   │   ├── Dockerfile.agent # 에이전트 런타임
│   │   ├── Dockerfile.ui    # 프론트엔드
│   │   └── Dockerfile.gateway
│   ├── keycloak/            # Keycloak realm 설정
│   ├── prometheus/          # 모니터링 설정
│   ├── zipkin/              # 분산 추적
│   └── docker-compose.yml   # 로컬 개발용
│
├── tests/
│   ├── core/                # KG 엔진 테스트 (flux-n8n에서 이식)
│   ├── maritime/            # 해사 도메인 테스트
│   ├── agent/               # 에이전트 테스트
│   └── e2e/                 # E2E 테스트
│
├── docs/
│   ├── architecture.md      # 아키텍처 문서
│   ├── api-spec.md          # Suredata ↔ KRISO API 명세
│   └── ontology/            # 온톨로지 설계 문서
│
├── pyproject.toml           # Python 백엔드 설정
└── README.md
```

## 3. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    사용자 레이어                               │
├──────────┬──────────────┬───────────────────────────────────┤
│ 데이터    │ 1차 사용자    │ 2차 사용자                        │
│ 제공처    │ (내부 연구자)  │ (해양공무원, 해운사, 어민 등)      │
│ ─────    │ ──────────   │ ──────────────────────            │
│ 해수부    │              │                                   │
│ 기상청    │  VueFlow     │  서비스 포털                       │
│ 해경     │  캔버스       │  (읽기 전용)                       │
│ 자율운항  │  + 대화창     │                                   │
│ 센터     │              │                                   │
└──────────┴───────┬──────┴──────────────┬────────────────────┘
                   │                     │
            ┌──────▼──────┐       ┌──────▼──────┐
            │   Gateway   │       │  Keycloak   │
            │  (FastAPI)  │◄─────►│   (인증)     │
            └──────┬──────┘       └─────────────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
┌────▼────┐  ┌────▼────┐  ┌────▼────┐
│  Agent  │  │  Core   │  │ Domain  │
│ Runtime │  │  (KG    │  │Maritime │
│ (ReAct) │  │ Engine) │  │ Plugin  │
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └────────────┼────────────┘
                  │
    ┌─────────────┼──────────────┐
    │             │              │
┌───▼───┐  ┌─────▼─────┐  ┌────▼────┐
│Neo4j  │  │시계열 DB   │  │Data Lake│
│(KG)   │  │(InfluxDB)  │  │(MinIO)  │
└───────┘  └───────────┘  └─────────┘
```

## 4. 데이터 흐름 (ELT)

```
Raw 데이터 ──→ Data Lake (MinIO) ──→ 메타데이터 추출 ──→ Neo4j (KG)
(AIS, ENC,     (원본 보존)           (EXIF, GPS,        (엔티티,
 레이더 등)                          파일속성)           관계, 속성)
                                         │
                                    ┌────▼────┐
                                    │ AI 분석  │
                                    │ (엔티티  │
                                    │  추출)   │
                                    └─────────┘
```

## 5. 기존 코드 이식 계획

### flux-n8n → flux-platform

| flux-n8n 소스 | flux-platform 대상 | 변경사항 |
|--------------|-------------------|---------|
| `kg/` | `core/kg/` | 거의 그대로 |
| `maritime/` | `domains/maritime/` | 온톨로지 AIS 중심 축소 |
| `tests/core/` | `tests/core/` | import 경로만 변경 |
| `tests/maritime/` | `tests/maritime/` | import 경로만 변경 |

### flux-agent-builder → flux-platform

| flux-agent-builder 소스 | flux-platform 대상 | 변경사항 |
|------------------------|-------------------|---------|
| `backend/agent/` | `agent/` | 거의 그대로 |
| `backend/tools/` | `agent/tools/` | 거의 그대로 |
| `backend/core/llm/` | `agent/llm/` | 거의 그대로 |
| `backend/api/` | `gateway/` | Keycloak 전환 |

## 6. 인증 전환 (JWT → Keycloak)

| 항목 | 현재 (flux-n8n) | 목표 (flux-platform) |
|------|----------------|---------------------|
| 인증 | JWT + API Key | Keycloak OIDC |
| 권한 | 자체 RBAC | Keycloak Realm Roles + 자체 RBAC |
| 사용자 관리 | 코드 내 | Keycloak Admin Console |
| SSO | 없음 | Keycloak SSO |

## 7. 주요 기술 결정 사항 (미확정)

| 결정 사항 | 후보 | 확정 시점 |
|----------|------|----------|
| 시계열 DB | InfluxDB vs TimescaleDB | 계약 후 |
| Data Lake | MinIO vs S3 | 인프라 확정 후 |
| Vector DB | Milvus vs Weaviate | 2차년도 |
| K8s 배포 | Helm vs Kustomize | 인프라 확정 후 |
| GPU 분산 | Ray vs vLLM | 하드웨어 확정 후 |
| 프론트엔드 | Vue 3 + VueFlow | 확정 |

## 8. Suredata Lab 연계

```
Suredata Lab                    인사이트마이닝 (flux-platform)
┌──────────────┐    REST API    ┌──────────────┐
│ 데이터 수집   │──────────────→│ KG 적재       │
│ 데이터 마트   │               │ 온톨로지 매핑  │
│ AI 모델 서빙  │←──────────────│ 추론 결과     │
│ DW 파이프라인 │    REST API    │ 리니지 추적   │
└──────────────┘               └──────────────┘
```

### API 인터페이스 (초안)

```
# Suredata → flux-platform (데이터 주입)
POST /api/v1/ingest/raw          # Raw 데이터 등록
POST /api/v1/ingest/metadata     # 메타데이터 등록
POST /api/v1/ingest/entities     # 추출된 엔티티 등록

# flux-platform → Suredata (결과 조회)
GET  /api/v1/query/nl            # 자연어 쿼리
GET  /api/v1/query/cypher        # Cypher 직접 쿼리
GET  /api/v1/lineage/{asset_id}  # 리니지 조회
GET  /api/v1/ontology/schema     # 온톨로지 스키마 조회
```

## 9. 1차년도 우선순위 (예상)

| 우선순위 | 항목 | 비고 |
|---------|------|------|
| P0 | 해상교통 온톨로지 스키마 (AIS 중심) | 미팅에서 명시적 요청 |
| P0 | 전체 추상 개념도 | 다음 액션 아이템 #1 |
| P1 | Suredata REST API 명세 | 연계 필수 |
| P1 | ELT 파이프라인 PoC | ETL→ELT 전환 |
| P2 | VueFlow 워크플로우 UI PoC | 프론트엔드 |
| P2 | Keycloak 인증 연동 | 인프라 |
| P3 | K8s 배포 | 인프라 확정 후 |

---

*이 문서는 초안이며, KRISO로부터 상세 문서 수령 후 확정 예정.*
