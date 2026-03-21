"""Evaluation framework for maritime KG quality measurement.

RAGAS-style lightweight evaluation metrics for the Text-to-Cypher pipeline.
Measures Cypher accuracy, query relevancy, and reasoning-type performance
without external evaluation library dependencies.

Usage::

    from kg.evaluation import (
        CypherAccuracy,
        QueryRelevancy,
        ReasoningTypeMetric,
        EvalDataset,
        EvaluationRunner,
    )

    dataset = EvalDataset.builtin()
    runner = EvaluationRunner()
    report = runner.run(dataset)
    print(report.summary())
"""

from kg.evaluation.metrics import (
    CypherAccuracy,
    QueryRelevancy,
    ReasoningTypeMetric,
)
from kg.evaluation.runner import EvalReport, EvaluationRunner

__all__ = [
    "CypherAccuracy",
    "QueryRelevancy",
    "ReasoningTypeMetric",
    "EvaluationRunner",
    "EvalReport",
]

# Maritime evaluation dataset is optional; available only when maritime domain is installed.
try:
    from maritime.evaluation.dataset import (  # noqa: F401
        Difficulty,
        EvalDataset,
        EvalQuestion,
        ReasoningType,
    )

    __all__ += [
        "EvalQuestion",
        "EvalDataset",
        "ReasoningType",
        "Difficulty",
    ]
except ImportError:
    pass  # maritime domain not installed
