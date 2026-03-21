# 14. 디렉토리 구조 (최종 목표 - Y5 기준)

[← 연차별 로드맵](./13-roadmap.md) | [다음: 플랫폼 운영 기능 →](./15-platform-operations.md)

## 개요

본 문서는 IMSP 플랫폼의 최종 목표(Y5, 2030년) 기준 디렉토리 구조를 정의한다. 현재(Y1 Q1) 구현된 모듈과 향후 이식/신규 개발 예정인 모듈을 구분하여, 프로젝트의 성장 방향을 명확히 한다. 모든 모듈은 `core/kg/`를 중심으로 단방향 의존 구조를 유지하며, 각 디렉토리의 역할과 포함 파일을 상세히 기술한다.

---

## 14.1 최종 목표 디렉토리 트리

```
flux-platform/
│
├── core/                              <- 도메인 독립 KG 엔진 (20,000+ lines)
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
│       │   └── ollama_embedder.py     # nomic-embed-text 768-dim (256d 궤적/512d 시각/768d 텍스트/1024d 융합 지원 예정)
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
│       │   │   ├── query.py           # POST /api/v1/query (Text2Cypher)
│       │   │   ├── graph.py           # GET  /api/v1/subgraph, /neighbors, /search
│       │   │   ├── schema.py          # GET  /api/v1/schema
│       │   │   ├── etl.py             # POST /api/v1/etl/trigger, webhook, status, history
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
├── domains/                           <- 도메인 플러그인
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
├── agent/                             <- 에이전트 런타임 (flux-agent-builder 이식 예정)
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
├── rag/                               <- RAG 엔진 (flux-rag 이식 예정)
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
├── ui/                                <- 프론트엔드 (Vue 3 + VueFlow, 신규)
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
├── gateway/                           <- API Gateway (신규)
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
├── infra/                             <- 인프라
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
│   └── docker-compose.yml             # 로컬 개발용 (Neo4j 5.26 + FastAPI + Activepieces + PostgreSQL 14 + Redis 7)
│
├── tests/                             <- 테스트 스위트
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
│   ├── maritime/                      # 해사 도메인 테스트 (17 파일)
│   ├── agent/                         # 에이전트 테스트
│   ├── rag/                           # RAG 엔진 테스트
│   ├── e2e/                           # E2E 시나리오 테스트
│   │   ├── test_text2cypher_e2e.py    # "부산항 선박 목록" 전체 흐름
│   │   ├── test_etl_e2e.py            # AIS 수신 → KG 적재 전체 흐름
│   │   └── test_agent_e2e.py          # 에이전트 대화 전체 흐름
│   └── conftest.py                    # 공통 pytest 픽스처
│
├── docs/                              <- 문서
│   ├── strategy_5year_IMSP.md         # 5개년 전략서 (1,479줄)
│   ├── architecture/                  # 아키텍처 상세 문서 (17개 파일)
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
├── examples/                          <- 사용 예제
│   ├── text2cypher_basic.py           # 기본 Text2Cypher 사용법
│   ├── etl_ais_ingest.py              # AIS 데이터 수집 예제
│   └── agent_kg_query.py              # 에이전트 KG 쿼리 예제
│
├── scripts/                           <- 운영 스크립트
│   ├── migrate_schema.py              # Neo4j 스키마 마이그레이션
│   ├── load_evaluation_dataset.py     # 평가 데이터셋 로드
│   ├── export_ontology.py             # 온톨로지 OWL 내보내기
│   └── seed_demo_data.py              # 데모 데이터 시드
│
├── pyproject.toml                     # Python 프로젝트 설정 (setuptools)
├── CLAUDE.md                          # AI 어시스턴트 지침
└── AGENTS.md                          # 에이전트 코드 인덱스 (deepinit 생성)
```

---

## 14.2 현재 구현 상태 (Y1 Q1 기준)

아래 표는 2026년 3월 현재 각 디렉토리의 구현 상태를 정리한 것이다.

| 디렉토리 | 상태 | 파일 수 | 비고 |
|---------|------|--------|------|
| `core/kg/` | ✅ 구현 완료 | 83 | flux-n8n에서 이식. 20,000+ lines. 40+ public API exports |
| `core/kg/ontology/` | ✅ 구현 완료 | 2 | Palantir Foundry 패턴. ObjectType/LinkType/PropertyDef 삼중 구조 |
| `core/kg/nlp/` | ✅ 구현 완료 | 3 | NLParser + TermDictionary Protocol + 해사 용어 3,000+ 항목 |
| `core/kg/entity_resolution/` | ✅ 구현 완료 | 3 | 3단계 해석기 (정확/퍼지/LLM). O(n^2) → O(n log n) 개선 예정 |
| `core/kg/embeddings/` | ✅ 구현 완료 | 1 | Ollama nomic-embed-text 768-dim |
| `core/kg/etl/` | ✅ 구현 완료 | 6 | ETLPipeline 5단계 + DLQ + BatchLoader |
| `core/kg/lineage/` | ✅ 구현 완료 | 4 | W3C PROV-O. in-memory (Neo4j flush 추가 예정) |
| `core/kg/rbac/` | ✅ 구현 완료 | 4 | SecureCypherBuilder. JWT 기반 (→ Keycloak 전환 예정) |
| `core/kg/n10s/` | ✅ 구현 완료 | 2 | OWL import/export via Neosemantics |
| `core/kg/evaluation/` | ✅ 구현 완료 | 3 | EvaluationRunner + CypherAccuracy 메트릭 |
| `core/kg/api/` | ✅ 구현 완료 | 9 | FastAPI. query/graph/schema/etl/lineage/health 라우트 |
| `domains/maritime/` | ✅ 이식 완료 | 44 | flux-n8n에서 복사. KRISO 요구 기반 완전 재설계 예정 |
| `agent/` | ⏳ 미구현 | 0 | flux-agent-builder에서 이식 예정 (Y1 Q3~Q4) |
| `rag/` | ⏳ 미구현 | 0 | flux-rag에서 이식 예정 (Y2) |
| `ui/` | 🆕 미착수 | 0 | Vue 3 + VueFlow 신규 개발 (Y1 Q3 PoC, Y2 본격) |
| `gateway/` | 🆕 미착수 | 0 | API Gateway 신규 개발 (Y2) |
| `infra/` | ⚠️ 최소 | 2 | docker-compose.yml + Dockerfile.core만 존재 |
| `tests/core/` | ✅ 구현 완료 | 19 | KG 엔진 단위/통합 테스트 |
| `tests/maritime/` | ✅ 구현 완료 | 17 | 해사 도메인 테스트 |
| `tests/` (전체) | ✅ 구현 완료 | 36+ | 1,136 테스트 통과 |
| `docs/` | ✅ 작성 중 | 15+ | 전략서, 아키텍처, 설계서, 요구사항 |
| `examples/` | ⏳ 미착수 | 0 | Y1 Q4에 작성 예정 |
| `scripts/` | ⏳ 미착수 | 0 | Y1 Q2에 작성 시작 예정 |

---

## 14.3 Y1 vs Y5 디렉토리 비교

현재(Y1 Q1)와 최종 목표(Y5) 사이의 차이를 시각적으로 비교한다.

```
Y1 Q1 (2026-03, 현재)                    Y5 (2030, 최종 목표)
========================                  ========================

flux-platform/                            flux-platform/
├── core/kg/          [✅ 83 files]       ├── core/kg/          [✅ 100+ files]
│   ├── ontology/     [✅]                │   ├── ontology/     [✅ 확장]
│   ├── nlp/          [✅]                │   ├── nlp/          [✅ 확장]
│   ├── entity_resolution/ [✅]           │   ├── entity_resolution/ [✅ HNSW]
│   ├── embeddings/   [✅]                │   ├── embeddings/   [✅]
│   ├── etl/          [✅]                │   ├── etl/          [✅ +Async]
│   ├── lineage/      [✅]                │   ├── lineage/      [✅ 4종 통합]
│   ├── rbac/         [✅]                │   ├── rbac/         [✅ Keycloak]
│   ├── n10s/         [✅]                │   ├── n10s/         [✅]
│   ├── evaluation/   [✅]                │   ├── evaluation/   [✅ 500문항]
│   └── api/          [✅]                │   └── api/          [✅ v2]
│                                         │
├── domains/maritime/ [✅ 44 files]       ├── domains/maritime/ [✅ 80+ files]
│   (재설계 예정)                          │   ├── s100/         [✅ S-101/S-124]
│                                         │   ├── workflows/    [✅ Argo]
│                                         │   └── ...
│                                         │
├── agent/            [⏳ 비어있음]        ├── agent/            [✅ 30+ files]
│                                         │   ├── runtime/      [✅ ReAct/Pipeline]
│                                         │   ├── tools/        [✅ 10+ 도구]
│                                         │   ├── memory/       [✅ Redis+Neo4j]
│                                         │   ├── llm/          [✅ Multi-provider]
│                                         │   ├── mcp/          [✅ A2A]
│                                         │   └── skills/       [✅ 20+ 스킬]
│                                         │
├── rag/              [⏳ 비어있음]        ├── rag/              [✅ 15+ files]
│                                         │   ├── engines/      [✅ 5종]
│                                         │   ├── documents/    [✅ PDF/HWP/OCR]
│                                         │   └── embeddings/   [✅ Vector store]
│                                         │
├── ui/               [🆕 없음]           ├── ui/               [✅ 50+ files]
│                                         │   ├── canvas/       [✅ VueFlow]
│                                         │   ├── chat/         [✅ 대화 UI]
│                                         │   ├── auth/         [✅ Keycloak]
│                                         │   ├── map/          [✅ 전자해도]
│                                         │   └── portal/       [✅ 서비스 포털]
│                                         │
├── gateway/          [🆕 없음]           ├── gateway/          [✅ 15+ files]
│                                         │   ├── routes/       [✅ v1+v2]
│                                         │   ├── ws/           [✅ WebSocket]
│                                         │   └── middleware/   [✅ 보안+제한]
│                                         │
├── infra/            [⚠️ 2 files]        ├── infra/            [✅ 30+ files]
│   └── docker-compose.yml               │   ├── helm/         [✅ Helm 차트]
│                                         │   ├── docker/       [✅ 4 Dockerfiles]
│                                         │   ├── keycloak/     [✅ Realm 설정]
│                                         │   ├── prometheus/   [✅ 모니터링]
│                                         │   ├── argo/         [✅ 워크플로우]
│                                         │   └── docker-compose.yml
│                                         │
├── tests/            [✅ 36 files]       ├── tests/            [✅ 100+ files]
│   ├── core/         [✅ 19]             │   ├── core/         [✅ 30+]
│   └── maritime/     [✅ 17]             │   ├── maritime/     [✅ 25+]
│                                         │   ├── agent/        [✅ 15+]
│                                         │   ├── rag/          [✅ 10+]
│                                         │   └── e2e/          [✅ 15+]
│                                         │
├── docs/             [✅ 15+ files]      ├── docs/             [✅ 30+ files]
├── examples/         [⏳ 없음]           ├── examples/         [✅ 5+ files]
└── scripts/          [⏳ 없음]           └── scripts/          [✅ 5+ files]

총 파일 수:  ~170                         총 파일 수:  ~500+
총 코드량:   ~25,000 lines               총 코드량:   ~80,000+ lines
테스트 수:   1,136                        테스트 수:   3,000+
```

---

## 14.4 디렉토리별 역할 요약

| 계층 | 디렉토리 | 역할 | 의존 관계 |
|------|---------|------|----------|
| **엔진** | `core/kg/` | 도메인 독립 KG 엔진. Cypher 빌더, 파이프라인, 검증, ETL, 리니지 | 외부 라이브러리만 |
| **도메인** | `domains/maritime/` | 해사 도메인 플러그인. 온톨로지, 용어 사전, 크롤러, S-100 | `core/kg/` |
| **에이전트** | `agent/` | AI 에이전트 런타임. ReAct 루프, 도구, 메모리, LLM, MCP | `core/kg/` |
| **RAG** | `rag/` | 검색 증강 생성. 벡터/그래프/하이브리드 검색, 문서 파이프라인 | `core/kg/`, `agent/` |
| **프론트엔드** | `ui/` | Vue 3 SPA. VueFlow 캔버스, 대화 UI, 전자해도, 포털 | `gateway/` (HTTP) |
| **게이트웨이** | `gateway/` | API Gateway. 라우팅, WebSocket, 인증, Rate Limit | `core/kg/api/` |
| **인프라** | `infra/` | 배포 설정. Helm, Docker, Keycloak, Prometheus, Argo | 코드 의존 없음 |
| **테스트** | `tests/` | 단위/통합/E2E 테스트 | `core/kg/`, `domains/` |
| **문서** | `docs/` | 전략서, 아키텍처, 설계서, 요구사항 | 코드 참조만 |

---

*관련 문서: [컴포넌트 아키텍처](./03-component-architecture.md), [배포 아키텍처](./05-deployment-architecture.md), [설계 원칙](./12-design-principles.md)*
