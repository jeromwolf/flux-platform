"""Unit tests for the TextToCypherPipeline.

All tests are marked with ``@pytest.mark.unit`` and require no external
services (no Neo4j, no LLM).
"""

from __future__ import annotations

import pytest

from kg.exceptions import QueryError
from kg.nlp.nl_parser import ParseResult
from kg.pipeline import TextToCypherPipeline
from kg.query_generator import (
    ExtractedFilter,
    GeneratedQuery,
    QueryIntent,
    QueryIntentType,
    StructuredQuery,
)
from kg.types import FilterOperator


@pytest.fixture()
def pipeline() -> TextToCypherPipeline:
    """Provide a fresh pipeline for each test."""
    return TextToCypherPipeline()


# ---------------------------------------------------------------------------
# Full pipeline process
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineProcess:
    """Test the full process() pipeline."""

    def test_successful_pipeline(self, pipeline: TextToCypherPipeline) -> None:
        """Valid Korean text produces a successful PipelineOutput with Cypher."""
        output = pipeline.process("부산항 선박")
        assert output.success is True
        assert output.generated_query is not None
        assert output.generated_query.language == "cypher"
        assert "MATCH" in output.generated_query.query
        assert output.error is None

    def test_pipeline_preserves_input_text(self, pipeline: TextToCypherPipeline) -> None:
        """PipelineOutput.input_text matches the original input."""
        text = "컨테이너선 목록"
        output = pipeline.process(text)
        assert output.input_text == text

    def test_pipeline_includes_parameters(self, pipeline: TextToCypherPipeline) -> None:
        """Generated query includes parameters when filters are present."""
        output = pipeline.process("부산항 컨테이너선")
        assert output.success is True
        assert output.generated_query is not None
        # At minimum the filter values should be parameterized
        assert isinstance(output.generated_query.parameters, dict)


# ---------------------------------------------------------------------------
# process_to_structured
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProcessToStructured:
    """Test the process_to_structured() step in isolation."""

    def test_returns_parse_result(self, pipeline: TextToCypherPipeline) -> None:
        """process_to_structured returns a ParseResult object."""
        result = pipeline.process_to_structured("선박 정보")
        assert isinstance(result, ParseResult)
        assert isinstance(result.query, StructuredQuery)

    def test_structured_has_entities(self, pipeline: TextToCypherPipeline) -> None:
        """Parsed result has object_types populated."""
        result = pipeline.process_to_structured("유조선 현황")
        assert "Tanker" in result.query.object_types


# ---------------------------------------------------------------------------
# process_to_cypher
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProcessToCypher:
    """Test the process_to_cypher() step in isolation."""

    def test_generates_cypher_from_structured(self, pipeline: TextToCypherPipeline) -> None:
        """A valid StructuredQuery produces Cypher output."""
        sq = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=["Vessel"],
            filters=[
                ExtractedFilter(
                    field="vesselType",
                    operator=FilterOperator.EQUALS,
                    value="ContainerShip",
                )
            ],
        )
        gen = pipeline.process_to_cypher(sq)
        assert isinstance(gen, GeneratedQuery)
        assert "Vessel" in gen.query
        assert "MATCH" in gen.query

    def test_raises_on_empty_object_types(self, pipeline: TextToCypherPipeline) -> None:
        """process_to_cypher raises QueryError when no object_types."""
        sq = StructuredQuery(
            intent=QueryIntent(intent=QueryIntentType.FIND),
            object_types=[],
        )
        with pytest.raises(QueryError):
            pipeline.process_to_cypher(sq)


# ---------------------------------------------------------------------------
# Pipeline with empty/invalid input
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineEdgeCases:
    """Test pipeline with edge-case inputs."""

    def test_empty_text_fails_gracefully(self, pipeline: TextToCypherPipeline) -> None:
        """Empty string input produces a failed PipelineOutput."""
        output = pipeline.process("")
        assert output.success is False
        assert output.generated_query is None
        assert output.error is not None

    def test_unresolvable_text_fails(self, pipeline: TextToCypherPipeline) -> None:
        """Input with no recognizable terms produces failure."""
        output = pipeline.process("xyzzy foobar baz")
        assert output.success is False
        assert output.error is not None


# ---------------------------------------------------------------------------
# PipelineOutput fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineOutputFields:
    """Test PipelineOutput dataclass fields."""

    def test_output_has_parse_result(self, pipeline: TextToCypherPipeline) -> None:
        """PipelineOutput always contains a parse_result."""
        output = pipeline.process("선박")
        assert isinstance(output.parse_result, ParseResult)
        assert output.parse_result.confidence > 0

    def test_output_fields_on_success(self, pipeline: TextToCypherPipeline) -> None:
        """Successful output has all expected fields populated."""
        output = pipeline.process("항구 목록")
        assert output.input_text == "항구 목록"
        assert output.success is True
        assert output.generated_query is not None
        assert output.generated_query.query
        assert output.error is None
