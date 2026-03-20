"""Maritime Knowledge Graph module.

Provides:
- Ontology definitions (ObjectType, LinkType, Ontology)
- CypherBuilder for fluent Neo4j queries
- QueryGenerator for multi-language query generation (Cypher, SQL, MongoDB)
- Crawlers for maritime data sources
- Schema management utilities

Ported patterns from flux-ontology-local TypeScript project to Python.
"""

from kg.config import (
    AppConfig,
    Neo4jConfig,
    close_driver,
    get_config,
    get_driver,
    set_config,
    setup_logging,
)
from kg.cypher_builder import (
    CypherBuilder,
    QueryFilter,
    QueryOptions,
    SpatialQuery,
)
from kg.cypher_corrector import CorrectionResult, CypherCorrector
from kg.cypher_validator import CypherValidator, FailureType, ValidationResult
from kg.etl import ETLPipeline, PipelineConfig, PipelineResult
from kg.exceptions import (
    AccessDeniedError,
    CrawlerError,
    MaritimeKGError,
    QueryError,
    SchemaError,
)
from kg.exceptions import (
    ConnectionError as KGConnectionError,
)
from kg.hallucination_detector import DetectionResult, HallucinationDetector
from kg.lineage import LineageEventType, LineagePolicy, LineageRecorder, RecordingLevel
from kg.nlp.nl_parser import NLParser, ParseResult
from kg.ontology_bridge import (
    OntologyAwareCypherBuilder,
    validate_structured_query,
)
from kg.pipeline import PipelineOutput, TextToCypherPipeline
from kg.quality_gate import CheckResult, CheckStatus, GateReport, QualityGate
from kg.query_generator import (
    AggregationFunction,
    AggregationSpec,
    ExtractedFilter,
    GeneratedQuery,
    Pagination,
    QueryComplexity,
    QueryGenerator,
    QueryIntent,
    QueryIntentType,
    RelationshipSpec,
    SortSpec,
    StructuredQuery,
)
from kg.types import FilterOperator, ReasoningType

__all__ = [
    # Config
    "AppConfig",
    "Neo4jConfig",
    "get_config",
    "set_config",
    "get_driver",
    "close_driver",
    "setup_logging",
    # Exceptions
    "MaritimeKGError",
    "KGConnectionError",
    "SchemaError",
    "CrawlerError",
    "AccessDeniedError",
    "QueryError",
    # CypherBuilder
    "CypherBuilder",
    "QueryFilter",
    "QueryOptions",
    "SpatialQuery",
    "FilterOperator",
    # QueryGenerator
    "QueryGenerator",
    "StructuredQuery",
    "GeneratedQuery",
    "QueryIntent",
    "ExtractedFilter",
    "RelationshipSpec",
    "AggregationSpec",
    "SortSpec",
    "Pagination",
    "QueryIntentType",
    "AggregationFunction",
    "QueryComplexity",
    "ReasoningType",
    # OntologyBridge
    "OntologyAwareCypherBuilder",
    "validate_structured_query",
    # ETL Pipeline
    "ETLPipeline",
    "PipelineConfig",
    "PipelineResult",
    # Lineage
    "LineageRecorder",
    "LineagePolicy",
    "LineageEventType",
    "RecordingLevel",
    # NL Parser
    "NLParser",
    "ParseResult",
    # Text-to-Cypher Pipeline
    "TextToCypherPipeline",
    "PipelineOutput",
    # Cypher Validator & Corrector
    "CypherValidator",
    "ValidationResult",
    "FailureType",
    "CypherCorrector",
    "CorrectionResult",
    # Hallucination Detector
    "HallucinationDetector",
    "DetectionResult",
    # Quality Gate
    "QualityGate",
    "GateReport",
    "CheckResult",
    "CheckStatus",
]
