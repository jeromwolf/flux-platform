# 8. Suredata Lab 연동 아키텍처

[← 데이터 흐름도](./07-data-flow.md) | [다음: 기술 스택 →](./09-tech-stack.md)

## 개요

IMSP 플랫폼 전체는 InsightMining이 개발하나, 데이터 수집/마트/AI 서빙/DW 파이프라인은
Suredata Lab이 전담한다. 두 시스템은 REST API로 연동되며, 명확한 역할 분담과
장애 격리를 통해 독립적인 개발/운영이 가능한 구조를 유지한다.

---

## 8.1 시스템 연동 구조

```
+----------------------------+              +--------------------------------------+
|       Suredata Lab          |              |        IMSP (InsightMining)           |
|                             |              |                                      |
| +------------------+        |  REST API    | +--------------------------------+   |
| | Data Collector   |--------+------------->| POST /api/v1/ingest/raw         |   |
| | AIS 수신기        |        |              | POST /api/v1/ingest/metadata     |   |
| | 기상 수집기       |        |              | POST /api/v1/ingest/entities     |   |
| | 크롤러 (논문 등)  |        |              +----------------+---------------+   |   |
| +------------------+        |              |                |                   |   |
|                             |              |                v                   |   |
| +------------------+        |  REST API    | +--------------------------------+   |
| | Data Mart        |--------+------------->| KG Engine                        |   |
| | PostgreSQL 마트  |        |              | - Ontology Mapping               |   |
| | 집계 / 통계 뷰   |        |              | - Entity Resolution              |   |
| | 실시간 피드      |        |              | - Lineage Tracking               |   |
| +------------------+        |              +--------------------------------+   |   |
|                             |              |                                      |
| +------------------+        |  REST API    | +--------------------------------+   |
| | AI Model Serving |<-------+------------- | POST /api/v1/model/invoke       |   |
| | vLLM / Ray       |        |              | (모델 호출 -> 결과 KG 반영)      |   |
| | Model Registry   |        |              +--------------------------------+   |   |
| +------------------+        |              |                                      |
|                             |              | +--------------------------------+   |
| +------------------+        |  REST API    | | GET  /api/v1/query/nl         |   |
| | DW Pipeline      |<-------+------------- | GET  /api/v1/query/cypher      |   |
| | ETL 관리          |        |              | GET  /api/v1/lineage/{id}       |   |
| | 품질 관리         |        |              | GET  /api/v1/ontology/schema    |   |
| +------------------+        |              +--------------------------------+   |   |
+----------------------------+              +--------------------------------------+
```

---

## 8.2 역할 분담 매트릭스

| 기능 영역 | Suredata Lab | InsightMining (우리) | 연동 경계 |
|----------|-------------|---------------------|----------|
| 데이터 수집 | 크롤러/수집기 운영, 스케줄 관리 | 수집 어댑터 표준 인터페이스 정의 | Suredata 수집 -> REST API 전달 |
| 원천 저장 | DW (PostgreSQL), Data Lake | Object Storage (Ceph RGW) + Neo4j KG | REST API로 이중 저장 |
| 데이터 마트 | 마트 설계/구축/관리 | 마트 -> KG 통합 파이프라인 | GET API로 마트 데이터 조회 |
| AI 모델 서빙 | 모델 레지스트리, 서빙 인프라 | 모델 호출 인터페이스, 결과 KG 반영 | POST API로 모델 호출 |
| **KG 구축/검색** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |
| **온톨로지 설계** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |
| **Text2Cypher** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |
| **데이터 리니지** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |
| **VueFlow 캔버스** | **없음 (해당 없음)** | **전권 소유** | InsightMining 단독 책임 |

---

## 8.3 공동 협력 영역

| 협력 항목 | InsightMining 역할 | Suredata Lab 역할 |
|----------|------------------|------------------|
| API 명세 | OpenAPI 3.0 정의 및 게이트웨이 운영 | 명세 기반 구현 및 통합 테스트 |
| 데이터 품질 | KG 품질 게이트 (QualityGate 모듈) | DW 품질 규칙, 교차 검증 |
| 보안 정책 | Keycloak Realm 설계, API Key 발급 | DW 접근 제어, 통합 보안 정책 참여 |
| 모니터링 | K8s + KG 메트릭 (Prometheus) | DW + 모델 메트릭 수집, Prometheus 통합 |
| 장애 대응 | API 계층, KG, 워크플로우 장애 | 데이터 수집 중단, 마트 이상 대응 |

---

## 8.4 API 연동 표준

**인증:** API Key (헤더: `X-API-Key`) + IP 화이트리스트
**형식:** JSON (Content-Type: application/json)
**버전:** `/api/v1/` 경로 접두사, 하위 호환 보장
**오류:** RFC 7807 Problem Details 형식

```
POST /api/v1/ingest/raw
Authorization: X-API-Key {suredata_api_key}
Content-Type: application/json

{
  "source": "suredata-ais",
  "collected_at": "2026-03-20T10:00:00Z",
  "data_type": "ais_position",
  "records": [...]
}

Response 202 Accepted:
{
  "job_id": "ingest-20260320-001",
  "status": "queued",
  "estimated_processing_time_sec": 30
}
```

---

## 8.5 장애 시나리오 및 대응

두 시스템 간 연동에서 발생 가능한 장애를 사전 분류하고 대응 방안을 수립한다.
각 시나리오별로 자동 복구(Self-Healing)를 우선 적용하고, 불가 시 수동 개입 절차를 따른다.

| 시나리오 | 영향 | 대응 방안 | 복구 유형 |
|---------|------|----------|----------|
| Suredata DW API 다운 | 실시간 데이터 수집 중단 | 로컬 캐시(Redis) 기반 최근 데이터 서빙, AlertManager 알림 | 자동 |
| 데이터 포맷 변경 | ETL 파이프라인 실패 | 스키마 버전 관리, DLQ(Dead Letter Queue) 격리 후 수동 검토 | 수동 |
| 인증 토큰 만료 | API 연동 차단 | 자동 갱신 (OAuth2 `client_credentials` flow), 실패 시 알림 | 자동 |
| 네트워크 분리 | 전체 연동 불가 | Offline 모드: 로컬 데이터만으로 제한적 서비스 운영 | 수동 |
| 모델 서빙 과부하 | 추론 지연 급증 | Rate Limiting + Request Queue, GPU 스케일아웃 요청 | 자동 |
| 데이터 정합성 불일치 | KG 데이터 신뢰도 저하 | 교차 검증 배치 실행, 불일치 레코드 격리 및 재처리 | 반자동 |

### 장애 대응 플로우

```
장애 감지 (Prometheus Alert)
  │
  ├── 자동 복구 가능?
  │     ├── Yes → Circuit Breaker 활성화 → 캐시/폴백 서빙
  │     │         → 복구 대기 (Exponential Backoff)
  │     │         → 복구 확인 → Circuit Breaker 해제
  │     │
  │     └── No  → AlertManager → Slack #ops + Email
  │               → 담당자 수동 개입
  │               → 원인 분석 → 수정 → 재배포
  │
  └── 포스트모템 (Postmortem)
        → 원인/타임라인/개선 사항 기록
        → 알림 규칙 / 대응 절차 업데이트
```

### Circuit Breaker 설정

Suredata Lab API 호출에 Circuit Breaker 패턴을 적용하여 연쇄 장애를 방지한다.

```python
# gateway/middleware/circuit_breaker.py
class SuredataCircuitBreaker:
    failure_threshold: int = 5        # 연속 실패 N회 시 Open
    recovery_timeout_sec: int = 60    # Open 후 대기 시간
    half_open_max_calls: int = 3      # Half-Open 시 허용 요청 수

    states:
      CLOSED   → 정상 호출, 실패 카운트 누적
      OPEN     → 즉시 폴백 반환, 타이머 대기
      HALF_OPEN → 제한적 호출로 복구 확인
```

---

## 8.6 데이터 동기화 전략

Suredata Lab과 IMSP 간 데이터 유형별로 최적의 동기화 방식을 적용한다.

### 실시간 동기화

지연에 민감한 데이터(AIS 위치, 기상 관측)에 적용한다.

```
Suredata Collector
  │
  ├── AIS 위치 데이터 (5초 간격)
  │     └── Redis Streams → IMSP Consumer Group → KG Ingest
  │
  └── 기상 관측 데이터 (1분 간격)
        └── Redis Streams → IMSP Consumer Group → KG Ingest
```

| 데이터 유형 | 전송 방식 | 주기 | 지연 허용 |
|------------|----------|------|----------|
| AIS 위치 | Redis Streams | 5초 | < 30초 |
| 기상 관측 | Redis Streams | 1분 | < 5분 |
| 항행 경고 | Webhook (Push) | 이벤트 기반 | < 1분 |

### 배치 동기화

대량 데이터 또는 주기적 집계에 적용한다. Argo CronWorkflow로 스케줄링한다.

| 데이터 유형 | 스케줄 | 예상 볼륨 | 실행 방식 |
|------------|--------|----------|----------|
| 항만 시설 정보 | 일 1회 (02:00 KST) | ~10K 레코드 | Argo CronWorkflow |
| 선박 등록 정보 | 주 1회 (일요일 03:00) | ~50K 레코드 | Argo CronWorkflow |
| 해양 사고 통계 | 월 1회 (1일 04:00) | ~1K 레코드 | Argo CronWorkflow |
| DW 집계 뷰 갱신 | 일 1회 (05:00 KST) | 가변 | Argo CronWorkflow |

### 초기 데이터 마이그레이션

프로젝트 시작 시 Suredata Lab의 기존 DW 데이터를 IMSP KG로 일괄 이관한다.

```
1. 데이터 범위 합의 → 스키마 매핑 테이블 작성
2. Suredata: Bulk Export API (/api/v1/export/bulk) 제공
3. IMSP: Bulk Import Pipeline 실행
   - Ceph RGW에 원천 저장 (Parquet/CSV)
   - ELT 파이프라인으로 Neo4j KG 적재
   - Lineage 노드 자동 생성 (W3C PROV-O)
4. 교차 검증: DW 레코드 수 vs KG 노드 수 일치 확인
5. 데이터 품질 보고서 생성
```

---

## 8.7 SLA 및 데이터 품질 계약

Suredata Lab과 InsightMining 간 데이터 교환의 품질 기준을 명시한다.
계약 위반 시 자동 알림 및 에스컬레이션 절차를 수행한다.

### 데이터 신선도 (Freshness)

| 데이터 유형 | 최대 지연 | 측정 방법 | 위반 시 조치 |
|------------|----------|----------|-------------|
| AIS 위치 데이터 | < 5분 | `collected_at` vs `ingested_at` 차이 | AlertManager 알림, 캐시 서빙 |
| 기상 관측 데이터 | < 1시간 | 동일 | AlertManager 알림 |
| 항만/시설 정보 | < 24시간 | 마지막 배치 완료 시각 | Slack #data 알림 |
| AI 모델 응답 | < 30초 (P95) | API 응답 시간 측정 | 큐 조절, 스케일아웃 |

### 데이터 완전성 (Completeness)

| 지표 | 목표 | 측정 주기 | 측정 방법 |
|------|------|----------|----------|
| 결측률 | < 1% (99% 완전성) | 일 1회 배치 | 필수 필드 NULL 비율 검사 |
| 중복률 | < 0.1% | 일 1회 배치 | Entity Resolution 중복 감지 |
| 스키마 적합률 | 100% | 실시간 | JSON Schema 검증 (Ingest 시점) |

### API 가용성

| 지표 | SLA 목표 | 측정 방법 |
|------|---------|----------|
| Suredata API 가용성 | 99.5% (월 기준, 다운타임 < 3.6시간/월) | Health Check 엔드포인트 모니터링 |
| IMSP API 가용성 | 99.5% (월 기준) | Prometheus `up` 메트릭 |
| 장애 상호 통보 | 5분 이내 | AlertManager → 상호 Webhook |

### 에스컬레이션 절차

```
Level 1 (자동)  : AlertManager → Slack #ops (즉시)
Level 2 (5분)   : 담당 엔지니어 호출 (PagerDuty)
Level 3 (30분)  : 양사 PM 통보 (Email + 전화)
Level 4 (2시간) : 양사 기술 리드 합동 대응
```

---

*관련 문서: [07-data-flow.md](./07-data-flow.md) (데이터 흐름도), [10-observability.md](./10-observability.md) (모니터링)*
