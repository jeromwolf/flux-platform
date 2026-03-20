"""Unified Text-to-Cypher pipeline service.

Orchestrates the NLParser and QueryGenerator into a 4-stage pipeline that
converts Korean natural language text into validated, executable Cypher queries.

Stages::

    1. Parse      -- Korean NL text -> StructuredQuery
    2. Generate   -- StructuredQuery -> Cypher
    3. Validate   -- Check Cypher against ontology/syntax (optional)
    4. Correct    -- Rule-based fix of common issues (optional)

Usage::

    from kg.pipeline import TextToCypherPipeline

    # Basic (2-stage: Parse -> Generate)
    pipeline = TextToCypherPipeline()
    output = pipeline.process("부산항 근처 컨테이너선")

    # Full 4-stage with validation & correction
    from kg.cypher_validator import CypherValidator
    from kg.cypher_corrector import CypherCorrector

    validator = CypherValidator.from_maritime_ontology()
    corrector = CypherCorrector.from_maritime_ontology()
    pipeline = TextToCypherPipeline(validator=validator, corrector=corrector)
    output = pipeline.process("부산항 근처 컨테이너선")

    if output.success:
        print(output.generated_query.query)
        print(output.validation_errors)
        print(output.corrections_applied)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from kg.exceptions import QueryError
from kg.nlp.nl_parser import NLParser, ParseResult
from kg.query_generator import GeneratedQuery, QueryGenerator, QueryIntent, StructuredQuery

logger = logging.getLogger(__name__)

# Optional ontology import -- only used when an Ontology instance is provided.
try:
    from kg.ontology.core import Ontology
except ImportError:  # pragma: no cover
    Ontology = None  # type: ignore[assignment,misc]

# Optional validator/corrector imports
try:
    from kg.cypher_validator import CypherValidator, ValidationResult
except ImportError:  # pragma: no cover
    CypherValidator = None  # type: ignore[assignment,misc]
    ValidationResult = None  # type: ignore[assignment,misc]

try:
    from kg.cypher_corrector import CorrectionResult, CypherCorrector
except ImportError:  # pragma: no cover
    CypherCorrector = None  # type: ignore[assignment,misc]
    CorrectionResult = None  # type: ignore[assignment,misc]

# Optional hallucination detector import
try:
    from kg.hallucination_detector import DetectionResult, HallucinationDetector
except ImportError:  # pragma: no cover
    HallucinationDetector = None  # type: ignore[assignment,misc]
    DetectionResult = None  # type: ignore[assignment,misc]


@dataclass
class PipelineOutput:
    """Result of the full Text-to-Cypher pipeline.

    Attributes:
        input_text: The original Korean text that was processed.
        parse_result: Detailed result from the NL parser step.
        generated_query: The generated Cypher query, or None if parsing
            produced no actionable entities.
        success: Whether the pipeline completed without errors and
            produced a usable query.
        error: Error message if the pipeline failed at any step.
        validation_errors: Errors found during Cypher validation (Stage 3).
        validation_warnings: Warnings found during Cypher validation.
        validation_score: Quality score from validation (0.0-1.0).
        corrections_applied: Descriptions of corrections made (Stage 4).
        failure_type: GraphRAG Part 11 failure classification string
            (``"none"``, ``"schema"``, ``"retrieval"``, ``"generation"``),
            or ``None`` if validation was not performed.
    """

    input_text: str
    parse_result: ParseResult
    generated_query: GeneratedQuery | None = None
    success: bool = False
    error: str | None = None
    reasoning_type: str | None = None
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    validation_score: float | None = None
    corrections_applied: list[str] = field(default_factory=list)
    failure_type: str | None = None
    hallucination_result: dict[str, Any] | None = None


class TextToCypherPipeline:
    """4-stage pipeline: Korean text -> StructuredQuery -> Cypher -> Validate -> Correct.

    Orchestrates :class:`~kg.nlp.nl_parser.NLParser`,
    :class:`~kg.query_generator.QueryGenerator`,
    :class:`~kg.cypher_validator.CypherValidator` (optional), and
    :class:`~kg.cypher_corrector.CypherCorrector` (optional) into a single
    service.

    When ``validator`` and ``corrector`` are not provided, the pipeline
    operates in 2-stage mode (Parse -> Generate) for backward compatibility.

    Args:
        ontology: Optional Ontology instance for ontology-bridge validation.
        validator: Optional CypherValidator for Stage 3 validation.
        corrector: Optional CypherCorrector for Stage 4 correction.
        hallucination_detector: Optional HallucinationDetector for
            validating generated answers against the KG (Stage 5).
    """

    def __init__(
        self,
        ontology: Any | None = None,
        validator: Any | None = None,
        corrector: Any | None = None,
        hallucination_detector: Any | None = None,
    ) -> None:
        self._parser = NLParser()
        self._generator = QueryGenerator()
        self._ontology = ontology
        self._validator = validator
        self._corrector = corrector
        self._hallucination_detector = hallucination_detector

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, text: str) -> PipelineOutput:
        """Run the full pipeline: Korean text -> StructuredQuery -> Cypher.

        Args:
            text: Korean natural language query string.

        Returns:
            PipelineOutput with parse result and generated Cypher.
        """
        # Step 1: Parse
        try:
            parse_result = self._parser.parse(text)
        except Exception as exc:
            logger.exception("NL parsing failed for: %s", text)
            empty_parse = ParseResult(
                query=StructuredQuery(
                    intent=QueryIntent(
                        intent="FIND", confidence=0.0,
                    ),
                ),
                confidence=0.0,
                parse_details={"error": str(exc)},
            )
            return PipelineOutput(
                input_text=text,
                parse_result=empty_parse,
                success=False,
                error=f"Parse error: {exc}",
            )

        # Step 2: Check if we have anything to generate from
        if not parse_result.query.object_types:
            return PipelineOutput(
                input_text=text,
                parse_result=parse_result,
                generated_query=None,
                success=False,
                error="No entities could be extracted from the input text",
            )

        # Step 3: Generate Cypher
        try:
            generated = self._generator.generate_cypher(parse_result.query)
        except Exception as exc:
            logger.exception("Cypher generation failed for: %s", text)
            return PipelineOutput(
                input_text=text,
                parse_result=parse_result,
                generated_query=None,
                success=False,
                error=f"Generation error: {exc}",
            )

        # Step 4: Optional ontology-bridge validation (legacy)
        if self._ontology is not None:
            try:
                from kg.ontology_bridge import validate_structured_query

                warnings = validate_structured_query(
                    parse_result.query, self._ontology
                )
                if warnings:
                    existing = generated.warnings or []
                    generated = GeneratedQuery(
                        language=generated.language,
                        query=generated.query,
                        parameters=generated.parameters,
                        explanation=generated.explanation,
                        estimated_complexity=generated.estimated_complexity,
                        warnings=existing + warnings,
                    )
            except Exception:
                logger.debug("Ontology validation skipped", exc_info=True)

        # Step 5: Cypher validation (Stage 3)
        validation_errors: list[str] = []
        validation_warnings: list[str] = []
        validation_score: float | None = None
        corrections_applied: list[str] = []
        failure_type: str | None = None

        if self._validator is not None:
            try:
                val_result = self._validator.validate(generated.query)
                validation_errors = list(val_result.errors)
                validation_warnings = list(val_result.warnings)
                validation_score = val_result.score
                failure_type = val_result.failure_type.value

                # Step 6: Cypher correction (Stage 4) -- only if invalid
                if not val_result.is_valid and self._corrector is not None:
                    try:
                        corr_result = self._corrector.correct(generated.query)
                        if corr_result.was_modified:
                            corrections_applied = list(
                                corr_result.corrections_applied
                            )
                            # Update the generated query with corrected Cypher
                            generated = GeneratedQuery(
                                language=generated.language,
                                query=corr_result.corrected,
                                parameters=generated.parameters,
                                explanation=generated.explanation,
                                estimated_complexity=generated.estimated_complexity,
                                warnings=generated.warnings,
                            )
                            # Re-validate the corrected query
                            re_val = self._validator.validate(
                                corr_result.corrected
                            )
                            validation_errors = list(re_val.errors)
                            validation_warnings = list(re_val.warnings)
                            validation_score = re_val.score
                            failure_type = re_val.failure_type.value
                    except Exception:
                        logger.debug(
                            "Cypher correction failed", exc_info=True
                        )
            except Exception:
                logger.debug("Cypher validation failed", exc_info=True)

        # Step 7: Hallucination detection (Stage 5)
        hallucination_result: dict[str, Any] | None = None
        if self._hallucination_detector is not None:
            try:
                # Validate the generated Cypher entity references
                detection = self._hallucination_detector.validate(
                    generated.query
                )
                hallucination_result = {
                    "is_valid": detection.is_valid,
                    "mentioned_entities": detection.mentioned_entities,
                    "verified_entities": detection.verified_entities,
                    "hallucinated_entities": detection.hallucinated_entities,
                    "confidence": detection.confidence,
                }
            except Exception:
                logger.debug(
                    "Hallucination detection failed", exc_info=True
                )

        return PipelineOutput(
            input_text=text,
            parse_result=parse_result,
            generated_query=generated,
            success=True,
            reasoning_type=parse_result.query.reasoning_type.value,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            validation_score=validation_score,
            corrections_applied=corrections_applied,
            failure_type=failure_type,
            hallucination_result=hallucination_result,
        )

    def process_to_structured(self, text: str) -> ParseResult:
        """Run only the parsing step: Korean text -> StructuredQuery.

        Args:
            text: Korean natural language query string.

        Returns:
            ParseResult from the NL parser.
        """
        return self._parser.parse(text)

    def process_to_cypher(self, structured: StructuredQuery) -> GeneratedQuery:
        """Run only the generation step: StructuredQuery -> Cypher.

        Args:
            structured: A pre-built StructuredQuery.

        Returns:
            GeneratedQuery with Cypher text and parameters.

        Raises:
            QueryError: If the query has no object types or generation fails.
        """
        if not structured.object_types:
            raise QueryError(
                "StructuredQuery must have at least one object_type",
                language="cypher",
            )
        return self._generator.generate_cypher(structured)
