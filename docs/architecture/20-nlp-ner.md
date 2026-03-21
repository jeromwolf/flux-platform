# 20. NLP 및 개체명 인식 (NER) 전략

[← 마이그레이션 전략](./19-migration-strategy.md) | [다음: 시각화 아키텍처 →](./21-visualization.md)

---

## 20.1 개요

IMSP의 NLP 파이프라인은 Text2Cypher (자연어 → Cypher 변환)의 전처리 단계로,
해사 도메인 특화 개체명 인식(NER)과 엔티티 해석(Entity Resolution)을 수행한다.

```
사용자 질의 (한국어/영어)
    |
    v
+-----------------------------+
|   1. NL Parser              |  <-- core/kg/nlp/nl_parser.py
|   (형태소 분석 + 의도 분류)  |
+-----------------------------+
|   2. NER (개체명 인식)       |  <-- Y1: 사전 기반, Y2: ML 기반
|   (선박명, 항만명, 기관명)   |
+-----------------------------+
|   3. Entity Resolution      |  <-- core/kg/entity_resolution/
|   (KG 엔티티 매칭)          |
+-----------------------------+
|   4. Term Dictionary        |  <-- domains/maritime/nlp/
|   (해사 용어 정규화)         |
+-----------------------------+
|   5. Cypher Generation      |  <-- core/kg/query_generator.py
|   (구조화 쿼리 생성)         |
+-----------------------------+
```

---

## 20.2 현재 구현 상태 (Y1 -- 사전 기반)

### 20.2.1 NL Parser (`core/kg/nlp/nl_parser.py`)

- 규칙 기반 한국어 자연어 파서
- 의도 분류: SEARCH / AGGREGATE / FILTER / NAVIGATE
- 엔티티 추출: 정규식 + 사전 매칭

### 20.2.2 해사 용어 사전 (`domains/maritime/nlp/maritime_terms.py`)

- Korean → English 레이블 매핑 (180+ 항목)
- 동의어 사전 (50+ 동의어 그룹)
- 개체명 매핑 (Named Entity Mappings) -- 항만, 기관, 해역 등
- `resolve_named_entity()` 함수: 이름 → Neo4j 매치 조건 변환

### 20.2.3 엔티티 해석기 (`core/kg/entity_resolution/`)

- 3단계 해석 파이프라인:
  1. **정확 매칭** (Exact Match)
  2. **퍼지 매칭** (Fuzzy Match -- Levenshtein distance)
  3. **임베딩 유사도** (Embedding Similarity -- Ollama)
- `resolver.py`: 메인 해석 로직
- `fuzzy_matcher.py`: 유사 문자열 매칭
- `models.py`: 해석 결과 모델

### 20.2.4 TermDictionary Protocol (`core/kg/nlp/term_dictionary.py`)

- Strategy 패턴: 도메인별 용어 사전 교체 가능
- 현재 구현: `MaritimeTermDictionary`
- 인터페이스: `lookup()`, `synonyms()`, `resolve()`

---

## 20.3 해사 도메인 NER 태그셋

| NER 태그 | 설명 | 예시 | KG 레이블 |
|----------|------|------|----------|
| VESSEL | 선박명 | "HMM 알헤시라스", "Ever Given" | `:Vessel` |
| PORT | 항만명 | "부산항", "Port of Singapore" | `:Port` |
| BERTH | 선석명 | "부산 신항 7-1선석" | `:Berth` |
| ORG | 기관/조직 | "KRISO", "HMM", "해양수산부" | `:Organization` |
| SEA_AREA | 해역 | "동해", "대한해협" | `:SeaArea` |
| FACILITY | 시설 | "심해공학수조", "캐비테이션터널" | `:Facility` |
| REGULATION | 규정 | "MARPOL", "SOLAS" | `:Regulation` |
| MODEL_SHIP | 모형선 | "KCS 모형선" | `:ModelShip` |
| EXPERIMENT | 실험 | "내항성능시험" | `:Experiment` |
| WEATHER | 기상현상 | "태풍 힌남노", "동풍 15m/s" | (속성) |
| DATE | 날짜/기간 | "2026년 3월", "최근 1주일" | (필터) |
| MMSI | 선박식별번호 | "440123456" | (속성) |

---

## 20.4 NER 모델 진화 로드맵

### Phase 1: Y1 -- 사전 기반 NER (현재)

```
입력: "부산항에 정박 중인 HMM 알헤시라스 선박 정보"
     |
     v
사전 매칭 (maritime_terms.py)
     |
     +-- "부산항"        --> PORT   {name: "Busan Port"}
     +-- "HMM 알헤시라스" --> VESSEL {name: "HMM Algeciras"}
     +-- "정박"          --> RELATION (DOCKED_AT)
```

- **장점:** 빠른 응답 (< 10ms), 외부 의존 없음
- **단점:** 미등록 개체 인식 불가, 문맥 무시

### Phase 2: Y2 -- ML 기반 NER

| 항목 | 기술 선택 |
|------|----------|
| 한국어 형태소 분석 | Kiwi (v0.16+) 또는 KoNLPy (Mecab) |
| NER 모델 | SpaCy v3 + 한국어 파이프라인 (ko_core_web_trf) |
| 커스텀 NER | SpaCy NER + 해사 도메인 학습 데이터 |
| 학습 프레임워크 | SpaCy prodigy 또는 Label Studio |

### Phase 3: Y3+ -- 도메인 Fine-tuned NER

| 항목 | 기술 선택 |
|------|----------|
| Base 모델 | KLUE-BERT 또는 KoELECTRA |
| Fine-tuning | 해사 NER 데이터셋 (5,000+ 문장) |
| 서빙 | ONNX Runtime (CPU) 또는 vLLM (GPU) |
| 성능 목표 | F1 > 0.90 (해사 엔티티) |

---

## 20.5 NER 학습 데이터 구축 계획

### 데이터 소스

| 출처 | 데이터 유형 | 예상 수량 | 확보 시기 |
|------|-----------|----------|----------|
| KRISO 연구 보고서 | 기술 문서 | 500+ 문서 | Y1 Q4 |
| 해양수산부 공고 | 행정 문서 | 1,000+ 건 | Y1 Q3 |
| 해사 뉴스 (연합뉴스 등) | 뉴스 기사 | 2,000+ 건 | Y2 Q1 |
| AIS 항적 메시지 | 구조화 데이터 | 100,000+ 건 | Y1 Q2 |
| VTS 교신 기록 | 반구조화 텍스트 | 500+ 건 | Y2 Q2 |

### 어노테이션 파이프라인

```
1. 사전 어노테이션
   +-- 기존 사전 기반 NER로 자동 태깅
   |
   v
2. 수동 검수
   +-- Label Studio 기반 교정 (도메인 전문가 2인 이상)
   |
   v
3. 품질 검증
   +-- Inter-Annotator Agreement (IAA) > 0.85
   +-- Cohen's Kappa 기반 일치도 측정
   |
   v
4. 데이터 증강
   +-- 동의어 치환 (vessel name 변형)
   +-- 문장 재구성 (어순 변환)
   +-- Back-translation (한국어 -> 영어 -> 한국어)
   +-- 문맥 삽입 (날짜, 기상 조건 추가)
```

### 데이터셋 목표

| 연차 | 어노테이션 문장 수 | NER 태그 종류 | F1 목표 |
|------|------------------|-------------|---------|
| Y1 | 500 (사전 기반) | 6종 | -- (규칙 기반) |
| Y2 | 3,000 | 10종 | 0.80+ |
| Y3 | 5,000+ | 12종 | 0.90+ |

### 어노테이션 가이드라인 핵심 원칙

1. **최소 범위 원칙:** 개체명은 최소 범위로 태깅 ("부산항"은 PORT, "부산항 제1부두"는 BERTH)
2. **중첩 불허:** 동일 토큰에 복수 태그 불가, 더 구체적인 태그 우선
3. **문맥 의존:** "동해"는 해역(SEA_AREA)이지만 "동해시"는 지명(태깅 제외)
4. **약칭 포함:** "MOF"는 ORG ("해양수산부"와 동일 엔티티)

---

## 20.6 Text2Cypher 파이프라인 통합

### NER → Entity Resolution → Cypher 매핑

```python
# 예시: NER 결과를 Entity Resolution에 전달

# Step 1: NER 수행
ner_results = ner_model.predict("부산항에 정박 중인 컨테이너선")
# [("부산항", "PORT"), ("컨테이너선", "VESSEL_TYPE")]

# Step 2: Entity Resolution (KG 매칭)
resolved = entity_resolver.resolve(ner_results, ontology)
# [
#   ResolvedEntity(label="Port", property="name", value="Busan Port"),
#   ResolvedEntity(label="Vessel", property="vesselType", value="ContainerShip")
# ]

# Step 3: Cypher 생성
cypher = cypher_generator.from_entities(resolved)
# MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port {name: 'Busan Port'})
# WHERE v.vesselType = 'ContainerShip'
# RETURN v
```

### 다중 엔티티 해석 전략

복수 개의 NER 결과가 존재할 때 Entity Resolution은 다음 전략을 적용한다:

```
NER 결과: [("부산항", PORT), ("HMM", ORG), ("컨테이너선", VESSEL_TYPE)]
                |                |               |
                v                v               v
         Exact Match       Fuzzy Match     Type Mapping
         (KG 노드 검색)    (유사 조직 검색)  (속성 변환)
                |                |               |
                v                v               v
         Port 노드 확정    Organization    vesselType 속성
                           후보 3건 반환    "ContainerShip"
                                |
                                v
                        Confidence 순 정렬
                        (상위 1건 선택)
```

### 모호성 해소 (Disambiguation)

| 모호성 유형 | 예시 | 해소 전략 |
|------------|------|----------|
| 동음이의어 | "현대" (선사 vs 자동차) | 문맥 키워드 ("선박", "항만" 등) 기반 도메인 필터 |
| 약칭 충돌 | "MOF" (해양수산부 vs 기타) | 해사 도메인 우선순위 테이블 |
| 부분 매칭 | "부산" (부산항 vs 부산신항) | 대화 컨텍스트 (이전 질의 참조) + 사용자 확인 |
| 언어 혼용 | "Busan Port" vs "부산항" | 정규화 사전 (canonical name 매핑) |

---

## 20.7 성능 요구사항

| 지표 | Y1 (사전 기반) | Y2 (ML) | Y3 (Fine-tuned) |
|------|--------------|---------|----------------|
| 처리 속도 | < 10ms | < 50ms | < 100ms |
| F1 (전체) | ~0.70 | 0.80+ | 0.90+ |
| F1 (선박명) | ~0.90 | 0.95+ | 0.98+ |
| F1 (항만명) | ~0.85 | 0.92+ | 0.96+ |
| 미등록 엔티티 인식 | 불가 | 부분 가능 | 가능 |
| GPU 필요 | 아니오 | 아니오 (CPU) | 선택적 |

### 성능 측정 방법

```
평가 데이터셋 (domains/maritime/evaluation/)
    |
    v
NER 모델 실행
    |
    v
예측 결과 vs 정답 비교
    |
    +-- Precision: 예측 엔티티 중 정답 비율
    +-- Recall: 정답 엔티티 중 인식 비율
    +-- F1: Precision * Recall 의 조화 평균
    |
    v
태그별 F1 분석
    |
    +-- VESSEL F1, PORT F1, ORG F1, ...
    +-- Confusion Matrix (오분류 패턴 분석)
    |
    v
Entity Resolution 정확도
    |
    +-- KG 매칭 성공률 (Top-1 Accuracy)
    +-- KG 매칭 성공률 (Top-3 Accuracy)
```

---

## 20.8 코드 매핑

| 모듈 | 파일 | 역할 |
|------|------|------|
| NL Parser | `core/kg/nlp/nl_parser.py` | 자연어 의도 분류 + 규칙 기반 엔티티 추출 |
| Term Dictionary | `core/kg/nlp/term_dictionary.py` | 용어 사전 Protocol (Strategy 패턴) |
| Maritime Terms | `domains/maritime/nlp/maritime_terms.py` | 해사 용어 사전 (180+ 레이블, 50+ 동의어) |
| Entity Resolver | `core/kg/entity_resolution/resolver.py` | 3단계 엔티티 해석 |
| Fuzzy Matcher | `core/kg/entity_resolution/fuzzy_matcher.py` | Levenshtein 거리 기반 매칭 |
| Resolution Models | `core/kg/entity_resolution/models.py` | 해석 결과 데이터 모델 |
| Embeddings | `core/kg/embeddings/` | Ollama 기반 벡터 임베딩 |
| Relation Extractor | `domains/maritime/crawlers/relation_extractor.py` | 키워드 → 관계 추출 (NER/RE 전환 예정) |
| Evaluation | `core/kg/evaluation/` | 평가 프레임워크 (F1, 정확도 측정) |

> **역방향 의존성 경고:** `core/kg/nlp/maritime_terms.py`는 `maritime.*`을 import하는
> shim 파일이다. Y1 Q4에 Plugin Architecture로 전환하여 `core/`의 도메인 독립성을
> 확보해야 한다. 상세한 수정 계획은 [16-architecture-review.md](./16-architecture-review.md)
> C-1 항목을 참조한다.

---

## 20.9 Plugin Architecture 전환 (Y1 Q4)

현재 `core/kg/nlp/` 모듈은 해사 도메인에 직접 의존하고 있다.
Y1 Q4에 다음과 같은 Plugin Architecture로 전환하여 도메인 독립성을 확보한다.

```
Before (현재):
  core/kg/nlp/nl_parser.py
      |
      +-- import maritime_terms  (역방향 의존)

After (Y1 Q4):
  core/kg/nlp/nl_parser.py
      |
      +-- TermDictionary Protocol (추상 인터페이스)
              ^
              |
  domains/maritime/nlp/maritime_terms.py
      +-- MaritimeTermDictionary(TermDictionary)  (구현)

  domains/energy/nlp/energy_terms.py          (향후 확장 예시)
      +-- EnergyTermDictionary(TermDictionary)    (구현)
```

### NER Provider 인터페이스

```python
# core/kg/nlp/ner_provider.py (Y2 신규)
from typing import Protocol

class NERProvider(Protocol):
    """도메인별 NER 모델을 교체할 수 있는 추상 인터페이스."""

    def predict(self, text: str) -> list[tuple[str, str, float]]:
        """텍스트에서 개체명을 인식한다.

        Returns:
            list of (entity_text, ner_tag, confidence)
        """
        ...

    def supported_tags(self) -> list[str]:
        """지원하는 NER 태그 목록을 반환한다."""
        ...


class DictionaryNERProvider:
    """사전 기반 NER (Y1)."""
    ...

class SpaCyNERProvider:
    """SpaCy 기반 ML NER (Y2)."""
    ...

class TransformerNERProvider:
    """Transformer 기반 Fine-tuned NER (Y3)."""
    ...
```

---

## 20.10 구현 로드맵

| 시기 | 마일스톤 | 산출물 |
|------|---------|--------|
| Y1 Q2 | 사전 기반 NER 고도화 | 해사 용어 사전 300+ 확장, 동의어 100+ |
| Y1 Q3 | NER 평가 프레임워크 구축 | F1 자동 측정 스크립트, 평가 데이터셋 v1 |
| Y1 Q4 | 어노테이션 파이프라인 구축 | Label Studio 배포, 500 문장 어노테이션 |
| Y1 Q4 | Plugin Architecture 전환 | `core/kg/` 역방향 의존 제거 완료 |
| Y2 Q1 | SpaCy 한국어 NER PoC | ko_core_web_trf 기반 파이프라인 검증 |
| Y2 Q2 | 해사 커스텀 NER 모델 v1 | 3,000 문장 학습, F1 0.80+ 달성 |
| Y2 Q3 | Entity Resolution 고도화 | 임베딩 기반 해석 강화, MinHash LSH 도입 |
| Y3 Q1 | Fine-tuned NER 모델 | KLUE-BERT 기반, 5,000+ 문장 학습 |
| Y3 Q2 | NER + Text2Cypher 통합 최적화 | 엔드투엔드 파이프라인 F1 0.90+ |
| Y3 Q3 | NER 서빙 최적화 | ONNX Runtime 변환, < 100ms 응답 |

---

## 20.11 관련 아키텍처 문서

| 문서 | 관련 내용 |
|------|----------|
| [07-data-flow.md](./07-data-flow.md) | Text2Cypher 5단계 파이프라인 데이터 흐름 |
| [11-ai-llm.md](./11-ai-llm.md) | LLM 모델 스택, 파인튜닝 전략 |
| [16-architecture-review.md](./16-architecture-review.md) | C-1 역방향 의존 제거 계획 |
| [04-data-architecture.md](./04-data-architecture.md) | 온톨로지 스키마, 엔티티 타입 |

---

[← 마이그레이션 전략](./19-migration-strategy.md) | [다음: 시각화 아키텍처 →](./21-visualization.md)
