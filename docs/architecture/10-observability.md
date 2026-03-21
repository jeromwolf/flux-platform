# 10. 관측성 아키텍처 (Observability)

[← 기술 스택](./09-tech-stack.md) | [다음: AI/LLM 아키텍처 →](./11-ai-llm.md)

## 개요

관측성은 단순한 로그 수집을 넘어 플랫폼 전반의 상태를 실시간으로 파악하고
이상 징후를 선제적으로 감지하는 것을 목표로 한다. Prometheus(메트릭),
Zipkin(분산 추적), 구조화 JSON 로그(감사/운영)의 세 축이 Grafana를
허브로 통합된다. 연차별로 도구를 고도화하되, Y1에는 최소 비용으로
핵심 가시성을 확보하고 Y3 이후 엔터프라이즈급 관측성을 구축한다.

---

## 10.1 3대 관측 축

```
┌─────────────────────────────────────────────────────────────┐
│                    Observability 3 Pillars                    │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   Metrics   │  │    Traces    │  │       Logs         │  │
│  │ (Prometheus)│  │   (Zipkin)   │  │ (JSON structured)  │  │
│  │             │  │              │  │                    │  │
│  │ • API 응답시간│ │ • 요청 추적   │  │ • 구조화된 로그     │  │
│  │ • Neo4j 성능 │ │ • 서비스 간   │  │ • 에러 스택트레이스  │  │
│  │ • K8s 리소스 │ │   호출 체인   │  │ • ETL 실행 이력     │  │
│  │ • ETL 처리량 │ │ • 지연 분석   │  │ • 인증 감사         │  │
│  │ • GPU 사용률 │ │              │  │                    │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│             │              │                │                │
│             ▼              ▼                ▼                │
│       ┌─────────────────────────────────────────────┐       │
│       │              Grafana Dashboard               │       │
│       │  K8s Health │ Neo4j │ API │ ETL │ Text2Cypher│       │
│       └─────────────────────────────────────────────┘       │
│                           │                                  │
│                           ▼                                  │
│                    AlertManager                              │
│                    (Slack / Email 알림)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 10.2 메트릭 수집 (Prometheus)

### Scrape Target 목록

| Target | 주요 메트릭 | 수집 주기 |
|--------|-----------|----------|
| maritime-api | API 요청 수, 응답 시간, 에러율 | 15s |
| neo4j-exporter | 트랜잭션 수, 쿼리 지연, 캐시 히트율, 볼륨 사용량 | 30s |
| node-exporter | CPU, 메모리, 디스크 I/O, 네트워크 | 15s |
| kube-state-metrics | Pod 상태, HPA 메트릭, CronJob 성공/실패 | 30s |
| ollama-server | GPU 사용률, 추론 지연, 모델 메모리 | 30s |

### 커스텀 API 메트릭 (MetricsMiddleware 자동 기록)

```
# API 요청 카운터/지연/활성 요청
maritime_api_requests_total{method, path, status}
maritime_api_request_duration_seconds{method, path}
maritime_api_active_requests

# Text2Cypher 품질
maritime_text2cypher_accuracy{confidence_bucket}

# ETL 파이프라인 처리량
maritime_etl_records_processed_total{pipeline}
maritime_etl_records_failed_total{pipeline}

# KG 규모 추이
maritime_kg_nodes_total
maritime_kg_relationships_total
```

> **NOTE: 메트릭 네이밍 마이그레이션 계획**
>
> 현재 구현체(`core/kg/api/middleware/metrics.py`)는 범용 `http_*` 접두사를 사용한다:
> `http_requests_total`, `http_request_duration_seconds`, `http_requests_active`, `http_errors_total`.
>
> - **Y2 마이그레이션:** 멀티 서비스 배포 시 네임스페이스 격리를 위해 `imsp_*` 접두사로 일괄 변경 예정
>   (예: `imsp_api_requests_total`, `imsp_api_request_duration_seconds`)
> - **Y1 Q3 도입 예정 (도메인 메트릭):** `imsp_text2cypher_accuracy`, `imsp_etl_records_processed_total`, `imsp_kg_nodes_total` 등 도메인 특화 메트릭 추가
> - 위 문서의 `maritime_*` 메트릭명은 최종 목표 네이밍이며, 실제 코드와 차이가 있을 수 있음

### Prometheus 설정 예시 (`infra/prometheus/prometheus.yml`)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  - job_name: maritime-api
    static_configs:
      - targets: ["maritime-api:8000"]
    metrics_path: /metrics

  - job_name: neo4j
    static_configs:
      - targets: ["neo4j-exporter:9474"]
    scrape_interval: 30s

  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: "true"
```

---

## 10.3 분산 추적 (Zipkin)

요청 흐름 추적 경로:

```
Browser
  │
  ▼
API Gateway  ─── [Span: gateway]
  │
  ├──► TextToCypherPipeline  ─── [Span: text2cypher]
  │         │
  │         ├──► NLParser          [Span: nlp.parse]
  │         ├──► QueryGenerator    [Span: query.generate]
  │         ├──► CypherValidator   [Span: cypher.validate]
  │         ├──► CypherCorrector   [Span: cypher.correct]
  │         ├──► HallucinationDet  [Span: hallucination.detect]
  │         └──► Neo4j Execute     [Span: neo4j.execute]
  │
  ├──► ETL Pipeline  ─── [Span: etl]
  │         │
  │         ├──► Object Storage Fetch [Span: s3.fetch]
  │         ├──► Transform          [Span: etl.transform]
  │         └──► Neo4j BatchLoad    [Span: neo4j.batch_load]
  │
  └──► Agent Runtime  ─── [Span: agent]
            │
            ├──► LLM Inference      [Span: llm.infer]
            └──► Neo4j Query        [Span: neo4j.query]
```

각 Span에 `trace_id`, `span_id`, `parent_span_id`, 시작/종료 타임스탬프,
태그(`db.type=neo4j`, `llm.model=qwen2.5-vl-7b` 등)가 기록된다.
P99 지연이 임계치를 초과하면 Zipkin UI에서 병목 Span을 즉시 식별 가능하다.

---

## 10.4 Grafana 대시보드 (5개)

| 대시보드 | 주요 패널 | 갱신 주기 |
|---------|----------|----------|
| K8s Cluster Health | CPU/메모리 사용률, Pod 상태, HPA 활동, 노드 Ready 여부 | 30s |
| Neo4j Performance | 쿼리 지연 P50/P95/P99, 트랜잭션 수, 캐시 히트율, 볼륨 사용량 | 30s |
| API Monitoring | 요청 수, 응답 시간, 에러율, 엔드포인트별 트래픽, DLQ 크기 | 15s |
| ETL Pipeline | 파이프라인별 처리량, 실패율, 마지막 실행 시간, 누적 레코드 | 1m |
| Text2Cypher Quality | 정확도 분포, 검증 통과율, 교정 빈도, 환각 감지율, 신뢰도 히스토그램 | 5m |

모든 대시보드는 `infra/prometheus/grafana/` 아래 JSON으로 관리되며
ArgoCD가 배포 시 자동 import한다.

---

## 10.5 알림 규칙 (AlertManager)

| 규칙 이름 | 조건 | 심각도 | 알림 채널 |
|----------|------|--------|----------|
| Neo4jDiskHigh | 사용률 > 80% (5분간) | WARNING | Slack #ops |
| Neo4jDiskCritical | 사용률 > 90% (5분간) | CRITICAL | Slack #ops + Email |
| APILatencyHigh | P99 응답 > 5s (5분간) | WARNING | Slack #ops |
| APIErrorRateHigh | 5xx 비율 > 5% (5분간) | CRITICAL | Slack #ops + Email |
| ETLPipelineFailed | 연속 3회 실패 | WARNING | Slack #etl |
| GPUUtilizationHigh | GPU 사용률 > 95% (10분간) | WARNING | Slack #ml |
| PodRestartLoop | Pod 재시작 > 3회 (1시간) | WARNING | Slack #ops |
| CronJobMissed | 스케줄 미실행 (지연 > 1시간) | WARNING | Slack #etl |
| KGNodeGrowthStall | KG 노드 증가 없음 (24시간) | INFO | Slack #data |

### AlertManager 라우팅 설정

```yaml
route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: slack-default
  routes:
    - match:
        severity: critical
      receiver: pagerduty-critical
    - match:
        team: etl
      receiver: slack-etl

receivers:
  - name: slack-default
    slack_configs:
      - api_url: "${SLACK_WEBHOOK_URL}"
        channel: "#ops"
        title: "[{{ .Status | toUpper }}] {{ .GroupLabels.alertname }}"
  - name: pagerduty-critical
    pagerduty_configs:
      - routing_key: "${PAGERDUTY_KEY}"
```

---

## 10.6 로그 아키텍처

구조화 로그(Structured Logging)를 통해 메트릭/추적과 상관관계를 연결하고,
장애 분석 시 빠른 원인 추적을 가능하게 한다.

### 로그 포맷 표준

모든 서비스는 JSON 구조화 로그를 표준으로 사용한다. `trace_id`/`span_id`를 포함하여
Zipkin 추적과 로그를 연결할 수 있다.

```json
{
  "timestamp": "2026-03-20T10:30:00Z",
  "level": "INFO",
  "service": "kg-api",
  "trace_id": "abc123def456",
  "span_id": "789ghi012",
  "message": "Query executed",
  "duration_ms": 150,
  "user_id": "user-1",
  "query_type": "text2cypher",
  "extra": {
    "cypher_length": 120,
    "result_count": 15,
    "confidence": 0.92
  }
}
```

### 로그 레벨 가이드라인

| 레벨 | 용도 | 예시 |
|------|------|------|
| `ERROR` | 요청 실패, 예외 발생 | Cypher 실행 실패, LLM Provider 타임아웃 |
| `WARN` | 비정상이나 처리 가능한 상황 | 환각 감지 임계값 근접, 캐시 미스율 높음 |
| `INFO` | 정상 비즈니스 이벤트 | 쿼리 실행 완료, ETL 배치 시작/종료 |
| `DEBUG` | 개발/디버깅용 상세 정보 | Cypher 생성 중간 결과, NLP 파싱 토큰 |

### 연차별 로그 수집 인프라

#### Y1: 파일 기반 로그 수집 (경량)

```
서비스 컨테이너
  │ stdout/stderr (JSON)
  ▼
Docker Log Driver (json-file)
  │
  ▼
호스트 파일시스템 (/var/log/imsp/)
  │
  ▼
Grafana (Loki Explore, 선택적)
```

- Docker 기본 json-file 드라이버로 수집
- 로그 로테이션: 100MB x 5 파일 (Docker 설정)
- 검색: `docker logs --since` 또는 `jq` 활용
- 비용: 추가 인프라 불필요

#### Y2~Y3: EFK/Loki 스택 (확장)

```
서비스 컨테이너
  │ stdout/stderr (JSON)
  ▼
Fluent Bit (DaemonSet)
  │ 파싱, 필터링, 라우팅
  ├──► Loki (or Elasticsearch)
  │      │
  │      ▼
  │    Grafana (Explore / LogQL)
  │
  └──► Object Storage (Cold Archive)
       Ceph RGW / S3
```

| 옵션 | Loki + Grafana | Elasticsearch + Kibana (EFK) | 비고 |
|------|---------------|------------------------------|------|
| 리소스 사용 | 낮음 | 높음 (JVM 기반) | Loki는 인덱스 없이 레이블 기반 |
| 쿼리 언어 | LogQL | KQL / Lucene | LogQL은 PromQL과 유사 |
| Grafana 통합 | 네이티브 | 플러그인 | Loki는 Grafana 동일 생태계 |
| 전문 검색 | 제한적 | 강력 | 로그 내 풀텍스트 검색 시 EFK 우세 |
| 권장 | Y2 도입 (기본) | 전문 검색 필요 시 전환 | 비용 대비 Loki 우선 |

### 로그 보존 정책

| 구간 | 보존 기간 | 저장소 | 검색 성능 |
|------|----------|--------|----------|
| Hot | 30일 | Loki / Elasticsearch | 실시간 (~초) |
| Warm | 90일 | 압축 저장 (gzip) | 수 초 ~ 분 |
| Cold | 1년 | Object Storage (Ceph RGW) | 분 단위 (복원 후 검색) |
| Archive | 5년 (감사 로그만) | Object Storage (별도 버킷) | 시간 단위 |

### 감사 로그 (Audit Log)

보안/컴플라이언스를 위한 감사 로그는 별도 스트림으로 관리한다.

```json
{
  "timestamp": "2026-03-20T10:30:00Z",
  "event_type": "AUTH_LOGIN",
  "service": "gateway",
  "user_id": "user-1",
  "client_ip": "10.0.1.50",
  "action": "LOGIN_SUCCESS",
  "resource": "/api/v1/query/nl",
  "details": {
    "auth_method": "oidc",
    "realm": "imsp",
    "roles": ["kg-reader", "workflow-editor"]
  }
}
```

감사 대상 이벤트:
- 인증 성공/실패 (`AUTH_LOGIN`, `AUTH_LOGOUT`, `AUTH_FAILED`)
- KG 쓰기 작업 (`KG_WRITE`, `KG_DELETE`)
- 관리자 작업 (`ADMIN_CONFIG_CHANGE`, `ADMIN_USER_CREATE`)
- API Key 발급/폐기 (`APIKEY_ISSUE`, `APIKEY_REVOKE`)

---

## 10.7 SLO 정의 (Service Level Objectives)

SLO는 플랫폼 품질 목표를 정량화하며, 연차별로 목표를 상향 조정한다.
각 SLO에 대응하는 SLI(Service Level Indicator)를 Prometheus 메트릭으로 측정한다.

### 핵심 SLO 매트릭스

| SLI (지표) | 측정 방법 | SLO (Y1) | SLO (Y2) | SLO (Y3) | SLO (Y4) | SLO (Y5) |
|-----------|----------|----------|----------|----------|----------|----------|
| API 가용성 | `up{job="maritime-api"}` 비율 | 95% | 99% | 99.5% | 99.8% | 99.9% |
| Text2Cypher 정확도 | `maritime_text2cypher_accuracy` 평균 | 70% | 75% | 85% | 90% | 90% |
| ETL 성공률 | 성공 배치 / 전체 배치 비율 | 95% | 97% | 98% | 99% | 99.5% |
| API p95 응답 시간 | `maritime_api_request_duration_seconds` P95 | < 500ms | < 400ms | < 300ms | < 250ms | < 200ms |
| KG 쿼리 p99 지연 | Neo4j 쿼리 실행 시간 P99 | < 2s | < 1.5s | < 1s | < 700ms | < 500ms |
| LLM 추론 p95 지연 | `llm.infer` Span 지연 P95 | < 10s | < 7s | < 5s | < 4s | < 3s |

### Error Budget 정책

SLO 기반 Error Budget을 운영하여, 남은 예산이 있을 때 기능 개발을 우선하고
예산 소진 시 안정성 작업에 집중한다.

```
Error Budget = 1 - SLO 목표

예시: API 가용성 SLO 95% (Y1, 개발 환경)
  → Error Budget = 5% = 월 36시간 다운타임 허용
  → Budget 소진 시: 신규 기능 배포 동결, 안정성 개선 집중

Error Budget 소진율 알림:
  - 50% 소진 (월 중순): INFO → Slack #sre
  - 80% 소진: WARNING → Slack #ops + PM 통보
  - 100% 소진: CRITICAL → 배포 동결 + 개선 스프린트
```

### SLO 대시보드

Grafana에 SLO 전용 대시보드를 구성한다.

| 패널 | 내용 | 시각화 |
|------|------|--------|
| 가용성 게이지 | 현재 월 API 가용성 (%) | Gauge (Green/Yellow/Red) |
| Error Budget 잔량 | 남은 Error Budget (시간) | Bar Gauge |
| SLO 준수 추이 | 주간/월간 SLO 달성률 | Time Series |
| Text2Cypher 정확도 | 일별 정확도 추이 | Time Series + 목표선 |
| ETL 성공률 | 파이프라인별 성공/실패 비율 | Stacked Bar |

---

## 10.8 성능 테스트 전략

### 테스트 도구 및 프레임워크

| 도구 | 용도 | 도입 시기 |
|------|------|----------|
| k6 | HTTP API 부하 테스트 | Y1 Q3 |
| Locust | Python 기반 분산 부하 테스트 | Y2 |
| pytest-benchmark | 단위 성능 벤치마크 | Y1 Q2 |

### 부하 프로파일

| 시나리오 | 동시 사용자 | 요청/초 | 지속 시간 | 합격 기준 |
|----------|-----------|---------|----------|----------|
| Smoke | 1 | 1 | 1분 | 에러율 0% |
| Load (Y1) | 5 | 10 | 10분 | p95 < 200ms, 에러율 < 1% |
| Load (Y3) | 30 | 50 | 30분 | p95 < 200ms, 에러율 < 0.5% |
| Stress | 100 | 200 | 10분 | 정상 복구 확인 |
| Soak | 10 | 20 | 4시간 | 메모리 누수 없음 |

### 엔드포인트별 성능 버짓

| 엔드포인트 | p50 | p95 | p99 | 비고 |
|-----------|-----|-----|-----|------|
| `GET /api/v1/health` | < 5ms | < 10ms | < 50ms | |
| `GET /api/v1/search` | < 50ms | < 200ms | < 500ms | |
| `GET /api/v1/subgraph` | < 100ms | < 300ms | < 1s | 결과 크기에 비례 |
| `POST /api/v1/query` (Text2Cypher) | < 2s | < 5s | < 10s | LLM 호출 포함 |
| `POST /api/v1/etl/trigger` | < 100ms | < 200ms | < 500ms | 비동기 트리거만 |

### 회귀 탐지

- CI/CD 파이프라인에 `k6 run tests/perf/smoke.js` 통합 (Y1 Q3)
- 성능 버짓 초과 시 CI 실패 처리
- 주간 부하 테스트 결과를 Grafana 대시보드에 기록

---

*관련 문서: [09-tech-stack.md](./09-tech-stack.md) (기술 스택), [11-ai-llm.md](./11-ai-llm.md) (AI/LLM 아키텍처)*
