# neo4j-graphrag KG Builder 가이드

## 1. 개요

`neo4j-graphrag`는 Neo4j 회사가 공식 제공하는 Python 패키지로, GraphRAG 파이프라인과 KG Builder를 포함한다.

```
Neo4j (회사)
├── Neo4j DB          ← 그래프 데이터베이스 서버 (Community / Enterprise)
├── neo4j driver      ← DB 연결용 Python 드라이버 (pip install neo4j)
├── neo4j-graphrag    ← GraphRAG + KG Builder 라이브러리 (pip install neo4j-graphrag) ⭐
├── APOC              ← Neo4j 서버 플러그인 (프로시저 확장)
└── n10s (Neosemantics) ← Neo4j 서버 플러그인 (OWL/RDF 통합)
```

**KG Builder**는 `neo4j_graphrag.experimental` 모듈 하위에 위치하며, 텍스트 데이터에서 LLM을 사용하여 노드(엔티티)와 관계를 자동 추출하여 Neo4j에 저장하는 파이프라인이다.

현재 우리 프로젝트는 `neo4j-graphrag 1.13.0`을 사용하며, GraphRAG Retriever 5종(`poc/graphrag_retrievers.py`)을 이미 통합한 상태다. KG Builder는 그 다음 단계인 **비정형 텍스트 → 그래프 자동 구축**을 담당한다.

---

## 2. 핵심 구성요소

### 2.1 SimpleKGPipeline

엔드투엔드 파이프라인으로, 텍스트 입력부터 Neo4j 저장까지 한번에 처리한다.

주요 파라미터:

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `llm` | LLMInterface | 엔티티/관계 추출에 사용할 LLM |
| `driver` | neo4j.Driver | Neo4j 연결 드라이버 |
| `entities` | list[str] | 추출할 엔티티 레이블 목록 |
| `relations` | list[str] | 추출할 관계 타입 목록 |
| `potential_schema` | list[tuple] | `(소스, 관계, 타겟)` 형태의 스키마 힌트 |
| `from_pdf` | bool | PDF 파일 직접 입력 여부 (기본값: `False`) |

PDF 파일 직접 입력도 지원하므로, 해양사고 보고서나 규정 문서를 바로 파이프라인에 넣을 수 있다.

### 2.2 SchemaBuilder

추출할 엔티티와 관계의 스키마를 정의한다. 스키마를 명시하면 LLM이 해당 구조에 맞춰 추출하므로 정확도가 크게 향상된다.

주요 메서드:

- `add_entity(label: str, properties: list[str])` — 엔티티 레이블과 속성 정의
- `add_relation(type: str, source: str, target: str)` — 관계 타입 및 방향 정의
- `build()` — 완성된 스키마 객체 반환

### 2.3 LLMEntityRelationExtractor

LLM 기반 엔티티/관계 추출기. `SimpleKGPipeline`이 내부적으로 사용하지만, 직접 호출하면 Neo4j 저장 전에 추출 결과를 검토할 수 있다.

- `result.nodes` — 추출된 노드 목록
- `result.relationships` — 추출된 관계 목록

### 2.4 TextChunker

긴 텍스트를 청크로 분할한다. LLM 컨텍스트 윈도우 제한에 대응하며, `SimpleKGPipeline` 내부에서 자동으로 동작한다.

---

## 3. 사용 예제

### 3.1 기본 사용법 (SimpleKGPipeline)

```python
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.llm import OllamaLLM
import neo4j

driver = neo4j.GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
llm = OllamaLLM(model_name="qwen2.5:7b")

entities = ["Vessel", "Port", "Organization", "Incident", "SeaArea"]
relations = ["DOCKED_AT", "OWNED_BY", "LOCATED_IN", "INVOLVES"]
potential_schema = [
    ("Vessel", "DOCKED_AT", "Port"),
    ("Vessel", "OWNED_BY", "Organization"),
    ("Incident", "INVOLVES", "Vessel"),
    ("Port", "LOCATED_IN", "SeaArea"),
]

pipeline = SimpleKGPipeline(
    llm=llm,
    driver=driver,
    entities=entities,
    relations=relations,
    potential_schema=potential_schema,
)

# 텍스트에서 노드/관계 자동 추출 → Neo4j 저장
import asyncio
asyncio.run(pipeline.run(text="""
HMM 알헤시라스호는 부산항에 2024년 3월 15일 입항하였다.
이 선박은 HMM 소속 컨테이너선으로 인천항으로 출항 예정이다.
"""))
```

추출 결과 예시:

- 노드: `(:Vessel {name: "HMM 알헤시라스"})`, `(:Port {name: "부산항"})`, `(:Organization {name: "HMM"})`, `(:Port {name: "인천항"})`
- 관계: `(HMM 알헤시라스)-[:DOCKED_AT]->(부산항)`, `(HMM 알헤시라스)-[:OWNED_BY]->(HMM)`

### 3.2 스키마 기반 세밀한 제어

```python
from neo4j_graphrag.experimental.components.entity_relation_extractor import (
    LLMEntityRelationExtractor,
)
from neo4j_graphrag.experimental.components.schema import SchemaBuilder

schema_builder = SchemaBuilder()
schema_builder.add_entity("Vessel", ["name", "mmsi", "vesselType"])
schema_builder.add_entity("Port", ["name", "unlocode"])
schema_builder.add_entity("Organization", ["name", "orgId"])
schema_builder.add_relation("DOCKED_AT", "Vessel", "Port")
schema_builder.add_relation("OWNED_BY", "Vessel", "Organization")

schema = schema_builder.build()

extractor = LLMEntityRelationExtractor(llm=llm)
result = await extractor.run(text=text, schema=schema)

# 추출 결과 검토
for node in result.nodes:
    print(f"Node: {node.label} - {node.properties}")
for rel in result.relationships:
    print(f"Rel: {rel.start_node} -[{rel.type}]-> {rel.end_node}")
```

### 3.3 PDF에서 직접 추출

```python
pipeline = SimpleKGPipeline(
    llm=llm,
    driver=driver,
    entities=entities,
    relations=relations,
    potential_schema=potential_schema,
    from_pdf=True,
)

await pipeline.run(file_path="docs/해양사고_보고서.pdf")
```

### 3.4 우리 프로젝트 해사 온톨로지에 맞춘 스키마

```python
# maritime/ontology/maritime_ontology.py의 127 엔티티 중 주요 엔티티
maritime_entities = [
    "Vessel", "Port", "Berth", "SeaArea",
    "Organization", "Incident", "Voyage",
    "TestFacility", "Experiment", "ModelShip",
    "WeatherCondition", "Regulation",
]

maritime_relations = [
    "DOCKED_AT", "OWNED_BY", "LOCATED_IN",
    "ON_VOYAGE", "INVOLVES", "ACCESSIBLE_FROM",
    "CONDUCTED_AT", "HAS_FACILITY", "PRODUCED",
    "CLASSIFIED_BY", "COMPLIES_WITH",
]

maritime_schema = [
    ("Vessel", "DOCKED_AT", "Port"),
    ("Vessel", "OWNED_BY", "Organization"),
    ("Vessel", "ON_VOYAGE", "Voyage"),
    ("Voyage", "TO_PORT", "Port"),
    ("Port", "LOCATED_IN", "SeaArea"),
    ("Port", "ACCESSIBLE_FROM", "SeaArea"),
    ("Incident", "INVOLVES", "Vessel"),
    ("Incident", "OCCURRED_AT", "SeaArea"),
    ("Organization", "HAS_FACILITY", "TestFacility"),
    ("Experiment", "CONDUCTED_AT", "TestFacility"),
    ("Experiment", "PRODUCED", "ExperimentalDataset"),
    ("Vessel", "COMPLIES_WITH", "Regulation"),
]
```

---

## 4. 우리 프로젝트에서의 활용 방안

| 활용처 | 현재 방식 | KG Builder 적용 시 | 우선순위 |
|--------|----------|------------------|----------|
| 해양사고 보고서 | `relation_extractor.py` 규칙 기반 | LLM 기반 자동 추출 (정확도 ↑) | HIGH |
| KRISO 논문 | 제목/저자 메타데이터만 저장 | 본문에서 연구 주제, 시설, 선박 관계 추출 | MEDIUM |
| 규정/법규 문서 | 수동 노드 생성 | PDF → 규정 간 참조 관계 자동 추출 | MEDIUM |
| VHF 교신 (2차년도) | 없음 | STT 텍스트 → 교신 참여자/위치/상황 추출 | 2차년도 |
| CCTV 캡션 (2차년도) | 없음 | 영상 설명 텍스트 → 선박/항만 관계 추출 | 2차년도 |

---

## 5. 기존 크롤러와의 통합 패턴

```python
# maritime/crawlers/relation_extractor.py 와 KG Builder 병행 사용 패턴
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline

class EnhancedRelationExtractor:
    """규칙 기반 + LLM 기반 하이브리드 관계 추출기."""

    def __init__(self, driver, llm):
        self.rule_based = RuleBasedExtractor()  # 기존 규칙 기반
        self.llm_pipeline = SimpleKGPipeline(
            llm=llm,
            driver=driver,
            entities=maritime_entities,
            relations=maritime_relations,
            potential_schema=maritime_schema,
        )

    async def extract(self, text: str) -> dict:
        # 1단계: 규칙 기반 추출 (빠르고 확실한 패턴)
        rule_results = self.rule_based.extract(text)

        # 2단계: LLM 기반 추출 (규칙으로 못 잡는 암묵적 관계)
        llm_results = await self.llm_pipeline.run(text=text)

        # 3단계: 결과 병합 + 중복 제거
        return merge_results(rule_results, llm_results)
```

---

## 6. 주의사항

1. **experimental 모듈**: `neo4j_graphrag.experimental` 하위에 있어 API가 변경될 수 있음. `pyproject.toml`에서 버전 고정 권장 (`neo4j-graphrag==1.13.0`).
2. **LLM 의존성**: 추출 품질이 LLM 성능에 크게 좌우됨. Qwen 7B로는 복잡한 관계 추출이 부정확할 수 있음.
3. **한국어 성능**: 영어 대비 한국어 엔티티/관계 추출 정확도가 낮을 수 있음. 프롬프트 튜닝 필요.
4. **비용/속도**: LLM 호출당 비용 발생. 대량 문서 처리 시 배치 + 캐싱 전략 필요.
5. **스키마 가이드 필수**: `potential_schema` 없이 사용하면 노이즈가 많음. 반드시 우리 온톨로지에 맞춰 스키마 정의.

---

## 7. 참고 자료

- [neo4j-graphrag PyPI](https://pypi.org/project/neo4j-graphrag/)
- [Neo4j GraphRAG Python 공식 문서](https://neo4j.com/docs/neo4j-graphrag-python/current/)
- [KG Builder 예제](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html)
- 우리 프로젝트 관련 파일:
  - `poc/graphrag_retrievers.py` — GraphRAG Retriever 5종
  - `poc/graphrag_demo.py` — Agentic GraphRAG 데모
  - `maritime/crawlers/relation_extractor.py` — 기존 규칙 기반 관계 추출기
  - `maritime/ontology/maritime_ontology.py` — 해사 온톨로지 (127 엔티티, 83 관계)
