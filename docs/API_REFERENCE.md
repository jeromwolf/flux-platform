# IMSP API 레퍼런스

IMSP 플랫폼의 완벽한 REST API 문서입니다. 모든 엔드포인트는 OAuth2/OIDC를 통해 보호되며, RFC 7807 표준 에러 형식을 사용합니다.

## 개요

### Base URL

```
http://localhost:8080/api/v1    (Gateway를 통한 프로덕션)
http://localhost:8000/api/v1    (직접 API 접속, 개발/테스트)
```

### 인증

모든 엔드포인트는 Bearer JWT 토큰이 필요합니다:

```bash
# Keycloak에서 토큰 획득
curl -X POST http://localhost:8180/realms/imsp/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=imsp-api" \
  -d "username=user" \
  -d "password=password"

# 응답:
{
  "access_token": "eyJhbGciOiJSUzI1NiIsIn...",
  "token_type": "Bearer",
  "expires_in": 300
}

# API 호출
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8080/api/v1/health
```

### 에러 형식 (RFC 7807)

모든 에러 응답은 표준 형식을 따릅니다:

```json
{
  "type": "https://api.imsp.io/docs/errors#validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "Invalid label 'MyLabel': must be a valid identifier",
  "instance": "/api/v1/nodes"
}
```

HTTP 상태 코드:
- `200 OK` — 성공
- `201 Created` — 리소스 생성 성공
- `204 No Content` — 성공 (응답 본문 없음)
- `400 Bad Request` — 잘못된 파라미터
- `401 Unauthorized` — 인증 필요
- `403 Forbidden` — 권한 부족
- `404 Not Found` — 리소스 없음
- `422 Unprocessable Entity` — 검증 오류
- `500 Internal Server Error` — 서버 오류
- `503 Service Unavailable` — 서비스 불가 (Neo4j/GDS 오류)

---

## API 엔드포인트

### 시스템 / 헬스체크

#### 기본 헬스체크

**GET** `/health`

시스템 기본 상태를 반환합니다.

```bash
curl http://localhost:8080/api/v1/health
```

**응답:**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "neo4j_connected": true
}
```

| 상태 | 의미 |
|------|------|
| `ok` | 모든 서비스 정상 |
| `degraded` | Neo4j 연결 불가 (읽기 전용) |

#### 심층 헬스체크

**GET** `/health?deep=true`

컴포넌트별 상세 진단을 포함합니다.

```bash
curl http://localhost:8080/api/v1/health?deep=true
```

**응답:**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "neo4j_connected": true,
  "components": [
    {
      "name": "neo4j",
      "status": "ok",
      "latency_ms": 2.3
    },
    {
      "name": "disk",
      "status": "ok",
      "details": {
        "total_gb": 100.0,
        "free_gb": 45.2,
        "free_pct": 68.5
      }
    },
    {
      "name": "memory",
      "status": "ok",
      "details": {
        "total_gb": 8.0,
        "available_gb": 6.2,
        "used_pct": 22.3
      }
    }
  ],
  "system": {
    "python_version": "3.10.12",
    "platform": "Linux-6.1.0-amd64",
    "hostname": "maritime-api"
  }
}
```

---

### 그래프 탐색

#### 서브그래프 조회

**GET** `/subgraph?label=Vessel&limit=50`

지정된 라벨의 노드들과 그들의 관계를 조회합니다.

**파라미터:**

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `label` | string | `Vessel` | Neo4j 노드 라벨 (예: Vessel, Port, Facility) |
| `limit` | integer | 50 | 반환할 최대 노드 수 (1-200) |

**요청:**

```bash
curl "http://localhost:8080/api/v1/subgraph?label=Vessel&limit=30"
```

**응답:**

```json
{
  "nodes": [
    {
      "id": "4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8",
      "labels": ["Vessel"],
      "primaryLabel": "Vessel",
      "group": "vessel",
      "color": "#FF6B6B",
      "properties": {
        "vesselId": "IMO-1234567",
        "name": "한진셜리",
        "type": "컨테이너선",
        "grt": 50000,
        "built": 2015
      },
      "displayName": "한진셜리"
    }
  ],
  "edges": [
    {
      "id": "5:r1e2d3c4-5678-90ab-cdef-1234567890ab",
      "type": "REGISTERED_AT",
      "sourceId": "4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8",
      "targetId": "4:b9f2cf3f-2345-6789-b2c3-d4e5f6g7h8i9",
      "properties": {
        "registeredYear": 2015
      }
    }
  ],
  "meta": {
    "label": "Vessel",
    "limit": 30,
    "nodeCount": 25,
    "edgeCount": 18
  }
}
```

#### 노드 이웃 조회

**GET** `/neighbors?nodeId={elementId}`

특정 노드의 모든 1-hop 이웃을 조회합니다.

**파라미터:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|-----|------|
| `nodeId` | string | ✓ | Neo4j element ID |

**요청:**

```bash
curl "http://localhost:8080/api/v1/neighbors?nodeId=4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8"
```

**응답:** (subgraph와 동일한 구조)

#### 키워드 검색

**GET** `/search?q=한진셜리&limit=30`

노드의 이름, 제목, 설명에서 검색합니다.

**파라미터:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|-----|------|
| `q` | string | ✓ | 검색어 (최소 1글자) |
| `limit` | integer | - | 최대 결과 수 (1-100, 기본값: 30) |

**요청:**

```bash
curl "http://localhost:8080/api/v1/search?q=한진&limit=20"
```

**응답:** (subgraph와 동일한 구조)

---

### 스키마

#### 스키마 정보 조회

**GET** `/schema`

그래프의 모든 노드 라벨, 관계 타입, 엔티티 그룹을 반환합니다.

```bash
curl http://localhost:8080/api/v1/schema
```

**응답:**

```json
{
  "labels": [
    {
      "label": "Vessel",
      "group": "vessel",
      "color": "#FF6B6B",
      "count": 250
    },
    {
      "label": "Port",
      "group": "location",
      "color": "#4ECDC4",
      "count": 45
    }
  ],
  "relationshipTypes": [
    "REGISTERED_AT",
    "DOCKED_AT",
    "OPERATED_BY",
    "MANAGED_BY"
  ],
  "entityGroups": {
    "vessel": {
      "color": "#FF6B6B",
      "labels": ["Vessel", "VesselClass", "VesselType"]
    },
    "location": {
      "color": "#4ECDC4",
      "labels": ["Port", "Country", "Region"]
    }
  },
  "totalLabels": 42,
  "totalRelationshipTypes": 28
}
```

---

### 노드 CRUD

#### 노드 생성

**POST** `/nodes`

새로운 노드를 생성합니다.

**요청 본문:**

```json
{
  "labels": ["Vessel", "Container"],
  "properties": {
    "vesselId": "IMO-1234567",
    "name": "한진셜리",
    "type": "컨테이너선",
    "grt": 50000,
    "built": 2015
  }
}
```

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/nodes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "labels": ["Vessel"],
    "properties": {"vesselId": "IMO-2024001", "name": "새로운선박"}
  }'
```

**응답:** (201 Created)

```json
{
  "id": "4:c0f3dg4g-3456-7890-c3d4-e5f6g7h8i9j0",
  "labels": ["Vessel"],
  "primaryLabel": "Vessel",
  "group": "vessel",
  "color": "#FF6B6B",
  "properties": {
    "vesselId": "IMO-2024001",
    "name": "새로운선박"
  },
  "displayName": "새로운선박"
}
```

**에러:**

```json
{
  "status": 422,
  "detail": "Invalid label 'Vessel!': must be a valid identifier"
}
```

#### 노드 조회

**GET** `/nodes/{nodeId}`

단일 노드를 조회합니다.

**요청:**

```bash
curl http://localhost:8080/api/v1/nodes/4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8
```

**응답:**

```json
{
  "id": "4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8",
  "labels": ["Vessel"],
  "primaryLabel": "Vessel",
  "group": "vessel",
  "color": "#FF6B6B",
  "properties": {
    "vesselId": "IMO-1234567",
    "name": "한진셜리"
  },
  "displayName": "한진셜리"
}
```

#### 노드 목록 조회 (페이징)

**GET** `/nodes?label=Vessel&limit=20&offset=0&q=한진`

조건에 맞는 노드 목록을 페이징하여 반환합니다.

**파라미터:**

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `label` | string | - | 노드 라벨 필터 |
| `limit` | integer | 50 | 페이지 크기 (1-500) |
| `offset` | integer | 0 | 스킵할 노드 수 |
| `q` | string | - | 이름/제목 검색어 |

**요청:**

```bash
curl "http://localhost:8080/api/v1/nodes?label=Vessel&limit=20&offset=0"
```

**응답:**

```json
{
  "nodes": [
    {
      "id": "4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8",
      "labels": ["Vessel"],
      "primaryLabel": "Vessel",
      "properties": {
        "vesselId": "IMO-1234567",
        "name": "한진셜리"
      },
      "displayName": "한진셜리"
    }
  ],
  "total": 250,
  "limit": 20,
  "offset": 0
}
```

#### 노드 수정

**PUT** `/nodes/{nodeId}`

노드의 속성을 병합하여 업데이트합니다 (MERGE 의미론).

**요청 본문:**

```json
{
  "properties": {
    "lastUpdated": "2024-01-15",
    "grt": 52000
  }
}
```

**요청:**

```bash
curl -X PUT http://localhost:8080/api/v1/nodes/4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"properties": {"lastUpdated": "2024-01-15"}}'
```

**응답:** (200 OK, 업데이트된 노드)

#### 노드 삭제

**DELETE** `/nodes/{nodeId}`

노드와 그 모든 관계를 삭제합니다 (DETACH DELETE).

**요청:**

```bash
curl -X DELETE http://localhost:8080/api/v1/nodes/4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8 \
  -H "Authorization: Bearer $TOKEN"
```

**응답:** (200 OK)

```json
{
  "deleted": true,
  "nodeId": "4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8"
}
```

---

### 관계 CRUD

#### 관계 생성

**POST** `/relationships`

두 노드 사이에 관계를 생성합니다.

**요청 본문:**

```json
{
  "sourceId": "4:node1-id",
  "targetId": "4:node2-id",
  "type": "DOCKED_AT",
  "properties": {
    "dockingTime": "2024-01-15T08:30:00Z",
    "duration": 48
  }
}
```

**파라미터:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `sourceId` | string | 시작 노드 element ID |
| `targetId` | string | 대상 노드 element ID |
| `type` | string | 관계 타입 (SCREAMING_SNAKE_CASE) |
| `properties` | object | 관계 속성 (선택) |

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/relationships \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sourceId": "4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8",
    "targetId": "4:b9f2cf3f-2345-6789-b2c3-d4e5f6g7h8i9",
    "type": "DOCKED_AT"
  }'
```

**응답:** (201 Created)

```json
{
  "relationship": {
    "id": "5:r1e2d3c4-5678-90ab-cdef-1234567890ab",
    "type": "DOCKED_AT",
    "sourceId": "4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8",
    "targetId": "4:b9f2cf3f-2345-6789-b2c3-d4e5f6g7h8i9",
    "properties": {}
  },
  "sourceNode": { /* 시작 노드 */ },
  "targetNode": { /* 대상 노드 */ }
}
```

#### 관계 조회

**GET** `/relationships/{relationshipId}`

단일 관계를 조회합니다.

**요청:**

```bash
curl http://localhost:8080/api/v1/relationships/5:r1e2d3c4-5678-90ab-cdef-1234567890ab
```

**응답:** (관계 생성 응답과 동일)

#### 관계 목록 조회

**GET** `/relationships?type=DOCKED_AT&sourceId={nodeId}&limit=50`

관계를 필터링하여 조회합니다.

**파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `type` | string | 관계 타입 필터 |
| `sourceId` | string | 시작 노드 필터 |
| `targetId` | string | 대상 노드 필터 |
| `limit` | integer | 최대 결과 수 (1-500) |
| `offset` | integer | 스킵할 개수 |

**요청:**

```bash
curl "http://localhost:8080/api/v1/relationships?type=DOCKED_AT&limit=20"
```

**응답:**

```json
{
  "relationships": [
    {
      "id": "5:r1e2d3c4-5678-90ab-cdef-1234567890ab",
      "type": "DOCKED_AT",
      "sourceId": "4:a8e1be2e-1234-5678-a1b2-c3d4e5f6g7h8",
      "targetId": "4:b9f2cf3f-2345-6789-b2c3-d4e5f6g7h8i9",
      "properties": {}
    }
  ],
  "total": 128,
  "limit": 20,
  "offset": 0
}
```

#### 관계 수정

**PUT** `/relationships/{relationshipId}`

관계 속성을 업데이트합니다.

**요청 본문:**

```json
{
  "properties": {
    "duration": 72
  }
}
```

**요청:**

```bash
curl -X PUT http://localhost:8080/api/v1/relationships/5:r1e2d3c4-5678-90ab-cdef-1234567890ab \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"properties": {"duration": 72}}'
```

**응답:** (200 OK, EdgeResponse)

#### 관계 삭제

**DELETE** `/relationships/{relationshipId}`

관계를 삭제합니다.

**요청:**

```bash
curl -X DELETE http://localhost:8080/api/v1/relationships/5:r1e2d3c4-5678-90ab-cdef-1234567890ab \
  -H "Authorization: Bearer $TOKEN"
```

**응답:** (200 OK)

```json
{
  "deleted": true,
  "relationshipId": "5:r1e2d3c4-5678-90ab-cdef-1234567890ab"
}
```

---

### Cypher 실행

#### Cypher 실행

**POST** `/cypher/execute`

Cypher 쿼리를 실행합니다. 위험한 작업(DROP, DETACH DELETE 등)은 차단됩니다.

**요청 본문:**

```json
{
  "cypher": "MATCH (v:Vessel)-[r:DOCKED_AT]->(p:Port) RETURN v.name, p.name LIMIT 10",
  "parameters": {}
}
```

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/cypher/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cypher": "MATCH (v:Vessel) WHERE v.grt > $minGrt RETURN v.name, v.grt",
    "parameters": {"minGrt": 50000}
  }'
```

**응답:**

```json
{
  "results": [
    {
      "v.name": "한진셜리",
      "v.grt": 50000
    },
    {
      "v.name": "마스크로이얄",
      "v.grt": 65000
    }
  ],
  "columns": ["v.name", "v.grt"],
  "rowCount": 2,
  "executionTimeMs": 12.5
}
```

**에러 (403):**

```json
{
  "status": 403,
  "detail": "Query contains a disallowed operation: \\bDROP\\b"
}
```

#### Cypher 검증

**POST** `/cypher/validate`

Cypher 쿼리를 실행 없이 검증합니다.

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/cypher/validate \
  -H "Content-Type: application/json" \
  -d '{
    "cypher": "MATCH (v:Vessel) RETURN v"
  }'
```

**응답:**

```json
{
  "valid": true,
  "errors": [],
  "queryType": "read"
}
```

**응답 (검증 실패):**

```json
{
  "valid": false,
  "errors": ["Missing RETURN clause"],
  "queryType": "write"
}
```

#### Cypher 실행 계획

**POST** `/cypher/explain`

쿼리의 실행 계획을 반환합니다 (실행하지 않음).

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/cypher/explain \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cypher": "MATCH (v:Vessel) RETURN v"
  }'
```

**응답:**

```json
{
  "plan": {
    "operator": "ProduceResults",
    "identifiers": ["v"],
    "children": [
      {
        "operator": "AllNodesScan"
      }
    ]
  },
  "estimatedRows": 250
}
```

---

### 자연어 질의

#### 한국어 질의 실행

**POST** `/query`

한국어 자연언어를 Cypher로 변환하여 실행합니다.

**요청 본문:**

```json
{
  "text": "한진셜리가 언제 항구에 입항했나요?",
  "execute": true,
  "limit": 10
}
```

**파라미터:**

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `text` | string | - | 한국어 질의 (필수) |
| `execute` | boolean | true | Cypher 실행 여부 |
| `limit` | integer | 10 | 반환 행 수 제한 |

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "GRT가 50000 이상인 선박 목록",
    "execute": true,
    "limit": 20
  }'
```

**응답:**

```json
{
  "input_text": "GRT가 50000 이상인 선박 목록",
  "confidence": 0.92,
  "generated_cypher": "MATCH (v:Vessel) WHERE v.grt >= 50000 RETURN v.name, v.grt",
  "parameters": {},
  "results": [
    {
      "name": "한진셜리",
      "grt": 50000
    }
  ],
  "parse_details": {
    "entities": [
      {"text": "GRT", "type": "attribute"},
      {"text": "50000", "type": "value"}
    ]
  },
  "error": null
}
```

---

### RAG (Retrieval-Augmented Generation)

#### RAG 쿼리

**POST** `/rag/query`

하이브리드 RAG 엔진으로 문서를 검색합니다.

**요청 본문:**

```json
{
  "query": "해양 안전 규정",
  "mode": "hybrid",
  "top_k": 5
}
```

**파라미터:**

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `query` | string | - | 검색 쿼리 |
| `mode` | string | `hybrid` | `semantic`, `keyword`, `hybrid` |
| `top_k` | integer | 5 | 반환 청크 수 (1-50) |

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/rag/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "선박 안전",
    "mode": "hybrid",
    "top_k": 5
  }'
```

**응답:**

```json
{
  "query": "선박 안전",
  "answer": "선박 안전은 IMO 규정에 따라 정기적인 검사와 문서화를 요구합니다...",
  "chunks": [
    {
      "content": "해양 안전 관리 규정 제1장...",
      "doc_id": "doc-001",
      "score": 0.92
    }
  ],
  "scores": [0.92, 0.87],
  "mode": "hybrid",
  "total_chunks": 2
}
```

#### 문서 업로드

**POST** `/rag/documents`

RAG 엔진에 문서를 인제스트합니다.

**요청 본문:**

```json
{
  "title": "해양 안전 가이드",
  "content": "해양 안전 관리 규정... (전체 문서 텍스트)",
  "doc_type": "txt",
  "metadata": {
    "source": "IMO",
    "year": 2023
  }
}
```

**파라미터:**

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `title` | string | - | 문서 제목 |
| `content` | string | - | 문서 내용 |
| `doc_type` | string | `txt` | `txt`, `markdown`, `html`, `csv` |
| `metadata` | object | {} | 메타데이터 |

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/rag/documents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "선박 운영 매뉴얼",
    "content": "제1장 기본 안전...",
    "doc_type": "txt"
  }'
```

**응답:** (201 Created)

```json
{
  "doc_id": "a1b2c3d4e5f6g7h8",
  "title": "선박 운영 매뉴얼",
  "chunks_created": 12,
  "message": "Document ingested successfully"
}
```

#### RAG 엔진 상태

**GET** `/rag/status`

RAG 엔진의 가용성 상태를 확인합니다.

**요청:**

```bash
curl http://localhost:8080/api/v1/rag/status
```

**응답:**

```json
{
  "available": true,
  "engine": "HybridRAGEngine",
  "retriever": "SimpleRetriever"
}
```

---

### Agent (대화 에이전트)

#### Agent와 대화

**POST** `/agent/chat`

ReAct 에이전트와 대화합니다.

**요청 본문:**

```json
{
  "message": "한진셜리의 현재 위치를 알려주세요",
  "mode": "react",
  "max_steps": 5
}
```

**파라미터:**

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `message` | string | - | 사용자 메시지 |
| `mode` | string | `react` | `react`, `pipeline` |
| `max_steps` | integer | 5 | 최대 실행 단계 (1-20) |

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/agent/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "2024년 1월의 선박 입항 통계",
    "mode": "react",
    "max_steps": 5
  }'
```

**응답:**

```json
{
  "message": "2024년 1월의 선박 입항 통계",
  "answer": "2024년 1월에는 총 35척의 선박이 입항했습니다...",
  "steps": [
    {
      "thought": "질의를 분석해야 합니다.",
      "action": "query_kg",
      "observation": "데이터베이스에서 검색 완료"
    }
  ],
  "tools_used": ["query_kg", "summarize"],
  "mode": "react"
}
```

#### 도구 직접 실행

**POST** `/agent/tools/execute`

특정 도구를 직접 실행합니다.

**요청 본문:**

```json
{
  "tool_name": "query_kg",
  "parameters": {
    "cypher": "MATCH (v:Vessel) RETURN count(v)"
  }
}
```

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/agent/tools/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "query_kg",
    "parameters": {"cypher": "MATCH (n) RETURN count(n)"}
  }'
```

**응답:**

```json
{
  "tool_name": "query_kg",
  "success": true,
  "output": "{\"count\": 2458}",
  "error": null
}
```

#### 도구 목록

**GET** `/agent/tools`

사용 가능한 모든 도구를 반환합니다.

**요청:**

```bash
curl http://localhost:8080/api/v1/agent/tools
```

**응답:**

```json
{
  "tools": [
    {
      "name": "query_kg",
      "description": "지식 그래프에서 Cypher 쿼리 실행",
      "parameters": {
        "cypher": {"type": "string", "description": "Cypher 쿼리"}
      }
    },
    {
      "name": "search",
      "description": "그래프에서 노드 검색",
      "parameters": {
        "query": {"type": "string"}
      }
    }
  ]
}
```

#### Agent 상태

**GET** `/agent/status`

Agent 런타임의 가용성을 확인합니다.

**요청:**

```bash
curl http://localhost:8080/api/v1/agent/status
```

**응답:**

```json
{
  "available": true,
  "engines": ["react", "pipeline"],
  "tools_count": 8
}
```

---

### 임베딩 / 벡터 검색

#### 벡터 검색

**POST** `/embeddings/search`

Neo4j 벡터 인덱스에서 유사도 검색을 수행합니다.

**요청 본문:**

```json
{
  "label": "Vessel",
  "property": "description",
  "queryVector": [0.1, 0.2, 0.3, ...],
  "topK": 5
}
```

**파라미터:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `label` | string | 노드 라벨 |
| `property` | string | 임베딩 속성명 |
| `queryVector` | array | 쿼리 벡터 (float array) |
| `topK` | integer | 반환 결과 수 (1-50) |

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/embeddings/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Vessel",
    "property": "embedding",
    "queryVector": [0.1, 0.2, ...],
    "topK": 5
  }'
```

**응답:**

```json
{
  "results": [
    {
      "node": {
        "id": "4:...",
        "labels": ["Vessel"],
        "properties": {"name": "한진셜리"}
      },
      "score": 0.92
    }
  ],
  "meta": {
    "algorithm": "cosine",
    "topK": 5,
    "indexName": "vessel_embedding_index"
  }
}
```

#### 하이브리드 검색

**POST** `/embeddings/hybrid`

벡터 검색 + 전문(fulltext) 검색을 Reciprocal Rank Fusion으로 결합합니다.

**요청 본문:**

```json
{
  "label": "Vessel",
  "property": "description",
  "queryVector": [0.1, 0.2, ...],
  "textQuery": "컨테이너선",
  "topK": 5
}
```

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/embeddings/hybrid \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Vessel",
    "property": "embedding",
    "queryVector": [...],
    "textQuery": "컨테이너",
    "topK": 5
  }'
```

**응답:**

```json
{
  "results": [...],
  "meta": {
    "fusion": "rrf",
    "topK": 5,
    "vectorIndex": "vessel_embedding_index",
    "fulltextIndex": "vessel_fulltext_index",
    "textQuery": "컨테이너"
  }
}
```

#### 벡터 인덱스 목록

**GET** `/embeddings/indexes`

모든 등록된 벡터 인덱스를 반환합니다.

**요청:**

```bash
curl http://localhost:8080/api/v1/embeddings/indexes
```

**응답:**

```json
{
  "indexes": [
    {
      "name": "vessel_description_index",
      "label": "Vessel",
      "property": "description",
      "dimensions": 1536,
      "similarityFunction": "cosine",
      "status": "active",
      "nodeCount": 250,
      "createdAt": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### 벡터 인덱스 생성

**POST** `/embeddings/indexes`

새로운 벡터 인덱스를 생성합니다.

**요청 본문:**

```json
{
  "label": "Vessel",
  "property": "description",
  "dimensions": 1536,
  "similarity": "cosine"
}
```

**파라미터:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `label` | string | 노드 라벨 |
| `property` | string | 임베딩 속성명 |
| `dimensions` | integer | 벡터 차원 (예: 1536 for OpenAI) |
| `similarity` | string | 유사도 함수 (`cosine`, `euclidean`) |

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/embeddings/indexes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Port",
    "property": "embedding",
    "dimensions": 1536,
    "similarity": "cosine"
  }'
```

**응답:** (201 Created)

```json
{
  "created": true,
  "indexName": "port_embedding_index",
  "cypher": "CREATE VECTOR INDEX port_embedding_index ...",
  "label": "Port",
  "property": "embedding",
  "dimensions": 1536,
  "similarity": "cosine"
}
```

---

### 그래프 알고리즘

#### 알고리즘 목록

**GET** `/algorithms`

지원하는 모든 GDS 알고리즘을 반환합니다.

**요청:**

```bash
curl http://localhost:8080/api/v1/algorithms
```

**응답:**

```json
{
  "algorithms": [
    "pagerank",
    "louvain",
    "betweenness",
    "dijkstra",
    "nodeSimilarity"
  ]
}
```

#### PageRank 실행

**POST** `/algorithms/pagerank`

PageRank 중심성 알고리즘을 실행합니다.

**요청 본문:**

```json
{
  "label": "Vessel",
  "relationshipType": "DOCKED_AT",
  "iterations": 20,
  "dampingFactor": 0.85
}
```

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/algorithms/pagerank \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Vessel",
    "relationshipType": "DOCKED_AT",
    "iterations": 20,
    "dampingFactor": 0.85
  }'
```

**응답:**

```json
{
  "algorithm": "pagerank",
  "results": [
    {
      "node": {"id": "4:...", "labels": ["Vessel"]},
      "score": 2.45
    }
  ],
  "cypher": "CALL gds.pagerank.stream...",
  "meta": {
    "iterations": 20,
    "dampingFactor": 0.85
  }
}
```

#### 커뮤니티 감지 (Louvain)

**POST** `/algorithms/community`

Louvain 알고리즘으로 커뮤니티를 감지합니다.

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/algorithms/community \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Vessel",
    "relationshipType": "DOCKED_AT"
  }'
```

#### 중심성 (Betweenness)

**POST** `/algorithms/centrality`

Betweenness Centrality로 브릿지 노드를 식별합니다.

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/algorithms/centrality \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Port",
    "relationshipType": "CONNECTED_TO"
  }'
```

#### 최단 경로 (Dijkstra)

**POST** `/algorithms/shortest-path`

두 노드 사이의 최단 경로를 찾습니다.

**요청 본문:**

```json
{
  "relationshipType": "DOCKED_AT",
  "sourceId": "4:node1-id",
  "targetId": "4:node2-id",
  "weightProperty": "distance"
}
```

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/algorithms/shortest-path \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "relationshipType": "DOCKED_AT",
    "sourceId": "4:...",
    "targetId": "4:...",
    "weightProperty": "distance"
  }'
```

#### 노드 유사도 (Jaccard)

**POST** `/algorithms/similarity`

Jaccard 계수로 노드 유사도를 계산합니다.

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/algorithms/similarity \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Vessel",
    "relationshipType": "DOCKED_AT",
    "topK": 10
  }'
```

#### GDS 상태 확인

**GET** `/algorithms/gds-status`

Neo4j Graph Data Science 플러그인의 가용성을 확인합니다.

**요청:**

```bash
curl http://localhost:8080/api/v1/algorithms/gds-status
```

**응답:**

```json
{
  "available": true,
  "version": "2.5.0"
}
```

---

### 데이터 리니지

#### 전체 리니지 조회

**GET** `/lineage/{entityType}/{entityId}`

엔티티의 전체 리니지(상위 + 하위)를 조회합니다.

**파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `entityType` | string | 엔티티 라벨 (예: Vessel) |
| `entityId` | string | 엔티티 식별자 (예: IMO-1234567) |

**요청:**

```bash
curl "http://localhost:8080/api/v1/lineage/Vessel/IMO-1234567"
```

**응답:**

```json
{
  "nodes": [
    {
      "nodeId": "4:...",
      "entityType": "Vessel",
      "entityId": "IMO-1234567",
      "createdAt": "2024-01-10T08:00:00Z"
    }
  ],
  "edges": [
    {
      "edgeId": "5:...",
      "eventType": "CREATED",
      "agent": "system",
      "activity": "vessel_registration"
    }
  ],
  "meta": {
    "entityType": "Vessel",
    "entityId": "IMO-1234567",
    "nodeCount": 5,
    "edgeCount": 4
  }
}
```

#### 상위 리니지 (Ancestors)

**GET** `/lineage/{entityType}/{entityId}/ancestors`

엔티티의 모든 소스(상위)를 조회합니다.

**요청:**

```bash
curl "http://localhost:8080/api/v1/lineage/Vessel/IMO-1234567/ancestors"
```

**응답:**

```json
{
  "nodes": [
    {
      "nodeId": "4:...",
      "entityType": "Port",
      "entityId": "PORT-001",
      "createdAt": "2024-01-10T07:00:00Z",
      "depth": 1
    }
  ],
  "meta": {
    "direction": "ancestors",
    "count": 3
  }
}
```

#### 하위 리니지 (Descendants)

**GET** `/lineage/{entityType}/{entityId}/descendants`

엔티티의 모든 파생(하위)을 조회합니다.

**요청:**

```bash
curl "http://localhost:8080/api/v1/lineage/Vessel/IMO-1234567/descendants"
```

#### 리니지 타임라인

**GET** `/lineage/{entityType}/{entityId}/timeline`

엔티티의 모든 변경 이벤트를 시간순으로 조회합니다.

**요청:**

```bash
curl "http://localhost:8080/api/v1/lineage/Vessel/IMO-1234567/timeline"
```

**응답:**

```json
{
  "events": [
    {
      "edgeId": "5:...",
      "eventType": "REGISTERED",
      "agent": "admin",
      "activity": "vessel_registration",
      "timestamp": "2024-01-10T08:00:00Z"
    },
    {
      "edgeId": "5:...",
      "eventType": "DOCKED",
      "agent": "port_system",
      "activity": "port_arrival",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ],
  "meta": {
    "eventCount": 5
  }
}
```

---

### ETL 파이프라인

#### ETL 트리거

**POST** `/etl/trigger`

ETL 파이프라인을 수동으로 트리거합니다.

**요청 본문:**

```json
{
  "source": "manual",
  "pipeline_name": "papers",
  "mode": "incremental",
  "force_full": false
}
```

**파라미터:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `source` | string | 트리거 소스 (`manual`, `schedule`, `webhook`, `file_watcher`) |
| `pipeline_name` | string | 파이프라인 이름 |
| `mode` | string | `full` 또는 `incremental` |
| `force_full` | boolean | 증분 무시하고 전체 재구축 |

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/etl/trigger \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "manual",
    "pipeline_name": "papers",
    "mode": "incremental"
  }'
```

**응답:** (201 Created)

```json
{
  "run_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
  "pipeline_name": "papers",
  "status": "COMPLETED",
  "message": "Pipeline papers completed successfully"
}
```

#### ETL 상태 조회

**GET** `/etl/status/{runId}`

특정 ETL 실행의 상태를 조회합니다.

**요청:**

```bash
curl "http://localhost:8080/api/v1/etl/status/a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"
```

**응답:**

```json
{
  "run_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
  "pipeline_name": "papers",
  "status": "COMPLETED",
  "records_processed": 150,
  "records_failed": 2,
  "records_skipped": 5,
  "duration_seconds": 45.2,
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:01:00Z",
  "errors": []
}
```

#### ETL 실행 이력

**GET** `/etl/history?limit=20`

최근 ETL 실행 이력을 조회합니다.

**파라미터:**

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `limit` | integer | 20 | 반환 실행 수 (1-100) |

**요청:**

```bash
curl "http://localhost:8080/api/v1/etl/history?limit=10"
```

**응답:**

```json
{
  "runs": [
    {
      "run_id": "...",
      "pipeline_name": "papers",
      "status": "COMPLETED",
      "records_processed": 150
    }
  ],
  "total": 147
}
```

#### ETL 파이프라인 목록

**GET** `/etl/pipelines`

사용 가능한 모든 파이프라인을 반환합니다.

**요청:**

```bash
curl http://localhost:8080/api/v1/etl/pipelines
```

**응답:**

```json
[
  {
    "name": "papers",
    "description": "KRISO ScholarWorks 논문 크롤링",
    "schedule": "0 2 * * 6",
    "entity_type": "Document"
  },
  {
    "name": "accidents",
    "description": "해양사고 데이터 수집",
    "schedule": "0 4 * * *",
    "entity_type": "Incident"
  }
]
```

#### 웹훅 트리거

**POST** `/etl/webhook/{source}`

외부 시스템으로부터 웹훅을 수신하여 ETL을 트리거합니다.

**파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `source` | string | 파이프라인 이름 (URL 경로) |

**요청:**

```bash
curl -X POST http://localhost:8080/api/v1/etl/webhook/papers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "data_changed",
    "entity_type": "Document",
    "data": {"count": 5}
  }'
```

**응답:** (ETL 트리거와 동일)

---

## 예제

### 예제 1: 선박 정보 조회 및 수정

```bash
# 1단계: 선박 검색
curl "http://localhost:8080/api/v1/search?q=한진셜리&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# 응답에서 node ID 추출 (예: 4:abc123def456...)

# 2단계: 선박 상세 정보 조회
curl "http://localhost:8080/api/v1/nodes/4:abc123def456..." \
  -H "Authorization: Bearer $TOKEN"

# 3단계: 선박 정보 업데이트
curl -X PUT "http://localhost:8080/api/v1/nodes/4:abc123def456..." \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "properties": {
      "lastUpdated": "2024-01-20",
      "status": "in_port"
    }
  }'

# 4단계: 이웃 노드 조회 (연결된 항구, 운영사 등)
curl "http://localhost:8080/api/v1/neighbors?nodeId=4:abc123def456..." \
  -H "Authorization: Bearer $TOKEN"
```

### 예제 2: 자연어로 데이터 조회

```bash
# 한국어 질의로 데이터 검색
curl -X POST "http://localhost:8080/api/v1/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "2024년 1월에 부산 항구에 입항한 선박 목록",
    "execute": true,
    "limit": 20
  }'

# 응답: 자동 생성된 Cypher + 결과
```

### 예제 3: PageRank로 중요한 항구 찾기

```bash
# PageRank 실행
curl -X POST "http://localhost:8080/api/v1/algorithms/pagerank" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Port",
    "relationshipType": "CONNECTED_TO",
    "iterations": 20,
    "dampingFactor": 0.85
  }'

# 응답: 각 항구의 PageRank 점수 (높을수록 중요)
```

---

## 인증 및 보안

### OAuth2 토큰 획득

```bash
# Step 1: Keycloak에서 토큰 획득
TOKEN=$(curl -X POST http://localhost:8180/realms/imsp/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=imsp-api" \
  -d "username=$USERNAME" \
  -d "password=$PASSWORD" \
  -d "client_secret=$CLIENT_SECRET" | jq -r '.access_token')

# Step 2: 토큰으로 API 호출
curl "http://localhost:8080/api/v1/health" \
  -H "Authorization: Bearer $TOKEN"
```

### CORS

Gateway는 CORS 헤더를 설정합니다:

```
Access-Control-Allow-Origin: (CORS_ALLOWED_ORIGINS 환경변수 기반)
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
```

---

## 문제 해결

### "Connection refused" (연결 거부)

API가 실행 중이지 않습니다:

```bash
docker compose -f infra/docker-compose.yml ps api
docker compose -f infra/docker-compose.yml logs api
make docker-up
```

### "Unauthorized" (인증 오류)

토큰이 만료되었거나 유효하지 않습니다:

```bash
# 새로운 토큰 획득
TOKEN=$(curl ... | jq -r '.access_token')

# 토큰 검증
curl "http://localhost:8180/realms/imsp/protocol/openid-connect/userinfo" \
  -H "Authorization: Bearer $TOKEN"
```

### "Service Unavailable" (GDS 미설치)

Neo4j에 GDS 플러그인이 설치되지 않았습니다. 알고리즘 엔드포인트는 사용 불가:

```bash
# GDS 상태 확인
curl http://localhost:8080/api/v1/algorithms/gds-status

# Neo4j 콘솔에서 수동 확인
curl -u neo4j:$PASSWORD http://localhost:7474/db/data/ | jq '.extensions'
```

---

## 추가 리소스

- [Neo4j Cypher 문서](https://neo4j.com/docs/cypher-manual/current/)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [RFC 7807 (Problem Details)](https://tools.ietf.org/html/rfc7807)
- [OpenAPI/Swagger 스펙](http://localhost:8000/docs)

---

**마지막 업데이트:** 2024년 1월 20일
**API 버전:** 0.1.0
**상태:** 개발 중 (실험적 기능)
