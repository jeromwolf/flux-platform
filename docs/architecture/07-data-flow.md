# 7. 데이터 흐름도

[← 보안 아키텍처](./06-security-architecture.md) | [다음: Suredata Lab 연동 →](./08-suredata-integration.md)

## 개요

IMSP 플랫폼의 데이터 흐름은 크게 4가지 주요 경로로 구성된다: (1) 자연어 질의를 Cypher로 변환하여 지식그래프를 조회하는 **Text2Cypher Pipeline**, (2) 외부 데이터 소스에서 원본을 수집/보존한 뒤 AI 분석을 거쳐 KG에 적재하는 **ELT 데이터 흐름**, (3) VueFlow 캔버스에서 설계한 워크플로우를 Argo DAG로 변환하여 실행하는 **워크플로우 실행 흐름**, (4) Protege 온톨로지 설계 도구와 Neo4j 사이의 **OWL 동기화 흐름**이다. 본 문서는 각 흐름의 상세 단계와 Latency Budget, 에러 핸들링 경로를 기술한다.

---

## 7.1 자연어 쿼리 흐름 (Text2Cypher Pipeline)

```
사용자: "부산항 근처에 정박 중인 대형 선박을 알려줘"
    |
    v HTTP POST /api/v1/query/nl
    |
    +-- Auth Middleware    (API Key 또는 JWT 검증)
    +-- Metrics Middleware (요청 시간 측정, Zipkin Span 시작)
    |
    v TextToCypherPipeline.process()
    |
    +-- Stage 1: NLParser.parse()
    |   |  규칙 기반 한국어 토큰화 (KoNLPy 또는 커스텀 토크나이저)
    |   |  TermDictionary 조회:
    |   |    "부산항" -> Port (신뢰도 0.99)
    |   |    "선박"   -> Vessel (신뢰도 0.97)
    |   |    "정박"   -> DOCKED_AT (신뢰도 0.93)
    |   |    "대형"   -> tonnage > threshold (필터)
    |   \-> StructuredQuery {
    |         entities: [Port("부산항"), Vessel],
    |         relationships: [DOCKED_AT],
    |         filters: [{field: tonnage, op: >, value: 50000}]
    |       }
    |
    +-- Stage 2: QueryGenerator.generate_cypher()
    |   \-> MATCH (p:Port {name: '부산항'})<-[:DOCKED_AT]-(v:Vessel)
    |        WHERE v.tonnage > 50000
    |        RETURN v.name, v.type, v.tonnage
    |        ORDER BY v.tonnage DESC LIMIT 20
    |
    +-- Stage 3: CypherValidator.validate()
    |   |  [1] 구문 검증  : Cypher 파서 AST 검증
    |   |  [2] 스키마 검증: Port, Vessel, DOCKED_AT 존재 여부
    |   |  [3] 속성 검증  : name, tonnage 유효한 속성
    |   |  [4] 타입 검증  : tonnage -> 숫자형 비교 적합
    |   |  [5] 보안 검증  : Injection 패턴 없음
    |   |  [6] 성능 검증  : Port.name 인덱스 활용 가능
    |   \-> ValidationResult { valid: true, score: 0.95, checks_passed: 6/6 }
    |
    +-- Stage 4: CypherCorrector.correct()  [Stage 3 실패 시에만 실행]
    |   \-> 규칙 기반 교정 (속성명 오타, 레이블 케이스 등) 적용
    |
    +-- Stage 5: HallucinationDetector.validate()
    |   |  "부산항" 실제 존재? -> Neo4j MATCH 확인 -> FOUND
    |   |  "DOCKED_AT" 관계 타입 존재? -> 온톨로지 확인 -> VALID
    |   \-> DetectionResult { hallucinated: [], confidence: 0.98 }
    |
    v Neo4j Driver.run(cypher, params)
    |
    v 결과 직렬화
    |   +-- spatial: Point(latitude, longitude) -> {"lat": ..., "lng": ...}
    |   +-- temporal: datetime -> ISO 8601 문자열
    |   \-- 페이지네이션: cursor 기반 (skip/limit)
    |
    v NLQueryResponse {
        cypher: "MATCH ...",
        results: [...],
        confidence: 0.95,
        execution_time_ms: 42,
        trace_id: "abc-123"
      }
```

### 코드 매핑

| 파이프라인 단계 | 코드베이스 위치 | 비고 |
|---------------|---------------|------|
| TextToCypherPipeline | `core/kg/pipeline.py` | 전체 파이프라인 오케스트레이션 |
| NLParser | `core/kg/nlp/nl_parser.py` | 규칙 기반 NL 파서 + TermDictionary Protocol |
| QueryGenerator | `core/kg/query_generator.py` | 다중 언어 쿼리 생성기 |
| CypherValidator | `core/kg/cypher_validator.py` | 6가지 검증 (구문/스키마/속성/타입/보안/성능) |
| CypherCorrector | `core/kg/cypher_corrector.py` | 규칙 기반 + LLM Fallback 교정 |
| HallucinationDetector | `core/kg/hallucination_detector.py` | Neo4j 실재 확인 + 온톨로지 검증 |

### Latency Budget 분석

Text2Cypher 파이프라인의 전체 응답 시간 목표(SLO)는 **5초 이내**이다. 각 Stage별 Latency Budget은 다음과 같다:

| Stage | 처리 방식 | 예상 Latency | 비고 |
|-------|----------|-------------|------|
| Auth + Metrics Middleware | JWT/API Key 검증 | ~5ms | 인메모리 검증 |
| Stage 1: NLParser.parse() | 규칙 기반 토큰화 + 사전 조회 | **~50ms** | KoNLPy 또는 커스텀 토크나이저, TermDictionary 인메모리 캐시 |
| Stage 2: QueryGenerator.generate_cypher() | LLM 호출 (Ollama) | **~2-3s** | 가장 긴 구간. Y1 CPU 서빙 시 최대 5s까지 가능 |
| Stage 3: CypherValidator.validate() | 규칙 기반 AST 검증 | **~10ms** | 6개 검증 항목 병렬 처리 가능 |
| Stage 4: CypherCorrector.correct() | 규칙 기반 교정 | **~100ms** | Stage 3 실패 시에만 실행. LLM Fallback 시 ~2s 추가 |
| Stage 5: HallucinationDetector.validate() | Neo4j 조회 확인 | **~50ms** | 엔티티 존재 여부 MATCH 쿼리 |
| Neo4j Driver.run() | 쿼리 실행 | **~50-200ms** | 인덱스 활용 시 50ms, 풀스캔 시 200ms+ |
| 결과 직렬화 + 응답 | JSON 변환 | ~5ms | spatial/temporal 변환 포함 |
| **Total** | | **< 5s** | SLO 목표 |

**Latency 최적화 전략:**

| 전략 | 대상 Stage | 예상 효과 |
|------|-----------|----------|
| TermDictionary 프리로드 | Stage 1 | 사전 조회 50ms -> 5ms |
| LLM 응답 캐싱 (동일 패턴) | Stage 2 | 반복 질의 2-3s -> 10ms |
| GPU 서빙 전환 (Y2) | Stage 2 | CPU 5s -> GPU 0.5-1s |
| Cypher 결과 캐싱 (Redis) | Neo4j 실행 | 동일 쿼리 50-200ms -> 1ms |

### Dual-Path Query Router (3차년도 계획)

```
사용자 질문
    |
    v Intent Classifier (LLM 기반 분류)
    |
    +-- "Structured Query" -----> Direct Path
    |   (엔티티/관계 명확)         CypherBuilder
    |                              빠름, 확정적
    |
    +-- "Complex Reasoning" ---> LLM Path
    |   (자연어 추론 필요)          Text2Cypher (LLM)
    |                              유연, 오류 가능성
    |
    \-- "Knowledge Search" ----> RAG Path
        (배경 지식 필요)            GraphRAG
                                   풍부한 컨텍스트
    |
    v 라우팅된 결과 수집
    |
    v 응답 합성 (LLM 기반 자연어 생성)
    |
    v 최종 응답 반환
```

---

## 7.2 ELT 데이터 흐름

```
외부 데이터 소스                     IMSP Platform
+-------------------+
| AIS 수신기         |--NMEA--+
| 기상 API (KMA)    |--REST--+
| S-100 해도 (IHO)  |--GML---+
| 해양 법규 DB       |--REST--+     +--------------+        +----------+
| 위성 영상 (KOMPSAT)|--SFTP--+---> | Collection   |--Raw-->|  Object  |
| CCTV / 항만 카메라 |--RTSP--+     | Adapters     |        | Storage  |
| 레이더 데이터       |--Kafka-+     | (어댑터 패턴) |        | (Ceph)   |
| 사고 DB (MSC)     |--REST--+     +--------------+        +----+-----+
+-------------------+                                           |
                                                                v
                                                    +-------------------+
                                                    | Metadata          |
                                                    | Extraction        |
                                                    | EXIF, GPS,        |
                                                    | 파일 해시, 수집 시각|
                                                    +--------+----------+
                                                             |
                                                             v
                                               +-------------------------+
                                               |  AI Content Analysis    |
                                               |                         |
                                               | PaddleOCR  -> 텍스트    |
                                               | NER Model  -> 엔티티    |
                                               | RE Model   -> 관계      |
                                               | Embedding  -> 768d 벡터 |
                                               | S-100 Parser -> 해도    |
                                               +------------+------------+
                                                            |
                                              +-------------+-------------+
                                              |             |             |
                                              v             v             v
                                         +--------+   +--------+   +----------+
                                         | Neo4j  |   | Object |   | Postgres |
                                         | KG     |   |Storage |   | 마트/DW  |
                                         | 엔티티 |   | 보존   |   | (Suredata|
                                         | 관계   |   |        |   |  Lab)    |
                                         | 벡터   |   |        |   |          |
                                         | 리니지 |   |        |   |          |
                                         +--------+   +--------+   +----------+
```

### 코드 매핑

| ELT 구성요소 | 코드베이스 위치 | 비고 |
|-------------|---------------|------|
| Collection Adapters | `core/kg/etl/` | 어댑터 패턴 기반 수집기 |
| 데이터 크롤러 | `domains/maritime/crawlers/` | 해사 도메인 특화 크롤러 |
| S-100 매핑 | `domains/maritime/s100/` | IHO S-100 해도 파서 |
| 리니지 기록 | `core/kg/lineage/` | W3C PROV-O 형식 |

### ETL -> ELT 전환 전략 (2차년도)

| 현재 (ETL) | 목표 (ELT) | 이유 |
|-----------|-----------|------|
| 수집 시 변환 | 원본 저장 후 변환 | 재처리 가능성, 스키마 변경 대응 |
| 파이프라인 내 변환 로직 | KG 구축 시 변환 | 분리된 관심사, 테스트 용이 |
| 단일 파이프라인 | 원본 보존 + 다중 뷰 | 다양한 분석 요구 대응 |

---

## 7.3 워크플로우 실행 흐름

```
사용자 (VueFlow 캔버스)
    |
    +-- 노드 드래그 & 드롭 (사전 정의된 노드 팔레트)
    +-- 엣지 연결 (데이터 흐름 정의)
    +-- 속성 패널 입력 (파라미터, 조건, 리소스)
    |
    v JSON Workflow Definition 저장
      { nodes: [...], edges: [...], metadata: {...} }
    |
    v VueFlow -> Argo DAG 변환기 (Python)
    |   +-- 노드 -> Argo Template 매핑 (노드 타입별 컨테이너)
    |   +-- 엣지 -> DAG dependencies 매핑
    |   +-- 속성 -> Argo Parameters / Artifacts 매핑
    |   +-- 조건 엣지 -> Argo when 표현식
    |   \-- 루프 노드 -> Argo withItems / withParam
    |
    v Argo Workflow API 제출
      kubectl apply -f workflow.yaml  또는  argo submit
    |
    v K8s Pod 스케줄링
    |   +-- 데이터 전달: Artifact (Object Storage 경유) / Parameter (인라인)
    |   +-- GPU 노드: nodeSelector gpu-type=a100 적용
    |   +-- 리소스 제한: resources.limits (OOM 방지)
    |   \-- 재시도 정책: retryStrategy (최대 3회, 지수 백오프)
    |
    v 실행 모니터링 (Argo UI + Grafana 대시보드)
    |   +-- 실시간 노드 상태: Pending/Running/Succeeded/Failed
    |   +-- 로그 스트리밍: kubectl logs -f
    |   +-- 이벤트 알림: Slack/이메일 (Alertmanager 연동)
    |   \-- 오류 핸들링: onExit handler, exitCode 기반 분기
    |
    v 결과 반영
        +-- KG 업데이트 (신규 엔티티/관계 추가)
        +-- 리니지 기록 (W3C PROV-O 형식)
        \-- 대시보드 갱신 (WebSocket 푸시)
```

---

## 7.4 OWL <-> Neo4j 동기화 흐름

온톨로지 설계 도구(Protege)와 Neo4j KG 사이의 단방향 동기화 파이프라인이다.
변경 사항은 Protege -> OWL -> Neo4j 방향으로만 흐른다 (Neo4j -> OWL 역방향 동기화 없음).

```
Protege (OWL 2 DL 설계)
    |
    v maritime.ttl (Turtle 형식)
      해상교통 온톨로지: Class, Property, Restriction, SHACL Shape
    |
    v OWL Exporter (owl_exporter.py)
      Python owlready2 -> Turtle/OWL 직렬화
    |
    v n10s Importer (importer.py)
      Neosemantics: n10s.onto.import()
      OWL Class     -> Neo4j (:OntologyClass) 노드
      OWL Property  -> Neo4j (:Relationship) 메타데이터
      OWL Instance  -> Neo4j 도메인 노드
    |
    v CI/CD Auto-Sync (Git Push 트리거)
    |   +-- OWL 파일 변경 감지 (git diff *.ttl)
    |   +-- 의존성 분석 (변경된 클래스 영향 범위)
    |   +-- Python 도메인 모델 자동 생성 (pydantic 스키마)
    |   +-- Neo4j 스키마 마이그레이션 (인덱스/제약조건 업데이트)
    |   +-- 단위 테스트 실행 (온톨로지 일관성 검증)
    |   \-- 불일치 알림: Python 모델 <-> OWL 스키마 드리프트 감지
    |
    v 배포 완료
      Neo4j에 최신 온톨로지 반영, API 서버 재시작 없이 스키마 갱신
```

### 코드 매핑

| 동기화 구성요소 | 코드베이스 위치 | 비고 |
|---------------|---------------|------|
| n10s Importer | `core/kg/n10s/importer.py` | Neosemantics OWL 가져오기 |
| Ontology Framework | `core/kg/ontology/core.py` | 온톨로지 클래스 정의 |
| OntologyBridge | `core/kg/ontology_bridge.py` | 온톨로지 -> KG 변환 브릿지 |
| Maritime Ontology | `domains/maritime/ontology/` | 해사 도메인 온톨로지 (재설계 예정) |

> **제약사항:** 현재 OWL -> Neo4j 단방향 동기화만 지원한다. Neo4j -> OWL 역방향 동기화는 지원하지 않으며, KG 직접 수정 시 OWL과 불일치가 발생할 수 있다. 이 불일치는 CI/CD Auto-Sync의 드리프트 감지 알림으로 탐지할 수 있으나, 자동 복구는 수행하지 않는다. KG 데이터 변경은 반드시 OWL 온톨로지 수정 -> n10s 동기화 경로를 통해 수행하는 것을 권장한다.

---

## 7.5 에러 흐름도

각 데이터 흐름에서 발생할 수 있는 오류 상황과 처리 경로를 정의한다.

### Text2Cypher 실패 흐름

```
TextToCypherPipeline.process()
    |
    +-- Stage 1 실패: NLParser 파싱 오류
    |   +-- 원인: 미등록 용어, 모호한 자연어 표현
    |   +-- 처리: ParseError 반환, 사용자에게 재입력 요청 메시지
    |   |         "질의를 이해하지 못했습니다. 엔티티명을 명확히 해주세요."
    |   \-- 기록: 실패 질의 DLQ(Dead Letter Queue) 적재 (Redis Stream)
    |
    +-- Stage 2 실패: LLM 응답 오류
    |   +-- 원인: Ollama 타임아웃 (>10s), 잘못된 Cypher 생성
    |   +-- 처리: 재시도 1회 -> 실패 시 Fallback 메시지 반환
    |   |         "쿼리 생성에 실패했습니다. 잠시 후 다시 시도해주세요."
    |   \-- 기록: DLQ 적재 + Prometheus 메트릭 (text2cypher_error_total++)
    |
    +-- Stage 3 실패: 검증 실패 (6개 항목 중 하나 이상)
    |   +-- 원인: 잘못된 레이블, 존재하지 않는 속성, Injection 패턴
    |   +-- 처리: Stage 4 (CypherCorrector) 자동 호출
    |   |   +-- 규칙 기반 교정 성공 -> Stage 3 재검증
    |   |   +-- 규칙 기반 교정 실패 -> LLM Fallback 교정 시도
    |   |   +-- LLM Fallback도 실패 -> Fallback 메시지 + DLQ
    |   \-- 기록: 검증 실패 상세 로그 (어떤 항목이 왜 실패했는지)
    |
    +-- Stage 5 실패: Hallucination 감지
    |   +-- 원인: 존재하지 않는 엔티티/관계 참조
    |   +-- 처리: 환각 항목 제거 후 재생성 시도 1회
    |   |         최종 실패 시 "일부 정보를 확인할 수 없습니다" 메시지
    |   \-- 기록: 환각 패턴 분석용 로그 (향후 모델 개선 데이터)
    |
    +-- Neo4j 실행 실패
    |   +-- 원인: 연결 실패, 타임아웃, OOM
    |   +-- 처리: 연결 실패 -> 503 Service Unavailable 반환
    |   |         타임아웃 -> 쿼리 LIMIT 축소 후 재시도 1회
    |   \-- 기록: AlertManager 알림 (Neo4j 장애 시)
    |
    v DLQ (Dead Letter Queue)
        +-- 저장소: Redis Stream (imsp:dlq:text2cypher)
        +-- 보존 기간: 7일
        +-- 용도: 실패 패턴 분석, 모델 재학습 데이터, 디버깅
        +-- 재처리: 관리자가 수동 재처리 또는 배치 재처리 (Daily)
```

### ETL 실패 흐름

```
ETL Pipeline (CronJob)
    |
    +-- 수집(Collection) 실패
    |   +-- 원인: 외부 API 타임아웃, 인증 만료, 네트워크 오류
    |   +-- 처리: 재시도 3회 (지수 백오프: 30s, 60s, 120s)
    |   |         최종 실패 시 DLQ 적재 + AlertManager 알림
    |   \-- 알림: Slack 채널 #imsp-etl-alerts
    |
    +-- 변환(Transform) 실패
    |   +-- 원인: OCR 오류, NER 추출 실패, 데이터 포맷 불일치
    |   +-- 처리: 원본 보존 (Object Storage), 실패 항목 스킵
    |   |         성공 항목만 KG 적재 (partial success 허용)
    |   \-- 기록: etl_audit 테이블에 오류율, 스킵 건수 기록
    |
    +-- 적재(Load) 실패
    |   +-- 원인: Neo4j 연결 실패, 제약조건 위반, 중복 키
    |   +-- 처리: 트랜잭션 롤백, 배치 단위 재시도
    |   |         제약조건 위반 -> MERGE 전략으로 자동 전환
    |   \-- 기록: 적재 실패 건수, 롤백 횟수 PostgreSQL 기록
    |
    v DLQ + 알림
        +-- DLQ: PostgreSQL etl_dlq 테이블
        +-- 알림: AlertManager -> Slack/이메일
        +-- 대시보드: Grafana ETL Status 패널 (성공률, 오류율, 처리량)
        +-- 임계값: 오류율 > 10% 시 CRITICAL 알림
```

### 워크플로우 노드 실패 흐름

```
Argo Workflow DAG 실행
    |
    +-- 노드 실행 실패
    |   +-- Argo retryStrategy 적용:
    |   |     maxRetries: 3
    |   |     retryPolicy: Always (모든 오류에 대해 재시도)
    |   |     backoff:
    |   |       duration: "30s"      # 첫 번째 재시도 대기
    |   |       factor: 2            # 지수 백오프 (30s -> 60s -> 120s)
    |   |       maxDuration: "5m"    # 최대 대기 시간
    |   |
    |   +-- 3회 재시도 후에도 실패
    |   |   +-- onExit handler 실행
    |   |   |   +-- 실패 노드 상태 기록 (Neo4j LineageNode)
    |   |   |   +-- 리니지에 "FAILED" 상태 기록 (W3C PROV-O)
    |   |   |   +-- AlertManager 알림 발송
    |   |   |   \-- 실패 아티팩트 보존 (Object Storage)
    |   |   |
    |   |   +-- DAG 전체 중단 여부 판단
    |   |       +-- failFast: true  -> 전체 워크플로우 중단
    |   |       +-- failFast: false -> 독립 노드 계속 실행
    |   |
    |   \-- 실패 후 복구
    |       +-- argo retry <workflow-name> --node-field-selector phase=Failed
    |       +-- 실패 노드만 선택적 재실행 (성공 노드 스킵)
    |       \-- 결과: 전체 워크플로우 재실행 없이 부분 복구
    |
    v 실행 완료 (성공/부분 실패)
        +-- 성공: KG 업데이트 + 리니지 기록 + 대시보드 갱신
        +-- 부분 실패: 성공 노드 결과만 반영 + 실패 알림
        \-- 전체 실패: 롤백 (이전 KG 상태 복원) + 사후 분석 보고서
```

---

## 관련 문서

| 문서 | 설명 |
|------|------|
| [보안 아키텍처](./06-security-architecture.md) | RBAC 필터, Cypher Injection 방어 |
| [데이터 아키텍처](./04-data-architecture.md) | 온톨로지 설계, 저장 전략, 리니지 |
| [컴포넌트 아키텍처](./03-component-architecture.md) | KG 엔진 파이프라인 컴포넌트 상세 |
| [AI/LLM 아키텍처](./11-ai-llm.md) | Ollama 서빙, Text2Cypher 모델 상세 |
| [관측성 아키텍처](./10-observability.md) | Prometheus 메트릭, AlertManager 알림 규칙 |
| [Suredata Lab 연동](./08-suredata-integration.md) | 외부 데이터 수집 인터페이스 상세 |
