"""NER Framework 단위 테스트.

TC-N01 ~ TC-N06: kg/nlp/ner/ 패키지의 NERTag, NERTagType, NERResult,
NERTagger 프로토콜, DictionaryTagger, NERPipeline 검증.
모든 테스트는 Neo4j 없이 순수 Python으로 동작한다.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from kg.nlp.ner import NERPipeline, NERResult, NERTag, NERTagType, NERTagger
from kg.nlp.ner.dictionary_tagger import DictionaryTagger
from kg.nlp.ner.models import NERResult as NERResultDirect
from kg.nlp.ner.models import NERTag as NERTagDirect
from kg.nlp.ner.models import NERTagType as NERTagTypeDirect
from kg.nlp.ner.pipeline import NERPipeline as NERPipelineDirect
from kg.nlp.ner.protocol import NERTagger as NERTaggerDirect


# =============================================================================
# TC-N01: NERTagType 열거형 검증
# =============================================================================


@pytest.mark.unit
class TestNERTagType:
    """NERTagType 열거형 값 및 타입 검증."""

    def test_all_12_types_exist(self) -> None:
        """TC-N01-a: 12개의 NERTagType 멤버가 모두 존재한다."""
        expected = {
            "VESSEL",
            "PORT",
            "BERTH",
            "ORG",
            "SEA_AREA",
            "FACILITY",
            "REGULATION",
            "MODEL_SHIP",
            "EXPERIMENT",
            "WEATHER",
            "DATE",
            "MMSI",
        }
        actual = {t.name for t in NERTagType}
        assert actual == expected, f"NERTagType 멤버 불일치: {actual} != {expected}"

    def test_member_count(self) -> None:
        """TC-N01-b: NERTagType 열거형 멤버 수는 정확히 12개이다."""
        assert len(NERTagType) == 12

    def test_str_enum(self) -> None:
        """TC-N01-c: NERTagType은 str 서브클래스이다."""
        assert isinstance(NERTagType.VESSEL, str)

    def test_vessel_value(self) -> None:
        """TC-N01-d: VESSEL 값은 문자열 'VESSEL'과 동일하다."""
        assert NERTagType.VESSEL == "VESSEL"

    def test_regulation_value(self) -> None:
        """TC-N01-e: REGULATION 값은 문자열 'REGULATION'과 동일하다."""
        assert NERTagType.REGULATION == "REGULATION"

    def test_str_comparison(self) -> None:
        """TC-N01-f: str Enum이므로 문자열 리터럴과 직접 비교 가능하다."""
        tag_type = NERTagType.PORT
        assert tag_type == "PORT"
        assert "PORT" == tag_type

    def test_imports_from_models(self) -> None:
        """TC-N01-g: kg.nlp.ner.models에서 직접 임포트도 동일 클래스이다."""
        assert NERTagTypeDirect is NERTagType


# =============================================================================
# TC-N02: NERTag 데이터클래스 검증
# =============================================================================


@pytest.mark.unit
class TestNERTag:
    """NERTag frozen 데이터클래스 생성 및 유효성 검증."""

    def test_valid_tag(self) -> None:
        """TC-N02-a: 올바른 값으로 NERTag 생성."""
        tag = NERTag(
            text="부산항",
            tag_type=NERTagType.PORT,
            start=0,
            end=3,
        )
        assert tag.text == "부산항"
        assert tag.tag_type == NERTagType.PORT
        assert tag.start == 0
        assert tag.end == 3
        assert tag.confidence == 1.0  # 기본값
        assert tag.source == ""  # 기본값

    def test_frozen(self) -> None:
        """TC-N02-b: NERTag는 frozen — 속성 할당 시 FrozenInstanceError."""
        tag = NERTag(text="COLREG", tag_type=NERTagType.REGULATION, start=0, end=6)
        with pytest.raises(FrozenInstanceError):
            tag.text = "SOLAS"  # type: ignore[misc]

    def test_invalid_confidence_high(self) -> None:
        """TC-N02-c: confidence > 1.0은 ValueError를 발생시킨다."""
        with pytest.raises(ValueError, match="confidence"):
            NERTag(text="test", tag_type=NERTagType.VESSEL, start=0, end=4, confidence=1.1)

    def test_invalid_confidence_low(self) -> None:
        """TC-N02-d: confidence < 0.0은 ValueError를 발생시킨다."""
        with pytest.raises(ValueError, match="confidence"):
            NERTag(text="test", tag_type=NERTagType.VESSEL, start=0, end=4, confidence=-0.1)

    def test_valid_confidence_boundary_zero(self) -> None:
        """TC-N02-e: confidence = 0.0은 유효한 값이다."""
        tag = NERTag(text="test", tag_type=NERTagType.VESSEL, start=0, end=4, confidence=0.0)
        assert tag.confidence == 0.0

    def test_valid_confidence_boundary_one(self) -> None:
        """TC-N02-f: confidence = 1.0은 유효한 값이다."""
        tag = NERTag(text="test", tag_type=NERTagType.VESSEL, start=0, end=4, confidence=1.0)
        assert tag.confidence == 1.0

    def test_invalid_start_negative(self) -> None:
        """TC-N02-g: start < 0은 ValueError를 발생시킨다."""
        with pytest.raises(ValueError, match="start"):
            NERTag(text="test", tag_type=NERTagType.VESSEL, start=-1, end=4)

    def test_end_before_start(self) -> None:
        """TC-N02-h: end < start는 ValueError를 발생시킨다."""
        with pytest.raises(ValueError):
            NERTag(text="test", tag_type=NERTagType.VESSEL, start=5, end=3)

    def test_end_equal_start_valid(self) -> None:
        """TC-N02-i: end == start는 유효하다 (빈 스팬)."""
        tag = NERTag(text="", tag_type=NERTagType.VESSEL, start=3, end=3)
        assert tag.start == tag.end

    def test_source_and_normalized_defaults(self) -> None:
        """TC-N02-j: source와 normalized의 기본값은 빈 문자열이다."""
        tag = NERTag(text="부산항", tag_type=NERTagType.PORT, start=0, end=3)
        assert tag.source == ""
        assert tag.normalized == ""

    def test_imports_from_models(self) -> None:
        """TC-N02-k: kg.nlp.ner.models에서 직접 임포트도 동일 클래스이다."""
        assert NERTagDirect is NERTag


# =============================================================================
# TC-N03: NERResult 데이터클래스 검증
# =============================================================================


@pytest.mark.unit
class TestNERResult:
    """NERResult frozen 데이터클래스 검증."""

    def test_empty_result(self) -> None:
        """TC-N03-a: 태그 없이 생성 시 has_entities는 False이다."""
        result = NERResult(text="hello")
        assert result.has_entities is False
        assert result.tags == ()

    def test_has_entities_with_tags(self) -> None:
        """TC-N03-b: 태그가 있으면 has_entities는 True이다."""
        tag = NERTag(text="부산항", tag_type=NERTagType.PORT, start=0, end=3)
        result = NERResult(text="부산항에서", tags=(tag,))
        assert result.has_entities is True

    def test_entities_by_type(self) -> None:
        """TC-N03-c: entities_by_type은 태그를 타입별로 올바르게 그룹화한다."""
        tag_port = NERTag(text="부산항", tag_type=NERTagType.PORT, start=0, end=3)
        tag_vessel = NERTag(text="컨테이너선", tag_type=NERTagType.VESSEL, start=5, end=10)
        tag_port2 = NERTag(text="인천항", tag_type=NERTagType.PORT, start=12, end=15)
        result = NERResult(text="부산항에서 컨테이너선이 인천항으로", tags=(tag_port, tag_vessel, tag_port2))

        by_type = result.entities_by_type
        assert NERTagType.PORT in by_type
        assert NERTagType.VESSEL in by_type
        assert len(by_type[NERTagType.PORT]) == 2
        assert len(by_type[NERTagType.VESSEL]) == 1

    def test_entities_by_type_empty(self) -> None:
        """TC-N03-d: 태그가 없으면 entities_by_type은 빈 dict이다."""
        result = NERResult(text="no entities here")
        assert result.entities_by_type == {}

    def test_frozen(self) -> None:
        """TC-N03-e: NERResult는 frozen — 속성 할당 시 FrozenInstanceError."""
        result = NERResult(text="test")
        with pytest.raises(FrozenInstanceError):
            result.text = "changed"  # type: ignore[misc]

    def test_processing_time_default(self) -> None:
        """TC-N03-f: processing_time_ms의 기본값은 0.0이다."""
        result = NERResult(text="hello")
        assert result.processing_time_ms == 0.0

    def test_imports_from_models(self) -> None:
        """TC-N03-g: kg.nlp.ner.models에서 직접 임포트도 동일 클래스이다."""
        assert NERResultDirect is NERResult


# =============================================================================
# TC-N04: NERTagger 프로토콜 검증
# =============================================================================


@pytest.mark.unit
class TestNERTaggerProtocol:
    """NERTagger 런타임 체크 가능 프로토콜 검증."""

    def test_runtime_checkable(self) -> None:
        """TC-N04-a: DictionaryTagger는 NERTagger 프로토콜을 만족한다."""
        tagger = DictionaryTagger()
        assert isinstance(tagger, NERTagger)

    def test_custom_tagger_satisfies_protocol(self) -> None:
        """TC-N04-b: tag, name, supported_types를 구현한 클래스는 프로토콜을 만족한다."""

        class MinimalTagger:
            def tag(self, text: str) -> list[NERTag]:
                return []

            @property
            def name(self) -> str:
                return "minimal"

            @property
            def supported_types(self) -> frozenset[NERTagType]:
                return frozenset({NERTagType.VESSEL})

        tagger = MinimalTagger()
        assert isinstance(tagger, NERTagger)

    def test_incomplete_tagger_fails_protocol(self) -> None:
        """TC-N04-c: tag 메서드가 없는 클래스는 프로토콜을 만족하지 않는다."""

        class IncompleteTagger:
            @property
            def name(self) -> str:
                return "incomplete"

            @property
            def supported_types(self) -> frozenset[NERTagType]:
                return frozenset()

        tagger = IncompleteTagger()
        assert not isinstance(tagger, NERTagger)

    def test_imports_from_protocol(self) -> None:
        """TC-N04-d: kg.nlp.ner.protocol에서 직접 임포트도 동일 클래스이다."""
        assert NERTaggerDirect is NERTagger


# =============================================================================
# TC-N05: DictionaryTagger 검증
# =============================================================================


@pytest.mark.unit
class TestDictionaryTagger:
    """DictionaryTagger 딕셔너리 기반 NER 검증."""

    def test_empty_tagger(self) -> None:
        """TC-N05-a: 빈 딕셔너리로 생성 시 아무 태그도 반환하지 않는다."""
        tagger = DictionaryTagger()
        tags = tagger.tag("부산항에서 컨테이너선이 출항")
        assert tags == []

    def test_simple_match(self) -> None:
        """TC-N05-b: 등록된 용어를 텍스트에서 찾아 올바른 오프셋을 반환한다."""
        tagger = DictionaryTagger(entries={"부산항": NERTagType.PORT})
        tags = tagger.tag("부산항에서 출항했다")
        assert len(tags) == 1
        tag = tags[0]
        assert tag.text == "부산항"
        assert tag.tag_type == NERTagType.PORT
        assert tag.start == 0
        assert tag.end == 3

    def test_case_insensitive_ascii(self) -> None:
        """TC-N05-c: ASCII 용어는 대소문자 구분 없이 매칭된다."""
        tagger = DictionaryTagger(entries={"COLREG": NERTagType.REGULATION})
        tags = tagger.tag("colreg 협약을 준수해야 한다")
        assert len(tags) == 1
        assert tags[0].tag_type == NERTagType.REGULATION

    def test_case_insensitive_ascii_upper_in_text(self) -> None:
        """TC-N05-d: 딕셔너리에 소문자, 텍스트에 대문자도 매칭된다."""
        tagger = DictionaryTagger(entries={"solas": NERTagType.REGULATION})
        tags = tagger.tag("SOLAS 협약")
        assert len(tags) == 1

    def test_case_sensitive_korean(self) -> None:
        """TC-N05-e: 한국어 용어는 대소문자 구분 없이 매칭이 되지 않는다 (정확 일치)."""
        tagger = DictionaryTagger(entries={"부산항": NERTagType.PORT})
        # 동일한 한국어라도 정확히 일치해야 매칭됨
        tags_match = tagger.tag("부산항 인근")
        tags_no_match = tagger.tag("BUSAN 인근")
        assert len(tags_match) == 1
        assert len(tags_no_match) == 0

    def test_multiple_matches(self) -> None:
        """TC-N05-f: 여러 용어가 동일 텍스트에서 모두 매칭된다."""
        tagger = DictionaryTagger(
            entries={
                "부산항": NERTagType.PORT,
                "컨테이너선": NERTagType.VESSEL,
                "COLREG": NERTagType.REGULATION,
            }
        )
        tags = tagger.tag("부산항에서 컨테이너선이 COLREG 준수하며 출항")
        tag_types = {t.tag_type for t in tags}
        assert NERTagType.PORT in tag_types
        assert NERTagType.VESSEL in tag_types
        assert NERTagType.REGULATION in tag_types

    def test_tag_source_is_dictionary(self) -> None:
        """TC-N05-g: DictionaryTagger가 생성한 태그의 source는 'dictionary'이다."""
        tagger = DictionaryTagger(entries={"부산항": NERTagType.PORT})
        tags = tagger.tag("부산항")
        assert len(tags) == 1
        assert tags[0].source == "dictionary"

    def test_name_property(self) -> None:
        """TC-N05-h: DictionaryTagger.name은 'dictionary'이다."""
        tagger = DictionaryTagger()
        assert tagger.name == "dictionary"

    def test_supported_types_empty_tagger(self) -> None:
        """TC-N05-i: 빈 딕셔너리 tagger의 supported_types는 빈 frozenset이다."""
        tagger = DictionaryTagger()
        assert tagger.supported_types == frozenset()

    def test_supported_types_reflects_entries(self) -> None:
        """TC-N05-j: supported_types는 등록된 용어의 타입을 반영한다."""
        tagger = DictionaryTagger(
            entries={
                "부산항": NERTagType.PORT,
                "컨테이너선": NERTagType.VESSEL,
            }
        )
        assert NERTagType.PORT in tagger.supported_types
        assert NERTagType.VESSEL in tagger.supported_types

    def test_from_maritime_terms(self) -> None:
        """TC-N05-k: from_maritime_terms() 팩토리로 생성한 tagger는 비어있지 않다."""
        tagger = DictionaryTagger.from_maritime_terms()
        assert len(tagger._entries) > 0
        assert len(tagger.supported_types) > 0

    def test_from_maritime_terms_has_port_type(self) -> None:
        """TC-N05-l: from_maritime_terms() tagger는 PORT 타입을 포함한다."""
        tagger = DictionaryTagger.from_maritime_terms()
        assert NERTagType.PORT in tagger.supported_types

    def test_repeated_term_in_text(self) -> None:
        """TC-N05-m: 동일 용어가 텍스트에 여러 번 등장하면 모두 매칭된다."""
        tagger = DictionaryTagger(entries={"항": NERTagType.PORT})
        tags = tagger.tag("부산항과 인천항")
        # '항'이 2번 등장
        assert len(tags) == 2


# =============================================================================
# TC-N06: NERPipeline 검증
# =============================================================================


@pytest.mark.unit
class TestNERPipeline:
    """NERPipeline 합성 및 중복 제거 검증."""

    def test_empty_pipeline(self) -> None:
        """TC-N06-a: 빈 파이프라인은 태그 없는 NERResult를 반환한다."""
        pipeline = NERPipeline()
        result = pipeline.process("부산항에서 출항")
        assert result.has_entities is False
        assert result.tags == ()

    def test_single_tagger(self) -> None:
        """TC-N06-b: 단일 tagger가 등록된 파이프라인은 해당 태그를 반환한다."""
        tagger = DictionaryTagger(entries={"부산항": NERTagType.PORT})
        pipeline = NERPipeline().add_tagger(tagger)
        result = pipeline.process("부산항에서 출항했다")
        assert result.has_entities is True
        assert len(result.tags) == 1
        assert result.tags[0].tag_type == NERTagType.PORT

    def test_dedup_longer_span_wins(self) -> None:
        """TC-N06-c: 겹치는 스팬 중 더 긴 스팬이 선택된다."""

        class ShortTagger:
            def tag(self, text: str) -> list[NERTag]:
                # "부산"만 매칭 (짧은 스팬)
                pos = text.find("부산")
                if pos == -1:
                    return []
                return [NERTag(text="부산", tag_type=NERTagType.SEA_AREA, start=pos, end=pos + 2)]

            @property
            def name(self) -> str:
                return "short"

            @property
            def supported_types(self) -> frozenset[NERTagType]:
                return frozenset({NERTagType.SEA_AREA})

        long_tagger = DictionaryTagger(entries={"부산항": NERTagType.PORT})
        pipeline = NERPipeline().add_tagger(long_tagger).add_tagger(ShortTagger())
        result = pipeline.process("부산항에서 출항")

        # 더 긴 스팬("부산항")이 남아야 함
        assert len(result.tags) == 1
        assert result.tags[0].text == "부산항"
        assert result.tags[0].tag_type == NERTagType.PORT

    def test_dedup_higher_confidence_wins(self) -> None:
        """TC-N06-d: 동일 스팬 길이일 때 confidence가 높은 태그가 선택된다."""

        class HighConfTagger:
            def tag(self, text: str) -> list[NERTag]:
                pos = text.find("부산항")
                if pos == -1:
                    return []
                return [
                    NERTag(
                        text="부산항",
                        tag_type=NERTagType.PORT,
                        start=pos,
                        end=pos + 3,
                        confidence=0.95,
                        source="high",
                    )
                ]

            @property
            def name(self) -> str:
                return "high_conf"

            @property
            def supported_types(self) -> frozenset[NERTagType]:
                return frozenset({NERTagType.PORT})

        class LowConfTagger:
            def tag(self, text: str) -> list[NERTag]:
                pos = text.find("부산항")
                if pos == -1:
                    return []
                return [
                    NERTag(
                        text="부산항",
                        tag_type=NERTagType.SEA_AREA,
                        start=pos,
                        end=pos + 3,
                        confidence=0.5,
                        source="low",
                    )
                ]

            @property
            def name(self) -> str:
                return "low_conf"

            @property
            def supported_types(self) -> frozenset[NERTagType]:
                return frozenset({NERTagType.SEA_AREA})

        pipeline = NERPipeline().add_tagger(LowConfTagger()).add_tagger(HighConfTagger())
        result = pipeline.process("부산항에서")

        assert len(result.tags) == 1
        assert result.tags[0].confidence == 0.95
        assert result.tags[0].tag_type == NERTagType.PORT

    def test_non_overlapping_tags_both_kept(self) -> None:
        """TC-N06-e: 겹치지 않는 태그는 모두 유지된다."""
        tagger = DictionaryTagger(
            entries={
                "부산항": NERTagType.PORT,
                "컨테이너선": NERTagType.VESSEL,
            }
        )
        pipeline = NERPipeline().add_tagger(tagger)
        result = pipeline.process("부산항에서 컨테이너선이 출항")
        assert len(result.tags) == 2

    def test_fluent_add_tagger(self) -> None:
        """TC-N06-f: add_tagger()는 self를 반환하여 체이닝이 가능하다."""
        pipeline = NERPipeline()
        tagger = DictionaryTagger()
        returned = pipeline.add_tagger(tagger)
        assert returned is pipeline

    def test_processing_time_recorded(self) -> None:
        """TC-N06-g: 처리 시간이 0 이상으로 기록된다."""
        tagger = DictionaryTagger(entries={"부산항": NERTagType.PORT})
        pipeline = NERPipeline().add_tagger(tagger)
        result = pipeline.process("부산항에서 출항했다")
        assert result.processing_time_ms >= 0.0

    def test_result_sorted_by_start(self) -> None:
        """TC-N06-h: 결과 태그는 start 오프셋 오름차순으로 정렬된다."""
        tagger = DictionaryTagger(
            entries={
                "컨테이너선": NERTagType.VESSEL,
                "부산항": NERTagType.PORT,
            }
        )
        pipeline = NERPipeline().add_tagger(tagger)
        result = pipeline.process("부산항에서 컨테이너선이")
        assert len(result.tags) == 2
        assert result.tags[0].start <= result.tags[1].start

    def test_result_text_preserved(self) -> None:
        """TC-N06-i: NERResult의 text는 원본 입력 텍스트이다."""
        pipeline = NERPipeline()
        input_text = "부산항에서 출항했다"
        result = pipeline.process(input_text)
        assert result.text == input_text

    def test_multiple_taggers_combined(self) -> None:
        """TC-N06-j: 여러 tagger의 결과가 합산된다 (겹침 없을 때)."""
        port_tagger = DictionaryTagger(entries={"부산항": NERTagType.PORT})
        vessel_tagger = DictionaryTagger(entries={"컨테이너선": NERTagType.VESSEL})
        pipeline = NERPipeline().add_tagger(port_tagger).add_tagger(vessel_tagger)
        result = pipeline.process("부산항에서 컨테이너선이 출항")
        tag_types = {t.tag_type for t in result.tags}
        assert NERTagType.PORT in tag_types
        assert NERTagType.VESSEL in tag_types

    def test_imports_from_pipeline(self) -> None:
        """TC-N06-k: kg.nlp.ner.pipeline에서 직접 임포트도 동일 클래스이다."""
        assert NERPipelineDirect is NERPipeline
