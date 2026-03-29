"""Evaluation runner for the Text-to-Cypher pipeline.

Orchestrates evaluation of the pipeline against a dataset of questions,
computing per-question and aggregate metrics. Supports both live pipeline
evaluation and structural-only comparison.

Usage::

    from kg.evaluation.runner import EvaluationRunner
    from kg.evaluation.dataset import EvalDataset
    from kg.pipeline import TextToCypherPipeline

    # With pipeline (generates Cypher then scores)
    runner = EvaluationRunner(pipeline=TextToCypherPipeline())
    report = runner.run(EvalDataset.builtin())
    print(report.summary())

    # Without pipeline (structural comparison only)
    runner = EvaluationRunner()
    result = runner.run_single(question, generated_cypher="MATCH ...")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from maritime.evaluation.dataset import EvalDataset, EvalQuestion
from kg.evaluation.metrics import CypherAccuracy, QueryRelevancy, ReasoningTypeMetric


@dataclass
class EvalReport:
    """Aggregated evaluation report.

    Attributes:
        total: Total number of questions evaluated.
        by_difficulty: Average scores grouped by difficulty level.
        by_reasoning_type: Average scores grouped by reasoning type.
        details: Per-question result dictionaries.
        timestamp: ISO 8601 timestamp of the evaluation run.
    """

    total: int = 0
    by_difficulty: dict[str, float] = field(default_factory=dict)
    by_reasoning_type: dict[str, float] = field(default_factory=dict)
    details: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def summary(self) -> str:
        """Generate a formatted summary string of the evaluation.

        Returns:
            Human-readable multi-line summary with overall score,
            difficulty breakdown, reasoning type breakdown, and
            per-question details.
        """
        lines = [
            "=" * 60,
            "  Evaluation Report",
            f"  Timestamp: {self.timestamp}",
            f"  Total Questions: {self.total}",
            "=" * 60,
        ]

        # Overall score
        if self.details:
            scores = [d.get("accuracy", 0.0) for d in self.details]
            overall = sum(scores) / len(scores) if scores else 0.0
            lines.append(f"\n  Overall Accuracy: {overall:.2%}")

        # By difficulty
        if self.by_difficulty:
            lines.append("\n  By Difficulty:")
            for diff, score in sorted(self.by_difficulty.items()):
                lines.append(f"    {diff}: {score:.2%}")

        # By reasoning type
        if self.by_reasoning_type:
            lines.append("\n  By Reasoning Type:")
            for rt, score in sorted(self.by_reasoning_type.items()):
                lines.append(f"    {rt}: {score:.2%}")

        # Per-question details (abbreviated)
        if self.details:
            lines.append("\n  Details:")
            lines.append(
                f"  {'#':>3s}  {'Difficulty':<8s}  {'Type':<14s}  "
                f"{'Accuracy':>8s}  {'Relevancy':>9s}  Question"
            )
            lines.append("  " + "-" * 76)
            for i, d in enumerate(self.details, 1):
                q_text = d.get("question", "")
                if len(q_text) > 28:
                    q_text = q_text[:25] + "..."
                lines.append(
                    f"  {i:3d}  {d.get('difficulty', ''):8s}  "
                    f"{d.get('reasoning_type', ''):14s}  "
                    f"{d.get('accuracy', 0.0):8.2%}  "
                    f"{d.get('relevancy', 0.0):9.2%}  "
                    f"{q_text}"
                )

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


class EvaluationRunner:
    """Run evaluation of the Text-to-Cypher pipeline against a dataset.

    When a pipeline is provided, questions are processed through it and
    the generated Cypher is scored against ground truth. When no pipeline
    is provided, only structural comparison is available via
    ``run_single()`` with an explicit ``generated_cypher`` parameter.

    Args:
        pipeline: Optional TextToCypherPipeline instance. If None,
            ``run()`` will skip questions (use ``run_single()`` instead).
    """

    def __init__(self, pipeline: Any | None = None) -> None:
        self._pipeline = pipeline
        self._accuracy = CypherAccuracy()
        self._relevancy = QueryRelevancy()
        self._reasoning = ReasoningTypeMetric()

    def run_single(
        self,
        question: EvalQuestion,
        generated_cypher: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate a single question.

        If ``generated_cypher`` is not provided, the pipeline is used to
        generate it. If neither is available, scores default to 0.0.

        Args:
            question: EvalQuestion to evaluate.
            generated_cypher: Optional pre-generated Cypher string.
                If None, the pipeline is used.

        Returns:
            Dict with keys: question, difficulty, reasoning_type,
            accuracy, relevancy, score (average), generated_cypher,
            ground_truth_cypher, success.
        """
        cypher = generated_cypher
        success = True
        error = None

        # Generate if not provided
        if cypher is None and self._pipeline is not None:
            try:
                output = self._pipeline.process(question.question)
                if output.success and output.generated_query:
                    cypher = output.generated_query.query
                else:
                    cypher = ""
                    success = False
                    error = output.error or "Pipeline produced no output"
            except Exception as exc:
                cypher = ""
                success = False
                error = str(exc)
        elif cypher is None:
            cypher = ""
            success = False
            error = "No pipeline and no generated_cypher provided"

        # Compute metrics
        accuracy = self._accuracy.evaluate(cypher, question.ground_truth_cypher)
        relevancy = self._relevancy.evaluate(
            question.question, cypher, question.expected_labels
        )
        # Combined score (average of accuracy and relevancy)
        score = (accuracy + relevancy) / 2.0

        result: dict[str, Any] = {
            "question": question.question,
            "difficulty": question.difficulty.value,
            "reasoning_type": question.reasoning_type.value,
            "description": question.description,
            "accuracy": accuracy,
            "relevancy": relevancy,
            "score": score,
            "generated_cypher": cypher,
            "ground_truth_cypher": question.ground_truth_cypher,
            "success": success,
        }
        if error:
            result["error"] = error

        return result

    def run(self, dataset: EvalDataset) -> EvalReport:
        """Evaluate all questions in a dataset.

        Processes each question through the pipeline (if available),
        scores against ground truth, and aggregates results.

        Args:
            dataset: EvalDataset containing questions to evaluate.

        Returns:
            EvalReport with per-question and aggregate scores.
        """
        report = EvalReport(
            total=len(dataset.questions),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        for question in dataset.questions:
            result = self.run_single(question)
            report.details.append(result)

        # Aggregate by difficulty
        diff_scores: dict[str, list[float]] = {}
        for d in report.details:
            diff = d["difficulty"]
            diff_scores.setdefault(diff, []).append(d["accuracy"])
        report.by_difficulty = {
            diff: sum(scores) / len(scores)
            for diff, scores in diff_scores.items()
            if scores
        }

        # Aggregate by reasoning type
        report.by_reasoning_type = self._reasoning.evaluate(
            [
                {"reasoning_type": d["reasoning_type"], "score": d["accuracy"]}
                for d in report.details
            ]
        )

        return report


def _generate_markdown_report(report: EvalReport) -> str:
    """Generate Markdown formatted evaluation report.

    Args:
        report: EvalReport instance with evaluation results.

    Returns:
        Markdown formatted string.
    """
    lines = [
        "# 해사 KG Text-to-Cypher 평가 리포트",
        "",
        f"**평가 일시**: {report.timestamp}",
        f"**총 질문 수**: {report.total}",
        "",
        "## 전체 정확도 (Overall Accuracy)",
        "",
    ]

    # Overall accuracy
    if report.details:
        scores = [d.get("accuracy", 0.0) for d in report.details]
        overall = sum(scores) / len(scores) if scores else 0.0
        lines.append(f"**{overall:.2%}**")
        lines.append("")

    # By difficulty
    if report.by_difficulty:
        lines.append("## 난이도별 정확도")
        lines.append("")
        lines.append("| 난이도 | 정확도 |")
        lines.append("|--------|--------|")
        for diff, score in sorted(report.by_difficulty.items()):
            lines.append(f"| {diff} | {score:.2%} |")
        lines.append("")

    # By reasoning type
    if report.by_reasoning_type:
        lines.append("## 추론유형별 정확도")
        lines.append("")
        lines.append("| 추론 유형 | 정확도 |")
        lines.append("|-----------|--------|")
        for rt, score in sorted(report.by_reasoning_type.items()):
            lines.append(f"| {rt} | {score:.2%} |")
        lines.append("")

    # Per-question details
    if report.details:
        lines.append("## 질문별 상세 결과")
        lines.append("")
        lines.append("| # | 난이도 | 추론 유형 | 정확도 | 적합성 | 질문 |")
        lines.append("|---|--------|-----------|--------|--------|------|")
        for i, d in enumerate(report.details, 1):
            q_text = d.get("question", "")
            lines.append(
                f"| {i} | {d.get('difficulty', '')} | "
                f"{d.get('reasoning_type', '')} | "
                f"{d.get('accuracy', 0.0):.2%} | "
                f"{d.get('relevancy', 0.0):.2%} | "
                f"{q_text} |"
            )
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    """CLI entry point for running evaluation."""
    from pathlib import Path

    from kg.pipeline import TextToCypherPipeline

    # Create pipeline
    pipeline = TextToCypherPipeline()

    # Load builtin dataset (300 questions)
    dataset = EvalDataset.builtin()

    # Run evaluation
    print("Running evaluation on 300 builtin questions...")
    runner = EvaluationRunner(pipeline=pipeline)
    report = runner.run(dataset)

    # Print summary to console
    print(report.summary())

    # Generate and save Markdown report
    docs_dir = Path(__file__).parent.parent.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / "evaluation_report.md"

    markdown_content = _generate_markdown_report(report)
    report_path.write_text(markdown_content, encoding="utf-8")
    print(f"\nMarkdown report saved to: {report_path}")
