"""ETL pipeline framework for maritime data ingestion.

Provides:
- Pipeline configuration and lifecycle models
- Composable transform and validation steps
- Dead Letter Queue for failed records
- Neo4j batch loader with MERGE semantics
- Orchestrating ETLPipeline combining all stages
"""

from kg.etl.dlq import DLQEntry, DLQManager
from kg.etl.loader import Neo4jBatchLoader
from kg.etl.models import (
    ETLMode,
    IncrementalConfig,
    PipelineConfig,
    PipelineResult,
    PipelineStatus,
    RecordEnvelope,
)
from kg.etl.pipeline import ETLPipeline
from kg.etl.raw_store import LocalFileStore, NullRawStore, RawStore, make_raw_key
from kg.etl.transforms import (
    ChainTransform,
    DateTimeNormalizer,
    IdentifierNormalizer,
    TextNormalizer,
    TransformStep,
)
from kg.etl.validator import (
    OntologyLabelRule,
    RecordValidator,
    RequiredFieldsRule,
    TypeCheckRule,
    ValidationRule,
)

__all__ = [
    # Models
    "ETLMode",
    "IncrementalConfig",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStatus",
    "RecordEnvelope",
    # Transforms
    "TransformStep",
    "DateTimeNormalizer",
    "TextNormalizer",
    "IdentifierNormalizer",
    "ChainTransform",
    # Validation
    "ValidationRule",
    "RequiredFieldsRule",
    "TypeCheckRule",
    "OntologyLabelRule",
    "RecordValidator",
    # DLQ
    "DLQEntry",
    "DLQManager",
    # Loader
    "Neo4jBatchLoader",
    # Pipeline
    "ETLPipeline",
    # Raw Store
    "RawStore",
    "NullRawStore",
    "LocalFileStore",
    "make_raw_key",
]
