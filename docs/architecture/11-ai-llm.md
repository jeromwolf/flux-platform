# 11. AI/LLM 아키텍처

[← 관측성](./10-observability.md) | [다음: 설계 원칙 →](./12-design-principles.md)

## 개요

IMSP의 AI/LLM 아키텍처는 온프레미스 우선(On-Premise First) 원칙 하에 설계된다.
Language Model, Vision Model, Embedding Model의 3계층 모델 스택을 구성하고,
Failover Provider 패턴으로 가용성을 보장한다. 에이전트 런타임은 A2A(Agent-to-Agent)
프로토콜과 MCP(Model Context Protocol)를 기반으로 도구 접근을 추상화하며,
Text2Cypher 5단계 파이프라인이 KG 질의의 핵심 경로를 담당한다.

---

## 11.1 모델 스택

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Model Stack                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 1: Language Models (대화, 추론, OCR)               │   │
│  │                                                          │   │
│  │  ┌──────────────────┐   ┌───────────────────┐           │   │
│  │  │  Qwen 2.5 VL 7B  │   │   MiniCPM-V 4.5   │           │   │
│  │  │  (Primary)        │   │   (Backup/Batch)   │           │   │
│  │  │                   │   │                   │           │   │
│  │  │ • 한국어 대화     │   │ • 경량 폴백        │           │   │
│  │  │ • 이미지 이해     │   │ • 배치 처리        │           │   │
│  │  │ • OCR             │   │ • CPU 가능         │           │   │
│  │  │ • A100 GPU 필요   │   │ • 소규모 GPU       │           │   │
│  │  └──────────────────┘   └───────────────────┘           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 2: Vision Models (객체 탐지, 다중 추적)             │   │
│  │                                                          │   │
│  │  ┌──────────────────┐   ┌───────────────────┐           │   │
│  │  │ YOLOv8 / RT-DETR │   │    DeepSORT        │           │   │
│  │  │ (Detection)       │   │    (Tracking)      │           │   │
│  │  │                   │   │                   │           │   │
│  │  │ • 위성 선박 탐지  │   │ • CCTV 다중 추적  │           │   │
│  │  │ • CCTV 선박 인식  │   │ • 궤적 연결        │           │   │
│  │  └──────────────────┘   └───────────────────┘           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 3: Embedding Models (의미 벡터 검색)               │   │
│  │                                                          │   │
│  │  ┌──────────────────┐                                   │   │
│  │  │ nomic-embed-text │  768-dim, Ollama serving           │   │
│  │  └──────────────────┘                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Serving Engine (연차별 전환)                             │   │
│  │                                                          │   │
│  │  Y1: Ollama (CPU/경량) ──► Y2: Ollama (GPU, 1x A100)    │   │
│  │                        ──► Y3: vLLM + Ray 분산 추론       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11.2 LLM Provider 추상화 및 Failover

```python
# agent/llm/provider.py (이식 예정)
class LLMProvider(Protocol):
    async def complete(self, prompt: str, **kwargs) -> LLMResponse: ...
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]: ...

class OllamaProvider(LLMProvider):    # 온프레미스 기본
    model: str = "qwen2.5-vl:7b"
    base_url: str = "http://ollama:11434"

class OpenAIProvider(LLMProvider):    # 클라우드 폴백 (규정 검토 후)
    model: str = "gpt-4o"

class AnthropicProvider(LLMProvider): # 백업 (규정 검토 후)
    model: str = "claude-opus-4-6"

class FailoverProvider(LLMProvider):
    """순서대로 시도, 실패 시 다음으로"""
    providers: list[LLMProvider]

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        for provider in self.providers:
            try:
                return await provider.complete(prompt, **kwargs)
            except LLMUnavailableError:
                continue
        raise AllProvidersFailedError()
```

**기본 구성:** Ollama(primary) -> OpenAI(fallback) -> Anthropic(backup)
온프레미스 보안 요구사항에 따라 클라우드 Provider 활성화 여부를
환경변수(`LLM_ALLOW_CLOUD=false`)로 제어한다.

---

## 11.3 Agentic AI 시스템

```
┌──────────────────────────────────────────────────────────────────┐
│                     Orchestrator Agent                             │
│            (글로벌 대화 통합 / 의도 분류 / 라우팅)                   │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                A2A Protocol (Agent-to-Agent)                │   │
│  │                                                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │   │
│  │  │  KG Agent   │  │  Workflow   │  │  Analytics  │       │   │
│  │  │             │  │  Agent      │  │  Agent      │       │   │
│  │  │• Text2Cypher│  │• 노드 추천  │  │• 시각화 생성│       │   │
│  │  │• GraphRAG   │  │• 자동 생성  │  │• 대시보드   │       │   │
│  │  │• 스키마 탐색│  │• 실행 관리  │  │• 차트 구성  │       │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │   │
│  └─────────┼────────────────┼────────────────┼──────────────┘   │
│            │                │                │                    │
│  ┌─────────▼────────────────▼────────────────▼──────────────┐   │
│  │                    MCP Protocol                            │   │
│  │               (Model Context Protocol)                     │   │
│  │                                                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │   │
│  │  │KG Query  │ │Workflow  │ │File      │ │External  │    │   │
│  │  │Tool      │ │CRUD Tool │ │System    │ │API Tool  │    │   │
│  │  │          │ │          │ │Tool      │ │          │    │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐     │
│  │   Memory    │  │   Skills    │  │   LLM Provider       │     │
│  │             │  │             │  │                      │     │
│  │ • 단기 메모리│  │ • 스킬 팩   │  │ • Ollama (primary)   │     │
│  │   (대화)    │  │ • 워크플로우 │  │ • OpenAI (fallback)  │     │
│  │ • 장기 메모리│  │   스킬      │  │ • Anthropic (backup) │     │
│  │   (KG 기반) │  │ • 데이터 스킬│  │ • Auto failover      │     │
│  └─────────────┘  └─────────────┘  └──────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

### 에이전트 런타임 유형

| 런타임 | 사용 목적 | 특징 |
|--------|---------|------|
| ReAct Runtime | 대화형 KG 탐색 | Reason -> Act -> Observe 반복, 동적 도구 선택 |
| Pipeline Runtime | 정형 ETL 후처리 | 고정 단계 순서, 병렬 실행 지원 |
| Batch Runtime | 주기적 평가/리포트 | CronJob 연동, 대량 데이터 처리 |

---

## 11.4 Agent VM 모델

```
Agent Configuration (YAML 정의)
├── id: kg-agent-v1
├── core_system_prompt
│   ├── 해사 도메인 온톨로지 요약 (압축 JSON)
│   ├── 사용 가능 도구 목록 + 시그니처
│   └── 역할별 권한 범위 (RBAC Role 매핑)
├── skills:
│   - workflow_create
│   - workflow_execute
│   - kg_query
│   - data_ingest
└── mcp_servers:
    - uri: mcp://kg-query-server:3000
    - uri: mcp://workflow-crud-server:3001

Agent VM (격리 실행 환경, K8s Pod 단위)
├── /skills/          # 등록된 스킬 정의 (YAML)
├── /workspace/       # 작업 공간 (임시 데이터, Pod 수명 동안)
├── /context/         # 대화 컨텍스트 (Redis 백업)
└── Tool Access (RBAC 적용)
    ├── KG Query     (Text2Cypher 경유, 역할별 데이터 분류 필터)
    ├── Workflow CRUD(생성/수정/실행/삭제, 소유자 검증)
    ├── Data Ingest  (Object Storage 업로드 + KG 등록, 용량 쿼터)
    └── Visualization(차트/지도/그래프 생성, 읽기 전용)
```

### 메모리 아키텍처

```
단기 메모리 (Short-term)
└── Redis List (TTL 24h)
    └── 최근 N 턴의 대화 내용 (요약 압축)

장기 메모리 (Long-term)
└── Neo4j KG
    └── (:MemoryNode {content, embedding, timestamp})
        -[:RELATED_TO]->(:Concept)
    (nomic-embed-text 벡터 인덱스로 유사 기억 검색)
```

---

## 11.5 Text2Cypher 5단계 파이프라인 (상세)

```
입력: "부산항에서 출항한 컨테이너 선박 목록"
  │
  ▼
[1단계: NLParser]
  • 한국어 형태소 분석
  • 해사 용어 사전 매핑 (부산항 → PORT_BUSAN)
  • 의도 분류 (QUERY_LIST)
  출력: StructuredQuery {entity: Vessel, filter: {type: container},
                         relation: DEPARTED_FROM, target: PORT_BUSAN}
  │
  ▼
[2단계: QueryGenerator]
  • Direct Path: CypherBuilder (확정적, 80% 커버)
  • LLM Path: Few-shot Prompt + LLM (20% 복잡 쿼리)
  • RAG Path: GraphRAG (스키마 탐색 후 생성)
  출력: MATCH (v:Vessel)-[:DEPARTED_FROM]->(p:Port {name:"부산항"})
         WHERE v.type = "container" RETURN v
  │
  ▼
[3단계: CypherValidator]
  • 구문 검증 (Cypher 파서)
  • 스키마 정합성 (존재하는 레이블/관계 타입인지)
  • RBAC 레이블 허용 여부
  • 위험 패턴 감지 (DELETE/MERGE 무제한)
  • 파라미터 주입 검사
  • 복잡도 상한 (Hop 수 <= 5)
  │
  ▼
[4단계: CypherCorrector]
  • 규칙 기반 교정 (오탈자 레이블, 잘못된 방향)
  • 스키마 기반 자동 제안 (Vessel → :Vessel)
  • 교정 불가 시 LLM 재생성 요청
  │
  ▼
[5단계: HallucinationDetector]
  • 존재하지 않는 노드 ID 참조 감지
  • 스키마에 없는 프로퍼티 사용 감지
  • 신뢰도 점수 산출 (0.0 ~ 1.0)
  • 임계값(0.7) 미달 시 사람 검토 요청
  │
  ▼
출력: ValidatedQuery {cypher, confidence: 0.92, corrections: [...]}
```

---

## 11.6 한국어 해사 도메인 파인튜닝

범용 LLM은 해사 도메인 전문 용어와 한국어 특성을 충분히 반영하지 못한다.
Y2부터 KRISO 협력 데이터를 활용한 도메인 특화 파인튜닝을 수행하여
Text2Cypher 정확도와 대화 품질을 향상시킨다.

### 파인튜닝 데이터 구축

| 단계 | 시점 | 작업 | 예상 규모 |
|------|------|------|----------|
| 1. 원천 확보 | Y1 Q4 | KRISO 논문/보고서/매뉴얼 수집, 저작권 확인 | ~5,000 문서 |
| 2. QA 쌍 생성 | Y2 Q1 | 문서 -> Question-Answer 쌍 자동 생성 (LLM 활용) + 전문가 검수 | ~50,000 QA 쌍 |
| 3. Text2Cypher 쌍 | Y2 Q1 | 자연어 질문 -> Cypher 쿼리 쌍 구축 (기존 평가 데이터셋 확장) | ~10,000 쌍 |
| 4. 품질 검증 | Y2 Q2 | 전문가 리뷰, 중복/오류 제거, 난이도 레이블링 | 정제 후 ~40,000 |

### 파인튜닝 방법론

```
Base Model (Qwen2.5-32B 또는 EXAONE 3.5)
  │
  ├── LoRA / QLoRA 적용
  │   ├── Rank: 64
  │   ├── Alpha: 128
  │   ├── Target Modules: q_proj, v_proj, k_proj, o_proj
  │   └── Quantization: 4-bit (QLoRA) for memory efficiency
  │
  ├── 학습 설정
  │   ├── GPU: A100 80GB x 1 (QLoRA 시 단일 GPU 가능)
  │   ├── Batch Size: 4 (gradient accumulation 8)
  │   ├── Learning Rate: 2e-4 (cosine scheduler)
  │   ├── Epochs: 3
  │   └── 예상 학습 시간: ~24시간
  │
  └── 출력: LoRA Adapter Weights (~200MB)
      └── Base Model에 동적 로드 (vLLM LoRA 지원)
```

### 파인튜닝 모델 후보

| 모델 | 파라미터 | 한국어 성능 | 라이선스 | 비고 |
|------|---------|------------|---------|------|
| Qwen2.5-32B | 32B | 우수 (다국어 학습) | Apache 2.0 | 멀티모달 지원, 기본 후보 |
| EXAONE 3.5 32B | 32B | 최우수 (한국어 특화) | 연구/상용 | LG AI Research, 한국어 1위급 |
| Solar-10.7B | 10.7B | 양호 (한국어 특화) | Apache 2.0 | Upstage, 경량 대안 |
| Llama 3.3 70B | 70B | 양호 (다국어) | Llama 3.3 | Meta, 대규모 모델 |

**모델 선정 기준:** 해사 도메인 30문항 벤치마크 (Y1 Q3 수행)를 기반으로
한국어 이해도, Cypher 생성 정확도, 추론 속도를 종합 평가한다.

### 평가 파이프라인

기존 `core/kg/evaluation/` 모듈을 활용하여 파인튜닝 효과를 정량 측정한다.

```python
# core/kg/evaluation/dataset.py 활용
evaluation_dimensions = {
    "text2cypher_accuracy": {
        "dataset": "evaluation/maritime_text2cypher_500.json",
        "metric": "exact_match + execution_match",
        "target_y2": 0.80,
        "target_y5": 0.92
    },
    "domain_qa": {
        "dataset": "evaluation/maritime_qa_200.json",
        "metric": "ROUGE-L + human_eval",
        "target_y2": 0.75,
        "target_y5": 0.90
    },
    "hallucination_rate": {
        "dataset": "evaluation/hallucination_test_100.json",
        "metric": "false_positive_rate",
        "target_y2": "< 10%",
        "target_y5": "< 3%"
    }
}
```

---

## 11.7 프롬프트 관리 전략

LLM 기반 시스템에서 프롬프트는 코드만큼 중요한 자산이다.
체계적인 버전 관리와 도메인 컨텍스트 주입을 통해 일관된 품질을 유지한다.

### 프롬프트 템플릿 버전 관리

모든 프롬프트 템플릿은 Git으로 관리하며, 변경 이력을 추적한다.

```
agent/
├── prompts/
│   ├── system/
│   │   ├── kg_agent_v1.yaml         # KG Agent 시스템 프롬프트
│   │   ├── workflow_agent_v1.yaml   # Workflow Agent 시스템 프롬프트
│   │   └── analytics_agent_v1.yaml  # Analytics Agent 시스템 프롬프트
│   │
│   ├── text2cypher/
│   │   ├── generator_v3.yaml        # Cypher 생성 프롬프트
│   │   ├── corrector_v2.yaml        # Cypher 교정 프롬프트
│   │   └── few_shot_examples.yaml   # Few-shot 예제 모음
│   │
│   └── domain/
│       ├── maritime_context.yaml    # 해사 도메인 컨텍스트
│       └── ontology_summary.yaml   # 온톨로지 압축 요약
```

### 프롬프트 템플릿 구조

```yaml
# agent/prompts/text2cypher/generator_v3.yaml
metadata:
  id: text2cypher-generator
  version: "3.0"
  updated: "2027-01-15"
  author: "kg-team"
  model_compatibility:
    - "qwen2.5-*"
    - "exaone-3.5-*"

system_prompt: |
  당신은 해사 도메인 Knowledge Graph 전문가입니다.
  사용자의 자연어 질문을 Neo4j Cypher 쿼리로 변환합니다.

  ## 온톨로지 스키마
  {ontology_context}

  ## 규칙
  1. 노드 레이블은 PascalCase (예: Vessel, Port)
  2. 관계 타입은 SCREAMING_SNAKE_CASE (예: DEPARTED_FROM)
  3. 속성명은 camelCase (예: vesselType)
  4. 파라미터는 $paramName 형식 사용
  5. 최대 Hop 수: 5

  ## 제약 조건
  - DELETE, MERGE 문 생성 금지
  - LIMIT 없는 MATCH 금지 (기본 LIMIT 100)

variables:
  ontology_context:
    source: "domain/ontology_summary.yaml"
    injection: "runtime"

few_shot_examples:
  source: "text2cypher/few_shot_examples.yaml"
  selection: "similarity"    # 입력 질문과 유사한 예제 동적 선택
  max_examples: 5
```

### 도메인별 시스템 프롬프트

에이전트 유형별로 해사 도메인 온톨로지 컨텍스트를 시스템 프롬프트에 주입한다.

```
시스템 프롬프트 구성:

[기본 역할 정의]
  + [온톨로지 스키마 요약]     ← core/kg/ontology/ 에서 자동 추출
  + [도메인 용어 사전]         ← domains/maritime/nlp/ 에서 로드
  + [RBAC 권한 범위]          ← Keycloak Role 매핑
  + [사용 가능 도구 시그니처]   ← MCP Server 자동 검색
```

온톨로지 변경 시 프롬프트를 자동 갱신하는 CI/CD 파이프라인:

```
ontology/ 변경 감지 (Git Hook)
  │
  ▼
온톨로지 요약 재생성 (Python 스크립트)
  │
  ▼
프롬프트 템플릿 내 {ontology_context} 갱신
  │
  ▼
회귀 테스트 (evaluation dataset 30문항)
  │
  ├── 통과 → 자동 배포
  └── 실패 → PR 블로킹 + 담당자 알림
```

### Few-shot 예제 관리

평가 데이터셋에서 대표적인 예제를 선별하여 Few-shot 프롬프트에 활용한다.

| 예제 유형 | 출처 | 선별 기준 | 관리 위치 |
|----------|------|----------|----------|
| 기본 쿼리 | evaluation/dataset.py | 정확도 100% 달성 예제 | prompts/text2cypher/few_shot_examples.yaml |
| 복잡 쿼리 | 운영 로그 분석 | 다중 Hop, 집계 쿼리 | 동일 |
| 에지 케이스 | 장애 분석 결과 | 이전에 실패했던 패턴 | 동일 |
| 도메인 특화 | KRISO 검수 | 해사 전문 용어 포함 쿼리 | 동일 |

**동적 예제 선택:** 사용자 입력과 의미적으로 유사한 예제를 nomic-embed-text 벡터 유사도 기반으로 상위 5개 선택하여 프롬프트에 포함한다.

```python
# core/kg/pipeline.py 내 예제 선택 로직
async def select_few_shot_examples(
    query: str,
    all_examples: list[FewShotExample],
    top_k: int = 5
) -> list[FewShotExample]:
    query_embedding = await embed(query)  # nomic-embed-text
    similarities = [
        (ex, cosine_similarity(query_embedding, ex.embedding))
        for ex in all_examples
    ]
    return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]
```

### 프롬프트 A/B 테스트

새로운 프롬프트 버전 배포 시 A/B 테스트를 수행하여 품질 회귀를 방지한다.

```
Traffic Split:
  ├── 90% → 현재 프롬프트 (v3.0)
  └── 10% → 신규 프롬프트 (v3.1-candidate)

측정 지표:
  - Text2Cypher 정확도 (execution_match)
  - 평균 신뢰도 점수
  - 환각 감지 비율
  - 사용자 피드백 (thumbs up/down)

승격 조건:
  - 72시간 이상 운영
  - 모든 지표에서 기존 대비 >= 0% (회귀 없음)
  - 1개 이상 지표에서 > 2% 개선
```

---

## 11.8 실험 및 연구 인프라

### 실험 추적 (Y2+)

| 도구 | 용도 | 도입 시기 |
|------|------|----------|
| MLflow OSS | 실험 추적, 모델 레지스트리, 메트릭 기록 | Y2 Q1 |
| DVC | 데이터셋 버전 관리 | Y2 Q1 |
| Label Studio | NER 어노테이션 + 평가 데이터 라벨링 | Y1 Q4 |

### 벤치마크 데이터셋 관리

| 데이터셋 | 대상 | 규모 | 위치 |
|----------|------|------|------|
| Text2Cypher QA | Cypher 생성 정확도 | 200+ QA 쌍 | `domains/maritime/evaluation/` |
| NER 평가셋 | 개체명 인식 정확도 | 500+ 문장 | 구축 예정 (Y2) |
| GraphRAG 평가셋 | 검색 품질 | 100+ 질의 | 구축 예정 (Y2) |
| LLM 한국어 해사 | 도메인 이해도 | 300+ 질의 | 구축 예정 (Y3) |

### 실험 재현성

- 모든 fine-tuning 실험: MLflow에 하이퍼파라미터, 메트릭, 아티팩트 기록
- 데이터셋 버전: DVC + Ceph RGW 백엔드
- 모델 체크포인트: Ceph RGW에 버전별 저장
- GPU 사용 로그: Prometheus `gpu_utilization` + 비용 추적

### 논문/특허 지원 (연간 산출물)

| 연차 | SCI | KCI | 특허 출원 | 특허 등록 |
|------|-----|-----|----------|----------|
| Y1 | 0 | 0 | 1 | 0 |
| Y2 | 1 | 1 | 2 | 1 |
| Y3 | 1 | 1 | 2 | 2 |
| Y4 | 1 | 1 | 2 | 2 |
| Y5 | 1 | 1 | 1 | 1 |

> 실험 추적 인프라는 SCI 수준 논문에 필요한 재현 가능한 벤치마크 결과를 보장하기 위해 Y2에 도입한다.

---

*관련 문서: [10-observability.md](./10-observability.md) (관측성), [20-nlp-ner.md](./20-nlp-ner.md) (NLP/NER 전략), [core/kg/pipeline.py](../../core/kg/pipeline.py) (Text2Cypher 구현)*
