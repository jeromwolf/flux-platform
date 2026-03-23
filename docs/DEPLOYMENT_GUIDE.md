# IMSP 플랫폼 배포 가이드

IMSP(Interactive Maritime Service Platform)는 해사 도메인을 위한 대화형 서비스 설계 플랫폼입니다. 이 문서는 로컬 개발부터 Kubernetes 프로덕션 배포까지의 전체 과정을 다룹니다.

## 목차

1. [사전 요구사항](#사전-요구사항)
2. [빠른 시작 (로컬 개발)](#빠른-시작-로컬-개발)
3. [Docker Compose 배포](#docker-compose-배포)
4. [Kubernetes 배포](#kubernetes-배포)
5. [환경변수 설정](#환경변수-설정)
6. [서비스 아키텍처](#서비스-아키텍처)
7. [헬스체크 및 모니터링](#헬스체크-및-모니터링)
8. [문제 해결](#문제-해결)

---

## 사전 요구사항

### 개발 환경
- **Docker** 24+ 및 **Docker Compose** v2
- **Python** 3.10+
- **Node.js** 20+
- **git**

### Kubernetes 배포
- **kubectl** 1.24+
- **kustomize** 5.0+ (또는 내장된 `kubectl -k`)
- Kubernetes 클러스터 (1.24+)

### 최소 시스템 요구사항
- **메모리**: 8GB (로컬), 16GB 이상 (프로덕션)
- **디스크**: 20GB 여유 공간
- **네트워크**: 외부 인터넷 접속 필요 (Docker 이미지 다운로드)

---

## 빠른 시작 (로컬 개발)

### 1단계: 저장소 복제 및 환경 설정

```bash
# 저장소 복제
git clone https://github.com/your-org/flux-platform.git
cd flux-platform

# 환경변수 파일 생성
cp .env.example .env

# 보안이 필요한 값 설정 (아래 참조)
# .env 파일을 편집하여 필수값 입력
nano .env
```

필수 설정값:

```bash
# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password_here

# Keycloak
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=your_admin_password

# Activepieces (보안 키 생성 필요)
# openssl rand -hex 16 으로 생성
AP_ENCRYPTION_KEY=your_16_hex_chars
# openssl rand -hex 32 으로 생성
AP_JWT_SECRET=your_32_hex_chars

# 데이터베이스
KC_DB_PASSWORD=postgres
AP_POSTGRES_PASSWORD=postgres
```

### 2단계: 의존성 설치

```bash
# Python + Node.js 의존성 설치
make install

# 또는 수동으로:
pip install -e ".[dev]"
cd ui && npm ci && cd ..
```

### 3단계: 단위 테스트 실행

```bash
# Neo4j 없이 실행 가능한 단위 테스트
make test-unit

# 결과: 2,164 passed, 0 failed
```

### 4단계: 모든 서비스 기동

```bash
# Docker Compose로 전체 스택 시작
make docker-up

# 또는:
docker compose -f infra/docker-compose.yml up -d
```

### 5단계: 서비스 접속

모든 서비스가 헬스체크를 통과할 때까지 30초 정도 기다립니다.

| 서비스 | URL | 설명 |
|--------|-----|------|
| **API** | http://localhost:8000 | REST API (포트 포워딩 불필요) |
| **Gateway** | http://localhost:8080 | 통합 진입점 (인증 + 라우팅) |
| **Neo4j Browser** | http://localhost:7474 | 그래프 브라우저 |
| **Keycloak** | http://localhost:8180 | ID 및 접근 관리 |
| **Activepieces** | http://localhost:8081 | 워크플로우 자동화 |
| **Prometheus** | http://localhost:9090 | 메트릭 수집 |
| **Grafana** | http://localhost:3001 | 모니터링 대시보드 |

**초기 로그인:**
- Keycloak: `admin` / (KEYCLOAK_ADMIN_PASSWORD)
- Grafana: `admin` / (GRAFANA_ADMIN_PASSWORD)
- Neo4j: `neo4j` / (NEO4J_PASSWORD)

### 6단계: 통합 테스트 (선택사항)

```bash
# Neo4j가 실행 중일 때만 가능
make test-integration

# 모든 테스트
make test
```

### 7단계: UI 개발 서버

```bash
# Vue 개발 서버 시작 (Hot-reload)
make ui-dev

# 또는:
cd ui && npm run dev

# 브라우저에서 http://localhost:5180 접속
```

### 서비스 중지

```bash
# 모든 Docker 컨테이너 중지
make docker-down

# 또는:
docker compose -f infra/docker-compose.yml down

# 데이터도 삭제 (주의: 데이터 손실)
docker compose -f infra/docker-compose.yml down -v
```

---

## Docker Compose 배포

### 서비스 구성

IMSP 플랫폼은 10개의 마이크로서비스로 구성됩니다:

```
┌─────────────────────────────────────────┐
│ 클라이언트 (브라우저, CLI)              │
└────────────┬────────────────────────────┘
             │
             ▼
    ┌─────────────────┐
    │  Gateway:8080   │  ◄─ 통합 진입점
    │  (Node.js)      │     - 인증
    └────┬────────────┘     - 라우팅
         │                  - CORS
         ▼
    ┌─────────────────┐
    │   API:8000      │  ◄─ FastAPI
    │  (Python)       │     - Cypher 실행
    └────┬────────────┘     - NL 질의
         │                  - RAG/Agent
         ▼
    ┌─────────────────┐
    │ Neo4j:7687      │  ◄─ 지식 그래프
    │ (Bolt)          │
    └─────────────────┘

    인증:        Keycloak:8180
    워크플로우:  Activepieces:8081
    메트릭:      Prometheus:9090
    대시보드:    Grafana:3001
```

### 주요 서비스 설명

#### Neo4j (포트 7687, 7474)
- **역할**: 지식 그래프 데이터베이스
- **이미지**: `neo4j:5.26.0-community`
- **플러그인**: APOC, Neosemantics (n10s)
- **메모리**: 1GB 힙 + 1GB 페이지 캐시
- **볼륨**: `neo4j_data`, `neo4j_logs`, `neo4j_plugins`, `neo4j_import`
- **헬스체크**: cypher-shell `RETURN 1`

#### API (포트 8000)
- **역할**: 핵심 KG API
- **이미지**: 로컬 빌드 (`infra/docker/Dockerfile.core`)
- **의존성**: Neo4j (healthy)
- **환경**: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, LOG_FORMAT, LOG_LEVEL

#### Gateway (포트 8080)
- **역할**: 통합 진입점
- **이미지**: 로컬 빌드 (`infra/docker/Dockerfile.gateway`)
- **의존성**: API, Keycloak (healthy)
- **기능**: OAuth2 검증, JWT 재발급, 라우팅, CORS

#### Keycloak (포트 8180)
- **역할**: 인증/인가 (OIDC)
- **이미지**: `quay.io/keycloak/keycloak:24.0.1`
- **DB**: PostgreSQL 14.4 (keycloak-db)
- **데이터**: `/opt/keycloak/data/import/realm-imsp.json`

#### Activepieces (포트 8081)
- **역할**: 워크플로우 자동화
- **이미지**: `ghcr.io/activepieces/activepieces:0.78.0`
- **DB**: PostgreSQL 14.4
- **큐**: Redis 7.0.7
- **설정**: `AP_ENCRYPTION_KEY`, `AP_JWT_SECRET` 필수

#### Prometheus (포트 9090)
- **역할**: 메트릭 수집
- **이미지**: `prom/prometheus:v2.51.0`
- **설정**: `infra/prometheus/prometheus.yml`
- **보관 기간**: 30일

#### Grafana (포트 3001)
- **역할**: 모니터링 대시보드
- **이미지**: `grafana/grafana:10.4.0`
- **의존성**: Prometheus
- **설정**: `infra/grafana/provisioning/`

### 볼륨 관리

| 볼륨 | 서비스 | 경로 | 용도 |
|------|--------|------|------|
| `neo4j_data` | Neo4j | `/data` | 그래프 데이터 |
| `neo4j_logs` | Neo4j | `/logs` | 쿼리 로그 |
| `neo4j_plugins` | Neo4j | `/plugins` | APOC, n10s |
| `neo4j_import` | Neo4j | `/import` | 데이터 임포트 |
| `keycloak_db_data` | PostgreSQL | `/var/lib/postgresql/data` | Keycloak DB |
| `postgres_data` | PostgreSQL | `/var/lib/postgresql/data` | Activepieces DB |
| `redis_data` | Redis | `/data` | 작업 큐 |
| `prometheus_data` | Prometheus | `/prometheus` | 메트릭 저장소 |
| `grafana_data` | Grafana | `/var/lib/grafana` | 대시보드 설정 |
| `activepieces_cache` | Activepieces | `/usr/src/app/cache` | 캐시 |

### 기동 순서

Docker Compose는 `depends_on` 조건에 따라 서비스를 순차적으로 기동합니다:

1. **Database Layer** (5s): PostgreSQL (keycloak-db, postgres), Redis
2. **Authentication** (60s): Keycloak (DB 준비 대기)
3. **Core Services** (30s): Neo4j, Activepieces
4. **API** (30s): API (Neo4j healthy 대기)
5. **Gateway** (30s): Gateway (API, Keycloak healthy 대기)
6. **Observability** (30s): Prometheus (API healthy 대기), Grafana

전체 시작 시간: 약 2-3분

### 로그 확인

```bash
# 모든 서비스 로그 실시간 보기
make docker-logs

# 또는:
docker compose -f infra/docker-compose.yml logs -f

# 특정 서비스만:
docker compose -f infra/docker-compose.yml logs -f api
docker compose -f infra/docker-compose.yml logs -f neo4j
docker compose -f infra/docker-compose.yml logs -f gateway
```

### 서비스 상태 확인

```bash
# 컨테이너 상태
docker compose -f infra/docker-compose.yml ps

# 예상 출력:
# NAME                  STATUS         PORTS
# maritime-neo4j        Up (healthy)   7474->7474, 7687->7687
# maritime-api          Up (healthy)   8000->8000
# imsp-gateway          Up (healthy)   8080->8080
# imsp-keycloak         Up (healthy)   8180->8080
# ...
```

---

## Kubernetes 배포

### 전제 조건

- Kubernetes 클러스터 (1.24+)
- `kubectl` 및 `kustomize` 설치
- 프라이빗 이미지 레지스트리 또는 DockerHub 접근

### 네임스페이스 생성

```bash
kubectl create namespace imsp
kubectl config set-context --current --namespace=imsp
```

### 시크릿 생성

```bash
# Keycloak 데이터베이스 자격증명
kubectl create secret generic keycloak-db-secret \
  --from-literal=password=your_secure_postgres_password \
  -n imsp

# Neo4j 자격증명
kubectl create secret generic neo4j-secret \
  --from-literal=password=your_secure_neo4j_password \
  -n imsp

# Activepieces 키
kubectl create secret generic activepieces-secret \
  --from-literal=encryption-key=$(openssl rand -hex 16) \
  --from-literal=jwt-secret=$(openssl rand -hex 32) \
  -n imsp
```

### Dev 환경 배포

```bash
# Dev 환경 배포 (이 명령은 실제 K8s 클러스터가 필요)
# kubectl apply -k infra/k8s/dev/
```

### Prod 환경 배포

```bash
# Prod 환경 배포 (실제 클러스터에만 적용)
# kubectl apply -k infra/k8s/prod/
```

### 배포 상태 확인

```bash
# Pod 상태
kubectl get pods -n imsp
kubectl describe pod <pod-name> -n imsp
kubectl logs <pod-name> -n imsp

# 서비스 확인
kubectl get svc -n imsp

# Ingress 확인
kubectl get ingress -n imsp
```

### 스케일링

```bash
# API 서비스 3개로 확장
kubectl scale deployment api --replicas=3 -n imsp

# 모니터링
kubectl get pods -n imsp --watch
```

---

## 환경변수 설정

### 필수 환경변수

#### Neo4j
| 변수 | 설명 | 기본값 | 보안 |
|------|------|--------|------|
| `NEO4J_USER` | 데이터베이스 사용자 | `neo4j` | - |
| `NEO4J_PASSWORD` | 데이터베이스 비밀번호 | 없음 (필수) | 🔒 반드시 변경 |
| `NEO4J_DATABASE` | 데이터베이스 이름 | `neo4j` | - |

#### Keycloak
| 변수 | 설명 | 기본값 | 보안 |
|------|------|--------|------|
| `KEYCLOAK_ADMIN` | 관리자 사용자명 | `admin` | 🔒 변경 권장 |
| `KEYCLOAK_ADMIN_PASSWORD` | 관리자 비밀번호 | 없음 (필수) | 🔒 반드시 변경 |
| `KC_DB_USERNAME` | Keycloak DB 사용자 | `postgres` | - |
| `KC_DB_PASSWORD` | Keycloak DB 비밀번호 | `postgres` | 🔒 반드시 변경 |
| `KEYCLOAK_REALM` | 영역 이름 | `imsp` | - |
| `KEYCLOAK_CLIENT_ID` | OAuth2 클라이언트 ID | `imsp-api` | - |

#### Activepieces
| 변수 | 설명 | 기본값 | 보안 |
|------|------|--------|------|
| `AP_ENCRYPTION_KEY` | 데이터 암호화 키 (16진수) | 없음 (필수) | 🔒 generate: `openssl rand -hex 16` |
| `AP_JWT_SECRET` | JWT 서명 키 (32진수) | 없음 (필수) | 🔒 generate: `openssl rand -hex 32` |
| `AP_POSTGRES_USERNAME` | DB 사용자 | `postgres` | - |
| `AP_POSTGRES_PASSWORD` | DB 비밀번호 | `postgres` | 🔒 반드시 변경 |
| `AP_FRONTEND_URL` | 프론트엔드 URL | `http://localhost:8081` | - |

#### API & Gateway
| 변수 | 설명 | 기본값 | 보안 |
|------|------|--------|------|
| `ENV` | 배포 환경 | `production` | `development`, `staging`, `production` |
| `LOG_LEVEL` | 로그 수준 | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | 로그 형식 | `json` | `json`, `text` |
| `CORS_ALLOWED_ORIGINS` | CORS 허용 도메인 | `http://localhost:5180,http://localhost:8080` | 🔒 변경 필수 |
| `APP_API_KEY` | API 키 (선택) | 없음 | 🔒 생성 권장 |
| `JWT_SECRET_KEY` | JWT 서명 키 (선택) | 없음 | 🔒 Keycloak 대신 사용 가능 |

#### Grafana
| 변수 | 설명 | 기본값 | 보안 |
|------|------|--------|------|
| `GRAFANA_ADMIN_USER` | 관리자 사용자명 | `admin` | 🔒 변경 권장 |
| `GRAFANA_ADMIN_PASSWORD` | 관리자 비밀번호 | `admin` | 🔒 반드시 변경 |

### 프로덕션 환경 체크리스트

```bash
# .env 파일 보안 검사
cat .env | grep -E 'changeme|admin|postgres|__GENERATE' && echo "⚠️  기본값 발견!" || echo "✓ 환경변수 OK"

# 생성된 키 확인 (빈칸이면 생성 필요)
echo "AP_ENCRYPTION_KEY=$(openssl rand -hex 16)"
echo "AP_JWT_SECRET=$(openssl rand -hex 32)"
```

---

## 서비스 아키텍처

### 데이터 흐름

```
클라이언트 (React)
    │
    ├─ WebSocket (실시간 메시지)
    └─ REST API (HTTPS/TLS)
         │
         ▼
    Gateway (8080)
    ├─ Keycloak 검증
    ├─ JWT 갱신
    └─ 라우팅 & 속도 제한
         │
         ▼
    API (8000)
    ├─ 자연어 처리
    ├─ Cypher 생성/검증
    ├─ RAG 엔진
    └─ Agent 실행
         │
         ▼
    Neo4j (7687)
    ├─ 그래프 저장
    ├─ APOC 프로시저
    └─ 벡터 검색 (n10s)
         │
         ├─ PostgreSQL (메타데이터)
         └─ Redis (캐시)

    부가 시스템:
    - Keycloak: 사용자 관리, 토큰 발급
    - Activepieces: 워크플로우 자동화
    - Prometheus: 메트릭 수집
    - Grafana: 대시보드 & 알림
```

### 포트 매핑

| 포트 | 서비스 | 프로토콜 | 설명 |
|------|--------|---------|------|
| 7474 | Neo4j | HTTP | 브라우저 인터페이스 |
| 7687 | Neo4j | Bolt | Cypher 프로토콜 |
| 8000 | API | HTTP | FastAPI |
| 8080 | Gateway | HTTP | Node.js 라우팅 |
| 8081 | Activepieces | HTTP | 워크플로우 UI |
| 8180 | Keycloak | HTTP | OIDC/OAuth2 |
| 3001 | Grafana | HTTP | 모니터링 대시보드 |
| 9090 | Prometheus | HTTP | 메트릭 엔드포인트 |
| 5432 | PostgreSQL | TCP | DB 프로토콜 (컨테이너만) |
| 6379 | Redis | TCP | 캐시 프로토콜 (컨테이너만) |

### 네트워크 격리 (Docker Compose)

모든 컨테이너는 `bridge` 네트워크로 연결되어 같은 도메인 내 통신:

```bash
# 네트워크 확인
docker network ls | grep flux
docker network inspect flux-platform_default

# 컨테이너 간 통신 예
# api → neo4j: bolt://neo4j:7687
# gateway → api: http://api:8000
```

---

## 헬스체크 및 모니터링

### 기본 헬스체크

각 서비스는 Docker의 `healthcheck` 메커니즘으로 자동 모니터링됩니다.

#### API 헬스체크

```bash
# 간단한 헬스체크
curl http://localhost:8000/api/v1/health

# 응답 예:
{
  "status": "ok",
  "version": "0.1.0",
  "neo4j_connected": true
}
```

#### 심층 헬스체크

```bash
# 컴포넌트별 상세 진단
curl http://localhost:8000/api/v1/health?deep=true

# 응답 예:
{
  "status": "ok",
  "version": "0.1.0",
  "neo4j_connected": true,
  "components": [
    {
      "name": "neo4j",
      "status": "ok",
      "latency_ms": 2.5
    },
    {
      "name": "disk",
      "status": "ok",
      "details": {
        "free_gb": 45.2,
        "free_pct": 68.5
      }
    },
    {
      "name": "memory",
      "status": "ok",
      "details": {
        "available_gb": 6.2,
        "used_pct": 22.3
      }
    }
  ]
}
```

### Prometheus 메트릭

API는 Prometheus 형식의 메트릭을 내보냅니다:

```bash
# 메트릭 엔드포인트
curl http://localhost:8000/metrics

# Prometheus 대시보드
open http://localhost:9090
```

주요 메트릭:
- `http_requests_total` — 요청 수
- `http_request_duration_seconds` — 응답 시간
- `neo4j_query_duration_seconds` — Cypher 실행 시간

### Grafana 대시보드

Grafana는 자동으로 Prometheus 데이터 소스를 구성합니다.

```bash
# 대시보드 접속
open http://localhost:3001

# 로그인
user: admin
password: (GRAFANA_ADMIN_PASSWORD from .env)
```

기본 대시보드:
- **System Health**: CPU, 메모리, 디스크, 네트워크
- **API Performance**: 요청 수, 응답 시간, 에러율
- **Neo4j Status**: 연결 상태, 쿼리 성능

### 로그 스트림

```bash
# 모든 로그 (실시간)
docker compose -f infra/docker-compose.yml logs -f --tail=100

# 특정 서비스
docker compose -f infra/docker-compose.yml logs -f api --tail=50

# 시간 범위
docker compose -f infra/docker-compose.yml logs --since 10m --until 5m

# JSON 로그 필터링 (jq 필요)
docker compose -f infra/docker-compose.yml logs api | jq '.message' -r | head -20
```

---

## 문제 해결

### 일반적인 문제

#### 1. Neo4j 연결 실패

```bash
# 증상: "Connection refused" 또는 "BOLT protocol error"

# 해결:
# 1. Neo4j 컨테이너 상태 확인
docker compose -f infra/docker-compose.yml ps neo4j

# 2. 헬스체크 로그 확인
docker compose -f infra/docker-compose.yml logs neo4j --tail=50

# 3. 포트 확인
lsof -i :7687

# 4. Neo4j 재시작
docker compose -f infra/docker-compose.yml restart neo4j

# 5. 데이터 초기화 (데이터 손실)
docker compose -f infra/docker-compose.yml down -v
make docker-up
```

#### 2. Keycloak 로그인 불가

```bash
# 증상: "Invalid client ID" 또는 "Redirect URI mismatch"

# 해결:
# 1. Keycloak 상태 확인
curl http://localhost:8180/health

# 2. 로그인 페이지 접속
open http://localhost:8180/realms/imsp/account

# 3. realm-imsp.json 검증
cat infra/keycloak/realm-imsp.json | jq '.clients[] | {clientId, redirectUris}'

# 4. Keycloak 재시작
docker compose -f infra/docker-compose.yml restart keycloak
```

#### 3. Gateway 프록시 오류 (502 Bad Gateway)

```bash
# 증상: "Cannot GET /api/v1/health"

# 해결:
# 1. API 서비스 상태
curl http://localhost:8000/api/v1/health

# 2. Gateway 로그 확인
docker compose -f infra/docker-compose.yml logs gateway --tail=50

# 3. 환경변수 확인
docker compose -f infra/docker-compose.yml config | grep -A2 "gateway:"

# 4. 재시작
docker compose -f infra/docker-compose.yml restart gateway
```

#### 4. 메모리 부족 (OOM)

```bash
# 증상: 컨테이너가 갑자기 종료됨

# 확인:
docker stats --no-stream

# Neo4j 메모리 조정 (.env 또는 docker-compose.yml)
NEO4J_server_memory_heap_max__size=2G
NEO4J_server_memory_pagecache_size=2G

# Docker 메모리 할당 증가
# Docker Desktop: Preferences > Resources > Memory
```

#### 5. 디스크 공간 부족

```bash
# 확인:
df -h

# 정리:
docker system prune -a  # 사용하지 않는 이미지 삭제
docker volume prune     # 고아 볼륨 삭제

# 로그 크기 제한 추가 (.env)
LOG_DRIVER=json-file
LOG_MAX_SIZE=10m
LOG_MAX_FILE=3
```

### 성능 최적화

#### Neo4j 쿼리 성능

```bash
# 느린 쿼리 분석 (Neo4j Browser)
open http://localhost:7474

# 쿼리 실행 (EXPLAIN)
EXPLAIN MATCH (n:Vessel) RETURN n LIMIT 10;

# 인덱스 생성
CREATE INDEX vessel_name FOR (n:Vessel) ON (n.name);

# 쿼리 로그 확인
tail -f $(docker inspect --format='{{.LogPath}}' maritime-neo4j)
```

#### API 응답 시간 개선

```bash
# 1. Cypher 쿼리 최적화
# 불필요한 OPTIONAL MATCH 제거
# WHERE 조건을 가능한 빨리 추가

# 2. 캐싱 설정 (향후)
# Redis에 자주 사용하는 쿼리 결과 캐싱

# 3. 연결 풀 증가
# API 환경변수:
NEO4J_POOL_SIZE=50
```

### 로그 분석

```bash
# 에러 로그만 필터링
docker compose -f infra/docker-compose.yml logs api | grep -i error

# 타임스탬프별 로그
docker compose -f infra/docker-compose.yml logs --timestamps api

# 로그 저장
docker compose -f infra/docker-compose.yml logs api > api.log 2>&1
```

### 디버깅 모드

```bash
# 더 상세한 로깅 활성화
LOG_LEVEL=DEBUG docker compose -f infra/docker-compose.yml up api

# Python 디버거 (pdb) 연결
docker attach maritime-api

# Neo4j 로그 레벨 상향
NEO4J_dbms_logs_debug_enabled=true
```

---

## 추가 리소스

- [Neo4j 공식 문서](https://neo4j.com/docs/)
- [Keycloak 배포 가이드](https://www.keycloak.org/documentation)
- [Docker Compose 문법](https://docs.docker.com/compose/compose-file/)
- [Kubernetes 배포 가이드](https://kubernetes.io/docs/concepts/configuration/overview/)

## 지원

문제 발생 시:

1. 로그 확인: `make docker-logs`
2. 헬스체크: `curl http://localhost:8000/api/v1/health?deep=true`
3. 이슈 등록: GitHub Issues에 에러 로그와 함께 보고
