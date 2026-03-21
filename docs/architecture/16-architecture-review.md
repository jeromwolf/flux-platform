# 16. 아키텍처 리뷰 및 개선 계획

[← 플랫폼 운영 기능](./15-platform-operations.md) | [다음: 에러 처리 전략 →](./17-error-handling.md)

## 개요

본 문서는 IMSP 플랫폼 아키텍처에 대한 리뷰 결과와 개선 계획을 기술한다. 1차 리뷰(코드 기반)에서 CRITICAL 6건, HIGH 10건, MEDIUM 6건의 이슈를 식별하였으며, 2차 리뷰(PDF/RFP 기반)에서 추가로 CRITICAL 7건, HIGH 8건의 Gap을 발견하여 보완하였다. 모든 이슈에 대한 수정 방안과 일정을 포함한다.

> 리뷰일: 2026-03-20 | 리뷰어: Architect Agent (Opus)

---

## 16.1 식별된 문제 요약

| 구분 | 건수 | 주요 항목 |
|------|:---:|----------|
| CRITICAL (즉시 수정) | 6 | 역방향 의존, API Key 보안, Lineage 비영속, Dev 보안 우회, DB 마이그레이션 전략 부재, timezone |
| HIGH (빠른 대응) | 10 | Neo4j CE 한계, Entity Resolution O(n^2), ETL 동기 전용, RBAC regex, Batch Loader 트랜잭션, JWT→Keycloak 경로, Gateway 분리, Circuit Breaker, 데이터 보존, 재해 복구 |
| MEDIUM (계획 수립) | 6 | Coverage 60%, API 버전, 멀티테넌시, 부하 테스트, LangChain 의존, 문서 현재/미래 혼용 |

---

## 16.2 CRITICAL 수정 계획

### C-1. core/kg/ → maritime/ 역방향 의존 제거

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

### C-2. API Key 인증 보안 강화

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

### C-3. Lineage Neo4j 영속화

**문제:** LineageRecorder가 in-memory only, 크래시 시 데이터 소실

**수정:**
- `LineageRecorder.flush(session)` 메서드 추가
- `ETLPipeline.run()` 완료 시 자동 flush 호출
- `lineage/queries.py`의 MERGE_LINEAGE_NODE/EDGE 활용

### C-4. Development 모드 보안 개선

**수정:**
- dev 모드 시 `logger.critical("SECURITY: Running in development mode - ALL AUTH BYPASSED")` 경고
- `APP_API_KEY` 또는 `JWT_SECRET_KEY` 설정 시 dev 모드 자동 거부
- 프로덕션 환경 감지 시 dev 모드 진입 차단

### C-5. ETL datetime timezone 통일

**수정:** `datetime.now()` → `datetime.now(timezone.utc)` 전체 치환

### C-6. DB 마이그레이션 프레임워크 설계

**설계:**
```
infra/migrations/
├── 001_initial_schema.cypher
├── 002_add_lineage_indexes.cypher
├── 003_ontology_v1_redesign.cypher
└── migrate.py   # (:Migration {version, applied_at}) 노드 기반 추적
```

---

## 16.3 확장성 대응 계획

### S-1. Neo4j CE 한계 대응

| 연차 | 전략 |
|------|------|
| Y1-Y2 | CE 단일 인스턴스 + 애플리케이션 캐싱 + 읽기 최적화 |
| Y2 | EE 라이선스 예산 요청 (또는 Apache AGE 벤치마크) |
| Y3 | EE 전환 또는 AGE 전환 (3계층 온톨로지로 매핑만 교체) |
| Y4-Y5 | Causal Clustering + Read Replica + Online Backup |

### S-2. Entity Resolution 성능 개선

```
현재: O(n^2) 전수 비교
목표: O(n log n) Blocking + Canopy

Phase 1 (Y1): Blocking by entity type + first character
Phase 2 (Y2): MinHash LSH for fuzzy tier
Phase 3 (Y3): HNSW approximate NN for embedding tier
```

### S-3. ETL 비동기 경로 추가

```
현재: 동기 ETLPipeline.run() (Batch CronJob 전용)
추가: AsyncETLPipeline.run_async() (Streaming 전용, Y2)

Batch (현행 유지):  CronJob → ETLPipeline.run() → Neo4jBatchLoader
Streaming (Y2 신규): Kafka → AsyncETLPipeline → async Neo4j driver
```

### S-4. RBAC 강화

```
현재: regex 기반 WHERE 주입 (단순 쿼리만)
목표: SecureCypherBuilder 전용 경로

1. LLM 생성 Cypher → 반드시 SecureCypherBuilder 래핑
2. 직접 Cypher 실행 금지 (Query API에서 차단)
3. RBAC bypass detection 로직 추가
```

### S-5. Batch Loader 트랜잭션 관리

```python
# Before: session.run() 직접 호출, partial commit 위험
session.run(cypher, {"batch": batch})

# After: execute_write() + 재시도
session.execute_write(
    lambda tx: tx.run(cypher, {"batch": batch}),
    max_retry_time=30
)
```

---

## 16.4 누락 항목 보완 계획

| 항목 | 대응 | 시점 |
|------|------|------|
| DB 마이그레이션 | Migration runner + versioned .cypher 파일 | Y1 Q1 |
| Circuit Breaker | pybreaker + connection pool 모니터링 | Y1 Q2 |
| 데이터 보존 정책 | Object Storage lifecycle + Neo4j archival CronJob | Y1 Q2 |
| 재해 복구 | neo4j-admin dump CronJob + Object Storage 복제 | Y1 Q2 |
| 부하 테스트 | k6/Locust + tests/perf/ | Y1 Q3 |
| 멀티테넌시 | tenantId 속성 기반 격리 + BatchLoader 강제 | Y2 Q1 |
| LangChain 격리 | 얇은 래퍼 인터페이스 뒤에 격리 | Y1 Q1 |

---

## 16.5 API 버전 전략

```
현재: /api/health, /api/query, /api/schema (무버전)
목표: /api/v1/health, /api/v1/query, /api/v1/schema

전환 전략:
1. 모든 라우트를 /api/v1/ prefix로 이동
2. 기존 /api/ 경로는 301 Redirect (하위 호환, 3개월 유지)
3. Suredata 연동 API도 /api/v1/ 통일
```

---

## 16.6 확장성이 잘 설계된 부분 (유지)

| 설계 | 근거 |
|------|------|
| **3계층 온톨로지 분리** | DB 교체 시 Mapping만 교체. 5년 생존력 확보 |
| **ELT 전략 (Object Storage 원천 보존)** | 온톨로지 변경 시 원천 재처리 가능. 최고의 설계 결정 |
| **Text2Cypher 5단계 파이프라인** | 각 단계 독립 교체 가능. 70%→95% 경로 열림 |
| **Frozen Config** | 런타임 설정 변경 방지. 장기 운영 안정 |
| **DLQ 패턴** | 실패 레코드 보존. 정부 과제 추적성 충족 |
| **PEP 562 하위 호환** | DeprecationWarning 점진적 마이그레이션 |

---

## 16.7 2차 리뷰 결과 (PDF/RFP 기반)

RFP 원문 및 KRISO 미팅(2026-03-18) 자료를 기반으로 수행한 2차 리뷰 결과이다. 아키텍처 문서와 RFP 요구사항 간의 Gap을 식별하고, 모두 반영 완료하였다.

### 16.7.1 CRITICAL 이슈 (7건)

| # | 이슈 | 상세 | 수정 상태 |
|---|------|------|----------|
| P-1 | **용어 미정의** | RFP에서 사용하는 "자원", "자산", "컴포넌트", "응용", "서비스" 등 핵심 용어에 대한 정의가 아키텍처 문서에 없었음. 용어 혼용으로 인한 의사소통 리스크 | ✅ 반영 완료 — [00-terminology.md](./00-terminology.md) 신규 작성. 12개 핵심 용어 + 계층 관계 정의 |
| P-2 | **MDT-Ops 개념 누락** | RFP의 핵심 운영 개념인 MDT-Ops (Maritime Digital Twin Operations)가 아키텍처 문서에 전혀 언급되지 않았음 | ✅ 반영 완료 — [00-terminology.md](./00-terminology.md)에 MDT-Ops 정의 및 6개 운영 계층 기술 |
| P-3 | **MinIO → Ceph 전환** | 아키텍처 문서에서 Object Storage로 MinIO를 명시했으나, RFP 및 KRISO 미팅에서 Ceph 사용이 확정됨 | ✅ 반영 완료 — 전체 문서에서 MinIO → Ceph(Object Storage) 일괄 변경 |
| P-4 | **Nginx → Istio 전환** | Ingress Controller로 Nginx를 명시했으나, 서비스 메시 요구사항에 따라 Istio 사용이 결정됨 | ✅ 반영 완료 — [05-deployment-architecture.md](./05-deployment-architecture.md)에서 Istio 기반 트래픽 관리로 변경 |
| P-5 | **GitHub → GitLab 전환** | 소스코드 저장소로 GitHub을 가정했으나, KRISO 보안 정책상 온프레미스 GitLab 사용 | ✅ 반영 완료 — CI/CD 파이프라인을 GitLab CI 기반으로 재설계 |
| P-6 | **노드 5종 미정의** | RFP에서 Y1 산출물로 "워크플로우 노드 5종"을 요구하나, 구체적인 노드 타입이 정의되지 않았음 | ✅ 반영 완료 — DataSource, Transform, KGQuery, LLM, Visualization, Output 6종 정의. Y1에 5종 구현 목표 |
| P-7 | **API 경로 불일치** | 코드의 API 경로(`/api/query`, `/api/schema`)와 문서의 경로(`/api/v1/query/text`)가 불일치 | ✅ 반영 완료 — `/api/v1/` prefix 통일. 기존 경로는 301 Redirect (16.5 API 버전 전략 참조) |

### 16.7.2 HIGH 이슈 (8건)

| # | 이슈 | 상세 | 수정 상태 |
|---|------|------|----------|
| P-8 | **리니지 범위 부족** | 데이터 리니지만 설계되어 있었으나, RFP는 데이터/모델/노드/워크플로우 4종 통합 리니지를 요구 | ✅ 반영 완료 — [15-platform-operations.md](./15-platform-operations.md) 섹션 15.1에 4종 통합 리니지 설계 |
| P-9 | **이용자 유형 미구분** | RFP의 3가지 이용자 유형(운영자/1차 이용자/2차 이용자) 구분이 아키텍처에 반영되지 않았음 | ✅ 반영 완료 — [01-system-context.md](./01-system-context.md)에 이용자 유형별 역할/권한 기술 |
| P-10 | **데이터 제공기관 미식별** | RFP에서 명시한 데이터 제공기관(해양수산부, 해양경찰청, GSIS 등)이 데이터 아키텍처에 누락 | ✅ 반영 완료 — [04-data-architecture.md](./04-data-architecture.md)에 외부 데이터 소스 매핑 추가 |
| P-11 | **협업 기능 부재** | 멀티 연구자 협업(프로젝트 작업 공간, 자산 공유) 설계가 전혀 없었음 | ✅ 반영 완료 — [15-platform-operations.md](./15-platform-operations.md) 섹션 15.4에 협업 기능 설계 |
| P-12 | **서비스 Pool 개념 누락** | 워크플로우→서비스 전환, 서비스 카탈로그, 공개/비공개 관리 설계 부재 | ✅ 반영 완료 — [15-platform-operations.md](./15-platform-operations.md) 섹션 15.3에 서비스 Pool 설계 |
| P-13 | **Antigravity/SDK 연계 미설계** | 외부 개발자용 노드 SDK 및 Antigravity(VS Code 확장) 연계 설계 부재 | ✅ 반영 완료 — [15-platform-operations.md](./15-platform-operations.md) 섹션 15.5에 SDK 프로시저 및 노드 스펙 YAML 예시 |
| P-14 | **자산 관리 체계 미설계** | 플랫폼 자산(데이터/모델/노드/워크플로우/서비스)의 통합 라이프사이클 관리 부재 | ✅ 반영 완료 — [15-platform-operations.md](./15-platform-operations.md) 섹션 15.2에 자산 관리 체계 설계 |
| P-15 | **워크플로우 서비스 GW 미설계** | Internal API GW와 별도로 서비스 사용자용 전용 Gateway가 필요하나 설계되지 않았음 | ✅ 반영 완료 — [15-platform-operations.md](./15-platform-operations.md) 섹션 15.3에 Service GW 설계 (경로: `/service/v1/`) |

### 16.7.3 수정 완료 요약

- **2차 리뷰 수행일:** 2026-03-20
- **총 식별 이슈:** CRITICAL 7건 + HIGH 8건 = 15건
- **수정 완료:** 15건 전체 (100%)
- **영향 받은 문서:** 00-terminology.md (신규), 01-system-context.md, 02-system-architecture.md, 04-data-architecture.md, 05-deployment-architecture.md, 15-platform-operations.md (신규), 16-architecture-review.md

---

*관련 문서: [설계 원칙](./12-design-principles.md), [연차별 로드맵](./13-roadmap.md), [플랫폼 운영 기능](./15-platform-operations.md)*
