# 12. 설계 원칙 및 패턴

[← AI/LLM 아키텍처](./11-ai-llm.md) | [다음: 연차별 로드맵 →](./13-roadmap.md)

## 개요

IMSP 플랫폼은 5개년에 걸친 장기 프로젝트로서, 기술 스택 교체와 요구사항 변화에 유연하게 대응할 수 있는 설계 원칙이 필수적이다. 본 문서는 플랫폼 전체에 적용되는 10가지 핵심 설계 패턴, 소프트웨어 아키텍처 원칙(SOLID, 12-Factor 등), 모듈 간 의존성 규칙, 그리고 식별된 안티 패턴 및 대응 방안을 기술한다.

---

## 12.1 핵심 설계 패턴 10가지

| # | 패턴 | 적용 위치 | 설명 |
|---|------|----------|------|
| 1 | **Palantir Foundry-style Ontology** | `kg/ontology/core.py` | ObjectType / LinkType / PropertyDefinition 삼중 구조. DB 독립적 엔티티 모델링 프레임워크 |
| 2 | **Plugin Architecture** | `core/` + `domains/` | 도메인 독립 엔진(core) + 도메인 플러그인(maritime). TermDictionary Protocol 기반 DI로 새 도메인 확장 가능 |
| 3 | **3-Layer Ontology-Schema** | 온톨로지 전체 | Conceptual(DB 무관) → Mapping(DDL 생성) → Physical(Neo4j 전용). DB 교체 시 Mapping 레이어만 교체 |
| 4 | **ELT over ETL** | `kg/etl/` | "일단 올려라, 처리는 나중에". Object Storage (Ceph)에 원천 보존 후 AI 분석. 데이터 무결성 보장 + 재처리 가능 |
| 5 | **Dual-Path Query Routing** | TextToCypherPipeline | Direct Path(CypherBuilder) / LLM Path(Text2Cypher) / RAG Path(GraphRAG). 의도 기반 자동 라우팅 |
| 6 | **5-Stage Quality Pipeline** | Pipeline 5단계 | Parse → Generate → Validate → Correct → HallucinationDetect. 각 단계 독립 품질 검증 및 Span 추적 |
| 7 | **Metadata-First Graph** | 멀티모달 저장 | Neo4j는 메타데이터만 저장. 바이너리(영상/센서)는 Object Storage (Ceph)에 저장, `storagePath` 속성으로 참조 |
| 8 | **Multi-Agent Architecture** | Agent Runtime | Orchestrator → A2A Protocol → Sub-agents → MCP Protocol → Tools. 역할 분리 + 도구 추상화 |
| 9 | **GitOps Deployment** | CI/CD 전체 | ArgoCD + Flux. 모든 인프라 변경이 Git commit. `values-{env}.yaml`로 환경 분리 |
| 10 | **Temporal Knowledge Reasoning** | 온톨로지, RBAC | `validFrom` / `validTo` 속성. "3월에만 제한된 구역을 4월에 쿼리" 같은 시간 조건부 추론 지원 |

---

## 12.2 패턴별 코드 매핑 및 구현 상세

각 패턴이 실제 코드베이스에서 어떻게 구현되는지 구체적으로 기술한다.

### 12.2.1 Repository Pattern

**구현 위치:** `core/kg/etl/loader.py` — `Neo4jBatchLoader`

데이터 접근 로직을 비즈니스 로직으로부터 분리한다. `Neo4jBatchLoader`는 Neo4j 세션 관리, UNWIND MERGE 배치 실행, 트랜잭션 재시도를 캡슐화하여, ETL 파이프라인이 저장소 상세 구현에 의존하지 않도록 한다.

```python
# core/kg/etl/loader.py
class Neo4jBatchLoader:
    """Repository Pattern: 데이터 영속화 로직을 캡슐화."""

    def __init__(self, driver: neo4j.Driver, batch_size: int = 1000):
        self._driver = driver
        self._batch_size = batch_size

    def load_nodes(self, label: str, records: list[dict]) -> LoadResult:
        """UNWIND MERGE 패턴으로 배치 적재."""
        cypher = f"UNWIND $batch AS row MERGE (n:{label} {{id: row.id}}) SET n += row"
        for batch in self._chunked(records, self._batch_size):
            self._execute_write(cypher, {"batch": batch})
        return LoadResult(total=len(records), label=label)
```

### 12.2.2 Strategy Pattern

**구현 위치:** `core/kg/nlp/term_dictionary.py` — `TermDictionary` Protocol

도메인별 용어 사전을 교체 가능한 전략으로 추상화한다. `core/kg/` 엔진은 `TermDictionary` Protocol에만 의존하며, 해사 도메인(`domains/maritime/`)이나 향후 추가될 도메인이 각자의 구현체를 제공한다.

```python
# core/kg/nlp/term_dictionary.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class TermDictionary(Protocol):
    """Strategy Pattern: 도메인별 용어 매핑 전략."""

    def lookup(self, term: str) -> list[str]:
        """자연어 용어를 KG 엔티티 후보로 변환."""
        ...

    def get_synonyms(self, canonical: str) -> list[str]:
        """정규화된 엔티티의 동의어 목록 반환."""
        ...

# domains/maritime/nlp/maritime_terms.py — 해사 도메인 구현체
class MaritimeTermDictionary:
    """해사 용어 3,000+ 항목 매핑."""
    def lookup(self, term: str) -> list[str]: ...
    def get_synonyms(self, canonical: str) -> list[str]: ...
```

### 12.2.3 Pipeline Pattern

**구현 위치:** `core/kg/pipeline.py` — `TextToCypherPipeline`

요청 처리를 순차적 단계(Parse → Generate → Validate → Correct → HallucinationDetect)로 분리한다. 각 단계는 독립적으로 교체 가능하며, 단계별 Span 추적으로 병목 식별이 용이하다.

```python
# core/kg/pipeline.py
class TextToCypherPipeline:
    """Pipeline Pattern: 5단계 순차 처리."""

    def __init__(self, parser, generator, validator, corrector, detector):
        self._stages = [parser, generator, validator, corrector, detector]

    def run(self, text: str) -> PipelineResult:
        context = PipelineContext(input=text)
        for stage in self._stages:
            context = stage.process(context)
            if context.has_error:
                return PipelineResult.failure(context.error, stage=stage.name)
        return PipelineResult.success(context.cypher, context.metadata)
```

### 12.2.4 Builder Pattern

**구현 위치:** `core/kg/cypher_builder.py` — `CypherBuilder`

Fluent API로 Cypher 쿼리를 프로그래밍적으로 조합한다. 메서드 체이닝을 통해 복잡한 쿼리를 안전하게 구성하며, 파라미터 바인딩으로 Injection을 원천 차단한다.

```python
# core/kg/cypher_builder.py
class CypherBuilder:
    """Builder Pattern: Fluent Cypher 쿼리 빌더."""

    def match(self, label: str, alias: str = "n") -> "CypherBuilder":
        self._clauses.append(f"MATCH ({alias}:{label})")
        return self

    def where(self, condition: str, **params) -> "CypherBuilder":
        self._clauses.append(f"WHERE {condition}")
        self._params.update(params)
        return self

    def return_(self, *fields) -> "CypherBuilder":
        self._clauses.append(f"RETURN {', '.join(fields)}")
        return self

    def build(self) -> tuple[str, dict]:
        return " ".join(self._clauses), self._params

# 사용 예:
# CypherBuilder().match("Vessel").where("n.name = $name", name="세종대왕함").return_("n").build()
# → ("MATCH (n:Vessel) WHERE n.name = $name RETURN n", {"name": "세종대왕함"})
```

### 12.2.5 Factory Pattern

**구현 위치:** `domains/maritime/factories.py` — Maritime entity factories

해사 도메인 엔티티(Vessel, Port, Route 등)의 생성 로직을 표준화한다. 공통 속성 검증, 기본값 할당, 타입 변환을 팩토리 메서드에서 일괄 처리하여, 생성 로직의 중복을 제거한다.

```python
# domains/maritime/factories.py
class VesselFactory:
    """Factory Pattern: 해사 엔티티 생성 표준화."""

    @staticmethod
    def create(mmsi: str, name: str, vessel_type: str, **kwargs) -> dict:
        return {
            "id": f"vessel:{mmsi}",
            "label": "Vessel",
            "mmsi": mmsi,
            "name": name,
            "vesselType": vessel_type,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            **kwargs
        }
```

### 12.2.6 Observer Pattern

**구현 위치:** `core/kg/lineage/recorder.py` — `LineageRecorder`

ETL 파이프라인, 쿼리 실행, 모델 학습 등 시스템 이벤트를 구독하여 W3C PROV-O 기반의 리니지 그래프를 자동으로 기록한다. 이벤트 발생 지점과 기록 로직이 분리되어, 리니지 정책(NONE~FULL) 변경이 비즈니스 로직에 영향을 주지 않는다.

```python
# core/kg/lineage/recorder.py
class LineageRecorder:
    """Observer Pattern: 이벤트 기반 리니지 기록."""

    def __init__(self, policy: LineagePolicy):
        self._policy = policy
        self._graph = LineageGraph()

    def on_transform(self, source: str, target: str, activity: str):
        if self._policy.level >= LineageLevel.BASIC:
            self._graph.add_edge(source, target, activity=activity)

    def on_etl_complete(self, pipeline_id: str):
        if self._policy.level >= LineageLevel.FULL:
            self._graph.add_node(pipeline_id, type="Activity")
```

### 12.2.7 Decorator Pattern

**구현 위치:** `core/kg/rbac/secure_builder.py` — `SecureCypherBuilder`

기존 `CypherBuilder`를 래핑하여, 모든 쿼리에 RBAC 필터(데이터 분류 등급, 테넌트 격리 조건)를 자동 주입한다. 원본 `CypherBuilder`의 인터페이스를 변경하지 않으면서 보안 관심사를 횡단적으로 적용한다.

```python
# core/kg/rbac/secure_builder.py
class SecureCypherBuilder:
    """Decorator Pattern: CypherBuilder에 RBAC 필터 자동 주입."""

    def __init__(self, builder: CypherBuilder, user: RBACUser):
        self._builder = builder
        self._user = user

    def build(self) -> tuple[str, dict]:
        cypher, params = self._builder.build()
        # 사용자 데이터 분류 등급에 따른 WHERE 조건 주입
        secured = self._inject_rbac_filter(cypher, self._user)
        params["__user_clearance"] = self._user.clearance.value
        return secured, params
```

### 12.2.8 Bridge Pattern

**구현 위치:** `core/kg/ontology_bridge.py` — Ontology-KG 변환

온톨로지(Conceptual 레이어)와 KG(Physical 레이어) 사이의 변환을 담당한다. 온톨로지 모델이 변경되어도 Bridge만 수정하면 되며, DB 교체 시에도 Physical 레이어 매핑만 변경하면 된다.

```python
# core/kg/ontology_bridge.py
class OntologyBridge:
    """Bridge Pattern: Ontology ↔ KG 양방향 변환."""

    def object_type_to_label(self, obj_type: ObjectType) -> str:
        """Conceptual ObjectType → Neo4j Label 변환."""
        return obj_type.name  # PascalCase 유지

    def link_type_to_rel(self, link_type: LinkType) -> str:
        """Conceptual LinkType → Neo4j Relationship Type 변환."""
        return link_type.name.upper()  # SCREAMING_SNAKE_CASE

    def property_to_neo4j(self, prop: PropertyDefinition) -> dict:
        """PropertyDefinition → Neo4j 속성 스펙 변환."""
        return {"name": prop.name, "type": self._map_type(prop.data_type)}
```

### 12.2.9 DLQ (Dead Letter Queue) Pattern

**구현 위치:** `core/kg/etl/dlq.py` — Dead Letter Queue

ETL 파이프라인에서 검증 실패한 레코드를 별도의 대기열에 보존한다. 실패 레코드는 원본 데이터, 실패 사유, 타임스탬프와 함께 저장되어, 정부 과제의 데이터 추적성 요구사항을 충족한다.

```python
# core/kg/etl/dlq.py
class DeadLetterQueue:
    """DLQ Pattern: 실패 레코드 보존 및 재처리."""

    def __init__(self, storage_path: str):
        self._storage_path = storage_path
        self._entries: list[DLQEntry] = []

    def enqueue(self, record: dict, error: Exception, stage: str):
        entry = DLQEntry(
            record=record,
            error=str(error),
            stage=stage,
            timestamp=datetime.now(timezone.utc),
        )
        self._entries.append(entry)

    def retry_all(self, pipeline: "ETLPipeline") -> RetryResult:
        """보존된 실패 레코드를 재처리 시도."""
        ...
```

### 12.2.10 Quality Gate Pattern

**구현 위치:** `core/kg/quality_gate.py` — CI/CD pre-merge 검증

코드 변경이 품질 기준을 충족하는지 CI/CD 파이프라인에서 자동 검증한다. 온톨로지 정합성, Cypher 구문, 테스트 커버리지, 성능 벤치마크 등 다차원 품질 기준을 게이트로 적용한다.

```python
# core/kg/quality_gate.py
class QualityGate:
    """Quality Gate Pattern: CI/CD 품질 검증 게이트."""

    def __init__(self, checks: list[QualityCheck]):
        self._checks = checks

    def evaluate(self, context: QualityContext) -> GateResult:
        results = []
        for check in self._checks:
            result = check.run(context)
            results.append(result)
            if result.severity == "CRITICAL" and not result.passed:
                return GateResult(passed=False, blocker=result)
        return GateResult(passed=all(r.passed for r in results), details=results)
```

---

## 12.3 소프트웨어 아키텍처 원칙

| 원칙 | 설명 | 적용 위치 |
|------|------|----------|
| **12-Factor App** | 환경변수 외부화, Stateless 서비스, Port binding | FastAPI, Docker, K8s ConfigMap/Secret |
| **Domain-Driven Design** | 핵심 도메인(KG) + 지원 도메인(인프라/인증) 명확히 분리 | `core/` vs `infra/` vs `gateway/` |
| **CQRS 경향** | 데이터 주입(Write) / 쿼리(Read) 경로 분리. 향후 본격 CQRS 전환 검토 | Ingest API vs Query API |
| **Hexagonal Architecture** | Port & Adapter. 외부 의존성을 Protocol/Interface로 추상화 | TermDictionary Protocol, LLM Provider 추상화 |
| **Principle of Least Privilege** | 최소 권한 원칙. 컴포넌트별 필요 권한만 부여 | K8s RBAC, NetworkPolicy, Pod Security Standards |
| **Fail Fast** | 조기 오류 발견. 파이프라인 각 단계에서 명시적 예외 발생 | CypherValidator, RecordValidator |

---

## 12.4 SOLID 원칙 적용 현황

IMSP 코드베이스에서 SOLID 원칙이 어떻게 적용되고 있는지를 구체적으로 정리한다.

| SOLID 원칙 | 영문 | 적용 방식 | 코드 위치 |
|------------|------|----------|----------|
| **S** - 단일 책임 | Single Responsibility | 각 모듈이 하나의 관심사만 담당. `CypherBuilder`는 쿼리 조합만, `CypherValidator`는 검증만, `CypherCorrector`는 교정만 수행 | `core/kg/cypher_builder.py`, `cypher_validator.py`, `cypher_corrector.py` |
| **O** - 개방-폐쇄 | Open/Closed | `TermDictionary` Protocol을 통해 새 도메인(예: 항공, 에너지) 추가 시 기존 `core/kg/` 코드 수정 없이 확장 가능 | `core/kg/nlp/term_dictionary.py` (Protocol), `domains/maritime/nlp/` (구현) |
| **L** - 리스코프 치환 | Liskov Substitution | `MaritimeTermDictionary`는 `TermDictionary` Protocol을 완전히 충족하여, 어떤 도메인 사전이든 교체 투입 가능 | `TermDictionary` Protocol의 모든 구현체 |
| **I** - 인터페이스 분리 | Interface Segregation | `LLMProvider`, `TermDictionary`, `QualityCheck` 등 역할별 세분화된 Protocol 정의. 하나의 거대 인터페이스 대신 역할 단위로 분리 | `agent/llm/provider.py`, `core/kg/nlp/term_dictionary.py` |
| **D** - 의존성 역전 | Dependency Inversion | 고수준 모듈(`pipeline.py`)이 저수준 모듈(`neo4j driver`)에 직접 의존하지 않고, 추상(Protocol/DI)을 통해 의존. `FastAPI deps.py`에서 DI 컨테이너 제공 | `core/kg/pipeline.py` → Protocol 의존, `core/kg/api/deps.py` → DI |

---

## 12.5 모듈 의존성 원칙

### 12.5.1 의존성 방향 규칙

```
허용되는 의존 방향:
  domains/maritime/ ──► core/kg/          (도메인 → 엔진)
  core/kg/api/      ──► core/kg/          (API → 엔진)
  gateway/          ──► core/kg/api/      (게이트웨이 → API)
  agent/            ──► core/kg/          (에이전트 → 엔진)
  ui/               ──► gateway/          (프론트 → 게이트웨이)

금지되는 의존 방향:
  core/kg/          ──► domains/maritime/ (엔진은 도메인을 몰라야 함)
  core/kg/          ──► agent/            (순환 의존 금지)
  ui/               ──► core/kg/          (직접 DB 접근 금지)
```

### 12.5.2 의존성 방향 상세 다이어그램

아래는 IMSP 플랫폼 전체 모듈 간의 의존 방향을 도식화한 것이다. 화살표는 "depends-on" 관계를 나타내며, 위에서 아래로 의존하는 것이 원칙이다.

```
                         ┌──────────┐
                         │   ui/    │  (Vue 3 + VueFlow)
                         └────┬─────┘
                              │ HTTP/WS
                              ▼
                         ┌──────────┐
                         │ gateway/ │  (API Gateway)
                         └────┬─────┘
                              │ internal call
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
          ┌──────────┐  ┌──────────┐  ┌──────────┐
          │  agent/  │  │core/kg/  │  │   rag/   │
          │          │  │  api/    │  │          │
          └────┬─────┘  └────┬─────┘  └────┬─────┘
               │             │             │
               └──────┬──────┘             │
                      ▼                    │
                 ┌──────────┐              │
                 │ core/kg/ │◄─────────────┘
                 │ (engine) │
                 └────┬─────┘
                      ▲
                      │ depends-on
               ┌──────┴──────┐
               ▼
        ┌─────────────┐
        │  domains/   │  (maritime, etc.)
        │  maritime/  │
        └─────────────┘

        ┌─────────────┐
        │   tests/    │──depends-on──► core/kg/ + domains/maritime/
        └─────────────┘

        ┌─────────────┐
        │   infra/    │  (독립 — 코드 의존 없음, 배포 설정만)
        └─────────────┘
```

**모듈별 의존 관계 요약:**

| 모듈 | 의존 대상 | 상태 |
|------|----------|------|
| `domains/maritime/` | `core/kg/` | 현재 구현 |
| `core/kg/` | 외부 라이브러리만 (neo4j, pydantic 등) | 현재 구현 |
| `core/kg/api/` | `core/kg/` | 현재 구현 |
| `tests/` | `core/kg/` + `domains/maritime/` | 현재 구현 |
| `agent/` | `core/kg/` | 계획 (이식 예정) |
| `rag/` | `core/kg/` + `agent/` | 계획 (이식 예정) |
| `gateway/` | `core/kg/api/` | 계획 (신규 개발) |
| `ui/` | `gateway/` (HTTP/WS 통신만) | 계획 (신규 개발) |
| `infra/` | 없음 (배포 설정 전용) | 최소 구현 |

### 12.5.3 의존성 검증 자동화

CI/CD 파이프라인에서 금지된 의존 방향을 자동 탐지한다.

```bash
# scripts/check_dependencies.sh — CI에서 자동 실행
# core/kg/ → domains/ 역방향 의존 탐지
VIOLATIONS=$(grep -rn "from domains\." core/kg/ --include="*.py" | grep -v "__pycache__")
if [ -n "$VIOLATIONS" ]; then
    echo "CRITICAL: core/kg/ → domains/ 역방향 의존 발견!"
    echo "$VIOLATIONS"
    exit 1
fi

# core/kg/ → agent/ 순환 의존 탐지
VIOLATIONS=$(grep -rn "from agent\." core/kg/ --include="*.py" | grep -v "__pycache__")
if [ -n "$VIOLATIONS" ]; then
    echo "CRITICAL: core/kg/ → agent/ 순환 의존 발견!"
    echo "$VIOLATIONS"
    exit 1
fi
```

---

## 12.6 알려진 안티 패턴 및 대응

| 안티 패턴 | 현재 상태 | 대응 방안 |
|----------|----------|----------|
| PRD/전략서 프론트엔드 불일치 | PRD: Next.js+React Flow vs 전략: Vue 3+VueFlow | **Vue 3 + VueFlow 확정** (KRISO 미팅 후 결정, 2026-03-18) |
| Neo4j CE 클러스터링 제한 | CE는 단일 인스턴스만 지원 | 애플리케이션 레벨 Redis 캐싱 + Y4에서 EE 전환 검토 |
| Agent A2A 프로토콜 미성숙 | 멀티 에이전트 조율 복잡도 높음 | Y1~Y2: 단일 에이전트로 시작, Y3+ A2A 점진적 도입 |
| 온톨로지 규모 vs LLM 정확도 | 150 엔티티에서 Text2Cypher 정확도 저하 우려 | Few-shot Exemplar DB + 도메인 특화 프롬프트 + Direct Path 우선 |
| Lineage 비영속성 | LineageRecorder가 in-memory only | ETL 완료 후 Neo4j flush 단계 추가 (Y1 Q3 목표) |
| 테스트 DB 격리 부족 | 현재 통합 테스트가 공유 Neo4j 사용 | Test DB Container + Fixture 기반 격리 (진행 중) |

---

## 12.7 패턴 간 상호작용 다이어그램

아래는 Text2Cypher 요청 처리 시 각 설계 패턴이 어떻게 협력하는지를 보여준다.

```
사용자 질의: "부산항 근처 선박 목록"
     │
     ▼
[Pipeline Pattern] TextToCypherPipeline.run()
     │
     ├── Stage 1: Parse
     │   └── [Strategy Pattern] TermDictionary.lookup("부산항") → ["Port:Busan"]
     │
     ├── Stage 2: Generate
     │   ├── Direct Path: [Builder Pattern] CypherBuilder.match("Port")...build()
     │   └── LLM Path: [Bridge Pattern] OntologyBridge로 스키마 컨텍스트 제공
     │
     ├── Stage 3: Validate
     │   └── [Quality Gate] CypherValidator.validate(cypher)
     │
     ├── Stage 4: Correct
     │   └── CypherCorrector.correct(cypher, errors)
     │
     └── Stage 5: HallucinationDetect
         └── HallucinationDetector.check(cypher, ontology)
     │
     ▼
[Decorator Pattern] SecureCypherBuilder.build()  ← RBAC 필터 주입
     │
     ▼
[Repository Pattern] Neo4jBatchLoader → 결과 반환
     │
     ▼
[Observer Pattern] LineageRecorder.on_query(query_id, user, cypher)
```

---

*관련 문서: [소프트웨어 아키텍처 개요](./02-system-architecture.md), [컴포넌트 아키텍처](./03-component-architecture.md), [아키텍처 리뷰](./16-architecture-review.md)*
