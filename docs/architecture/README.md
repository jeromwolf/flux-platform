# IMSP 상세 아키텍처 문서

> 작성일: 2026-03-20 | 버전: v1.0

## 개요

**IMSP (Interactive Maritime Service Platform)** 는 KRISO(한국해양과학기술원 부설 선박해양플랜트연구소)가 발주하고 인사이트마이닝이 개발하는 대화형 해사서비스 설계 플랫폼이다. 5개년(2026-2030) 사업으로, 지식그래프 기반의 해사 데이터 통합 및 워크플로우 저작 환경을 구축하여 민간의 해사서비스 연구개발을 지원한다.

본 문서 모음은 IMSP 플랫폼의 상세 아키텍처를 22개 독립 문서로 분리하여 기술한다. 원본 문서(`ARCHITECTURE_DETAIL_IMSP.md`)의 각 섹션을 자기 완결적(self-contained) 파일로 추출하고, 코드 매핑 및 상세 설명을 보강하였다.

---

## 문서 목록

| # | 문서 | 설명 |
|---|------|------|
| 0 | [00-terminology.md](./00-terminology.md) | 용어 정의 및 MDT-Ops 개념 |
| 1 | [01-system-context.md](./01-system-context.md) | 시스템 컨텍스트 (액터, 데이터소스, 인터페이스) |
| 2 | [02-system-architecture.md](./02-system-architecture.md) | 시스템 아키텍처 개요 (5-Tier) |
| 3 | [03-component-architecture.md](./03-component-architecture.md) | 컴포넌트 아키텍처 (KG엔진, API, Agent, RAG) |
| 4 | [04-data-architecture.md](./04-data-architecture.md) | 데이터 아키텍처 (온톨로지, 저장전략, ELT, 리니지) |
| 5 | [05-deployment-architecture.md](./05-deployment-architecture.md) | 배포 아키텍처 (Kubernetes, CI/CD, GPU) |
| 6 | [06-security-architecture.md](./06-security-architecture.md) | 보안 아키텍처 (3계층 모델, RBAC, 감사) |
| 7 | [07-data-flow.md](./07-data-flow.md) | 데이터 흐름도 (Text2Cypher, ELT, 워크플로우, OWL) |
| 8 | [08-suredata-integration.md](./08-suredata-integration.md) | Suredata Lab 연동 아키텍처 |
| 9 | [09-tech-stack.md](./09-tech-stack.md) | 기술 스택 매트릭스 |
| 10 | [10-observability.md](./10-observability.md) | 관측성 아키텍처 (메트릭, 추적, 로그) |
| 11 | [11-ai-llm.md](./11-ai-llm.md) | AI/LLM 아키텍처 (모델스택, Agent, Text2Cypher) |
| 12 | [12-design-principles.md](./12-design-principles.md) | 설계 원칙 및 패턴 |
| 13 | [13-roadmap.md](./13-roadmap.md) | 연차별 아키텍처 진화 (Y1-Y5) |
| 14 | [14-directory-structure.md](./14-directory-structure.md) | 디렉토리 구조 (최종 목표 Y5) |
| 15 | [15-platform-operations.md](./15-platform-operations.md) | 플랫폼 운영 기능 (리니지, 자산관리, 서비스Pool, 협업, SDK) |
| 16 | [16-architecture-review.md](./16-architecture-review.md) | 아키텍처 리뷰 및 개선 계획 |
| 17 | [에러 처리 전략](./17-error-handling.md) | RFC 7807, 에러 코드 네임스페이스, 에러 심각도 |
| 18 | [API 설계 표준](./18-api-standards.md) | REST 규약, 페이지네이션, Rate Limiting, 버전 관리 |
| 19 | [마이그레이션 전략](./19-migration-strategy.md) | Neo4j 스키마 마이그레이션, 온톨로지 진화, 롤백 |
| 20 | [NLP/NER 전략](./20-nlp-ner.md) | 해사 NER, 엔티티 해석, Text2Cypher 연동, 학습 데이터 |
| 21 | [시각화 아키텍처](./21-visualization.md) | S-100, 3D 렌더러, 대시보드, 모바일, AR/VR |
| 22 | [지식그래프 고급 아키텍처](./22-kg-advanced.md) | 시간 KG, 그래프 알고리즘, 추론/Axioms, 메타데이터, 스트리밍 |

---

## 문서 구성 원칙

1. **독립성**: 각 문서는 독립적으로 읽을 수 있어야 한다. 필요한 컨텍스트는 문서 내부의 "개요" 섹션에서 제공하며, 다른 문서의 상세 내용이 필요한 경우 명시적으로 링크한다.
2. **네비게이션**: 모든 문서 상단에 이전/다음 문서 링크를 배치하여 순차 탐색이 가능하다.
3. **한국어 기술**: 설명과 주석은 한국어로 작성한다. 기술 용어(Kubernetes, RBAC, FastAPI 등)는 영문 원어를 그대로 사용한다.
4. **코드 매핑**: 각 아키텍처 개념이 실제 코드베이스의 어떤 모듈에 대응되는지 명시하여, 문서와 구현 간의 추적성(traceability)을 확보한다.
5. **다이어그램**: ASCII 다이어그램을 사용하여 별도 도구 없이도 텍스트 에디터에서 확인 가능하다.

---

## 관련 문서

| 문서 | 설명 | 경로 |
|------|------|------|
| 5개년 전략서 | IMSP 사업의 전체 전략 및 연차별 목표 | [`strategy_5year_IMSP.md`](../strategy_5year_IMSP.md) |
| 아키텍처 설계 초안 | 초기 아키텍처 구상 (본 문서의 전신) | [`architecture_flux_platform.md`](../architecture_flux_platform.md) |
| KRISO 미팅 정리 | 2026-03-18 KRISO 킥오프 미팅 결과 | [`meeting_20260318_KRISO.md`](../meeting_20260318_KRISO.md) |
| 원본 통합 문서 | 본 문서 모음의 원본 단일 파일 | [`ARCHITECTURE_DETAIL_IMSP.md`](../ARCHITECTURE_DETAIL_IMSP.md) |

---

> **참고:** 본 문서는 `ARCHITECTURE_DETAIL_IMSP.md` 원본에서 섹션별로 분리하고 코드 매핑, 네트워크 경계, 외부 인터페이스 상세 등을 보강한 것이다.
