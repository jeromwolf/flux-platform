# CLAUDE.md - IMSP (Interactive Maritime Service Platform)

이 파일은 Claude Code가 프로젝트를 이해하고 작업할 때 참조하는 지침입니다.

## 프로젝트 개요

**IMSP** — 대화형 해사서비스 설계 플랫폼 개발 및 이를 활용한 민간의 해사서비스 연구개발 지원
- **발주:** KRISO (한국해양과학기술원 부설 선박해양플랜트연구소)
- **수행:** 인사이트마이닝 (지식그래프 + 전체 플랫폼 개발)
- **협력:** Suredata Lab (데이터 수집/마트/AI서빙/DW 파이프라인)
- **기간:** 5개년 (1단계 3년 + 2단계 2년), 2026~2030
- **전략:** 전체 플랫폼을 내부 개발, 계약상 KG 파트만 납품

## 5개년 로드맵

| 단계 | 연차 | 목표 |
|------|------|------|
| 1단계 | 1차 (2026) | 운영 개념 정의 및 설계 |
| | 2차 (2027) | 데이터·모델 의미 체계화 + 구성 요소 개발 |
| | 3차 (2028) | 통합 연계 → 플랫폼 MVP |
| 2단계 | 4차 (2029) | 플랫폼 고도화 + 표준 개발 프로세스 |
| | 5차 (2030) | 안정화 + 민간 연구개발 지원 |

## 6대 개발 축

1. **플랫폼 운영 기술** — K8s, 보안/멀티테넌트, Keycloak, 관측성
2. **통합개발환경** — VueFlow 워크플로우 저작도구, 노드 개발, 자동 생성
3. **자원 저장소** — 원천(MinIO) + 서빙 데이터, 표준 인터페이스
4. **가시화/상호작용** — 전자해도(S-100), 3D 렌더러, 대시보드
5. **도메인 모델** — 해사 특화 기본+고급 모델 (매년 5종)
6. **민간 지원** — 총 29건

## 핵심 디렉토리

```
flux-platform/
├── core/                    ← 도메인 독립 KG 엔진 (flux-n8n/kg/ 이식)
│   ├── kg/                  # CypherBuilder, QueryGenerator, Pipeline
│   │   ├── cypher_builder.py        # Fluent Cypher 쿼리 빌더
│   │   ├── query_generator.py       # 다중 언어 쿼리 생성기
│   │   ├── pipeline.py              # TextToCypherPipeline 서비스
│   │   ├── cypher_validator.py      # Cypher 검증기 (6가지 검증)
│   │   ├── cypher_corrector.py      # 규칙 기반 Cypher 교정기
│   │   ├── quality_gate.py          # KG 품질 게이트
│   │   ├── hallucination_detector.py # 환각 감지기
│   │   ├── exceptions.py            # 예외 계층
│   │   ├── config.py                # Neo4j 연결 설정
│   │   ├── types.py                 # 공통 타입
│   │   ├── ontology_bridge.py       # 온톨로지 → KG 브릿지
│   │   ├── maritime_factories.py    # 해사 팩토리 (임시 위치)
│   │   ├── ontology/core.py         # Ontology 프레임워크
│   │   ├── nlp/                     # NL 파서 + TermDictionary Protocol
│   │   ├── entity_resolution/       # 3단계 엔티티 해석기
│   │   ├── embeddings/              # Ollama 임베딩
│   │   ├── n10s/                    # Neosemantics OWL 통합
│   │   ├── evaluation/              # 평가 프레임워크
│   │   ├── etl/                     # ELT 파이프라인
│   │   ├── lineage/                 # W3C PROV-O 리니지
│   │   ├── rbac/                    # RBAC 정책 (→ Keycloak 전환 예정)
│   │   ├── api/                     # FastAPI 앱 + 라우트
│   │   └── utils/                   # 유틸리티
│   ├── ontology/            # 온톨로지 프레임워크 (재설계 예정)
│   ├── nlp/                 # NL Parser + TermDictionary Protocol
│   ├── etl/                 # ELT 파이프라인 (ETL→ELT 전환)
│   ├── lineage/             # W3C PROV-O 리니지 (시간조건부 확장)
│   ├── rbac/                # RBAC → Keycloak 전환
│   ├── entity_resolution/   # 엔티티 해석기
│   ├── embeddings/          # 임베딩 모듈
│   └── n10s/                # Neosemantics
│
├── domains/
│   └── maritime/            ← 해사 도메인 (완전 재설계 예정)
│       ├── ontology/        # 해상교통 온톨로지 (KRISO 요구 기반 재설계)
│       ├── nlp/             # 해사 용어 사전
│       ├── crawlers/        # 데이터 크롤러
│       ├── schema/          # Neo4j 스키마
│       ├── s100/            # IHO S-100 매핑
│       ├── evaluation/      # 평가 데이터셋
│       ├── poc/             # PoC
│       └── workflows/       # Activepieces 워크플로우 (→ Argo 전환 예정)
│
├── agent/                   ← 에이전트 런타임 (flux-agent-builder 이식 예정)
│   ├── runtime/             # ReAct, Pipeline, Batch
│   ├── tools/               # 도구 레지스트리
│   ├── memory/              # 대화 메모리
│   ├── llm/                 # LLM 프로바이더 (Ollama/OpenAI/Anthropic + Failover)
│   ├── mcp/                 # MCP 클라이언트/서버
│   └── skills/              # 스킬팩 레지스트리
│
├── rag/                     ← RAG 엔진 (flux-rag 이식 예정)
│   ├── engines/             # 하이브리드 RAG 엔진
│   ├── documents/           # 문서 파이프라인 (PDF/HWP/OCR)
│   └── embeddings/          # 벡터 검색
│
├── ui/                      ← 프론트엔드 (신규)
│   └── src/
│       ├── canvas/          # VueFlow 워크플로우 캔버스
│       ├── chat/            # 대화창 (전역 + 노드별)
│       ├── auth/            # Keycloak 연동
│       ├── monitor/         # 옵저버빌리티 대시보드
│       └── portal/          # 서비스 포털
│
├── gateway/                 ← API Gateway
│   ├── routes/              # REST API
│   ├── ws/                  # WebSocket
│   └── middleware/          # Keycloak, Rate Limit
│
├── infra/                   ← 인프라
│   ├── k8s/                 # Kubernetes manifests
│   ├── docker/              # Dockerfiles
│   ├── keycloak/            # Keycloak realm 설정
│   ├── prometheus/          # 모니터링
│   └── docker-compose.yml   # 로컬 개발용
│
├── tests/                   ← 테스트
│   ├── core/                # KG 엔진 (19개 파일)
│   ├── maritime/            # 해사 도메인 (19개 파일)
│   ├── agent/               # 에이전트
│   ├── rag/                 # RAG
│   └── e2e/                 # E2E
│
├── docs/                    ← 문서
│   ├── ontology/            # Stanford 7-Step 온톨로지 설계
│   │   ├── stanford_7step_ontology.html  # 멀티KG 랜딩 + 7단계 설계 (메인)
│   │   └── step1_purpose_definition.md   # Step 1 마크다운 버전
│   └── strategy_5year_IMSP.md  # 5개년 전략서
│
├── examples/                ← 사용 예제
├── scripts/                 ← 스크립트
├── pyproject.toml           # Python 설정
└── CLAUDE.md                # 이 파일
```

## 코드 출처 (이식 매핑)

| 출처 | 대상 | 상태 |
|------|------|------|
| `flux-n8n/kg/` | `core/kg/` | ✅ 이식 완료 |
| `flux-n8n/maritime/` | `domains/maritime/` | ✅ 이식 완료 (재설계 예정) |
| `flux-n8n/tests/` | `tests/core/`, `tests/maritime/` | ✅ 이식 완료 |
| `flux-agent-builder/` | `agent/` | ✅ 이식 완료 |
| `flux-rag/` | `rag/` | ✅ 이식 완료 |
| 신규 | `ui/`, `gateway/`, `infra/` | ✅ 개발 완료 |

## 참조 프로젝트 (workspace)

| 프로젝트 | 활용 | 경로 |
|---------|------|------|
| **flux-ontology-local** | 온톨로지 재설계 시 스키마 패턴, SHACL 검증 참고 (TypeScript) | `../flux-ontology-local/` |
| **odin-ai** | 배치 ETL 5단계 아키텍처, 알림 엔진 패턴 참고 | `../odin-ai/` |
| **flux-polymarket** | WebSocket 실시간 스트리밍, 대시보드 UI 패턴 참고 | `../flux-polymarket/` |
| **flux-openclaw** | 멀티채널 봇 아키텍처, 7계층 보안 패턴 참고 | `../flux-openclaw/` |
| **flux-utility** | PDF 뷰어/어노테이션 패턴 참고 | `../flux-utility/` |

## 기술 스택

### 확정
- **KG DB:** Neo4j 5.x Community Edition
- **프론트엔드:** Vue 3 + VueFlow
- **인증:** Keycloak (OIDC)
- **컨테이너:** Kubernetes
- **모니터링:** Prometheus + Grafana + Loki + AlertManager + Zipkin
- **LLM:** 온프레미스 (A100급, 오픈소스)
- **워크플로우 실행:** Argo Workflow (DAG)
- **언어:** Python 3.10+ (백엔드), TypeScript (프론트엔드)

### 검토 중
| 항목 | 후보 |
|------|------|
| 시계열 DB | InfluxDB vs TimescaleDB |
| 객체 저장소 | MinIO vs S3 |
| Vector DB | Qdrant (확정) |
| GPU 분산추론 | Ray vs vLLM |
| K8s 배포 | Helm vs Kustomize |

## 주요 명령어

```bash
# 서비스 기동 (Neo4j + API + Postgres + Redis)
docker compose -f infra/docker-compose.yml up -d

# 단위 테스트 (Neo4j 불필요)
PYTHONPATH=. python3 -m pytest tests/ -m unit -v

# 통합 테스트 (Neo4j 필요)
PYTHONPATH=. python3 -m pytest tests/ -m integration -v

# 전체 테스트
PYTHONPATH=. python3 -m pytest tests/ -v

# E2E Mock Harness 테스트 (서비스 불필요)
PYTHONPATH=. python3 -m pytest tests/e2e/ -m unit -v

# E2E Real Neo4j 테스트 (Neo4j 필요)
NEO4J_TEST_URI=bolt://localhost:7687 NEO4J_TEST_PASSWORD=fluxrag2026 \
  PYTHONPATH=. python3 -m pytest tests/e2e/ -m "integration or e2e" -v

# Playwright 브라우저 E2E 테스트
cd ui && npx playwright test

# 서버 실행 (Gateway + UI)
PYTHONPATH=. python3 -m gateway --port 7749 --debug
cd ui && npm run dev
```

## 코딩 규칙

### Python
- Python 3.10+ 사용
- Type hints 필수
- Docstrings: Google 스타일
- 한국어 주석 허용

### Neo4j/Cypher
- 노드 레이블: PascalCase (Vessel, Port)
- 관계 타입: SCREAMING_SNAKE_CASE (DOCKED_AT)
- 속성명: camelCase (vesselType)
- 파라미터: $paramName

### 파일 명명
- Python: snake_case.py
- Cypher: snake_case.cypher
- TypeScript: camelCase.ts / PascalCase.tsx (컴포넌트)

## 환경변수

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=neo4j

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=imsp
POSTGRES_USER=imsp
POSTGRES_PASSWORD=your_password_here

# Redis
REDIS_URL=redis://:imsp-redis-2026@localhost:6379/1
REDIS_PASSWORD=imsp-redis-2026

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

## 핵심 전략 문서

- `docs/strategy_5year_IMSP.md` — 5개년 전략서 (1,479줄)
- `docs/architecture_flux_platform.md` — 아키텍처 설계 초안
- `docs/meeting_20260318_KRISO.md` — KRISO 미팅 정리
- `docs/ontology/stanford_7step_ontology.html` — DevKG 온톨로지 설계 (Stanford 7-Step, Step 1-3 완료, Vercel 배포)
- `docs/ontology/step1_purpose_definition.md` — Step 1: 목적 정의 (CQ1-CQ5, 도메인 범위, 조인 키)
- `docs/ontology/step2_reuse_evaluation.md` — Step 2: 재사용 분석 (S-100, AIS, MAKG 등 10종 판정)
- `docs/ontology/step3_key_term_enumeration.md` — Step 3: 핵심 용어 열거 (P0/P1/P2 3계층, 108 관계)
- `docs/ontology/step4_class_hierarchy.md` — Step 4: 클래스 계층 정의 (L1-L5, URN, 멀티레이블, S4-CQ1~3)

## 주의사항

1. `.env` 파일은 git에 포함하지 않음
2. 온톨로지 Stanford 7-Step 설계 Step 1-4 완료, 코드 동기화 완료 (147 엔티티(136+11 추상), 108 관계, 38 속성 블록, L1-L5 계층 + URN + 멀티레이블)
3. `domains/maritime/` — maritime_ontology.py에 9개 신규 엔티티 + 13개 신규 관계 반영 완료
4. `agent/`, `rag/` 이식 및 구현 완료 (4 LLM, MCP 3 transport, 하이브리드 RAG, VectorStore 3종)
5. Suredata Lab과 역할 분담: 우리가 전체 개발, 납품은 KG 파트만
6. JWT + Keycloak OIDC 듀얼 모드 인증 구현 완료 (RS256+JWKS + HS256 fallback, base64 fallback 제거됨)
7. ETL → ELT 전환 완료 (RawStore Protocol + LocalFileStore + deferred mode + reprocess API)
8. Activepieces 제거 완료, Argo Workflow (K8s only) 전환
9. 테스트 4,522+ 통과 (unit 4,447 + integration 75), 커버리지 ~92%
10. E2E 3-Tier 테스트 구축 완료: Mock Harness 112개 + Real Neo4j 10개 + Playwright 브라우저 35개
11. 멀티 프로젝트 KG 관리 구현 완료 — X-KG-Project 헤더 기반 레이블 격리 (KG_DevKG, KG_ProdKG 등)
12. S-100 ENC 매핑 스캐폴드 구현 (domains/maritime/s100/)
13. 온톨로지 설계 문서 Vercel 배포: https://imsp-ontology-docs.vercel.app (Step 1-4 완료)
14. 프로덕션 하드닝 완료: External Secrets, Redis 인증, Cypher 타임아웃, CD 파이프라인, HPA/PDB, AlertManager, Loki 로그, Grafana 대시보드, 운영 Runbook
15. Cypher LIMIT 자동삽입 RETURN절 한정, _inject_project_label MATCH절 한정, search fulltext fallback 버그 수정
