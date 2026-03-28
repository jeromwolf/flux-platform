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
                   │  WebSocket   │    │    Neo4j 5.x    │
                   │  heartbeat   │    │   PostgreSQL    │
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
| Gateway | ~99% | httpx proxy 22 routes, circuit breaker, cache, WS heartbeat |
| UI | ~92% | Vue 3 + VueFlow, WebSocket, Tailwind, vue-i18n |
| Infra | ~99% | Docker Compose 13 svcs, K8s, CI/CD, TLS, NetworkPolicy |

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
# 전체 테스트 (3,344 passed, 80 skipped)
PYTHONPATH=. python3 -m pytest tests/ -v

# 단위 테스트만 (Neo4j 불필요)
PYTHONPATH=. python3 -m pytest tests/ -m unit -v

# 통합 테스트 (Neo4j 필요)
PYTHONPATH=. python3 -m pytest tests/ -m integration -v
```

## 기술 스택

- **Backend:** Python 3.10+, FastAPI, asyncpg, Redis
- **KG DB:** Neo4j 5.x Community Edition
- **Vector DB:** Qdrant (InMemory/ChromaDB fallback)
- **Frontend:** Vue 3, VueFlow, Tailwind CSS, Pinia
- **Auth:** Keycloak (OIDC) — 현재 JWT 기반, 전환 예정
- **Infra:** Kubernetes, Docker Compose, Prometheus, Zipkin
- **LLM:** Ollama, OpenAI, Anthropic (온프레미스 우선)

## 환경변수

`.env.example` 참조. 주요 변수:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j 접속 URI |
| `POSTGRES_HOST` | `localhost` | PostgreSQL 호스트 |
| `REDIS_URL` | `redis://localhost:6379` | Redis URL |
| `QDRANT_HOST` | `localhost` | Qdrant 호스트 |
| `GATEWAY_PORT` | `8080` | Gateway 포트 |

## 프로젝트 구조

```
flux-platform/
├── core/          # 도메인 독립 KG 엔진 + FastAPI API
├── domains/       # 해사 도메인 (온톨로지, 크롤러, 스키마)
├── agent/         # AI 에이전트 런타임 (ReAct, MCP, Tools)
├── rag/           # RAG 엔진 (하이브리드 검색, 문서 파이프라인)
├── gateway/       # API Gateway (프록시, WS, 미들웨어)
├── ui/            # Vue 3 프론트엔드
├── infra/         # Docker, K8s, CI/CD
├── tests/         # 테스트 (3,344+)
├── docs/          # 전략서, 아키텍처
└── scripts/       # 유틸리티 스크립트
```

## 라이선스

Proprietary — 인사이트마이닝
