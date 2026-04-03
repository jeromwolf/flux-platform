# IMSP — Interactive Maritime Service Platform

대화형 해사서비스 설계 플랫폼

## 개요

KRISO(선박해양플랜트연구소) 발주, 인사이트마이닝 수행의 5개년(2026~2030) 해사서비스 플랫폼 프로젝트.
지식그래프 기반 해사 데이터 통합, AI 에이전트, RAG 검색, 워크플로우 저작 도구를 제공합니다.

## 아키텍처

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   UI (Vue3) │───▶│   Gateway    │───▶│   Core KG API   │
│   VueFlow   │    │   FastAPI    │    │   FastAPI 42+   │
│  Tailwind   │    │  httpx proxy │    │   routes        │
└─────────────┘    └──────┬───────┘    └────────┬────────┘
                          │                     │
                   ┌──────┴───────┐    ┌────────┴────────┐
                   │  Keycloak    │    │    Neo4j 5.x    │
                   │  OIDC + JWT  │    │   PostgreSQL    │
                   └──────────────┘    │   Redis/Qdrant  │
                                       └─────────────────┘
┌─────────────┐    ┌──────────────┐
│   Agent     │    │   RAG Engine │
│ ReAct/MCP   │    │  Hybrid BM25 │
│ 4 LLM/7tool │    │  3 VectorDB  │
└─────────────┘    └──────────────┘
```

## 모듈 현황

| 모듈 | 완성도 | 주요 기능 |
|------|--------|-----------|
| Core KG API | ~99% | 42+ REST routes, CRUD, Cypher, Fulltext, ETL/ELT, MCP |
| Core DB | ~95% | PostgreSQL (asyncpg), Redis rate limit, Alembic |
| RAG Engine | ~97% | BM25, PDF/HWP/DOCX/PPTX, VectorStore 3종, Reranker 4종 |
| Agent Runtime | ~97% | ReAct/Pipeline/Batch, MCP 3 transport, 7 tools, 4 LLM |
| Gateway | ~98% | httpx proxy 22 routes, circuit breaker, cache, WS heartbeat |
| UI | ~92% | Vue 3 + VueFlow, WebSocket, Tailwind, vue-i18n |
| Infra | ~99% | Docker Compose 12 svcs, K8s, CI/CD, TLS, NetworkPolicy |

## 온톨로지

Stanford 7-Step 설계 방법론 기반 해사 온톨로지 (Step 1-3 완료, 코드 동기화 완료).

- **136 엔티티** (P0 Core 27 + P1 Extended ~47 + P2 Future ~55 + 기존 7)
- **95 관계 타입** (P0 28 + P1 18 + P2 62 기반, 기존 포함)
- **38 속성 정의 블록**
- **설계 문서:** https://imsp-ontology-docs.vercel.app

## 빠른 시작

```bash
# 의존성 설치
pip install -e ".[dev]"
cd ui && npm install && cd ..

# 인프라 기동
docker compose -f infra/docker-compose.yml up -d

# 백엔드 서버
PYTHONPATH=. python3 -m gateway --port 7749 --debug

# 프론트엔드 개발 서버
cd ui && npm run dev
```

브라우저에서 http://localhost:5180 접속

## 테스트

```bash
# 전체 테스트 (4,430+ passed, 80 skipped)
PYTHONPATH=. python3 -m pytest tests/ -v

# 단위 테스트만 (Neo4j 불필요)
PYTHONPATH=. python3 -m pytest tests/ -m unit -v

# 통합 테스트 (Neo4j 필요)
PYTHONPATH=. python3 -m pytest tests/ -m integration -v

# E2E Mock Harness (서비스 불필요, 112 tests)
PYTHONPATH=. python3 -m pytest tests/e2e/ -m unit -v

# E2E Real Neo4j (Docker Neo4j 필요, 10 tests)
NEO4J_TEST_URI=bolt://localhost:7687 NEO4J_TEST_PASSWORD=fluxrag2026 \
  PYTHONPATH=. python3 -m pytest tests/e2e/ -m "integration or e2e" -v

# Playwright 브라우저 E2E (35 tests)
cd ui && npx playwright test
cd ui && npx playwright test --ui   # 디버그 UI 모드
```

### E2E 3-Tier 구조

| Tier | 유형 | 테스트 수 | 필요 서비스 |
|------|------|----------|------------|
| A | Mock Harness (Python) | 112 | 없음 |
| B | Real Neo4j (Python) | 10 | Neo4j |
| C | Playwright (Browser) | 35 | 없음 (API mock) |

## 기술 스택

- **Backend:** Python 3.10+, FastAPI, asyncpg, Redis
- **KG DB:** Neo4j 5.x Community Edition
- **Vector DB:** Qdrant (InMemory/ChromaDB fallback)
- **Frontend:** Vue 3, VueFlow, Tailwind CSS, Pinia
- **Auth:** Keycloak OIDC (RS256+JWKS) + JWT HS256 듀얼 모드
- **Infra:** Kubernetes, Docker Compose, Prometheus, Zipkin, Argo Workflow
- **LLM:** Ollama, OpenAI, Anthropic (온프레미스 우선)

## 환경변수

`.env.example` 참조. 주요 변수:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j 접속 URI |
| `POSTGRES_HOST` | `localhost` | PostgreSQL 호스트 |
| `REDIS_URL` | `redis://localhost:6379` | Redis URL |
| `QDRANT_HOST` | `localhost` | Qdrant 호스트 |
| `KEYCLOAK_URL` | - | Keycloak 서버 URL |
| `GATEWAY_PORT` | `8080` | Gateway 포트 |

## 프로젝트 구조

```
flux-platform/
├── core/          # 도메인 독립 KG 엔진 + FastAPI API
├── domains/       # 해사 도메인 (온톨로지, S-100 매핑, 크롤러)
├── agent/         # AI 에이전트 런타임 (ReAct, MCP, Tools)
├── rag/           # RAG 엔진 (하이브리드 검색, 문서 파이프라인)
├── gateway/       # API Gateway (프록시, WS, Keycloak 미들웨어)
├── ui/            # Vue 3 프론트엔드
├── infra/         # Docker, K8s, CI/CD, Keycloak
├── tests/         # 테스트 (4,430+ unit/harness + 35 Playwright)
├── docs/          # 전략서, 온톨로지 설계
└── scripts/       # 유틸리티 스크립트
```

## 라이선스

Proprietary — 인사이트마이닝
