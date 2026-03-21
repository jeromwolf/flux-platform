"""Comprehensive unit tests for the evaluation framework.

Tests all evaluation components: dataset CRUD, metrics (CypherAccuracy,
QueryRelevancy, ReasoningTypeMetric), EvaluationRunner, and EvalReport.

Usage::

    PYTHONPATH=. python -m pytest tests/test_evaluation.py -v -m unit
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from maritime.evaluation.dataset import (
    Difficulty,
    EvalDataset,
    EvalQuestion,
    ReasoningType,
)
from kg.evaluation.metrics import (
    CypherAccuracy,
    QueryRelevancy,
    ReasoningTypeMetric,
    _extract_node_labels,
    _extract_property_filters,
    _extract_relationship_types,
    _extract_return_fields,
)
from kg.evaluation.runner import EvalReport, EvaluationRunner

# =========================================================================
# Helpers
# =========================================================================


def _make_question(
    question: str = "테스트 질문",
    cypher: str = "MATCH (v:Vessel) RETURN v",
    labels: list[str] | None = None,
    reasoning_type: ReasoningType = ReasoningType.DIRECT,
    difficulty: Difficulty = Difficulty.EASY,
    description: str = "test question",
) -> EvalQuestion:
    """Helper to create EvalQuestion with defaults."""
    return EvalQuestion(
        question=question,
        ground_truth_cypher=cypher,
        expected_labels=labels or ["Vessel"],
        reasoning_type=reasoning_type,
        difficulty=difficulty,
        description=description,
    )


# =========================================================================
# 1. EvalDataset CRUD tests
# =========================================================================


class TestEvalDataset:
    """EvalDataset 생성, 추가, 필터링, 요약 테스트."""

    @pytest.mark.unit
    def test_empty_dataset(self) -> None:
        """빈 데이터셋 생성."""
        ds = EvalDataset()
        assert len(ds.questions) == 0

    @pytest.mark.unit
    def test_add_question(self) -> None:
        """질문 추가."""
        ds = EvalDataset()
        q = _make_question()
        ds.add_question(q)
        assert len(ds.questions) == 1
        assert ds.questions[0].question == "테스트 질문"

    @pytest.mark.unit
    def test_add_multiple_questions(self) -> None:
        """여러 질문 추가."""
        ds = EvalDataset()
        for i in range(5):
            ds.add_question(_make_question(question=f"질문 {i}"))
        assert len(ds.questions) == 5

    @pytest.mark.unit
    def test_get_by_difficulty_easy(self) -> None:
        """난이도별 필터링: EASY."""
        ds = EvalDataset()
        ds.add_question(_make_question(difficulty=Difficulty.EASY))
        ds.add_question(_make_question(difficulty=Difficulty.MEDIUM))
        ds.add_question(_make_question(difficulty=Difficulty.HARD))
        ds.add_question(_make_question(difficulty=Difficulty.EASY))

        easy = ds.get_by_difficulty(Difficulty.EASY)
        assert len(easy) == 2
        assert all(q.difficulty == Difficulty.EASY for q in easy)

    @pytest.mark.unit
    def test_get_by_difficulty_returns_empty_for_missing(self) -> None:
        """없는 난이도 필터링 시 빈 리스트."""
        ds = EvalDataset()
        ds.add_question(_make_question(difficulty=Difficulty.EASY))
        hard = ds.get_by_difficulty(Difficulty.HARD)
        assert len(hard) == 0

    @pytest.mark.unit
    def test_get_by_reasoning_type(self) -> None:
        """추론유형별 필터링."""
        ds = EvalDataset()
        ds.add_question(_make_question(reasoning_type=ReasoningType.DIRECT))
        ds.add_question(_make_question(reasoning_type=ReasoningType.BRIDGE))
        ds.add_question(_make_question(reasoning_type=ReasoningType.DIRECT))
        ds.add_question(_make_question(reasoning_type=ReasoningType.INTERSECTION))

        direct = ds.get_by_reasoning_type(ReasoningType.DIRECT)
        assert len(direct) == 2

        bridge = ds.get_by_reasoning_type(ReasoningType.BRIDGE)
        assert len(bridge) == 1

    @pytest.mark.unit
    def test_summary_contains_counts(self) -> None:
        """요약 문자열에 카운트 포함."""
        ds = EvalDataset()
        ds.add_question(_make_question(difficulty=Difficulty.EASY))
        ds.add_question(_make_question(difficulty=Difficulty.MEDIUM))

        summary = ds.summary()
        assert "2 questions" in summary
        assert "EASY: 1" in summary
        assert "MEDIUM: 1" in summary

    @pytest.mark.unit
    def test_summary_shows_reasoning_types(self) -> None:
        """요약 문자열에 추론유형 포함."""
        ds = EvalDataset()
        ds.add_question(_make_question(reasoning_type=ReasoningType.BRIDGE))
        summary = ds.summary()
        assert "BRIDGE: 1" in summary

    @pytest.mark.unit
    def test_init_with_questions_list(self) -> None:
        """질문 리스트로 초기화."""
        questions = [_make_question(), _make_question(question="질문2")]
        ds = EvalDataset(questions=questions)
        assert len(ds.questions) == 2


# =========================================================================
# 2. Built-in dataset tests
# =========================================================================


class TestBuiltinDataset:
    """Built-in 해사 평가 데이터셋 검증."""

    @pytest.mark.unit
    def test_builtin_has_30_questions(self) -> None:
        """Built-in 데이터셋 30문항."""
        ds = EvalDataset.builtin()
        assert len(ds.questions) == 30

    @pytest.mark.unit
    def test_builtin_difficulty_distribution(self) -> None:
        """Built-in 데이터셋 난이도 분포: 10/10/10."""
        ds = EvalDataset.builtin()
        assert len(ds.get_by_difficulty(Difficulty.EASY)) == 10
        assert len(ds.get_by_difficulty(Difficulty.MEDIUM)) == 10
        assert len(ds.get_by_difficulty(Difficulty.HARD)) == 10

    @pytest.mark.unit
    def test_builtin_all_have_cypher(self) -> None:
        """모든 질문에 ground truth Cypher 존재."""
        ds = EvalDataset.builtin()
        for q in ds.questions:
            assert q.ground_truth_cypher, f"Missing cypher: {q.question}"
            assert "MATCH" in q.ground_truth_cypher or "RETURN" in q.ground_truth_cypher

    @pytest.mark.unit
    def test_builtin_all_have_labels(self) -> None:
        """모든 질문에 expected_labels 존재."""
        ds = EvalDataset.builtin()
        for q in ds.questions:
            assert len(q.expected_labels) > 0, f"Missing labels: {q.question}"

    @pytest.mark.unit
    def test_builtin_all_have_description(self) -> None:
        """모든 질문에 설명 존재."""
        ds = EvalDataset.builtin()
        for q in ds.questions:
            assert q.description, f"Missing description: {q.question}"

    @pytest.mark.unit
    def test_builtin_has_all_reasoning_types(self) -> None:
        """Built-in 데이터셋에 DIRECT, BRIDGE, INTERSECTION, COMPOSITION, COMPARISON 포함."""
        ds = EvalDataset.builtin()
        present_types = {q.reasoning_type for q in ds.questions}
        # 최소한 DIRECT, BRIDGE는 반드시 존재
        assert ReasoningType.DIRECT in present_types
        assert ReasoningType.BRIDGE in present_types
        # HARD 질문에서 INTERSECTION, COMPOSITION, COMPARISON도 존재
        assert ReasoningType.INTERSECTION in present_types
        assert ReasoningType.COMPOSITION in present_types
        assert ReasoningType.COMPARISON in present_types

    @pytest.mark.unit
    def test_builtin_is_independent_copy(self) -> None:
        """builtin()이 독립적인 복사본을 반환."""
        ds1 = EvalDataset.builtin()
        ds2 = EvalDataset.builtin()
        ds1.questions.pop()
        assert len(ds1.questions) == 29
        assert len(ds2.questions) == 30


# =========================================================================
# 3. Cypher component extraction tests
# =========================================================================


class TestCypherExtraction:
    """Cypher 구성요소 추출 유틸리티 함수 테스트."""

    @pytest.mark.unit
    def test_extract_labels_simple(self) -> None:
        """단일 레이블 추출."""
        labels = _extract_node_labels("MATCH (v:Vessel) RETURN v")
        assert "Vessel" in labels

    @pytest.mark.unit
    def test_extract_labels_multiple(self) -> None:
        """복수 레이블 추출."""
        cypher = "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v, p"
        labels = _extract_node_labels(cypher)
        assert "Vessel" in labels
        assert "Port" in labels

    @pytest.mark.unit
    def test_extract_labels_no_variable(self) -> None:
        """변수 없는 노드 레이블 추출."""
        labels = _extract_node_labels("MATCH (:Vessel) RETURN *")
        assert "Vessel" in labels

    @pytest.mark.unit
    def test_extract_labels_with_properties(self) -> None:
        """인라인 속성이 있는 노드 레이블 추출."""
        cypher = "MATCH (p:Port {name: '부산항'}) RETURN p"
        labels = _extract_node_labels(cypher)
        assert "Port" in labels

    @pytest.mark.unit
    def test_extract_relationships_simple(self) -> None:
        """단일 관계 타입 추출."""
        cypher = "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v"
        rels = _extract_relationship_types(cypher)
        assert "DOCKED_AT" in rels

    @pytest.mark.unit
    def test_extract_relationships_multiple(self) -> None:
        """복수 관계 타입 추출."""
        cypher = (
            "MATCH (v:Vessel)-[:ON_VOYAGE]->(voy:Voyage)-[:TO_PORT]->(p:Port) "
            "RETURN v"
        )
        rels = _extract_relationship_types(cypher)
        assert "ON_VOYAGE" in rels
        assert "TO_PORT" in rels

    @pytest.mark.unit
    def test_extract_relationships_with_variable(self) -> None:
        """변수 바인딩된 관계 추출."""
        cypher = "MATCH (v)-[r:OWNS]->(p) RETURN v"
        rels = _extract_relationship_types(cypher)
        assert "OWNS" in rels

    @pytest.mark.unit
    def test_extract_return_fields_simple(self) -> None:
        """RETURN 필드 추출."""
        fields = _extract_return_fields("MATCH (v:Vessel) RETURN v")
        assert "v" in fields

    @pytest.mark.unit
    def test_extract_return_fields_with_alias(self) -> None:
        """RETURN AS 별칭 추출."""
        cypher = "MATCH (v:Vessel) RETURN v.name AS vessel_name"
        fields = _extract_return_fields(cypher)
        assert "vessel_name" in fields

    @pytest.mark.unit
    def test_extract_return_fields_multiple(self) -> None:
        """복수 RETURN 필드 추출."""
        cypher = "MATCH (v:Vessel) RETURN v.name AS name, v.mmsi AS mmsi"
        fields = _extract_return_fields(cypher)
        assert "name" in fields
        assert "mmsi" in fields

    @pytest.mark.unit
    def test_extract_property_filters_inline(self) -> None:
        """인라인 속성 필터 추출."""
        cypher = "MATCH (v:Vessel {vesselType: 'ContainerShip'}) RETURN v"
        props = _extract_property_filters(cypher)
        assert "vesselType" in props

    @pytest.mark.unit
    def test_extract_property_filters_where(self) -> None:
        """WHERE 절 속성 필터 추출."""
        cypher = "MATCH (v:Vessel) WHERE v.vesselType = 'ContainerShip' RETURN v"
        props = _extract_property_filters(cypher)
        assert "vesselType" in props

    @pytest.mark.unit
    def test_extract_property_filters_contains(self) -> None:
        """WHERE CONTAINS 속성 필터 추출."""
        cypher = "MATCH (v:Vessel) WHERE v.name CONTAINS 'HMM' RETURN v"
        props = _extract_property_filters(cypher)
        assert "name" in props


# =========================================================================
# 4. CypherAccuracy tests
# =========================================================================


class TestCypherAccuracy:
    """CypherAccuracy 메트릭 테스트."""

    @pytest.mark.unit
    def test_exact_match(self) -> None:
        """동일한 Cypher에 대해 1.0 점수."""
        metric = CypherAccuracy()
        cypher = "MATCH (v:Vessel {vesselType: 'ContainerShip'}) RETURN v"
        score = metric.evaluate(cypher, cypher)
        assert score == 1.0

    @pytest.mark.unit
    def test_partial_match_labels(self) -> None:
        """레이블만 일치하는 부분 매치."""
        metric = CypherAccuracy()
        generated = "MATCH (v:Vessel) RETURN v"
        truth = "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v"
        score = metric.evaluate(generated, truth)
        # truth has Vessel, Port labels and DOCKED_AT rel = 3 components
        # generated has Vessel = 1 match
        assert 0.0 < score < 1.0

    @pytest.mark.unit
    def test_no_match(self) -> None:
        """완전히 다른 Cypher에 대해 0.0 점수."""
        metric = CypherAccuracy()
        generated = "MATCH (o:Organization) RETURN o"
        truth = "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v"
        score = metric.evaluate(generated, truth)
        assert score == 0.0

    @pytest.mark.unit
    def test_empty_generated(self) -> None:
        """빈 생성 Cypher에 대해 0.0."""
        metric = CypherAccuracy()
        score = metric.evaluate("", "MATCH (v:Vessel) RETURN v")
        assert score == 0.0

    @pytest.mark.unit
    def test_empty_truth(self) -> None:
        """빈 ground truth에 대해 0.0."""
        metric = CypherAccuracy()
        score = metric.evaluate("MATCH (v:Vessel) RETURN v", "")
        assert score == 0.0

    @pytest.mark.unit
    def test_extract_components(self) -> None:
        """CypherComponents 추출 검증."""
        metric = CypherAccuracy()
        cypher = (
            "MATCH (v:Vessel {vesselType: 'ContainerShip'})"
            "-[:ON_VOYAGE]->(voy:Voyage) "
            "RETURN v.name AS name"
        )
        comp = metric.extract_components(cypher)
        assert "Vessel" in comp.labels
        assert "Voyage" in comp.labels
        assert "ON_VOYAGE" in comp.relationships
        assert "vesselType" in comp.property_filters

    @pytest.mark.unit
    def test_relationship_matching(self) -> None:
        """관계 타입 일치 점수에 반영."""
        metric = CypherAccuracy()
        generated = "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v"
        truth = "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v"
        score = metric.evaluate(generated, truth)
        assert score == 1.0

    @pytest.mark.unit
    def test_property_filter_matching(self) -> None:
        """속성 필터 일치 점수에 반영."""
        metric = CypherAccuracy()
        generated = "MATCH (v:Vessel {vesselType: 'ContainerShip'}) RETURN v"
        truth = "MATCH (v:Vessel {vesselType: 'ContainerShip'}) RETURN v"
        score = metric.evaluate(generated, truth)
        assert score == 1.0


# =========================================================================
# 5. QueryRelevancy tests
# =========================================================================


class TestQueryRelevancy:
    """QueryRelevancy 메트릭 테스트."""

    @pytest.mark.unit
    def test_full_label_coverage(self) -> None:
        """모든 레이블 포함 시 1.0."""
        metric = QueryRelevancy()
        cypher = "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v"
        score = metric.evaluate("선박 질문", cypher, ["Vessel", "Port"])
        assert score == 1.0

    @pytest.mark.unit
    def test_partial_label_coverage(self) -> None:
        """일부 레이블만 포함."""
        metric = QueryRelevancy()
        cypher = "MATCH (v:Vessel) RETURN v"
        score = metric.evaluate("선박 질문", cypher, ["Vessel", "Port"])
        assert score == 0.5

    @pytest.mark.unit
    def test_no_label_coverage(self) -> None:
        """레이블 미포함."""
        metric = QueryRelevancy()
        cypher = "MATCH (o:Organization) RETURN o"
        score = metric.evaluate("선박 질문", cypher, ["Vessel", "Port"])
        assert score == 0.0

    @pytest.mark.unit
    def test_empty_expected_labels(self) -> None:
        """기대 레이블 없음 시 1.0."""
        metric = QueryRelevancy()
        score = metric.evaluate("질문", "MATCH (v:Vessel) RETURN v", [])
        assert score == 1.0

    @pytest.mark.unit
    def test_empty_cypher(self) -> None:
        """빈 Cypher에 대해 0.0."""
        metric = QueryRelevancy()
        score = metric.evaluate("질문", "", ["Vessel"])
        assert score == 0.0

    @pytest.mark.unit
    def test_single_label(self) -> None:
        """단일 레이블 매칭."""
        metric = QueryRelevancy()
        cypher = "MATCH (f:TestFacility) RETURN f"
        score = metric.evaluate("시설 질문", cypher, ["TestFacility"])
        assert score == 1.0


# =========================================================================
# 6. ReasoningTypeMetric tests
# =========================================================================


class TestReasoningTypeMetric:
    """ReasoningTypeMetric 집계 테스트."""

    @pytest.mark.unit
    def test_single_type(self) -> None:
        """단일 추론유형 집계."""
        metric = ReasoningTypeMetric()
        results = [
            {"reasoning_type": "DIRECT", "score": 0.8},
            {"reasoning_type": "DIRECT", "score": 1.0},
        ]
        agg = metric.evaluate(results)
        assert agg["DIRECT"] == pytest.approx(0.9)

    @pytest.mark.unit
    def test_multiple_types(self) -> None:
        """복수 추론유형 집계."""
        metric = ReasoningTypeMetric()
        results = [
            {"reasoning_type": "DIRECT", "score": 1.0},
            {"reasoning_type": "BRIDGE", "score": 0.5},
            {"reasoning_type": "BRIDGE", "score": 0.7},
        ]
        agg = metric.evaluate(results)
        assert "DIRECT" in agg
        assert "BRIDGE" in agg
        assert agg["DIRECT"] == 1.0
        assert agg["BRIDGE"] == pytest.approx(0.6)

    @pytest.mark.unit
    def test_enum_values(self) -> None:
        """ReasoningType enum 값 처리."""
        metric = ReasoningTypeMetric()
        results = [
            {"reasoning_type": ReasoningType.INTERSECTION, "score": 0.5},
            {"reasoning_type": ReasoningType.INTERSECTION, "score": 0.3},
        ]
        agg = metric.evaluate(results)
        assert "INTERSECTION" in agg
        assert agg["INTERSECTION"] == pytest.approx(0.4)

    @pytest.mark.unit
    def test_empty_results(self) -> None:
        """빈 결과 리스트."""
        metric = ReasoningTypeMetric()
        agg = metric.evaluate([])
        assert agg == {}


# =========================================================================
# 7. EvaluationRunner tests
# =========================================================================


class TestEvaluationRunner:
    """EvaluationRunner 단위 테스트."""

    @pytest.mark.unit
    def test_run_single_with_generated_cypher(self) -> None:
        """사전 생성된 Cypher로 단일 질문 평가."""
        runner = EvaluationRunner()
        q = _make_question(
            cypher="MATCH (v:Vessel) RETURN v",
            labels=["Vessel"],
        )
        result = runner.run_single(q, generated_cypher="MATCH (v:Vessel) RETURN v")
        assert result["accuracy"] == 1.0
        assert result["relevancy"] == 1.0
        assert result["success"] is True

    @pytest.mark.unit
    def test_run_single_without_pipeline_or_cypher(self) -> None:
        """파이프라인과 Cypher 모두 없을 때 0.0 점수."""
        runner = EvaluationRunner()
        q = _make_question()
        result = runner.run_single(q)
        assert result["accuracy"] == 0.0
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.unit
    def test_run_single_with_mock_pipeline(self) -> None:
        """Mock 파이프라인으로 단일 질문 평가."""
        mock_pipeline = MagicMock()
        mock_output = MagicMock()
        mock_output.success = True
        mock_output.generated_query = MagicMock()
        mock_output.generated_query.query = "MATCH (v:Vessel) RETURN v"
        mock_pipeline.process.return_value = mock_output

        runner = EvaluationRunner(pipeline=mock_pipeline)
        q = _make_question(
            cypher="MATCH (v:Vessel) RETURN v",
            labels=["Vessel"],
        )
        result = runner.run_single(q)
        assert result["accuracy"] == 1.0
        assert result["success"] is True
        mock_pipeline.process.assert_called_once_with("테스트 질문")

    @pytest.mark.unit
    def test_run_single_pipeline_failure(self) -> None:
        """파이프라인 실패 시 0.0 점수."""
        mock_pipeline = MagicMock()
        mock_output = MagicMock()
        mock_output.success = False
        mock_output.generated_query = None
        mock_output.error = "Parse error"
        mock_pipeline.process.return_value = mock_output

        runner = EvaluationRunner(pipeline=mock_pipeline)
        q = _make_question()
        result = runner.run_single(q)
        assert result["accuracy"] == 0.0
        assert result["success"] is False

    @pytest.mark.unit
    def test_run_single_pipeline_exception(self) -> None:
        """파이프라인 예외 시 0.0 점수."""
        mock_pipeline = MagicMock()
        mock_pipeline.process.side_effect = RuntimeError("boom")

        runner = EvaluationRunner(pipeline=mock_pipeline)
        q = _make_question()
        result = runner.run_single(q)
        assert result["accuracy"] == 0.0
        assert result["success"] is False
        assert "boom" in result["error"]

    @pytest.mark.unit
    def test_run_dataset(self) -> None:
        """데이터셋 전체 평가."""
        runner = EvaluationRunner()
        ds = EvalDataset()
        ds.add_question(_make_question(
            question="Q1",
            difficulty=Difficulty.EASY,
            reasoning_type=ReasoningType.DIRECT,
        ))
        ds.add_question(_make_question(
            question="Q2",
            cypher="MATCH (p:Port) RETURN p",
            labels=["Port"],
            difficulty=Difficulty.MEDIUM,
            reasoning_type=ReasoningType.BRIDGE,
        ))

        # Without pipeline, all scores should be 0
        report = runner.run(ds)
        assert report.total == 2
        assert len(report.details) == 2
        assert "EASY" in report.by_difficulty
        assert "MEDIUM" in report.by_difficulty
        assert "DIRECT" in report.by_reasoning_type
        assert "BRIDGE" in report.by_reasoning_type

    @pytest.mark.unit
    def test_run_result_contains_required_keys(self) -> None:
        """결과 dict에 필수 키 포함."""
        runner = EvaluationRunner()
        q = _make_question()
        result = runner.run_single(q, generated_cypher="MATCH (v:Vessel) RETURN v")

        required_keys = [
            "question", "difficulty", "reasoning_type", "description",
            "accuracy", "relevancy", "score", "generated_cypher",
            "ground_truth_cypher", "success",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"


# =========================================================================
# 8. EvalReport tests
# =========================================================================


class TestEvalReport:
    """EvalReport 요약 포맷 테스트."""

    @pytest.mark.unit
    def test_summary_format(self) -> None:
        """요약 문자열 포맷 검증."""
        report = EvalReport(
            total=2,
            by_difficulty={"EASY": 1.0, "MEDIUM": 0.5},
            by_reasoning_type={"DIRECT": 1.0, "BRIDGE": 0.5},
            details=[
                {
                    "question": "부산항 정보",
                    "difficulty": "EASY",
                    "reasoning_type": "DIRECT",
                    "accuracy": 1.0,
                    "relevancy": 1.0,
                    "score": 1.0,
                },
                {
                    "question": "선박 항해 정보",
                    "difficulty": "MEDIUM",
                    "reasoning_type": "BRIDGE",
                    "accuracy": 0.5,
                    "relevancy": 0.5,
                    "score": 0.5,
                },
            ],
            timestamp="2026-02-14T00:00:00+00:00",
        )

        summary = report.summary()
        assert "Evaluation Report" in summary
        assert "Total Questions: 2" in summary
        assert "EASY" in summary
        assert "MEDIUM" in summary
        assert "DIRECT" in summary
        assert "BRIDGE" in summary
        assert "2026-02-14" in summary

    @pytest.mark.unit
    def test_summary_empty_report(self) -> None:
        """빈 리포트 요약."""
        report = EvalReport(total=0, timestamp="2026-02-14T00:00:00+00:00")
        summary = report.summary()
        assert "Total Questions: 0" in summary

    @pytest.mark.unit
    def test_summary_truncates_long_questions(self) -> None:
        """긴 질문 텍스트 절삭."""
        report = EvalReport(
            total=1,
            details=[
                {
                    "question": "이것은 매우 매우 긴 질문 텍스트입니다 삼십자가 넘어가면 절삭합니다",
                    "difficulty": "HARD",
                    "reasoning_type": "COMPOSITION",
                    "accuracy": 0.5,
                    "relevancy": 0.5,
                    "score": 0.5,
                },
            ],
            timestamp="2026-02-14T00:00:00+00:00",
        )
        summary = report.summary()
        assert "..." in summary

    @pytest.mark.unit
    def test_report_overall_accuracy(self) -> None:
        """전체 정확도 계산."""
        report = EvalReport(
            total=2,
            details=[
                {"accuracy": 1.0, "question": "Q1"},
                {"accuracy": 0.5, "question": "Q2"},
            ],
            timestamp="2026-02-14T00:00:00+00:00",
        )
        summary = report.summary()
        assert "75.00%" in summary


# =========================================================================
# 9. Enum tests
# =========================================================================


class TestEnums:
    """ReasoningType, Difficulty enum 검증."""

    @pytest.mark.unit
    def test_reasoning_type_values(self) -> None:
        """ReasoningType enum 값."""
        assert ReasoningType.DIRECT.value == "DIRECT"
        assert ReasoningType.BRIDGE.value == "BRIDGE"
        assert ReasoningType.COMPARISON.value == "COMPARISON"
        assert ReasoningType.INTERSECTION.value == "INTERSECTION"
        assert ReasoningType.COMPOSITION.value == "COMPOSITION"

    @pytest.mark.unit
    def test_difficulty_values(self) -> None:
        """Difficulty enum 값."""
        assert Difficulty.EASY.value == "EASY"
        assert Difficulty.MEDIUM.value == "MEDIUM"
        assert Difficulty.HARD.value == "HARD"

    @pytest.mark.unit
    def test_reasoning_type_is_string(self) -> None:
        """ReasoningType은 str Enum."""
        assert isinstance(ReasoningType.DIRECT, str)

    @pytest.mark.unit
    def test_difficulty_is_string(self) -> None:
        """Difficulty은 str Enum."""
        assert isinstance(Difficulty.EASY, str)
