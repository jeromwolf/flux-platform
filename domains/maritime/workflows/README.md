# Activepieces 워크플로우 정의

이 디렉토리는 ETL 파이프라인을 자동 실행하는 Activepieces 워크플로우 정의 파일을 포함합니다.

## 워크플로우 목록

| 파일 | 워크플로우 이름 | 스케줄 | 파이프라인 | 모드 |
|------|----------------|--------|-----------|------|
| `wf_etl_papers.json` | KRISO 논문 크롤링 | 매주 토요일 02:00 | papers | incremental |
| `wf_etl_facilities.json` | 시험시설 정보 수집 | 매월 1일 03:00 | facilities | full |
| `wf_etl_weather.json` | 해양기상 데이터 수집 | 매 3시간 | weather | incremental |
| `wf_etl_accidents.json` | 해양사고 데이터 수집 | 매일 04:00 | accidents | incremental |
| `wf_etl_relations.json` | 관계 추출 배치 | 매주 월요일 05:00 | relations | incremental |
| `wf_etl_facility_data.json` | 시험 데이터 적재 | 웹훅/수동 | facility_data | incremental |

## 필요한 환경변수

Activepieces UI 또는 `.env` 파일에서 다음 환경변수를 설정해야 합니다:

```bash
# ETL API 엔드포인트
API_BASE_URL=http://localhost:8000

# ETL API 인증 키
API_KEY=your-api-key-here

# Slack 웹훅 URL (선택사항, 알림용)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 환경변수 설정 방법

#### 1. Activepieces UI에서 설정

1. Activepieces 대시보드 접속 (http://localhost:8080)
2. Settings → Environment Variables 메뉴 이동
3. 위 3개 환경변수 추가
4. Save 클릭

#### 2. Docker Compose에서 설정

`docker-compose.yml`에서 Activepieces 서비스에 환경변수 추가:

```yaml
services:
  activepieces:
    environment:
      - API_BASE_URL=http://host.docker.internal:8000
      - API_KEY=${APP_API_KEY}
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
```

## 워크플로우 등록 방법

### 방법 1: Activepieces UI에서 수동 등록

1. Activepieces 대시보드 접속 (http://localhost:8080)
2. Flows → Import 메뉴 이동
3. 각 JSON 파일을 업로드
4. 환경변수가 올바르게 매핑되었는지 확인
5. Activate 버튼 클릭

### 방법 2: 스크립트로 일괄 등록

```bash
# Activepieces API 키 환경변수 설정
export AP_API_KEY=your-activepieces-api-key

# 모든 워크플로우 등록
python scripts/register_workflows.py

# 특정 Activepieces URL 지정
python scripts/register_workflows.py --ap-url http://localhost:8080

# Dry-run (등록하지 않고 확인만)
python scripts/register_workflows.py --dry-run
```

## Activepieces API 키 발급

1. Activepieces 대시보드 접속
2. Settings → API Keys 메뉴 이동
3. "Create API Key" 버튼 클릭
4. 생성된 키를 복사하여 `AP_API_KEY` 환경변수에 설정

## 워크플로우 설명

### 1. KRISO 논문 크롤링 (`wf_etl_papers.json`)

- **목적**: KRISO ScholarWorks에서 논문 메타데이터 수집
- **스케줄**: 매주 토요일 새벽 2시
- **모드**: 증분 수집 (지난주 이후 신규 논문)
- **옵션**:
  - `max_pages`: 최대 5페이지 크롤링
  - `start_date`: 2024-01-01 이후 논문만 수집

### 2. 시험시설 정보 수집 (`wf_etl_facilities.json`)

- **목적**: KRISO 8종 시험시설 정보 수집
- **스케줄**: 매월 1일 새벽 3시
- **모드**: 전체 갱신 (시설 정보는 변경 빈도가 낮음)
- **대상 시설**:
  - 해양공학수조, 선형시험수조, 빙해수조, 심해공학수조
  - 파력발전 시험장, 고압챔버, 캐비테이션터널, 선박운항시뮬레이터

### 3. 해양기상 데이터 수집 (`wf_etl_weather.json`)

- **목적**: 기상청 해양기상 API에서 실시간 데이터 수집
- **스케줄**: 매 3시간마다
- **모드**: 증분 수집 (최근 3시간 데이터)
- **대상 지역**: 부산, 인천, 제주

### 4. 해양사고 데이터 수집 (`wf_etl_accidents.json`)

- **목적**: 해양안전심판원 해양사고 통계 크롤링
- **스케줄**: 매일 새벽 4시
- **모드**: 증분 수집 (전일 사고 데이터)
- **옵션**: 사고 상세 정보 포함

### 5. 관계 추출 배치 (`wf_etl_relations.json`)

- **목적**: 수집된 엔티티 간 관계 추출 및 연결
- **스케줄**: 매주 월요일 새벽 5시
- **모드**: 증분 수집 (지난주 데이터)
- **추출 관계**:
  - AUTHORED_BY (논문 저자 관계)
  - PUBLISHED_IN (논문 게재지 관계)
  - RELATED_TO (관련 엔티티 관계)
  - TESTED_AT (실험 시설 관계)
  - LOCATED_IN (지리적 위치 관계)

### 6. 시험 데이터 적재 (`wf_etl_facility_data.json`)

- **목적**: KRISO 시험시설의 실험 데이터 적재
- **트리거**: 웹훅 또는 수동 실행
- **모드**: 증분 수집
- **웹훅 페이로드 예시**:
  ```json
  {
    "facility_id": "towing_tank",
    "experiment_id": "EXP-2026-001",
    "data_path": "/data/experiments/2026/001/results.csv",
    "metadata": {
      "vessel_type": "container_ship",
      "test_type": "resistance",
      "date": "2026-02-16"
    }
  }
  ```

## 알림 설정

각 워크플로우는 성공/실패 시 Slack 알림을 전송합니다.

- **성공 알림**: ✅ 처리 건수, 실패 건수, 소요시간
- **실패 알림**: ❌ 오류 메시지

Slack 알림을 사용하지 않으려면:
1. 워크플로우 JSON에서 `notify_success`, `notify_failure` 스텝 삭제
2. 또는 `SLACK_WEBHOOK_URL` 환경변수를 빈 문자열로 설정

## 모니터링

Activepieces 대시보드에서 워크플로우 실행 이력을 확인할 수 있습니다:

1. Flows → 워크플로우 선택
2. Runs 탭에서 실행 로그 확인
3. 각 스텝의 입력/출력 데이터 확인
4. 실패한 스텝의 오류 메시지 확인

## 트러블슈팅

### 워크플로우가 실행되지 않을 때

1. **환경변수 확인**:
   - `API_BASE_URL`이 올바른지 확인 (Docker 내부에서는 `host.docker.internal` 사용)
   - `API_KEY`가 FastAPI 서버의 키와 일치하는지 확인

2. **네트워크 확인**:
   - Activepieces 컨테이너에서 FastAPI 서버 접근 가능한지 확인
   - `docker compose logs activepieces`로 로그 확인

3. **스케줄 확인**:
   - Cron 표현식이 올바른지 확인
   - Timezone이 `Asia/Seoul`로 설정되었는지 확인

### ETL 파이프라인 오류

1. **FastAPI 서버 로그 확인**:
   ```bash
   docker compose logs api
   ```

2. **ETL 파이프라인 직접 테스트**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/etl/trigger \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{"pipeline_name": "papers", "mode": "incremental"}'
   ```

3. **Neo4j 연결 확인**:
   ```bash
   docker compose exec neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD"
   ```

## 추가 자료

- Activepieces 공식 문서: https://www.activepieces.com/docs
- FastAPI ETL API 문서: http://localhost:8000/docs
- KRISO 데이터 소스 문서: `docs/REQ-002_KG_구축_대상_자원_선정.md`
