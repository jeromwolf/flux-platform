# 5. 배포 아키텍처 (Kubernetes)

[← 데이터 아키텍처](./04-data-architecture.md) | [다음: 보안 아키텍처 →](./06-security-architecture.md)

## 개요

IMSP 플랫폼의 배포 아키텍처는 **점진적 전환 전략**을 채택한다. 1차년도에는 Docker Compose 기반의 로컬 개발 환경에서 시작하고, 2차년도부터 Helm-managed Kubernetes 클러스터로 마이그레이션한다. 본 문서는 목표 K8s 클러스터 토폴로지, Storage 전략, Helm 차트 구조, CI/CD 파이프라인, GPU 서빙 진화 경로, 그리고 Docker Compose에서 K8s로의 전환 전략을 기술한다.

---

## 5.1 클러스터 토폴로지

1차년도는 Docker Compose 기반 로컬 개발 환경으로 시작하고, 2차년도부터 Helm-managed Kubernetes로
전환한다. 아래는 목표 K8s 클러스터 토폴로지다.

```
KRISO K8s Cluster
|
+-- Namespace: imsp -----------------------------------------------
|   |
|   +-- Deployment: maritime-api (FastAPI)
|   |   +-- Replicas: 2~5 (HPA, CPU threshold 70%)
|   |   +-- Resources: 512Mi~2Gi mem, 0.5~2 CPU
|   |   +-- Probes: /api/health (liveness + readiness)
|   |   +-- ConfigMap: NEO4J_URI, APP_API_KEY, JWT_SECRET
|   |   \-- SecretRef: Vault (DB 패스워드, LLM API 키)
|   |
|   +-- Deployment: maritime-frontend (Vue 3 + VueFlow)
|   |   +-- Replicas: 2~3 (HPA)
|   |   +-- Nginx static serving (gzip, cache-control)
|   |   \-- ConfigMap: API_BASE_URL, KEYCLOAK_URL
|   |
|   +-- StatefulSet: neo4j (Neo4j 5.26 CE)
|   |   +-- Replicas: 1 (CE 단일 인스턴스 제한)
|   |   +-- PVC: 500Gi (StorageClass: ssd-fast)
|   |   +-- Resources: 4~8Gi mem, 2~4 CPU
|   |   +-- Plugins: APOC, n10s (Neosemantics)
|   |   \-- Probes: bolt://7687 TCP check
|   |
|   +-- Deployment: ollama-server (LLM Serving)
|   |   +-- nodeSelector: gpu-type=a100
|   |   +-- tolerations: nvidia.com/gpu NoSchedule
|   |   +-- Resources: 16Gi mem, 4 CPU, 1x nvidia.com/gpu
|   |   +-- InitContainer: model-init (모델 다운로드 및 캐시)
|   |   \-- Volume: nfs-shared (모델 파일 공유)
|   |
|   \-- CronJob: etl-pipelines (7개)
|       +-- papers-crawler     (Sat 02:00 KST)
|       +-- weather-collector  (매 3시간)
|       +-- accident-crawler   (Daily 04:00 KST)
|       +-- facility-sync      (매월 1일)
|       +-- relation-extractor (Mon 05:00 KST)
|       +-- s100-sync          (Wed 06:00 KST)
|       \-- experiment-loader  (Manual trigger, Argo Workflow)
|
|   +-- Istio Sidecar Injection: enabled (2차년도)
|   |   +-- mTLS: STRICT mode
|   |   +-- VirtualService / DestinationRule per service
|
+-- Namespace: monitoring ------------------------------------------------------
|   |
|   +-- Deployment: prometheus
|   |   \-- Scrape targets: maritime-api, neo4j-exporter, node-exporter,
|   |                       kube-state-metrics, ollama-exporter
|   |
|   +-- Deployment: grafana
|   |   \-- Dashboards: K8s health, Neo4j performance, API latency, ETL status
|   |
|   +-- Deployment: alertmanager
|   |   \-- Rules: disk > 80%, P99 > 5s, ETL failure, GPU utilization
|   |
|   +-- DaemonSet: node-exporter
|   +-- Deployment: kube-state-metrics
|   +-- Deployment: neo4j-exporter (neo4j-prometheus-exporter)
|   \-- Deployment: zipkin (분산 추적 수집기)
|
\-- Namespace: auth -------------------------------------------------------------
    |
    \-- Deployment: keycloak
        +-- PostgreSQL backend (별도 PVC 10Gi)
        +-- Realm: imsp
        +-- Clients: imsp-api, imsp-ui, argo-workflow
        \-- Roles: Admin, InternalResearcher, ExternalResearcher, Developer, Public
```

### 코드 매핑

| 아키텍처 구성요소 | 코드베이스 위치 | 비고 |
|-----------------|---------------|------|
| FastAPI 서버 | `core/kg/api/` | API 라우트, 미들웨어, Dependency Injection |
| Docker Compose | `infra/docker-compose.yml` | 1차년도 개발 환경 (5 서비스) |
| Helm 차트 | `infra/k8s/` (예정) | 2차년도 K8s 매니페스트 |
| ETL 파이프라인 | `core/kg/etl/` | CronJob으로 실행될 배치 작업 |
| 모니터링 설정 | `infra/prometheus/` (예정) | Prometheus scrape config, alert rules |

---

## 5.2 Storage Classes

| StorageClass | 용도 | 성능 특성 | 대표 PVC |
|-------------|------|----------|---------|
| `ssd-fast` | Neo4j 데이터, 벡터 인덱스 | IOPS 보장, 지연 < 1ms | 500Gi |
| `hdd-bulk` | S-100 원본, HDF5, OCR 원문 | 대용량, 순차 읽기 최적화 | 2Ti |
| `nfs-shared` | 모델 파일, 공유 설정 | ReadWriteMany, 멀티 Pod 공유 | 100Gi |

Neo4j Community Edition은 단일 인스턴스 제한으로 읽기 복제본(Read Replica)을 지원하지 않는다.
고가용성 요구가 발생하면 Enterprise Edition으로 업그레이드하거나 Neo4j Aura 검토가 필요하다.

---

## 5.3 Helm 차트 구조

```
helm/imsp/
|-- Chart.yaml                    # 차트 메타데이터 (버전, 의존성)
|-- values.yaml                   # 기본값 (전체 환경 공통)
|-- values-dev.yaml               # 개발: 샘플 데이터, GPU 미사용
|-- values-staging.yaml           # 스테이징: 운영 데이터 복사본
|-- values-prod.yaml              # 운영: A100 GPU, 실 데이터
|-- values-kriso.yaml             # KRISO 인프라 전용 오버라이드
\-- templates/
    |-- neo4j/
    |   |-- statefulset.yaml      # Neo4j StatefulSet + PVC claim
    |   |-- service.yaml          # Bolt 7687 + HTTP 7474
    |   |-- configmap.yaml        # neo4j.conf 커스텀 설정
    |   \-- pvc.yaml              # 데이터 볼륨 선언
    |-- api/
    |   |-- deployment.yaml       # FastAPI Deployment
    |   |-- hpa.yaml              # CPU 70% 기반 오토스케일링
    |   \-- configmap.yaml        # 환경변수 및 앱 설정
    |-- ollama/
    |   |-- deployment.yaml       # GPU Deployment + InitContainer
    |   \-- service.yaml          # 11434 포트 (내부 통신만)
    |-- etl/
    |   \-- cronjobs.yaml         # 7개 CronJob 정의 (스케줄/리소스 포함)
    |-- monitoring/
    |   |-- prometheus.yaml       # Prometheus + ServiceMonitor CRD
    |   \-- grafana.yaml          # 대시보드 ConfigMap (JSON)
    |-- ingress.yaml              # Kong/Nginx Ingress + TLS 설정
    |-- networkpolicy.yaml        # Pod 간 통신 제어 (최소 권한)
    \-- external-secrets.yaml     # External Secrets Operator (Vault 연동)
```

배포 명령:

```bash
# KRISO 환경 최초 설치
helm install maritime . -f values-kriso.yaml --namespace imsp

# 업그레이드 (새 이미지 태그 배포)
helm upgrade maritime . -f values-kriso.yaml --set api.image.tag=1.2.3

# 롤백
helm rollback maritime 2
```

---

## 5.4 CI/CD 파이프라인

```
+---- CI (GitLab CI) ---------------------------------------------------------+
|                                                                               |
|  +------+  +----------+  +-------------+  +------------+  +------+  +-----+ |
|  | Lint |->|Unit Tests|->|Integration  |->|Docker Build|->| Helm |->|Trivy| |
|  | ruff |  | pytest   |  | Tests       |  | multi-stage|  | Lint |  | CVE | |
|  | mypy |  | 1,095+건 |  | Neo4j Pod   |  | Python3.11 |  | Test |  |Scan | |
|  +------+  +----------+  +-------------+  +------------+  +------+  +--+--+ |
|                                                                        |      |
|                                                              +---------v----+ |
|                                                              |GitLab Registry| |
|                                                              |Push           | |
|                                                              |(KRISO 내부)   | |
|                                                              +---------------+ |
+-------------------------------------------------------------------------------+

+---- CD (ArgoCD / GitOps) ----------------------------------------------------+
|                                                                               |
|  +----------+      +----------+      +---------------------+                 |
|  |   dev    |      | staging  |      |        prod         |                 |
|  |          |      |          |      |                     |                 |
|  | 자동배포  +----->| 수동     +----->| PM 승인 게이트       |                 |
|  | (main)   |      | 프로모션  |      | (approval required) |                 |
|  | 샘플데이터|      | (dev lead|      | 실 데이터, A100 GPU  |                 |
|  | GPU 없음  |      |  승인)   |      |                     |                 |
|  +----------+      +----------+      +---------------------+                 |
|                                                                               |
|  Rollback: ArgoCD 헬스체크 실패 시 자동 롤백 (5분 이내)                       |
|  GitOps: Helm values 변경 -> Git commit -> ArgoCD 자동 동기화                 |
+-------------------------------------------------------------------------------+
```

### GitLab CI 파이프라인 상세 (`gitlab-ci.yml`)

아래는 1차년도부터 적용할 CI/CD 파이프라인의 상세 단계(stage)이다. 1차년도에는 `deploy-dev`까지만 활성화하고, 2차년도 K8s 전환 시 `deploy-staging` 이후 단계를 추가한다.

```yaml
stages:
  - lint          # ruff (코드 스타일), mypy (타입 검사)
  - test          # pytest -m unit (Neo4j 불필요, 순수 로직 테스트)
  - build         # Docker multi-stage build (Python 3.11-slim 기반)
  - scan          # Trivy CVE scan (CRITICAL 발견 시 파이프라인 실패)
  - push          # GitLab Container Registry push (KRISO 내부망)
  - deploy-dev    # docker-compose up -d (Y1, 개발 서버 자동 배포)
  - deploy-staging  # kubectl apply / helm upgrade (Y2~ K8s 전환 후)
```

**각 단계 설명:**

| Stage | 도구 | 실패 조건 | Y1 활성화 |
|-------|------|----------|----------|
| `lint` | `ruff check .` + `mypy --strict core/` | 경고 0 정책 (ruff), 타입 오류 (mypy) | O |
| `test` | `pytest tests/ -m unit -v` | 테스트 실패 또는 커버리지 < 80% | O |
| `build` | `docker build --target production` | 빌드 오류 | O |
| `scan` | `trivy image --severity CRITICAL` | CRITICAL CVE 발견 | O |
| `push` | `docker push registry.kriso.re.kr/imsp/...` | 레지스트리 접근 실패 | O |
| `deploy-dev` | `docker-compose -f infra/docker-compose.yml up -d` | 헬스체크 실패 | O |
| `deploy-staging` | `helm upgrade maritime ...` | K8s apply 실패 | X (Y2~) |

**브랜치 전략:**

| 브랜치 | 환경 | 배포 방식 | 승인 |
|--------|------|----------|------|
| `feature/*` | 없음 | PR 빌드만 | 자동 |
| `develop` | dev | 자동 배포 | 없음 |
| `main` | staging | 수동 프로모션 | Dev Lead |
| `release/*` | prod | 수동 프로모션 | PM + Dev Lead |

---

## 5.5 GPU 서빙 진화 경로

| Phase | 시기 | 서빙 엔진 | GPU | 처리량 | 비고 |
|-------|------|-----------|-----|--------|------|
| Phase 0 | Y1 | Ollama (CPU) | 없음 | ~5 req/min | GPU 조달 대기, 프로토타입 |
| Phase 1 | Y2 Q1-Q2 | Ollama | 1x A100 80G | ~30 req/min | 기본 서빙, 단일 요청 |
| Phase 2 | Y2 Q3 | vLLM | 1x A100 80G | ~100 req/min | Continuous Batching |
| Phase 3 | Y2 Q4 | vLLM + TP | 2x A100 80G | ~200 req/min | Tensor Parallelism |
| Phase 4 | Y3 | Ray + vLLM | A100/H200 클러스터 | ~500+ req/min | 분산 추론, 멀티 모델 |

---

## 5.6 Docker Compose -> K8s 전환 전략

### 현재 (1차년도): Docker Compose 5 서비스

```
infra/docker-compose.yml
+-- maritime-neo4j        (Neo4j 5.26 CE + APOC + n10s)
+-- maritime-api          (FastAPI/uvicorn, hot-reload)
+-- maritime-activepieces (워크플로우 -> Argo 전환 예정)
+-- maritime-postgres     (Activepieces 백엔드 + 로컬 DW)
\-- maritime-redis        (BullMQ 잡 큐, 세션 캐시)
```

### 목표 (2차년도): Helm-managed K8s

- 아키텍처 변경 없이 배포 환경만 마이그레이션 (Lift & Shift)
- 12-Factor App 준수: 환경변수 외부화, Stateless API 서버
- Named Volume -> PVC 전환 (ssd-fast 스토리지 클래스 적용)
- docker-compose.yml 로컬 개발 환경으로 유지 (개발자 DX 보존)

---

## 5.7 1차년도 배포 전략

1차년도(Y1, 2026)는 **Docker Compose 기반 개발 환경**에서 플랫폼의 핵심 컴포넌트를 개발하고 검증하는 단계이다. K8s 전환은 2차년도에 수행하며, 1차년도에는 12-Factor App 원칙을 준수하여 전환 비용을 최소화한다.

### docker-compose.yml 현재 상태

`infra/docker-compose.yml`에 정의된 5개 서비스의 현재 구성:

| 서비스 | 이미지 | 포트 | 역할 |
|--------|--------|------|------|
| `neo4j` | `neo4j:5.26.0-community` | 7474 (Browser), 7687 (Bolt) | 지식그래프 DB, APOC + n10s 플러그인 |
| `api` | 로컬 빌드 (`infra/Dockerfile`) | 8000 | FastAPI REST API (uvicorn) |
| `activepieces` | `ghcr.io/activepieces/activepieces:0.78.0` | 8080 | 워크플로우 자동화 (Argo 전환 예정) |
| `postgres` | `postgres:14.4` | - (내부) | Activepieces 메타데이터 + 로컬 DW |
| `redis` | `redis:7.0.7` | - (내부) | BullMQ 잡 큐, 세션 캐시 |

**Neo4j 설정 상세:**
- 메모리: Heap 1G + PageCache 1G (개발 환경 기준, 운영 시 4~8G로 확장)
- 플러그인: APOC (그래프 알고리즘), n10s/Neosemantics (OWL 통합)
- 보안: `NEO4J_PASSWORD` 환경변수 필수 (`.env` 파일 관리)
- 볼륨: `neo4j_data`, `neo4j_logs`, `neo4j_plugins`, `neo4j_import` (Named Volume)

**API 서버 설정:**
- Neo4j 의존성: `service_healthy` 조건 (cypher-shell RETURN 1 헬스체크 통과 후 기동)
- 인증: `APP_API_KEY` (API Key) + `JWT_SECRET_KEY` (JWT HS256)
- CORS: `CORS_ALLOWED_ORIGINS` (기본값 `http://localhost:3000`)
- 로그: 구조화 JSON 출력 (`LOG_FORMAT=json`)

### Y1 배포 워크플로우

```
개발자 로컬 환경
    |
    v  git push -> GitLab CI
    |
    +-- lint (ruff + mypy)
    +-- test (pytest -m unit)
    +-- build (Docker image)
    +-- scan (Trivy CVE)
    +-- push (GitLab Registry)
    |
    v  개발 서버 (KRISO 내부망)
    |
    +-- docker-compose pull
    +-- docker-compose up -d
    +-- healthcheck 확인 (/api/health)
    \-- Slack/이메일 알림 (성공/실패)
```

### Y2 K8s 전환 마이그레이션 체크리스트

2차년도 K8s 전환 시 아래 항목을 순차적으로 수행한다:

| # | 항목 | 상세 | 우선순위 |
|---|------|------|---------|
| 1 | **환경변수 외부화 검증** | 모든 설정이 환경변수/ConfigMap으로 주입 가능한지 확인. 하드코딩된 경로, URL 제거 | P0 |
| 2 | **Stateless API 검증** | API 서버에 로컬 상태(파일, 세션)가 없는지 확인. 공유 상태는 Redis/Neo4j로 이관 | P0 |
| 3 | **Named Volume -> PVC 매핑** | `neo4j_data` -> PVC(ssd-fast, 500Gi), `postgres_data` -> PVC(ssd-fast, 10Gi) | P0 |
| 4 | **Helm 차트 작성** | 5.3 구조에 따라 templates 작성, values-dev/staging/prod/kriso 분리 | P0 |
| 5 | **Healthcheck -> Probe 전환** | docker-compose `healthcheck` -> K8s `livenessProbe` + `readinessProbe` | P1 |
| 6 | **Secret 관리 체계 구축** | `.env` 파일 -> External Secrets Operator + HashiCorp Vault 연동 | P1 |
| 7 | **Activepieces -> Argo Workflow 전환** | 워크플로우 정의 마이그레이션, VueFlow -> Argo DAG 변환기 개발 | P1 |
| 8 | **Ingress 설정** | Kong/Nginx Ingress Controller, TLS 인증서 (cert-manager), 도메인 설정 | P1 |
| 9 | **NetworkPolicy 적용** | Neo4j Bolt 포트(7687) 접근 제한, 서비스 간 최소 권한 네트워크 정책 | P2 |
| 10 | **Monitoring Stack 배포** | Prometheus + Grafana + AlertManager, ServiceMonitor CRD 설정 | P2 |
| 11 | **Istio Service Mesh 도입** | mTLS 자동 적용, VirtualService/DestinationRule, 트래픽 분배 | P2 |
| 12 | **ArgoCD GitOps 설정** | Git 저장소 연동, 자동 동기화 정책, 롤백 전략 | P2 |

---

## 5.8 Dockerfile 현황

현재 `infra/Dockerfile`은 단일 API 서비스용으로 작성되어 있으며, 모노레포 레이아웃에 맞게 업데이트가 필요하다.

### 현재 문제점

| 문제 | 설명 | 영향 |
|------|------|------|
| 빌드 컨텍스트 | `infra/` 디렉토리를 컨텍스트로 사용 | `core/`, `domains/` 등 상위 디렉토리 파일 접근 불가 |
| PYTHONPATH | 모노레포 구조의 패키지 경로 미반영 | import 실패 가능 (`from core.kg.api import app`) |
| 멀티 타겟 미지원 | 단일 타겟 빌드 | dev/test/production 분리 불가 |

### 개선 방향

```dockerfile
# 목표: 프로젝트 루트를 빌드 컨텍스트로 사용하는 multi-stage Dockerfile
# 위치: Dockerfile.core (프로젝트 루트)

# Stage 1: 의존성 설치
FROM python:3.11-slim AS deps
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[api]"

# Stage 2: 테스트 (CI에서 사용)
FROM deps AS test
COPY core/ ./core/
COPY domains/ ./domains/
COPY tests/ ./tests/
RUN pytest tests/ -m unit -v

# Stage 3: 프로덕션
FROM deps AS production
COPY core/ ./core/
COPY domains/ ./domains/
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "core.kg.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
```

**빌드 명령:**

```bash
# 프로덕션 이미지 빌드 (프로젝트 루트에서 실행)
docker build --target production -t imsp-api:latest -f Dockerfile.core .

# 테스트 실행
docker build --target test -t imsp-api:test -f Dockerfile.core .
```

---

## 5.9 설정 관리 (12-Factor App)

### 설정 소스 우선순위

| 우선순위 | 소스 | 환경 | 예시 |
|----------|------|------|------|
| 1 (최고) | 환경변수 | 전체 | `NEO4J_URI`, `JWT_SECRET_KEY` |
| 2 | ConfigMap | K8s (Y2+) | API 설정, 로그 레벨 |
| 3 | Secret/Vault | K8s (Y2+) | DB 비밀번호, API 키 |
| 4 | `.env` 파일 | 로컬 개발 | `python-dotenv` 로드 |
| 5 (최저) | 코드 기본값 | 전체 | `config.py` 하드코딩 |

### 설정 키 목록

| 키 | 필수 | 기본값 | 설명 |
|----|------|--------|------|
| `NEO4J_URI` | Y | `bolt://localhost:7687` | Neo4j 연결 URI |
| `NEO4J_USER` | Y | `neo4j` | Neo4j 사용자 |
| `NEO4J_PASSWORD` | Y | - | Neo4j 비밀번호 |
| `NEO4J_DATABASE` | N | `neo4j` | Neo4j 데이터베이스명 |
| `JWT_SECRET_KEY` | Y (prod) | - | JWT 서명 키 (HS256) |
| `JWT_ALGORITHM` | N | `HS256` | JWT 알고리즘 |
| `JWT_ISSUER` | N | - | JWT 발급자 |
| `APP_API_KEY` | N | - | API Key 인증용 |
| `CORS_ALLOWED_ORIGINS` | N | `*` | CORS 허용 도메인 |
| `LOG_LEVEL` | N | `INFO` | 로그 레벨 |
| `LOG_FORMAT` | N | `json` | 로그 포맷 (`json`/`text`) |
| `PROJECT_NAME` | N | `Maritime KG` | 프로젝트명 |
| `ENV` | N | `development` | 실행 환경 (`development`/`production`) |

### 설정 검증

```python
# config.py 시작 시 필수 설정 검증
def validate_config(config: AppConfig) -> None:
    if config.env == "production":
        assert config.jwt_secret_key, "JWT_SECRET_KEY required in production"
        assert config.neo4j_password, "NEO4J_PASSWORD required in production"
```

### 시크릿 로테이션 (Y2+)

- HashiCorp Vault Agent Injector로 자동 주입
- JWT 키 로테이션: 30일 주기, 이전 키 7일 유효
- DB 비밀번호 로테이션: 90일 주기

---

## 5.10 헬스체크 프로브 설계

### Y1 (Docker Compose)

| 서비스 | 프로브 | 검사 대상 | 간격 | 타임아웃 |
|--------|--------|----------|------|----------|
| Neo4j | TCP | `bolt://7687` | 30s | 10s |
| API | HTTP | `GET /api/v1/health` | 15s | 5s |
| Redis | TCP | `:6379` | 30s | 5s |
| PostgreSQL | TCP | `:5432` | 30s | 5s |

### Y2+ (Kubernetes)

```yaml
# Startup Probe (느린 초기화 서비스용)
startupProbe:
  httpGet:
    path: /api/v1/health
    port: 8000
  failureThreshold: 30    # 최대 5분 대기 (30 x 10s)
  periodSeconds: 10

# Liveness Probe (자가 진단)
livenessProbe:
  httpGet:
    path: /api/v1/health
    port: 8000
  initialDelaySeconds: 0
  periodSeconds: 15
  timeoutSeconds: 5
  failureThreshold: 3

# Readiness Probe (트래픽 수신 준비)
readinessProbe:
  httpGet:
    path: /api/v1/health?deep=true
    port: 8000
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 2
```

> **Deep Health Check**: `?deep=true` 파라미터 시 Neo4j 연결, Redis 연결, 디스크 공간을 추가 검사

### Graceful Shutdown

```yaml
spec:
  terminationGracePeriodSeconds: 60
  containers:
  - lifecycle:
      preStop:
        exec:
          command: ["/bin/sh", "-c", "sleep 5"]  # LB 반영 대기
```

1. SIGTERM 수신 → 새 요청 수신 중단
2. preStop 훅: 5초 대기 (로드밸런서 반영)
3. 진행 중 요청 완료 대기 (최대 55초)
4. Neo4j/Redis 연결 풀 정리
5. 프로세스 종료

---

## 5.11 백업 및 재해 복구

### 백업 대상 및 전략

| 대상 | 방법 | 주기 | 보관 | RPO |
|------|------|------|------|-----|
| Neo4j | `neo4j-admin database dump` | 일 1회 (Y1), 6시간 (Y3+) | 30일 | < 24h (Y1), < 1h (Y3+) |
| PostgreSQL | `pg_dump` | 일 1회 | 30일 | < 24h |
| Object Storage | Ceph 자체 복제 (replica=3) | 실시간 | - | 0 (Y2+) |
| Redis | RDB 스냅샷 + AOF | 15분/실시간 | 7일 | < 15min |
| 설정/코드 | Git (GitLab) | 실시간 | 무제한 | 0 |

### Y1 백업 스크립트

```bash
#!/bin/bash
# infra/scripts/backup.sh
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups/${TIMESTAMP}
mkdir -p ${BACKUP_DIR}

# Neo4j dump
docker exec maritime-neo4j neo4j-admin database dump neo4j --to-path=/backups/
mv /backups/neo4j.dump ${BACKUP_DIR}/

# PostgreSQL dump
docker exec maritime-postgres pg_dump -U postgres activepieces > ${BACKUP_DIR}/postgres.sql

# 30일 이상 백업 삭제
find /backups -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;
```

### 복구 절차 (RTO 목표: Y1 < 30분)

1. 서비스 중단: `docker compose down`
2. Neo4j 복구: `neo4j-admin database load neo4j --from-path=/backups/latest/`
3. PostgreSQL 복구: `psql -U postgres < /backups/latest/postgres.sql`
4. 서비스 재시작: `docker compose up -d`
5. 데이터 정합성 검증: `/api/v1/health?deep=true` 확인

### Y3+ DR 아키텍처

- **Active-Passive**: Primary(KRISO IDC) + Standby(클라우드 DR)
- Ceph RGW 교차 복제, Neo4j Fabric 기반 원격 동기화
- RTO < 5분, RPO < 5분

---

## 관련 문서

| 문서 | 설명 |
|------|------|
| [보안 아키텍처](./06-security-architecture.md) | Keycloak, RBAC, 네트워크 보안 |
| [데이터 흐름도](./07-data-flow.md) | Text2Cypher, ELT, 워크플로우 실행 흐름 |
| [기술 스택](./09-tech-stack.md) | 전체 기술 스택 매트릭스 |
| [관측성 아키텍처](./10-observability.md) | Prometheus, Grafana, Zipkin 상세 |
| [연차별 로드맵](./13-roadmap.md) | Y1-Y5 아키텍처 진화 계획 |
