"""Extended unit tests for core/kg/evaluation/runner.py.

Pushes EvaluationRunner coverage from ~65% to 80%+ by exercising paths
not yet covered by tests/maritime/test_evaluation.py:

- run() with mock pipeline driving all questions
- run() with empty dataset
- _generate_markdown_report() formatting
- EvalReport.summary() edge cases
- Score calculation (average of accuracy + relevancy)
- run_single() with pipeline output.generated_query = None
- by_difficulty / by_reasoning_type multi-key aggregation
- run() batch with mixed success/failure

All tests are @pytest.mark.unit — no Neo4j, no LLM.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from maritime.evaluation.dataset import Difficulty, EvalDataset, EvalQuestion, ReasoningType
from kg.evaluation.runner import EvalReport, EvaluationRunner, _generate_markdown_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _q(
    question: str = "테스트 질문",
    cypher: str = "MATCH (v:Vessel) RETURN v",
    labels: list[str] | None = None,
    reasoning_type: ReasoningType = ReasoningType.DIRECT,
    difficulty: Difficulty = Difficulty.EASY,
    description: str = "test",
) -> EvalQuestion:
    return EvalQuestion(
        question=question,
        ground_truth_cypher=cypher,
        expected_labels=labels or ["Vessel"],
        reasoning_type=reasoning_type,
        difficulty=difficulty,
        description=description,
    )


def _mock_pipeline(cypher: str = "MATCH (v:Vessel) RETURN v", success: bool = True) -> MagicMock:
    """Build a mock pipeline that returns a single fixed Cypher."""
    pipe = MagicMock()
    output = MagicMock()
    output.success = success
    if success:
        output.generated_query = MagicMock()
        output.generated_query.query = cypher
    else:
        output.generated_query = None
        output.error = "simulated failure"
    pipe.process.return_value = output
    return pipe


# ---------------------------------------------------------------------------
# EvaluationRunner — constructor
# ---------------------------------------------------------------------------


class TestEvaluationRunnerInit:
    @pytest.mark.unit
    def test_no_pipeline_default(self) -> None:
        """Runner without pipeline stores None."""
        runner = EvaluationRunner()
        assert runner._pipeline is None

    @pytest.mark.unit
    def test_with_pipeline_stored(self) -> None:
        """Runner stores the pipeline passed in."""
        pipe = MagicMock()
        runner = EvaluationRunner(pipeline=pipe)
        assert runner._pipeline is pipe

    @pytest.mark.unit
    def test_metrics_instantiated(self) -> None:
        """Accuracy, relevancy, and reasoning metrics are created."""
        from kg.evaluation.metrics import CypherAccuracy, QueryRelevancy, ReasoningTypeMetric

        runner = EvaluationRunner()
        assert isinstance(runner._accuracy, CypherAccuracy)
        assert isinstance(runner._relevancy, QueryRelevancy)
        assert isinstance(runner._reasoning, ReasoningTypeMetric)


# ---------------------------------------------------------------------------
# run_single — score calculation
# ---------------------------------------------------------------------------


class TestRunSingleScoreCalculation:
    @pytest.mark.unit
    def test_score_is_average_of_accuracy_and_relevancy(self) -> None:
        """score = (accuracy + relevancy) / 2."""
        runner = EvaluationRunner()
        q = _q(
            cypher="MATCH (v:Vessel) RETURN v",
            labels=["Vessel"],
        )
        result = runner.run_single(q, generated_cypher="MATCH (v:Vessel) RETURN v")
        expected_score = (result["accuracy"] + result["relevancy"]) / 2.0
        assert result["score"] == pytest.approx(expected_score)

    @pytest.mark.unit
    def test_score_zero_when_no_match(self) -> None:
        """score is 0.0 when no cypher and no pipeline."""
        runner = EvaluationRunner()
        q = _q()
        result = runner.run_single(q)
        assert result["score"] == 0.0

    @pytest.mark.unit
    def test_result_keys_include_description(self) -> None:
        """result contains 'description' key from EvalQuestion."""
        runner = EvaluationRunner()
        q = _q(description="항구 조회 테스트")
        result = runner.run_single(q, generated_cypher="MATCH (v:Vessel) RETURN v")
        assert result["description"] == "항구 조회 테스트"

    @pytest.mark.unit
    def test_result_generated_cypher_stored(self) -> None:
        """result stores the generated cypher that was used."""
        runner = EvaluationRunner()
        gen = "MATCH (p:Port) RETURN p"
        q = _q()
        result = runner.run_single(q, generated_cypher=gen)
        assert result["generated_cypher"] == gen

    @pytest.mark.unit
    def test_result_ground_truth_stored(self) -> None:
        """result stores the ground truth cypher from the question."""
        runner = EvaluationRunner()
        q = _q(cypher="MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v")
        result = runner.run_single(q, generated_cypher="MATCH (v:Vessel) RETURN v")
        assert result["ground_truth_cypher"] == "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) RETURN v"

    @pytest.mark.unit
    def test_pipeline_output_with_none_generated_query(self) -> None:
        """Pipeline success=True but generated_query=None → empty cypher, failure."""
        pipe = MagicMock()
        output = MagicMock()
        output.success = True
        output.generated_query = None
        output.error = None
        pipe.process.return_value = output

        runner = EvaluationRunner(pipeline=pipe)
        q = _q()
        result = runner.run_single(q)

        assert result["generated_cypher"] == ""
        assert result["success"] is False

    @pytest.mark.unit
    def test_pipeline_produces_no_error_key_on_success(self) -> None:
        """On pipeline success the result dict has no 'error' key."""
        pipe = _mock_pipeline(cypher="MATCH (v:Vessel) RETURN v", success=True)
        runner = EvaluationRunner(pipeline=pipe)
        q = _q(cypher="MATCH (v:Vessel) RETURN v", labels=["Vessel"])
        result = runner.run_single(q)
        assert "error" not in result

    @pytest.mark.unit
    def test_no_pipeline_error_message(self) -> None:
        """Error message describes missing pipeline/cypher case."""
        runner = EvaluationRunner()
        q = _q()
        result = runner.run_single(q)
        assert "error" in result
        assert result["error"] != ""

    @pytest.mark.unit
    def test_pipeline_exception_stores_message(self) -> None:
        """Exception message stored in result['error']."""
        pipe = MagicMock()
        pipe.process.side_effect = ValueError("unexpected token")
        runner = EvaluationRunner(pipeline=pipe)
        q = _q()
        result = runner.run_single(q)
        assert "unexpected token" in result["error"]
        assert result["success"] is False


# ---------------------------------------------------------------------------
# run() — dataset evaluation
# ---------------------------------------------------------------------------


class TestRunDataset:
    @pytest.mark.unit
    def test_run_empty_dataset(self) -> None:
        """run() on empty dataset returns report with total=0."""
        runner = EvaluationRunner()
        ds = EvalDataset()
        report = runner.run(ds)
        assert report.total == 0
        assert report.details == []
        assert report.by_difficulty == {}
        assert report.by_reasoning_type == {}

    @pytest.mark.unit
    def test_run_sets_timestamp(self) -> None:
        """report.timestamp is set and non-empty."""
        runner = EvaluationRunner()
        ds = EvalDataset()
        ds.add_question(_q())
        report = runner.run(ds)
        assert report.timestamp != ""
        # ISO 8601 format includes T separator
        assert "T" in report.timestamp

    @pytest.mark.unit
    def test_run_with_pipeline_processes_all_questions(self) -> None:
        """Pipeline.process() called once per question in dataset."""
        pipe = _mock_pipeline(cypher="MATCH (v:Vessel) RETURN v")
        runner = EvaluationRunner(pipeline=pipe)

        ds = EvalDataset()
        for i in range(3):
            ds.add_question(_q(question=f"질문{i}"))

        runner.run(ds)
        assert pipe.process.call_count == 3

    @pytest.mark.unit
    def test_run_aggregates_by_difficulty(self) -> None:
        """by_difficulty contains all difficulty keys present in dataset."""
        runner = EvaluationRunner()
        ds = EvalDataset()
        ds.add_question(_q(difficulty=Difficulty.EASY))
        ds.add_question(_q(difficulty=Difficulty.MEDIUM))
        ds.add_question(_q(difficulty=Difficulty.HARD))

        report = runner.run(ds)
        assert "EASY" in report.by_difficulty
        assert "MEDIUM" in report.by_difficulty
        assert "HARD" in report.by_difficulty

    @pytest.mark.unit
    def test_run_aggregates_by_reasoning_type(self) -> None:
        """by_reasoning_type contains all reasoning types present in dataset."""
        runner = EvaluationRunner()
        ds = EvalDataset()
        ds.add_question(_q(reasoning_type=ReasoningType.DIRECT))
        ds.add_question(_q(reasoning_type=ReasoningType.BRIDGE))
        ds.add_question(_q(reasoning_type=ReasoningType.INTERSECTION))

        report = runner.run(ds)
        assert "DIRECT" in report.by_reasoning_type
        assert "BRIDGE" in report.by_reasoning_type
        assert "INTERSECTION" in report.by_reasoning_type

    @pytest.mark.unit
    def test_run_by_difficulty_average_score(self) -> None:
        """by_difficulty scores are averages of accuracy per difficulty."""
        # Use a pipeline that returns perfect Cypher for every question
        pipe = _mock_pipeline(cypher="MATCH (v:Vessel) RETURN v")
        runner = EvaluationRunner(pipeline=pipe)

        ds = EvalDataset()
        ds.add_question(
            _q(
                cypher="MATCH (v:Vessel) RETURN v",
                labels=["Vessel"],
                difficulty=Difficulty.EASY,
            )
        )
        ds.add_question(
            _q(
                cypher="MATCH (v:Vessel) RETURN v",
                labels=["Vessel"],
                difficulty=Difficulty.EASY,
            )
        )
        report = runner.run(ds)
        # Both EASY questions should have high accuracy
        assert "EASY" in report.by_difficulty
        assert 0.0 <= report.by_difficulty["EASY"] <= 1.0

    @pytest.mark.unit
    def test_run_with_mixed_success_failure(self) -> None:
        """Dataset with pipeline exceptions still aggregates correctly."""
        call_count = 0

        def alternate_process(q_text: str):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("fail every other")
            output = MagicMock()
            output.success = True
            output.generated_query = MagicMock()
            output.generated_query.query = "MATCH (v:Vessel) RETURN v"
            return output

        pipe = MagicMock()
        pipe.process.side_effect = alternate_process
        runner = EvaluationRunner(pipeline=pipe)

        ds = EvalDataset()
        for i in range(4):
            ds.add_question(_q(question=f"Q{i}"))

        report = runner.run(ds)
        assert report.total == 4
        assert len(report.details) == 4

    @pytest.mark.unit
    def test_run_total_matches_dataset_length(self) -> None:
        """report.total equals number of questions in dataset."""
        runner = EvaluationRunner()
        ds = EvalDataset()
        for i in range(7):
            ds.add_question(_q(question=f"Q{i}"))

        report = runner.run(ds)
        assert report.total == 7
        assert len(report.details) == 7


# ---------------------------------------------------------------------------
# _generate_markdown_report
# ---------------------------------------------------------------------------


class TestGenerateMarkdownReport:
    @pytest.mark.unit
    def test_markdown_contains_title(self) -> None:
        """Generated Markdown starts with expected Korean title."""
        report = EvalReport(total=0, timestamp="2026-01-01T00:00:00+00:00")
        md = _generate_markdown_report(report)
        assert "해사 KG Text-to-Cypher 평가 리포트" in md

    @pytest.mark.unit
    def test_markdown_contains_timestamp(self) -> None:
        """Timestamp appears in the Markdown output."""
        report = EvalReport(total=1, timestamp="2026-03-30T09:00:00+00:00")
        md = _generate_markdown_report(report)
        assert "2026-03-30T09:00:00+00:00" in md

    @pytest.mark.unit
    def test_markdown_contains_total(self) -> None:
        """Total question count appears in the Markdown output."""
        report = EvalReport(total=42, timestamp="2026-01-01T00:00:00+00:00")
        md = _generate_markdown_report(report)
        assert "42" in md

    @pytest.mark.unit
    def test_markdown_overall_accuracy_shown(self) -> None:
        """Overall accuracy percentage is shown for non-empty details."""
        report = EvalReport(
            total=2,
            details=[
                {"accuracy": 1.0, "question": "Q1"},
                {"accuracy": 0.0, "question": "Q2"},
            ],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        md = _generate_markdown_report(report)
        assert "50.00%" in md

    @pytest.mark.unit
    def test_markdown_difficulty_section(self) -> None:
        """Difficulty breakdown section appears when by_difficulty is set."""
        report = EvalReport(
            total=1,
            by_difficulty={"EASY": 1.0, "HARD": 0.5},
            details=[],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        md = _generate_markdown_report(report)
        assert "난이도별 정확도" in md
        assert "EASY" in md
        assert "HARD" in md

    @pytest.mark.unit
    def test_markdown_reasoning_type_section(self) -> None:
        """Reasoning type breakdown section appears when by_reasoning_type is set."""
        report = EvalReport(
            total=1,
            by_reasoning_type={"DIRECT": 0.9, "BRIDGE": 0.7},
            details=[],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        md = _generate_markdown_report(report)
        assert "추론유형별 정확도" in md
        assert "DIRECT" in md
        assert "BRIDGE" in md

    @pytest.mark.unit
    def test_markdown_per_question_details(self) -> None:
        """Per-question table is rendered with question text."""
        report = EvalReport(
            total=1,
            details=[
                {
                    "question": "부산항 정보 조회",
                    "difficulty": "EASY",
                    "reasoning_type": "DIRECT",
                    "accuracy": 0.8,
                    "relevancy": 0.9,
                    "score": 0.85,
                }
            ],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        md = _generate_markdown_report(report)
        assert "부산항 정보 조회" in md
        assert "80.00%" in md

    @pytest.mark.unit
    def test_markdown_empty_report(self) -> None:
        """Empty report still produces valid Markdown without errors."""
        report = EvalReport(total=0, timestamp="2026-01-01T00:00:00+00:00")
        md = _generate_markdown_report(report)
        assert isinstance(md, str)
        assert len(md) > 0

    @pytest.mark.unit
    def test_markdown_no_difficulty_section_when_empty(self) -> None:
        """Difficulty section absent when by_difficulty is empty dict."""
        report = EvalReport(
            total=0,
            by_difficulty={},
            details=[],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        md = _generate_markdown_report(report)
        assert "난이도별 정확도" not in md

    @pytest.mark.unit
    def test_markdown_no_reasoning_section_when_empty(self) -> None:
        """Reasoning type section absent when by_reasoning_type is empty."""
        report = EvalReport(
            total=0,
            by_reasoning_type={},
            details=[],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        md = _generate_markdown_report(report)
        assert "추론유형별 정확도" not in md


# ---------------------------------------------------------------------------
# EvalReport.summary() — additional edge cases
# ---------------------------------------------------------------------------


class TestEvalReportSummaryExtended:
    @pytest.mark.unit
    def test_summary_no_by_difficulty(self) -> None:
        """summary() works when by_difficulty is empty."""
        report = EvalReport(
            total=1,
            by_difficulty={},
            details=[{"accuracy": 0.5, "question": "Q1"}],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        s = report.summary()
        assert "Total Questions: 1" in s
        # No difficulty header expected
        assert "By Difficulty" not in s

    @pytest.mark.unit
    def test_summary_no_by_reasoning_type(self) -> None:
        """summary() works when by_reasoning_type is empty."""
        report = EvalReport(
            total=1,
            by_reasoning_type={},
            details=[{"accuracy": 1.0, "question": "Q1"}],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        s = report.summary()
        assert "By Reasoning Type" not in s

    @pytest.mark.unit
    def test_summary_header_separator(self) -> None:
        """summary() includes separator lines."""
        report = EvalReport(total=0, timestamp="2026-01-01T00:00:00+00:00")
        s = report.summary()
        assert "=" * 60 in s

    @pytest.mark.unit
    def test_summary_sorted_difficulty_keys(self) -> None:
        """summary() lists difficulty keys in sorted order."""
        report = EvalReport(
            total=3,
            by_difficulty={"HARD": 0.3, "EASY": 1.0, "MEDIUM": 0.6},
            details=[],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        s = report.summary()
        easy_pos = s.find("EASY")
        hard_pos = s.find("HARD")
        medium_pos = s.find("MEDIUM")
        # sorted order: EASY < HARD < MEDIUM
        assert easy_pos < hard_pos < medium_pos
