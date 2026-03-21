# 9. 기술 스택 매트릭스

[← Suredata Lab 연동](./08-suredata-integration.md) | [다음: 관측성 아키텍처 →](./10-observability.md)

## 개요

IMSP 플랫폼의 기술 스택은 확정 기술과 미결정 기술로 구분된다.
확정 기술은 KRISO 미팅 및 내부 기술 검토를 통해 선정되었으며,
미결정 기술은 연차별 벤치마크를 통해 결정한다.
모든 기술은 오픈소스 기반으로 정부 R&D 납품 요건과 온프레미스 운영 환경에 적합해야 한다.

---

## 9.1 확정 기술

| 영역 | 기술 | 버전 | 라이선스 | 역할 | 선정 근거 |
|------|------|------|---------|------|----------|
| 프론트엔드 프레임워크 | Vue 3 + VueFlow | 3.x / 0.x | MIT | 워크플로우 캔버스, SPA | KRISO 미팅 확정, n8n 스타일 노드 에디터 최적 |
| KG Database | Neo4j CE | 5.26 | GPLv3 | Knowledge Graph 저장/조회 | Cypher, 그래프+벡터+공간 통합 인덱스 |
| 온톨로지 도구 | Protege + n10s | 5.6 / 5.x | BSD/Apache 2.0 | OWL 2 설계 -> Neo4j 변환 | W3C 표준, 자동화된 OWL-KG 변환 |
| 인증/인가 | Keycloak | 24.x | Apache 2.0 | OIDC SSO, RBAC 허브 | 공공기관 통합 인증, SAML/OIDC 지원 |
| 컨테이너 오케스트레이션 | Kubernetes | 1.28+ | Apache 2.0 | 프로덕션 인프라 관리 | GPU 워크로드, 멀티테넌트, HPA |
| 메트릭 모니터링 | Prometheus + Grafana | - | Apache 2.0 | 메트릭 수집 + 시각화 | K8s 네이티브, CNCF 표준 |
| 분산 추적 | Zipkin | 2.x | Apache 2.0 | 서비스 간 추적 | 경량, OpenTracing 호환 |
| 분산 추론 | Ray | 2.x | Apache 2.0 | A100+ GPU 분산 서빙 | 스케일아웃, vLLM 통합 |
| RDBMS | PostgreSQL | 14 | PostgreSQL | Keycloak/워크플로우 백엔드 | 안정성, 오픈소스, 라이선스 무료 |
| LLM 런타임 (초기) | Ollama | Latest | MIT | 온프레미스 LLM 서빙 | 간편한 모델 관리, CPU/GPU 지원 |
| LLM 런타임 (성장) | vLLM | 0.4+ | Apache 2.0 | 고성능 GPU 서빙 | Continuous Batching, 처리량 극대화 |
| 워크플로우 실행 | Argo Workflow | 3.x | Apache 2.0 | DAG 기반 파이프라인 실행 | K8s 네이티브, 스케줄링, UI 제공 |
| 객체 저장소 | Ceph RGW | Latest | Apache 2.0 | S3 호환 원천 데이터 보존 | 분산 파일시스템, PB급 확장, 온프레미스, ELT 패턴 지원 |
| 백엔드 언어 | Python | 3.10+ | PSF | KG 엔진, API, 파이프라인 | 데이터 과학 생태계, 팀 역량 |
| 프론트엔드 언어 | TypeScript | 5.x | Apache 2.0 | Vue 3 컴포넌트 | 타입 안전성, 대규모 유지보수 |
| API 프레임워크 | FastAPI | 0.100+ | MIT | REST API 서버 | async, OpenAPI 자동 생성, 성능 |
| K8s 패키지 관리 | Helm | 3.x | Apache 2.0 | K8s 배포 | values 기반 환경별 배포 |

---

## 9.2 미결정 기술 (벤치마크 예정)

### 후보 비교 및 평가 기준

| 결정 항목 | 후보 A | 후보 B | 결정 기준 | 결정 시점 |
|----------|--------|--------|----------|----------|
| 시계열 DB | TimescaleDB (PostgreSQL 확장) | InfluxDB v3 | AIS 궤적 쿼리 성능, 팀 역량 | Y1 Q2 |
| Vector DB 확장 | Neo4j 내장 벡터 인덱스 | Milvus 2.x | 1M+ 임베딩 스케일, 지연 | Y2 Q1 |
| K8s 배포 도구 | Helm (현재 후보) | Kustomize | 인프라팀 선호도, 환경 복잡도 | Y1 Q1 |
| 기본 LLM 모델 | Qwen2.5 VL 72B | Llama 3.3 70B | 한국어 해사 도메인 30문항 벤치마크 | Y1 Q3 |
| OCR 엔진 | PaddleOCR (현재 사용) | Tesseract 5 | 한국어 해사 문서 정확도 | Y1 Q2 |
| 메시지 큐 | Redis (BullMQ, 현재) | Kafka | 처리량 요구사항, 운영 복잡도 | Y2 |

### 상세 평가 매트릭스

각 미결정 기술에 대해 정량적/정성적 평가 기준을 수립하여 벤치마크를 수행한다.

#### 시계열 DB

| 평가 기준 | TimescaleDB | InfluxDB v3 | 비고 |
|----------|-------------|-------------|------|
| PostgreSQL 호환성 | 완전 호환 (확장 모듈) | 별도 쿼리 언어 (InfluxQL/Flux) | TimescaleDB는 기존 PostgreSQL 인프라 재활용 가능 |
| AIS 궤적 쿼리 성능 | Y1 Q2 벤치마크 예정 | Y1 Q2 벤치마크 예정 | 10M 레코드 기준 범위 쿼리 측정 |
| 운영 복잡도 | 낮음 (PostgreSQL ops 동일) | 중간 (별도 운영 지식 필요) | - |
| 공간 쿼리 지원 | PostGIS 연계 | GeoHash 기반 | 해사 도메인은 공간 쿼리 빈번 |

#### 객체 저장소

| 평가 기준 | Ceph RGW (확정) | MinIO (개발용) | 비고 |
|----------|----------------|---------------|------|
| S3 호환성 | 완전 호환 | 완전 호환 | 양쪽 모두 S3 API 준수 |
| 확장성 | PB급, 분산 파일시스템 | TB~PB급 | Ceph는 KRISO 인프라 표준 |
| 온프레미스 적합성 | 높음 | 높음 | 둘 다 온프레미스 최적화 |
| 용도 | 프로덕션 (Y2~) | 로컬 개발 (Y1) | 개발 시 MinIO로 경량 테스트 |

#### Vector DB

| 평가 기준 | Neo4j 내장 벡터 인덱스 | Milvus 2.x | 비고 |
|----------|---------------------|------------|------|
| 임베딩 차원 지원 | 768-dim (nomic-embed-text) | 2048-dim+ | 현재 768-dim 충분 |
| 검색 성능 (1M 벡터) | Y2 Q1 벤치마크 예정 | Y2 Q1 벤치마크 예정 | ANN 검색 P99 지연 측정 |
| K8s 운영 복잡도 | 없음 (Neo4j에 내장) | 중간 (별도 클러스터) | 내장 벡터는 추가 인프라 불필요 |
| 그래프+벡터 통합 쿼리 | 네이티브 (단일 Cypher) | 별도 조합 필요 | KG+의미검색 통합이 핵심 |

#### GPU 분산 추론

| 평가 기준 | vLLM | Ray Serve | 비고 |
|----------|------|-----------|------|
| 한국어 모델 호환 | Qwen, EXAONE 지원 | 모든 모델 | vLLM은 HuggingFace 모델 직접 로드 |
| 처리량 (tokens/sec) | Continuous Batching | Dynamic Batching | vLLM이 LLM 특화 최적화 우수 |
| 메모리 효율 | PagedAttention | 일반 메모리 관리 | vLLM PagedAttention으로 GPU 메모리 절약 |
| 멀티모델 서빙 | 제한적 | 유연 (여러 모델 동시) | Ray는 이기종 모델 혼합 서빙 강점 |
| 결정 방향 | Y1~Y2 단일 모델 시 선호 | Y3~ 다중 모델 시 전환 검토 | 점진적 전환 전략 |

#### K8s 배포 도구

| 평가 기준 | Helm | Kustomize | 비고 |
|----------|------|-----------|------|
| GitOps 호환 | ArgoCD Helm 지원 | ArgoCD 네이티브 지원 | 양쪽 모두 ArgoCD 통합 가능 |
| 환경별 오버라이드 | values.yaml 파일 | Overlay 디렉토리 | Helm이 단일 파일 관리로 직관적 |
| 학습 곡선 | 중간 (템플릿 문법) | 낮음 (순수 YAML) | - |
| 패키지 공유 | Helm Chart Registry | 없음 | 내부 Chart 재사용 시 Helm 유리 |

#### 메시지 브로커

| 평가 기준 | Redis Streams (BullMQ) | Kafka | 비고 |
|----------|----------------------|-------|------|
| 처리량 | 중간 (~100K msg/sec) | 높음 (~1M msg/sec) | Y1 예상 부하에는 Redis 충분 |
| 운영 복잡도 | 낮음 (기존 Redis 활용) | 높음 (ZooKeeper/KRaft) | Redis는 이미 캐시용으로 운영 중 |
| 메시지 보존 | 제한적 (메모리 기반) | 영구 (디스크 기반) | Kafka는 리플레이 가능 |
| 기존 인프라 활용 | 높음 (Redis 이미 사용) | 별도 클러스터 필요 | Y1은 Redis, Y2~Y3 부하 증가 시 Kafka 검토 |

---

## 9.3 기술 의존성 그래프

```
                           +-------------------+
                           |   Vue 3 + VueFlow  |
                           |   (프론트엔드)      |
                           +--------+----------+
                                    |
                                    v
+-------------+          +-------------------+          +-------------+
| Keycloak    |<-------->|   FastAPI          |<-------->| Prometheus  |
| (OIDC/RBAC) |          |   (API Gateway)   |          | + Grafana   |
+-------------+          +--------+----------+          +-------------+
                                  |
                    +-------------+-------------+
                    |             |             |
                    v             v             v
             +----------+  +---------+  +----------+
             |  Neo4j   |  |  Ceph   |  |  Ollama  |
             |  KG + 벡터|  | 원본저장|  |  vLLM   |
             +----------+  +---------+  +----------+
                    |
                    v
             +------------------+
             |  Argo Workflow   |
             |  (DAG 실행)      |
             +------------------+
                    |
                    v
             +------------------+
             |  Suredata Lab    |
             |  REST API 연동   |
             +------------------+
```

---

## 9.4 연차별 기술 도입 계획

| 기술 | Y1 (2026) | Y2 (2027) | Y3 (2028) | Y4 (2029) | Y5 (2030) |
|------|-----------|-----------|-----------|-----------|-----------|
| Neo4j CE | 도입 + KG 구축 | 성능 튜닝 | 스케일 검토 | EE 전환 검토 | 안정 운영 |
| Kubernetes | 없음 (Compose) | 전환 | 고도화 | 멀티테넌트 | 안정 운영 |
| Keycloak | JWT (임시) | 전환 완료 | MFA 강화 | 외부 IdP 연동 | 안정 운영 |
| Argo Workflow | Activepieces | 전환 완료 | 고도화 | 표준화 | 안정 운영 |
| vLLM | Ollama (CPU) | GPU 전환 | Tensor Parallel | Ray 분산 | 멀티 모델 |
| VueFlow 캔버스 | 기획/설계 | 프로토타입 | MVP | 고도화 | 안정 운영 |
| S-100 해도 | 표준 분석 | 파서 개발 | 렌더러 개발 | 실시간 통합 | 안정 운영 |
| GraphRAG | 없음 | 연구/설계 | 프로토타입 | 통합 | 안정 운영 |

---

## 9.5 라이선스 컴플라이언스

### 확정 기술 라이선스 요약

모든 확정 기술은 오픈소스이며, 정부 R&D 납품에 적합한 라이선스를 보유한다.

| 기술 | 라이선스 | 유형 | 납품 시 제약 | 비고 |
|------|---------|------|------------|------|
| Vue 3 | MIT | Permissive | 없음 | 저작권 고지만 유지 |
| VueFlow | MIT | Permissive | 없음 | - |
| Neo4j CE | GPLv3 | Copyleft | **소스 공개 의무** (서버 사이드) | AGPL이 아니므로 네트워크 서비스는 해당 없음, 배포 시 소스 공개 |
| Protege | BSD | Permissive | 없음 | - |
| n10s (Neosemantics) | Apache 2.0 | Permissive | 없음 | - |
| Keycloak | Apache 2.0 | Permissive | 없음 | - |
| Kubernetes | Apache 2.0 | Permissive | 없음 | - |
| Prometheus | Apache 2.0 | Permissive | 없음 | - |
| Grafana | AGPLv3 | Strong Copyleft | **수정 시 소스 공개 의무** | 수정 없이 사용 시 문제 없음 |
| Zipkin | Apache 2.0 | Permissive | 없음 | - |
| Ray | Apache 2.0 | Permissive | 없음 | - |
| PostgreSQL | PostgreSQL (MIT 유사) | Permissive | 없음 | - |
| Ollama | MIT | Permissive | 없음 | - |
| vLLM | Apache 2.0 | Permissive | 없음 | - |
| Argo Workflow | Apache 2.0 | Permissive | 없음 | - |
| Ceph | LGPL 2.1 / Apache 2.0 | Mixed | 라이브러리 링크 시 LGPL 조건 확인 | RGW는 독립 프로세스로 사용 |
| FastAPI | MIT | Permissive | 없음 | - |
| Helm | Apache 2.0 | Permissive | 없음 | - |

### 정부 R&D 납품 시 확인 사항

1. **GPLv3 (Neo4j CE):** IMSP 플랫폼을 바이너리로 배포하는 경우 소스 코드 공개 의무 발생. 단, SaaS/내부 서비스 형태로 운영 시 배포에 해당하지 않아 의무 없음. KRISO에 납품 시 바이너리 포함 여부 확인 필요.
2. **AGPLv3 (Grafana):** 네트워크 서비스로 제공 시에도 소스 공개 의무. Grafana를 수정 없이 사용하면 OSS 버전 그대로 공개하면 됨. 커스텀 플러그인 개발 시 별도 라이선스 검토 필요.
3. **LLM 모델 라이선스:** 오픈소스 모델(Qwen, Llama 등)은 각각 고유 라이선스 보유. 상업적 사용 가능 여부를 모델별로 확인해야 함.
4. **SBOM (Software Bill of Materials):** 납품 시 전체 오픈소스 구성 요소 목록(SBOM)을 SPDX 또는 CycloneDX 형식으로 제출.

### 라이선스 감사 자동화

```bash
# Python 의존성 라이선스 검사
pip-licenses --format=csv --output-file=licenses.csv

# npm 의존성 라이선스 검사 (프론트엔드)
npx license-checker --csv --out licenses-frontend.csv

# SBOM 생성 (CycloneDX)
cyclonedx-py environment --output sbom.json
```

---

*관련 문서: [08-suredata-integration.md](./08-suredata-integration.md) (Suredata Lab 연동), [10-observability.md](./10-observability.md) (관측성 아키텍처)*
