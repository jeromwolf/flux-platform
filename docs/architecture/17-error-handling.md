# 17. 에러 처리 전략

[← 아키텍처 리뷰](./16-architecture-review.md) | [다음: API 설계 표준 →](./18-api-standards.md)

## 개요

IMSP 플랫폼 전체에 적용되는 통일된 에러 처리 전략을 기술한다. RFC 7807 (Problem Details for HTTP APIs) 표준을 채택하여 일관된 에러 응답 포맷을 제공하며, 도메인별 에러 코드 네임스페이스, 예외 계층 구조, 다국어 에러 메시지, 심각도 기반 알림 체계를 포함한다. 본 문서의 에러 코드와 예외 계층은 현재 구현된 `core/kg/exceptions.py`를 기반으로 하되, 5개년에 걸쳐 확장될 전체 플랫폼 범위를 포괄한다.

---

## 17.1 설계 원칙

| 원칙 | 설명 |
|------|------|
| **표준 준수** | RFC 7807 (Problem Details) 기반 에러 응답. 클라이언트가 `type` URI로 에러를 프로그래밍적으로 식별 |
| **단일 진실 공급원** | 에러 코드 카탈로그를 중앙 관리. 모든 서비스가 동일한 코드 체계를 사용 |
| **Fail Fast** | 파이프라인 각 단계에서 명시적 예외를 조기 발생. 오류 전파 최소화 |
| **다국어** | 한국어(기본) + 영어 에러 메시지. `Accept-Language` 헤더 기반 언어 선택 |
| **추적성** | 모든 에러에 `traceId`를 포함하여 Zipkin/Jaeger 연동 |
| **계층적 심각도** | FATAL/ERROR/WARN/INFO 4단계 분류. 심각도별 알림 채널 분리 |

---

## 17.2 에러 응답 포맷

RFC 7807 기반의 표준 에러 응답 포맷을 정의한다. 모든 API 엔드포인트는 이 포맷을 준수해야 한다.

### 17.2.1 표준 에러 응답

```json
{
  "type": "https://imsp.kriso.re.kr/errors/KG-2001",
  "title": "Cypher Query Validation Failed",
  "status": 400,
  "detail": "생성된 Cypher 쿼리에 허용되지 않는 DELETE 절이 포함되어 있습니다.",
  "instance": "/api/v1/query",
  "timestamp": "2026-03-20T10:30:00Z",
  "traceId": "a1b2c3d4e5f6",
  "errors": [
    {
      "field": "query",
      "code": "KG-2001",
      "message": "보안상 허용되지 않는 쿼리 유형입니다."
    }
  ]
}
```

### 17.2.2 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `type` | string (URI) | Y | 에러 유형 식별 URI. 에러 코드 문서 페이지로 연결 |
| `title` | string | Y | 에러 유형의 영문 제목 (사람 판독용) |
| `status` | integer | Y | HTTP 상태 코드 |
| `detail` | string | Y | 현재 요청에 대한 구체적 설명 (한국어/영어) |
| `instance` | string (URI) | Y | 에러가 발생한 요청 경로 |
| `timestamp` | string (ISO 8601) | Y | 에러 발생 시각 (UTC) |
| `traceId` | string | Y | 분산 추적 ID (Zipkin/Jaeger 연동) |
| `errors` | array | N | 상세 에러 목록 (검증 에러 등 복수 에러 시) |

### 17.2.3 검증 에러 (다중 필드)

```json
{
  "type": "https://imsp.kriso.re.kr/errors/API-5001",
  "title": "Validation Error",
  "status": 422,
  "detail": "요청 본문의 2개 필드에서 검증 오류가 발생했습니다.",
  "instance": "/api/v1/etl/trigger",
  "timestamp": "2026-03-20T10:31:00Z",
  "traceId": "f6e5d4c3b2a1",
  "errors": [
    {"field": "pipeline_name", "code": "API-5001", "message": "필수 필드입니다."},
    {"field": "mode", "code": "API-5002", "message": "'batch'는 유효하지 않은 모드입니다. (허용: full, incremental)"}
  ]
}
```

---

## 17.3 에러 코드 네임스페이스

도메인별로 에러 코드 범위를 분리하여 충돌을 방지한다. 접두사 3~5자 + 4자리 숫자로 구성한다.

| 접두사 | 코드 범위 | 도메인 | 구현 상태 |
|--------|----------|--------|----------|
| `AUTH` | 1000-1999 | 인증/인가 (Keycloak, JWT, RBAC) | Y1 구현 중 |
| `KG` | 2000-2999 | 지식그래프 엔진 (Cypher, 온톨로지, 스키마) | Y1 구현 중 |
| `ETL` | 3000-3999 | ELT 파이프라인 (추출, 변환, 적재) | Y1 구현 중 |
| `NLP` | 4000-4999 | NLP/NER/Text2Cypher | Y1 구현 중 |
| `API` | 5000-5999 | API Gateway 일반 (검증, Rate Limit) | Y1 구현 중 |
| `AGENT` | 6000-6999 | 에이전트 런타임 (ReAct, MCP, A2A) | Y2 예정 |
| `RAG` | 7000-7999 | RAG 엔진 (검색, 임베딩, 문서) | Y2 예정 |
| `WF` | 8000-8999 | 워크플로우/Argo (DAG, 노드, 실행) | Y2 예정 |
| `SYS` | 9000-9999 | 시스템/인프라 (DB, 네트워크, K8s) | Y1 구현 중 |

---

## 17.4 에러 코드 상세

### 17.4.1 AUTH (인증/인가) — 1000-1999

| 코드 | HTTP | 설명 | 사용자 메시지 (한국어) |
|------|------|------|---------------------|
| AUTH-1001 | 401 | JWT 토큰 만료 | 인증 토큰이 만료되었습니다. 다시 로그인해주세요. |
| AUTH-1002 | 401 | JWT 서명 불일치 | 유효하지 않은 인증 토큰입니다. |
| AUTH-1003 | 403 | 권한 부족 (RBAC) | 이 작업을 수행할 권한이 없습니다. |
| AUTH-1004 | 403 | 데이터 분류 등급 미달 | 요청한 데이터에 대한 접근 등급이 부족합니다. |
| AUTH-1005 | 401 | API Key 미제공 | API 키가 필요합니다. X-API-Key 헤더를 확인해주세요. |
| AUTH-1006 | 401 | API Key 무효 | 유효하지 않은 API 키입니다. |
| AUTH-1007 | 403 | 테넌트 격리 위반 | 다른 테넌트의 데이터에 접근할 수 없습니다. |
| AUTH-1008 | 429 | 인증 시도 횟수 초과 | 로그인 시도 횟수를 초과했습니다. 잠시 후 다시 시도해주세요. |

### 17.4.2 KG (지식그래프 엔진) — 2000-2999

| 코드 | HTTP | 설명 | 사용자 메시지 (한국어) |
|------|------|------|---------------------|
| KG-2001 | 400 | Cypher 문법 오류 | 쿼리 문법 오류가 발견되었습니다. |
| KG-2002 | 400 | 금지된 Cypher 절 (DELETE, DETACH, DROP) | 보안상 허용되지 않는 쿼리 유형입니다. |
| KG-2003 | 404 | 엔티티 미존재 | 요청한 엔티티를 찾을 수 없습니다. |
| KG-2004 | 400 | 온톨로지 스키마 위반 | 요청이 온톨로지 스키마와 일치하지 않습니다. |
| KG-2005 | 409 | 엔티티 중복 (MERGE 충돌) | 동일한 식별자를 가진 엔티티가 이미 존재합니다. |
| KG-2006 | 400 | 관계 타입 미정의 | 정의되지 않은 관계 유형입니다. |
| KG-2007 | 400 | 속성 타입 불일치 | 속성 값의 데이터 타입이 스키마와 일치하지 않습니다. |
| KG-2008 | 500 | Cypher 실행 타임아웃 | 쿼리 실행 시간이 초과되었습니다. 조건을 좁혀 다시 시도해주세요. |

### 17.4.3 ETL (ELT 파이프라인) — 3000-3999

| 코드 | HTTP | 설명 | 사용자 메시지 (한국어) |
|------|------|------|---------------------|
| ETL-3001 | 400 | 파이프라인 미등록 | 요청한 파이프라인을 찾을 수 없습니다. |
| ETL-3002 | 422 | 레코드 검증 실패 | 데이터 형식이 올바르지 않습니다. |
| ETL-3003 | 500 | 추출(Extract) 단계 실패 | 데이터 소스에서 추출 중 오류가 발생했습니다. |
| ETL-3004 | 500 | 변환(Transform) 단계 실패 | 데이터 변환 중 오류가 발생했습니다. |
| ETL-3005 | 500 | 적재(Load) 단계 실패 | 데이터 적재 중 오류가 발생했습니다. |
| ETL-3006 | 409 | 파이프라인 이미 실행 중 | 동일 파이프라인이 이미 실행 중입니다. 완료 후 재시도해주세요. |
| ETL-3007 | 500 | DLQ 임계값 초과 | 실패 레코드가 임계값을 초과하여 파이프라인이 중단되었습니다. |
| ETL-3008 | 404 | 실행 이력 미존재 | 요청한 실행 ID를 찾을 수 없습니다. |

### 17.4.4 NLP (NLP/NER/Text2Cypher) — 4000-4999

| 코드 | HTTP | 설명 | 사용자 메시지 (한국어) |
|------|------|------|---------------------|
| NLP-4001 | 400 | 파싱 실패 (의도 미식별) | 질문의 의도를 파악할 수 없습니다. 다시 표현해주세요. |
| NLP-4002 | 400 | 엔티티 미인식 | 입력에서 해사 엔티티를 식별할 수 없습니다. |
| NLP-4003 | 500 | LLM 생성 실패 | AI 모델의 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요. |
| NLP-4004 | 500 | LLM 타임아웃 | AI 모델 응답 시간이 초과되었습니다. |
| NLP-4005 | 400 | 환각(Hallucination) 감지 | 생성된 쿼리가 온톨로지와 일치하지 않아 차단되었습니다. |
| NLP-4006 | 400 | 저신뢰도 파싱 (confidence < threshold) | 질문 해석의 신뢰도가 낮습니다. 더 구체적으로 질문해주세요. |
| NLP-4007 | 500 | 용어사전 로드 실패 | 해사 용어 사전 초기화에 실패했습니다. |

### 17.4.5 API (API Gateway 일반) — 5000-5999

| 코드 | HTTP | 설명 | 사용자 메시지 (한국어) |
|------|------|------|---------------------|
| API-5001 | 422 | 요청 본문 검증 실패 | 요청 데이터의 형식이 올바르지 않습니다. |
| API-5002 | 422 | 파라미터 범위 초과 | 파라미터 값이 허용 범위를 벗어났습니다. |
| API-5003 | 429 | Rate Limit 초과 | 요청 횟수 제한을 초과했습니다. 잠시 후 다시 시도해주세요. |
| API-5004 | 404 | 엔드포인트 미존재 | 요청한 API 경로를 찾을 수 없습니다. |
| API-5005 | 405 | HTTP 메서드 불허 | 이 엔드포인트에서 해당 HTTP 메서드는 지원하지 않습니다. |
| API-5006 | 415 | Content-Type 미지원 | 지원하지 않는 미디어 타입입니다. application/json을 사용해주세요. |
| API-5007 | 413 | 요청 본문 크기 초과 | 요청 본문이 허용 크기(10MB)를 초과했습니다. |
| API-5008 | 503 | 서비스 일시 중단 | 서비스가 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해주세요. |

### 17.4.6 AGENT (에이전트 런타임) — 6000-6999 (Y2 예정)

| 코드 | HTTP | 설명 | 사용자 메시지 (한국어) |
|------|------|------|---------------------|
| AGENT-6001 | 500 | 에이전트 실행 루프 실패 | 에이전트 실행 중 오류가 발생했습니다. |
| AGENT-6002 | 400 | 도구(Tool) 미등록 | 요청한 도구를 찾을 수 없습니다. |
| AGENT-6003 | 504 | 에이전트 타임아웃 (max iterations) | 에이전트 처리 시간이 초과되었습니다. |

### 17.4.7 RAG (RAG 엔진) — 7000-7999 (Y2 예정)

| 코드 | HTTP | 설명 | 사용자 메시지 (한국어) |
|------|------|------|---------------------|
| RAG-7001 | 500 | 임베딩 생성 실패 | 벡터 임베딩 생성에 실패했습니다. |
| RAG-7002 | 404 | 문서 미존재 | 요청한 문서를 찾을 수 없습니다. |
| RAG-7003 | 422 | 지원하지 않는 문서 형식 | 지원하지 않는 파일 형식입니다. (지원: PDF, HWP, DOCX) |

### 17.4.8 WF (워크플로우/Argo) — 8000-8999 (Y2 예정)

| 코드 | HTTP | 설명 | 사용자 메시지 (한국어) |
|------|------|------|---------------------|
| WF-8001 | 400 | DAG 순환 감지 | 워크플로우에 순환 의존이 발견되었습니다. |
| WF-8002 | 500 | 노드 실행 실패 | 워크플로우 노드 실행 중 오류가 발생했습니다. |
| WF-8003 | 404 | 워크플로우 미존재 | 요청한 워크플로우를 찾을 수 없습니다. |

### 17.4.9 SYS (시스템/인프라) — 9000-9999

| 코드 | HTTP | 설명 | 사용자 메시지 (한국어) |
|------|------|------|---------------------|
| SYS-9001 | 503 | Neo4j 연결 불가 | 데이터베이스 연결에 실패했습니다. 관리자에게 문의해주세요. |
| SYS-9002 | 500 | 설정 로드 실패 | 시스템 설정을 불러올 수 없습니다. |
| SYS-9003 | 503 | Object Storage (Ceph) 연결 불가 | 저장소 서비스에 연결할 수 없습니다. |
| SYS-9004 | 503 | Redis 연결 불가 | 캐시 서비스에 연결할 수 없습니다. |
| SYS-9005 | 503 | LLM 서버 연결 불가 | AI 모델 서버에 연결할 수 없습니다. |

---

## 17.5 에러 심각도 분류

모든 에러는 4단계 심각도로 분류되며, 각 심각도에 따라 로그 수준과 알림 채널이 결정된다.

| 레벨 | 의미 | 로그 수준 | 알림 채널 | 예시 |
|------|------|----------|----------|------|
| **FATAL** | 시스템 중단, 즉시 대응 필요 | CRITICAL | PagerDuty 즉시 호출 | SYS-9001 Neo4j 연결 불가, SYS-9003 Ceph 불가 |
| **ERROR** | 기능 장애, 사용자 요청 실패 | ERROR | Slack #alert 채널 (5분 내) | NLP-4003 LLM 생성 실패, ETL-3005 적재 실패 |
| **WARN** | 성능 저하 또는 잠재적 문제 | WARNING | 집계 알림 (1시간 단위) | KG-2008 쿼리 지연 > 5s, ETL-3007 DLQ 임계 근접 |
| **INFO** | 사용자 입력 오류 (시스템 정상) | INFO | 없음 (메트릭 집계만) | API-5001 검증 실패, NLP-4001 의도 미식별 |

### 알림 에스컬레이션 규칙

```
INFO  → 메트릭만 (Prometheus Counter: imsp_errors_total{code, severity})
WARN  → 1시간 내 3회 이상 → ERROR로 승격
ERROR → Slack 알림. 30분 내 미해결 → FATAL로 승격
FATAL → PagerDuty 호출 + Slack @channel
```

---

## 17.6 예외 계층 구조

현재 `core/kg/exceptions.py`에 구현된 예외 계층을 기반으로, 전체 플랫폼 범위로 확장한 예외 계층이다.

### 17.6.1 현재 구현 (core/kg/exceptions.py)

```python
KGError                          # 기본 예외 (모든 KG 에러의 부모)
├── ConnectionError              # SYS-9001: Neo4j 연결 실패
│   └── uri, cause 속성
├── SchemaError                  # KG-2004: 스키마 초기화/검증 오류
│   └── entity, constraint 속성
├── CrawlerError                 # ETL-3003: 데이터 크롤링 오류
│   └── url, crawler, status_code 속성
├── AccessDeniedError            # AUTH-1003: RBAC 접근 거부
│   └── user_id, data_class_id, required_level 속성
└── QueryError                   # KG-2001: 쿼리 생성/실행 오류
    └── query, parameters, language 속성
```

### 17.6.2 확장 계획 (Y1-Y2)

```python
IMSPError                        # 플랫폼 최상위 예외
├── KGError                      # 지식그래프 엔진
│   ├── ConnectionError          # SYS-9001
│   ├── SchemaError              # KG-2004
│   ├── CypherError              # KG-2001, KG-2002
│   │   ├── CypherSyntaxError    # KG-2001
│   │   └── CypherSecurityError  # KG-2002
│   ├── EntityNotFoundError      # KG-2003
│   ├── QueryError               # KG-2008
│   └── OntologyError            # KG-2006, KG-2007
├── ETLError                     # ELT 파이프라인
│   ├── ExtractError             # ETL-3003
│   ├── TransformError           # ETL-3004
│   ├── LoadError                # ETL-3005
│   ├── ValidationError          # ETL-3002
│   └── DLQOverflowError        # ETL-3007
├── NLPError                     # NLP/Text2Cypher
│   ├── ParseError               # NLP-4001
│   ├── EntityResolutionError    # NLP-4002
│   ├── LLMError                 # NLP-4003, NLP-4004
│   └── HallucinationError      # NLP-4005
├── AuthError                    # 인증/인가
│   ├── TokenExpiredError        # AUTH-1001
│   ├── InvalidTokenError        # AUTH-1002
│   └── AccessDeniedError        # AUTH-1003
├── AgentError                   # (Y2) 에이전트
│   ├── ToolNotFoundError        # AGENT-6002
│   └── AgentTimeoutError        # AGENT-6003
├── RAGError                     # (Y2) RAG
│   ├── EmbeddingError           # RAG-7001
│   └── DocumentNotFoundError    # RAG-7002
└── SystemError                  # 시스템/인프라
    ├── StorageError             # SYS-9003
    ├── CacheError               # SYS-9004
    └── LLMServerError           # SYS-9005
```

---

## 17.7 에러 흐름

### 17.7.1 Text2Cypher 파이프라인 에러 흐름

```
사용자 입력: "부산항 근처 유조선 목록"
     │
     ▼
[Stage 1: Parse] ─── 실패 → NLP-4001 ParseError
     │                       → HTTP 400, severity: INFO
     ▼
[Stage 2: Entity Resolution] ─── 실패 → NLP-4002 EntityResolutionError
     │                                   → HTTP 400, severity: INFO
     ▼
[Stage 3: Generate Cypher]
     ├── Direct Path ─── 실패 → KG-2001 CypherSyntaxError
     │                          → HTTP 400, severity: WARN
     └── LLM Path ─── 타임아웃 → NLP-4004 LLMTimeoutError
                       │          → HTTP 500, severity: ERROR
                       └── 생성 실패 → NLP-4003 LLMError
                                      → HTTP 500, severity: ERROR
     ▼
[Stage 4: Validate] ─── 보안 위반 → KG-2002 CypherSecurityError
     │                               → HTTP 400, severity: WARN (+ 감사 로그)
     ▼
[Stage 5: Hallucination Detect] ─── 환각 감지 → NLP-4005 HallucinationError
     │                                          → HTTP 400, severity: INFO
     ▼
[RBAC Filter] ─── 권한 부족 → AUTH-1003 AccessDeniedError
     │                        → HTTP 403, severity: INFO
     ▼
[Execute Cypher] ─── 타임아웃 → KG-2008 QueryTimeoutError
     │                          → HTTP 500, severity: WARN
     └── DB 연결 실패 → SYS-9001 ConnectionError
                        → HTTP 503, severity: FATAL
```

### 17.7.2 ETL 파이프라인 에러 흐름

```
ETL 트리거 (Manual/Webhook/Schedule)
     │
     ▼
[Validate Request] ─── 미등록 파이프라인 → ETL-3001
     │                                    → HTTP 400, severity: INFO
     ▼
[Extract] ─── 크롤러 오류 → ETL-3003 ExtractError
     │                      → HTTP 500, severity: ERROR
     ▼
[Transform] ─── 레코드 검증 실패 → ETL-3002 (DLQ로 이동)
     │          │                   → 로그 WARN, 계속 진행
     │          └── 변환 오류 → ETL-3004 TransformError
     │                         → HTTP 500, severity: ERROR
     ▼
[Load] ─── 적재 실패 → ETL-3005 LoadError
     │                 → HTTP 500, severity: ERROR
     └── DLQ 임계 초과 → ETL-3007 DLQOverflowError
                         → HTTP 500, severity: FATAL
```

### 17.7.3 API 계층 에러 처리 흐름

```
HTTP Request
     │
     ▼
[FastAPI Middleware] ─── Rate Limit → API-5003 (429)
     │                └── CORS 위반 → 브라우저 차단 (서버 로그만)
     ▼
[Auth Middleware] ─── 토큰 없음 → AUTH-1005 (401)
     │             ├── 토큰 만료 → AUTH-1001 (401)
     │             └── 권한 부족 → AUTH-1003 (403)
     ▼
[Request Validation] ─── Pydantic 오류 → API-5001 (422)
     │                                   → FastAPI 기본 핸들러를 RFC 7807로 래핑
     ▼
[Business Logic] ─── 도메인 예외 발생 → 에러 코드에 따른 응답
     │
     ▼
[Exception Handler] ─── IMSPError → RFC 7807 응답 생성
                    └── 예상치 못한 예외 → SYS-9999 Internal Error (500)
                                          → 상세 정보 숨김 (보안)
```

---

## 17.8 다국어 에러 메시지

### 17.8.1 설계

- 기본 언어: 한국어 (`ko`)
- 지원 언어: 한국어, 영어 (`en`)
- 언어 선택: `Accept-Language` 헤더 기반 (미지정 시 한국어)
- 메시지 카탈로그: JSON 파일로 관리

### 17.8.2 메시지 카탈로그 구조

```
core/kg/errors/
├── __init__.py
├── catalog.py          # ErrorCatalog 클래스
└── messages/
    ├── ko.json         # 한국어 메시지
    └── en.json         # 영어 메시지
```

### 17.8.3 메시지 파일 예시

```json
// core/kg/errors/messages/ko.json
{
  "AUTH-1001": {
    "title": "인증 토큰 만료",
    "detail": "인증 토큰이 만료되었습니다. 다시 로그인해주세요."
  },
  "KG-2001": {
    "title": "Cypher 쿼리 문법 오류",
    "detail": "쿼리 문법 오류가 발견되었습니다. 쿼리를 확인해주세요."
  },
  "KG-2002": {
    "title": "금지된 Cypher 절",
    "detail": "보안상 허용되지 않는 쿼리 유형입니다. ({clause} 절은 사용할 수 없습니다.)"
  }
}
```

```json
// core/kg/errors/messages/en.json
{
  "AUTH-1001": {
    "title": "Authentication Token Expired",
    "detail": "Your authentication token has expired. Please log in again."
  },
  "KG-2001": {
    "title": "Cypher Query Syntax Error",
    "detail": "A syntax error was found in the query. Please check the query."
  },
  "KG-2002": {
    "title": "Forbidden Cypher Clause",
    "detail": "This query type is not allowed for security reasons. ({clause} clause is forbidden.)"
  }
}
```

### 17.8.4 ErrorCatalog 구현

```python
# core/kg/errors/catalog.py
class ErrorCatalog:
    """에러 코드별 메시지 카탈로그. Accept-Language 기반 다국어 지원."""

    def __init__(self):
        self._messages: dict[str, dict[str, dict]] = {}
        self._load_messages()

    def get_message(self, code: str, lang: str = "ko", **kwargs) -> dict:
        """에러 코드에 해당하는 메시지를 반환한다."""
        lang_messages = self._messages.get(lang, self._messages["ko"])
        template = lang_messages.get(code, {"title": "Unknown Error", "detail": code})
        return {
            "title": template["title"],
            "detail": template["detail"].format(**kwargs) if kwargs else template["detail"],
        }
```

---

## 17.9 코드 매핑

현재 코드베이스에서 에러 처리와 관련된 파일 매핑이다.

| 파일 | 역할 | 상태 |
|------|------|------|
| `core/kg/exceptions.py` | 예외 계층 정의 (KGError 기반) | 현재 구현 |
| `core/kg/api/app.py` | FastAPI 앱 팩토리 (미들웨어 등록) | 현재 구현 |
| `core/kg/api/middleware/auth.py` | API Key 인증 미들웨어 | 현재 구현 |
| `core/kg/api/middleware/jwt_auth.py` | JWT 인증 미들웨어 | 현재 구현 |
| `core/kg/api/routes/query.py` | 쿼리 엔드포인트 (try/except 패턴) | 현재 구현 |
| `core/kg/api/routes/etl.py` | ETL 엔드포인트 (HTTPException 사용) | 현재 구현 |
| `core/kg/api/routes/lineage.py` | 리니지 엔드포인트 (HTTPException 사용) | 현재 구현 |
| `core/kg/cypher_validator.py` | Cypher 검증기 (6가지 검증 규칙) | 현재 구현 |
| `core/kg/hallucination_detector.py` | 환각 감지기 | 현재 구현 |
| `core/kg/etl/dlq.py` | Dead Letter Queue (실패 레코드 보존) | 현재 구현 |
| `core/kg/etl/validator.py` | ETL 레코드 검증기 | 현재 구현 |
| `core/kg/errors/` | 에러 카탈로그 + 다국어 메시지 | **Y1 Q2 신규** |

### 현재 에러 처리 패턴의 개선점

현재 코드에서는 FastAPI의 기본 `HTTPException`을 직접 사용하고 있다. RFC 7807 전환 시 아래와 같이 변경한다.

```python
# Before (현재)
raise HTTPException(status_code=400, detail=f"Unknown pipeline: {name}")

# After (RFC 7807)
raise IMSPHTTPException(
    code="ETL-3001",
    status=400,
    detail=f"요청한 파이프라인 '{name}'을 찾을 수 없습니다.",
    instance=request.url.path,
)
```

---

## 17.10 구현 로드맵

| 시점 | 작업 | 상세 |
|------|------|------|
| Y1 Q2 | 예외 계층 확장 | `KGError` → `IMSPError` 최상위 예외 도입. 하위 예외 체계 정리 |
| Y1 Q2 | RFC 7807 응답 포맷 | FastAPI Exception Handler에서 RFC 7807 형식으로 변환. `IMSPHTTPException` 구현 |
| Y1 Q2 | 에러 코드 카탈로그 | AUTH, KG, ETL, NLP, API, SYS 코드 등록. JSON 메시지 파일 작성 |
| Y1 Q3 | 다국어 메시지 지원 | `ErrorCatalog` 구현. `Accept-Language` 헤더 파싱 미들웨어 |
| Y1 Q3 | 심각도 기반 알림 | Prometheus 메트릭 + AlertManager 규칙 설정 |
| Y2 Q1 | AGENT, RAG, WF 에러 코드 | 에이전트/RAG/워크플로우 모듈 이식 시 에러 코드 추가 |
| Y2 Q2 | 에러 대시보드 | Grafana 대시보드: 에러 코드별 발생 빈도, 심각도 분포, 추이 |
| Y3 | 에러 분석 자동화 | 에러 패턴 분석 → 자동 대응 제안 (RCA 보조) |

---

*관련 문서: [아키텍처 리뷰](./16-architecture-review.md), [API 설계 표준](./18-api-standards.md), [관측성 아키텍처](./10-observability.md), [보안 아키텍처](./06-security-architecture.md)*
