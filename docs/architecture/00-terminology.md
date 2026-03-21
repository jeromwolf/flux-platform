# 0. 용어 정의

[← README](./README.md) | [다음: 시스템 컨텍스트 →](./01-system-context.md)

---

## 개요

본 문서는 IMSP 플랫폼 전체에서 사용하는 핵심 용어를 정의한다. 아키텍처 문서, 설계서, 코드 주석에서 동일한 의미로 사용되어야 하며, 용어 간 계층 관계(자원 → 자산 → 컴포넌트 → 워크플로우 → 서비스)를 명확히 구분한다.

---

## 핵심 용어

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

---

## MDT-Ops (Maritime Digital Twin Operations)

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

MDT-Ops의 4개 축은 다음과 같이 IMSP의 아키텍처 계층에 매핑된다:

| MDT-Ops 축 | IMSP 아키텍처 계층 | 핵심 기술 |
|------------|-------------------|----------|
| Dev | Presentation + Service Layer | VueFlow, FastAPI, SDK |
| Data | Data Layer | Neo4j, Ceph RGW, TimescaleDB, ELT |
| ML | Service Layer (AI/Agent) | Ollama, vLLM, Ray, Model Registry |
| Ops | Infrastructure Layer | K8s, Argo, Prometheus, Keycloak |

---

## 코드 매핑

아래 표는 각 용어가 현재 코드베이스의 어떤 모듈에 대응되는지를 보여준다. 아직 구현되지 않은 항목은 계획 상태로 표기한다.

| 용어 | 코드베이스 위치 | 설명 |
|------|---------------|------|
| **자원 (Resource)** | `core/kg/etl/` | ELT 파이프라인이 원천 데이터를 수집하여 자원으로 관리. Ceph RGW 객체 저장소에 원본 보존 (로컬 개발 시 MinIO 사용) |
| **자산 (Asset)** | 계획 단계 | 자산 레지스트리는 Section 15 (플랫폼 운영 기능)에서 설계. Y2에서 구현 예정 |
| **응용 (App)** | `domains/maritime/workflows/` | 현재 Activepieces 워크플로우 정의. Argo Workflow (K8s Job) 전환 예정 |
| **컴포넌트 (Component)** | `core/kg/` 전체 모듈 | CypherBuilder, QueryGenerator, Pipeline 등 재사용 가능한 KG 엔진 모듈 |
| **어댑터 (Adapter)** | `domains/maritime/crawlers/`, `core/kg/etl/` | 외부 데이터 수집용 크롤러 및 ETL Transform 모듈 |
| **워크플로우 (Workflow)** | `domains/maritime/workflows/` | Activepieces JSON 정의. 향후 Argo DAG YAML로 전환 |
| **서비스 (Service)** | `core/kg/api/app.py` | FastAPI 앱으로 KG 질의/관리 API 제공. K8s Deployment로 운영 |

---

## 약어 목록

본 아키텍처 문서 전체에서 사용되는 주요 약어를 정리한다.

| 약어 | 풀네임 | 설명 |
|------|--------|------|
| AIS | Automatic Identification System | 선박 자동 식별 시스템 |
| BM25 | Best Matching 25 | 확률적 텍스트 검색 알고리즘 |
| CIDR | Classless Inter-Domain Routing | IP 주소 범위 표기법 |
| CQRS | Command Query Responsibility Segregation | 명령-조회 책임 분리 패턴 |
| DAG | Directed Acyclic Graph | 유향 비순환 그래프 (워크플로우 실행 단위) |
| DLQ | Dead Letter Queue | 실패 메시지 격리 큐 |
| DW | Data Warehouse | 데이터 웨어하우스 |
| ELT | Extract-Load-Transform | 추출-적재-변환 (원본 보존 우선 패턴) |
| gRPC | gRPC Remote Procedure Call | 고성능 원격 프로시저 호출 프로토콜 |
| GRIB2 | GRIdded Binary Edition 2 | 기상 데이터 이진 포맷 |
| HNSW | Hierarchical Navigable Small World | 벡터 유사도 검색 인덱스 알고리즘 |
| KG | Knowledge Graph | 지식그래프 |
| KRISO | Korea Research Institute of Ships & Ocean Engineering | 한국해양과학기술원 부설 선박해양플랜트연구소 |
| LoRA | Low-Rank Adaptation | 경량 LLM 파인튜닝 기법 |
| MDT-Ops | Maritime Digital Twin Operations | 해사 디지털 트윈 운영 프레임워크 |
| mTLS | Mutual Transport Layer Security | 상호 TLS 인증 |
| NER | Named Entity Recognition | 개체명 인식 |
| NMEA | National Marine Electronics Association | 해양 전자 장비 통신 규격 (0183/2000) |
| OIDC | OpenID Connect | 인증 프로토콜 (Keycloak 기반) |
| OWL | Web Ontology Language | 웹 온톨로지 언어 |
| PKCE | Proof Key for Code Exchange | OAuth 2.0 인증 코드 보안 확장 |
| PROV-O | PROV Ontology | W3C 데이터 출처 추적 온톨로지 |
| QLoRA | Quantized LoRA | 양자화 기반 경량 파인튜닝 |
| RBAC | Role-Based Access Control | 역할 기반 접근 제어 |
| RRF | Reciprocal Rank Fusion | 다중 검색 결과 통합 알고리즘 |
| RTSP | Real Time Streaming Protocol | 실시간 스트리밍 프로토콜 (CCTV/영상) |
| S-100 | IHO S-100 | 국제수로기구 해사 데이터 표준 프레임워크 |
| SBOM | Software Bill of Materials | 소프트웨어 구성 요소 명세서 |
| SHACL | Shapes Constraint Language | 그래프 데이터 검증 언어 |
| SLI | Service Level Indicator | 서비스 수준 지표 |
| SLO | Service Level Objective | 서비스 수준 목표 |
| TOTP | Time-based One-Time Password | 시간 기반 일회용 비밀번호 |
| VTS | Vessel Traffic Service | 해상교통관제 서비스 |

---

## 아키텍처 핵심 개념

본 문서에서 반복적으로 사용되는 아키텍처 개념을 정의한다.

| 개념 | 정의 | 관련 문서 |
|------|------|----------|
| **Text2Cypher** | 자연어 질의를 Neo4j Cypher 쿼리로 변환하는 파이프라인. NL 파싱 → 엔티티 해석 → Cypher 생성 → 검증 → 교정 5단계로 구성 | [03-컴포넌트](./03-component-architecture.md), [07-데이터흐름](./07-data-flow.md) |
| **GraphRAG** | 지식그래프 기반 검색 증강 생성. 벡터 검색 + 그래프 순회를 결합하여 LLM 응답의 정확도를 향상 | [03-컴포넌트](./03-component-architecture.md), [11-AI/LLM](./11-ai-llm.md) |
| **Dual-Path Query Routing** | Text2Cypher(구조화 질의)와 GraphRAG(비구조화 질의) 두 경로를 질의 유형에 따라 자동 분기하는 라우팅 전략 | [07-데이터흐름](./07-data-flow.md) |
| **Collection Adapter** | 외부 데이터 소스(AIS, 기상, CCTV 등)로부터 데이터를 수집하여 Object Storage에 원본 적재하는 어댑터 패턴 | [01-시스템컨텍스트](./01-system-context.md), [04-데이터](./04-data-architecture.md) |
| **ELT 파이프라인** | Extract-Load-Transform 패턴. 원본 데이터를 먼저 Object Storage에 적재한 후, 변환하여 KG/TimescaleDB에 반영. ETL 대비 원본 보존 및 재처리 유연성 확보 | [04-데이터](./04-data-architecture.md) |
| **A2A Protocol** | Agent-to-Agent Protocol. 에이전트 간 통신을 위한 Google 제안 프로토콜. MCP와 상호 보완 관계 | [03-컴포넌트](./03-component-architecture.md), [11-AI/LLM](./11-ai-llm.md) |
| **MCP** | Model Context Protocol. LLM이 외부 도구/데이터에 접근하기 위한 Anthropic 제안 프로토콜 | [03-컴포넌트](./03-component-architecture.md) |
| **NER (개체명 인식)** | Named Entity Recognition. 텍스트에서 선박명, 항만명, 기관명 등 해사 도메인 개체를 식별하는 NLP 태스크. Text2Cypher 파이프라인의 전처리 단계 | [20-NLP/NER](./20-nlp-ner.md) |
| **MDT-Ops** | Maritime Digital Twin Operations. 해사 분야의 DevOps/MLOps를 통합한 운영 프레임워크 | 본 문서 상단 참조 |

---

[← README](./README.md) | [다음: 시스템 컨텍스트 →](./01-system-context.md)
