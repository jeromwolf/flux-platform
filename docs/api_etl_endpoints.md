# ETL Trigger API Endpoints

FastAPI 라우터로 ETL 파이프라인을 트리거하고 모니터링하기 위한 REST API입니다.

## 개요

- **파일**: `kg/api/routes/etl.py`
- **태그**: `etl`
- **인증**: API 키 필요 (X-API-Key 헤더)
- **상태 저장**: 인메모리 (PoC 버전, 프로덕션에서는 DB 백엔드 필요)

## 엔드포인트

### 1. POST /api/etl/trigger

ETL 파이프라인을 수동 또는 자동으로 트리거합니다.

**Request Body:**
```json
{
  "source": "manual",
  "pipeline_name": "papers",
  "mode": "incremental",
  "force_full": false
}
```

**Parameters:**
- `source` (string): 트리거 소스 (`manual`, `schedule`, `webhook`, `file_watcher`)
- `pipeline_name` (string): 파이프라인 이름 (아래 목록 참조)
- `mode` (string): ETL 모드 (`full`, `incremental`) - 기본값 `incremental`
- `force_full` (boolean): 증분 무시하고 전체 재구축 - 기본값 `false`

**Response:**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "pipeline_name": "papers",
  "status": "COMPLETED",
  "message": "Pipeline papers completed successfully"
}
```

**Status Codes:**
- `200 OK`: 파이프라인 실행 성공
- `400 Bad Request`: 알 수 없는 파이프라인 이름
- `401 Unauthorized`: API 키 누락 또는 무효

### 2. POST /api/etl/webhook/{source}

외부 시스템 웹훅을 수신하여 ETL을 트리거합니다.

**Path Parameter:**
- `source` (string): 파이프라인 이름 (URL 경로에서)

**Request Body:**
```json
{
  "event": "data_changed",
  "entity_type": "Document",
  "data": {
    "count": 10
  }
}
```

**Response:** `ETLTriggerResponse`와 동일

**Example:**
```bash
curl -X POST http://localhost:8000/api/etl/webhook/papers \
  -H "X-API-Key: dev_api_key_12345" \
  -H "Content-Type: application/json" \
  -d '{"event": "data_changed", "entity_type": "Document"}'
```

### 3. GET /api/etl/status/{run_id}

특정 실행의 상태를 조회합니다.

**Path Parameter:**
- `run_id` (string): 실행 ID (UUID)

**Response:**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "pipeline_name": "papers",
  "status": "COMPLETED",
  "records_processed": 42,
  "records_failed": 0,
  "records_skipped": 3,
  "duration_seconds": 12.345,
  "started_at": "2026-02-16T14:30:00",
  "completed_at": "2026-02-16T14:30:12",
  "errors": []
}
```

**Status Codes:**
- `200 OK`: 상태 조회 성공
- `404 Not Found`: run_id를 찾을 수 없음

### 4. GET /api/etl/history

실행 이력을 최신순으로 조회합니다.

**Query Parameter:**
- `limit` (int): 반환할 최대 실행 수 (기본값: 20, 범위: 1-100)

**Response:**
```json
{
  "runs": [
    {
      "run_id": "550e8400-e29b-41d4-a716-446655440000",
      "pipeline_name": "papers",
      "status": "COMPLETED",
      "records_processed": 42,
      "records_failed": 0,
      "records_skipped": 3,
      "duration_seconds": 12.345,
      "started_at": "2026-02-16T14:30:00",
      "completed_at": "2026-02-16T14:30:12",
      "errors": []
    }
  ],
  "total": 127
}
```

### 5. GET /api/etl/pipelines

사용 가능한 파이프라인 목록을 반환합니다.

**Response:**
```json
[
  {
    "name": "papers",
    "description": "KRISO ScholarWorks 논문 크롤링",
    "schedule": "0 2 * * 6",
    "entity_type": "Document"
  },
  {
    "name": "facilities",
    "description": "KRISO 시험시설 정보 크롤링",
    "schedule": "0 3 1 * *",
    "entity_type": "TestFacility"
  }
]
```

## 파이프라인 레지스트리

| 이름 | 설명 | 스케줄 | 엔티티 타입 |
|------|------|--------|------------|
| `papers` | KRISO ScholarWorks 논문 크롤링 | 매주 토 02:00 | Document |
| `facilities` | KRISO 시험시설 정보 크롤링 | 매월 1일 03:00 | TestFacility |
| `weather` | 기상청 해양기상 데이터 수집 | 매 3시간 | WeatherCondition |
| `accidents` | 해양사고 데이터 수집 | 매일 04:00 | Incident |
| `relations` | 관계 추출 배치 처리 | 매주 월 05:00 | Relationship |
| `facility_data` | 시험시설 실험 데이터 적재 | 수동 트리거 | Experiment |

## ETL 모드

### FULL (전체 재구축)
- 기존 데이터를 모두 삭제하고 처음부터 재구축
- `mode: "full"` 또는 `force_full: true` 사용

### INCREMENTAL (증분 업데이트)
- 마지막 실행 이후 변경된 데이터만 처리
- `IncrementalConfig.last_update_time` 기준으로 필터링
- 기본 모드

## 상태 관리

현재 PoC 버전은 인메모리 딕셔너리(`_run_history`)를 사용합니다.
프로덕션 환경에서는 다음 옵션을 고려하세요:

1. **PostgreSQL/MySQL**: 실행 이력을 관계형 DB에 저장
2. **Redis**: 빠른 조회를 위한 캐시 레이어
3. **Neo4j**: 리니지와 통합하여 실행 이력도 그래프에 저장

## 테스트

```bash
# 단위 테스트 (15개)
PYTHONPATH=. python3 -m pytest tests/test_api_etl.py -v -m unit

# 전체 API 테스트 (41개)
PYTHONPATH=. python3 -m pytest tests/test_api*.py -v -m unit
```

## 사용 예제

`examples/etl_api_usage.py` 참조:

```python
import requests

base_url = "http://localhost:8000"
headers = {"X-API-Key": "dev_api_key_12345"}

# Trigger pipeline
resp = requests.post(
    f"{base_url}/api/etl/trigger",
    headers=headers,
    json={
        "source": "manual",
        "pipeline_name": "papers",
        "mode": "incremental",
        "force_full": False,
    },
)
result = resp.json()
run_id = result["run_id"]

# Check status
resp = requests.get(f"{base_url}/api/etl/status/{run_id}", headers=headers)
status = resp.json()
print(f"Status: {status['status']}, Processed: {status['records_processed']}")
```

## 향후 확장

1. **비동기 실행**: Celery, RQ, 또는 FastAPI Background Tasks 사용
2. **실시간 진행률**: WebSocket을 통한 스트리밍 업데이트
3. **스케줄링**: APScheduler 또는 Cron 통합
4. **재시도 로직**: 실패한 실행 자동 재시도
5. **알림**: 실행 완료/실패 시 이메일/Slack 알림
6. **메트릭**: Prometheus 메트릭 내보내기
7. **실행 취소**: 진행 중인 파이프라인 취소 기능

## 관련 파일

- **Router**: `kg/api/routes/etl.py` (369 lines)
- **Tests**: `tests/test_api_etl.py` (413 lines, 15 tests)
- **Example**: `examples/etl_api_usage.py` (165 lines)
- **Models**: `kg/etl/models.py` (ETLMode, PipelineConfig, PipelineResult)
- **Pipeline**: `kg/etl/pipeline.py` (ETLPipeline 클래스)
