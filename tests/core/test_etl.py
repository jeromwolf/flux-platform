"""Unit tests for the kg.etl ETL pipeline framework.

Test Coverage:
- PipelineConfig defaults and immutability (3 tests)
- RecordEnvelope creation (2 tests)
- PipelineStatus enum values (2 tests)
- DateTimeNormalizer with various formats (3 tests)
- TextNormalizer stripping/collapsing (3 tests)
- IdentifierNormalizer (2 tests)
- ChainTransform chaining (2 tests)
- RequiredFieldsRule with missing fields (3 tests)
- TypeCheckRule with wrong types (2 tests)
- OntologyLabelRule with valid/invalid labels (3 tests)
- RecordValidator combining rules (2 tests)
- DLQManager add/get/retry/clear (5 tests)
- Neo4jBatchLoader merge cypher generation (3 tests)
- ETLPipeline full flow with mocked loader (5 tests)
- ETLPipeline with DLQ on validation failure (2 tests)

Total: ~42 tests
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from kg.etl.dlq import DLQManager
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
)
from kg.lineage import LineageEventType, LineagePolicy, LineageRecorder, RecordingLevel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(
    data: dict | None = None,
    source: str = "test",
    record_id: str = "rec-001",
) -> RecordEnvelope:
    """Create a RecordEnvelope with sensible defaults."""
    return RecordEnvelope(
        data=data if data is not None else {"name": "Test"},
        source=source,
        record_id=record_id,
    )


# =========================================================================
# PipelineConfig
# =========================================================================


@pytest.mark.unit
class TestPipelineConfig:
    def test_defaults(self):
        """PipelineConfig has expected default values."""
        cfg = PipelineConfig(name="test-pipeline")
        assert cfg.name == "test-pipeline"
        assert cfg.batch_size == 500
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 1.0
        assert cfg.dlq_enabled is True
        assert cfg.validate is True

    def test_frozen(self):
        """PipelineConfig is immutable."""
        cfg = PipelineConfig(name="test")
        with pytest.raises(AttributeError):
            cfg.name = "changed"  # type: ignore[misc]

    def test_custom_values(self):
        """PipelineConfig accepts custom overrides."""
        cfg = PipelineConfig(
            name="custom",
            batch_size=100,
            max_retries=5,
            retry_delay=2.5,
            dlq_enabled=False,
            validate=False,
        )
        assert cfg.batch_size == 100
        assert cfg.max_retries == 5
        assert cfg.retry_delay == 2.5
        assert cfg.dlq_enabled is False
        assert cfg.validate is False


# =========================================================================
# RecordEnvelope
# =========================================================================


@pytest.mark.unit
class TestRecordEnvelope:
    def test_creation(self):
        """RecordEnvelope stores data, source, and record_id."""
        env = RecordEnvelope(data={"key": "val"}, source="crawler", record_id="r1")
        assert env.data == {"key": "val"}
        assert env.source == "crawler"
        assert env.record_id == "r1"
        assert isinstance(env.timestamp, datetime)
        assert env.metadata == {}
        assert env.errors == []

    def test_mutable_fields(self):
        """RecordEnvelope allows mutation of data and errors."""
        env = _make_envelope()
        env.data["extra"] = 42
        env.errors.append("some error")
        assert env.data["extra"] == 42
        assert "some error" in env.errors


# =========================================================================
# PipelineStatus
# =========================================================================


@pytest.mark.unit
class TestPipelineStatus:
    def test_values(self):
        """PipelineStatus has all expected members."""
        assert PipelineStatus.PENDING == "PENDING"
        assert PipelineStatus.RUNNING == "RUNNING"
        assert PipelineStatus.COMPLETED == "COMPLETED"
        assert PipelineStatus.FAILED == "FAILED"
        assert PipelineStatus.CANCELLED == "CANCELLED"

    def test_is_str(self):
        """PipelineStatus members are strings."""
        assert isinstance(PipelineStatus.PENDING, str)
        assert PipelineStatus.RUNNING.upper() == "RUNNING"


# =========================================================================
# DateTimeNormalizer
# =========================================================================


@pytest.mark.unit
class TestDateTimeNormalizer:
    def test_iso_format(self):
        """DateTimeNormalizer handles standard ISO 8601 input."""
        norm = DateTimeNormalizer(fields=["date"])
        env = _make_envelope(data={"date": "2024-03-15T10:30:00"})
        result = norm.transform(env)
        assert result.data["date"] == "2024-03-15T10:30:00"

    def test_korean_date_format(self):
        """DateTimeNormalizer handles Korean date strings."""
        norm = DateTimeNormalizer(fields=["date"])
        env = _make_envelope(data={"date": "2024년 3월 15일"})
        result = norm.transform(env)
        assert result.data["date"] == "2024-03-15T00:00:00"

    def test_date_only_slash(self):
        """DateTimeNormalizer handles YYYY/MM/DD format."""
        norm = DateTimeNormalizer(fields=["date"])
        env = _make_envelope(data={"date": "2024/03/15"})
        result = norm.transform(env)
        assert result.data["date"] == "2024-03-15T00:00:00"


# =========================================================================
# TextNormalizer
# =========================================================================


@pytest.mark.unit
class TestTextNormalizer:
    def test_strip_whitespace(self):
        """TextNormalizer strips leading and trailing whitespace."""
        norm = TextNormalizer(fields=["name"])
        env = _make_envelope(data={"name": "  부산항  "})
        result = norm.transform(env)
        assert result.data["name"] == "부산항"

    def test_collapse_internal_whitespace(self):
        """TextNormalizer collapses internal runs of whitespace."""
        norm = TextNormalizer(fields=["name"])
        env = _make_envelope(data={"name": "부산   국제   항"})
        result = norm.transform(env)
        assert result.data["name"] == "부산 국제 항"

    def test_skips_non_string(self):
        """TextNormalizer ignores non-string field values."""
        norm = TextNormalizer(fields=["count"])
        env = _make_envelope(data={"count": 42})
        result = norm.transform(env)
        assert result.data["count"] == 42


# =========================================================================
# IdentifierNormalizer
# =========================================================================


@pytest.mark.unit
class TestIdentifierNormalizer:
    def test_prefix_added(self):
        """IdentifierNormalizer prepends prefix when missing."""
        norm = IdentifierNormalizer(field="portId", prefix="KRPUS")
        env = _make_envelope(data={"portId": "001"})
        result = norm.transform(env)
        assert result.data["portId"] == "KRPUS-001"

    def test_prefix_already_present(self):
        """IdentifierNormalizer does not double-prefix."""
        norm = IdentifierNormalizer(field="portId", prefix="KRPUS")
        env = _make_envelope(data={"portId": "KRPUS-001"})
        result = norm.transform(env)
        assert result.data["portId"] == "KRPUS-001"


# =========================================================================
# ChainTransform
# =========================================================================


@pytest.mark.unit
class TestChainTransform:
    def test_chain_applies_in_order(self):
        """ChainTransform applies transforms sequentially."""
        chain = ChainTransform([
            TextNormalizer(fields=["name"]),
            IdentifierNormalizer(field="id", prefix="V"),
        ])
        env = _make_envelope(data={"name": "  Test Ship  ", "id": "001"})
        result = chain.transform(env)
        assert result.data["name"] == "Test Ship"
        assert result.data["id"] == "V-001"

    def test_chain_name(self):
        """ChainTransform name includes child names."""
        chain = ChainTransform([
            TextNormalizer(fields=["name"]),
            DateTimeNormalizer(fields=["date"]),
        ])
        assert "TextNormalizer" in chain.name
        assert "DateTimeNormalizer" in chain.name


# =========================================================================
# RequiredFieldsRule
# =========================================================================


@pytest.mark.unit
class TestRequiredFieldsRule:
    def test_all_present(self):
        """No errors when all required fields are present."""
        rule = RequiredFieldsRule(fields=["name", "id"])
        env = _make_envelope(data={"name": "Ship", "id": "V001"})
        errors = rule.validate(env)
        assert errors == []

    def test_missing_field(self):
        """Error for missing required field."""
        rule = RequiredFieldsRule(fields=["name", "id"])
        env = _make_envelope(data={"name": "Ship"})
        errors = rule.validate(env)
        assert len(errors) == 1
        assert "id" in errors[0]

    def test_empty_string_field(self):
        """Error for empty-string required field."""
        rule = RequiredFieldsRule(fields=["name"])
        env = _make_envelope(data={"name": "   "})
        errors = rule.validate(env)
        assert len(errors) == 1
        assert "Empty" in errors[0]


# =========================================================================
# TypeCheckRule
# =========================================================================


@pytest.mark.unit
class TestTypeCheckRule:
    def test_correct_types(self):
        """No errors when types match."""
        rule = TypeCheckRule(schema={"name": str, "count": int})
        env = _make_envelope(data={"name": "Ship", "count": 5})
        errors = rule.validate(env)
        assert errors == []

    def test_wrong_type(self):
        """Error when field has wrong type."""
        rule = TypeCheckRule(schema={"count": int})
        env = _make_envelope(data={"count": "not_an_int"})
        errors = rule.validate(env)
        assert len(errors) == 1
        assert "int" in errors[0]
        assert "str" in errors[0]


# =========================================================================
# OntologyLabelRule
# =========================================================================


@pytest.mark.unit
class TestOntologyLabelRule:
    def test_valid_label(self):
        """No errors for a valid ontology label."""
        rule = OntologyLabelRule()
        env = _make_envelope(data={"label": "Vessel"})
        errors = rule.validate(env)
        assert errors == []

    def test_invalid_label(self):
        """Error for an unknown label."""
        rule = OntologyLabelRule()
        env = _make_envelope(data={"label": "SpaceShuttle"})
        errors = rule.validate(env)
        assert len(errors) == 1
        assert "Unknown" in errors[0]

    def test_missing_label_field(self):
        """Error when label field is absent."""
        rule = OntologyLabelRule()
        env = _make_envelope(data={"name": "Test"})
        errors = rule.validate(env)
        assert len(errors) == 1
        assert "Missing" in errors[0]


# =========================================================================
# RecordValidator
# =========================================================================


@pytest.mark.unit
class TestRecordValidator:
    def test_all_rules_pass(self):
        """No errors when all rules pass."""
        validator = RecordValidator(rules=[
            RequiredFieldsRule(fields=["name"]),
            TypeCheckRule(schema={"name": str}),
        ])
        env = _make_envelope(data={"name": "Ship"})
        errors = validator.validate(env)
        assert errors == []

    def test_multiple_rule_errors(self):
        """Errors from multiple rules are aggregated."""
        validator = RecordValidator(rules=[
            RequiredFieldsRule(fields=["name", "id"]),
            TypeCheckRule(schema={"count": int}),
        ])
        env = _make_envelope(data={"count": "bad"})
        errors = validator.validate(env)
        # 2 missing fields + 1 type error
        assert len(errors) == 3


# =========================================================================
# DLQManager
# =========================================================================


@pytest.mark.unit
class TestDLQManager:
    def test_add_and_size(self):
        """DLQManager tracks added entries and size."""
        dlq = DLQManager()
        assert dlq.size == 0
        env = _make_envelope()
        dlq.add(env, ["error1"])
        assert dlq.size == 1

    def test_get_entries(self):
        """DLQManager returns copies of entries."""
        dlq = DLQManager()
        env = _make_envelope()
        dlq.add(env, ["err"])
        entries = dlq.get_entries()
        assert len(entries) == 1
        assert entries[0].record is env
        assert entries[0].errors == ["err"]

    def test_retry_eligible(self):
        """DLQManager filters entries by retry count."""
        dlq = DLQManager()
        env1 = _make_envelope(record_id="r1")
        env2 = _make_envelope(record_id="r2")
        dlq.add(env1, ["err"])
        dlq.add(env2, ["err"])
        # Simulate one entry having been retried
        dlq.get_entries()[0].retry_count = 3
        eligible = dlq.retry_eligible(max_retries=3)
        assert len(eligible) == 1
        assert eligible[0].record.record_id == "r2"

    def test_clear(self):
        """DLQManager.clear() removes all entries."""
        dlq = DLQManager()
        dlq.add(_make_envelope(), ["err"])
        dlq.add(_make_envelope(record_id="r2"), ["err"])
        assert dlq.size == 2
        dlq.clear()
        assert dlq.size == 0

    def test_entry_has_failed_at(self):
        """DLQEntry records the timestamp of failure."""
        dlq = DLQManager()
        before = datetime.now()
        dlq.add(_make_envelope(), ["err"])
        after = datetime.now()
        entry = dlq.get_entries()[0]
        assert before <= entry.failed_at <= after


# =========================================================================
# Neo4jBatchLoader
# =========================================================================


@pytest.mark.unit
class TestNeo4jBatchLoader:
    def test_merge_cypher_generation(self):
        """Loader generates correct MERGE cypher with UNWIND."""
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")
        cypher = loader._build_merge_cypher()
        assert "UNWIND $batch AS row" in cypher
        assert "MERGE (n:Vessel {vesselId: row.vesselId})" in cypher
        assert "SET n += row" in cypher

    def test_load_calls_session(self):
        """Loader calls session.run with correct parameters."""
        loader = Neo4jBatchLoader(label="Port", id_field="portId", batch_size=2)
        mock_session = MagicMock()
        records = [
            {"portId": "P1", "name": "Busan"},
            {"portId": "P2", "name": "Incheon"},
            {"portId": "P3", "name": "Ulsan"},
        ]
        count = loader.load(records, mock_session)
        assert count == 3
        # 2 batches: [P1,P2] and [P3]
        assert mock_session.run.call_count == 2

    def test_load_empty_records(self):
        """Loader returns 0 for empty record list."""
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")
        mock_session = MagicMock()
        count = loader.load([], mock_session)
        assert count == 0
        mock_session.run.assert_not_called()


# =========================================================================
# ETLPipeline - Full Flow
# =========================================================================


@pytest.mark.unit
class TestETLPipelineFlow:
    def test_simple_flow(self):
        """Pipeline processes records through transform and load."""
        mock_session = MagicMock()
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")

        pipeline = (
            ETLPipeline(PipelineConfig(name="test"))
            .add_transform(TextNormalizer(fields=["name"]))
            .set_loader(loader)
        )

        records = [
            _make_envelope(data={"vesselId": "V1", "name": "  Ship One  "}),
            _make_envelope(data={"vesselId": "V2", "name": "Ship  Two"}, record_id="rec-002"),
        ]

        result = pipeline.run(records, session=mock_session)
        assert result.records_processed == 2
        assert result.records_failed == 0
        assert result.records_skipped == 0
        assert result.duration_seconds > 0
        assert result.started_at is not None
        assert result.completed_at is not None

    def test_pipeline_status_tracking(self):
        """Pipeline tracks status through lifecycle."""
        pipeline = ETLPipeline(PipelineConfig(name="status-test"))
        assert pipeline.status == PipelineStatus.PENDING

        pipeline.run([])
        assert pipeline.status == PipelineStatus.COMPLETED

    def test_no_loader_counts_records(self):
        """Pipeline without loader still counts processed records."""
        pipeline = ETLPipeline(PipelineConfig(name="no-loader"))
        records = [_make_envelope(data={"id": "1"})]
        result = pipeline.run(records)
        assert result.records_processed == 1

    def test_transform_error_to_dlq(self):
        """Records that fail transformation go to DLQ."""

        class FailingTransform(TransformStep):
            @property
            def name(self) -> str:
                return "Failing"

            def transform(self, record: RecordEnvelope) -> RecordEnvelope:
                raise ValueError("transform boom")

        pipeline = ETLPipeline(PipelineConfig(name="fail-test"))
        pipeline.add_transform(FailingTransform())

        records = [_make_envelope()]
        result = pipeline.run(records)
        assert result.records_failed == 1
        assert result.records_processed == 0
        assert pipeline.dlq.size == 1
        assert "transform boom" in result.errors[0]

    def test_loader_error_fails_pipeline(self):
        """Pipeline status is FAILED when loader raises."""
        mock_session = MagicMock()
        mock_session.run.side_effect = RuntimeError("neo4j down")
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")

        pipeline = ETLPipeline(PipelineConfig(name="loader-fail"))
        pipeline.set_loader(loader)

        records = [_make_envelope(data={"vesselId": "V1"})]
        result = pipeline.run(records, session=mock_session)
        assert pipeline.status == PipelineStatus.FAILED
        assert result.records_failed == 1
        assert "neo4j down" in result.errors[0]


# =========================================================================
# ETLPipeline - Validation + DLQ
# =========================================================================


@pytest.mark.unit
class TestETLPipelineValidation:
    def test_validation_failure_skips_record(self):
        """Records failing validation are skipped and sent to DLQ."""
        validator = RecordValidator(rules=[
            RequiredFieldsRule(fields=["vesselId"]),
        ])

        pipeline = (
            ETLPipeline(PipelineConfig(name="val-test"))
            .set_validator(validator)
        )

        records = [
            _make_envelope(data={"vesselId": "V1", "name": "Ship"}),
            _make_envelope(data={"name": "No ID"}, record_id="rec-002"),
        ]

        result = pipeline.run(records)
        assert result.records_processed == 1
        assert result.records_skipped == 1
        assert pipeline.dlq.size == 1

    def test_validation_disabled(self):
        """Validation is skipped when config.validate is False."""
        validator = RecordValidator(rules=[
            RequiredFieldsRule(fields=["vesselId"]),
        ])

        pipeline = (
            ETLPipeline(PipelineConfig(name="no-val", validate=False))
            .set_validator(validator)
        )

        # This record would fail validation, but validation is disabled
        records = [_make_envelope(data={"name": "No ID"})]
        result = pipeline.run(records)
        assert result.records_processed == 1
        assert result.records_skipped == 0


# =========================================================================
# ETLPipeline - Lineage Integration
# =========================================================================


@pytest.mark.unit
class TestETLPipelineLineageIntegration:
    def test_pipeline_with_lineage_recorder(self):
        """Pipeline records lineage events when recorder is set."""
        policy = LineagePolicy(default_level=RecordingLevel.DETAILED)
        recorder = LineageRecorder(policy=policy)
        mock_session = MagicMock()
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")

        pipeline = (
            ETLPipeline(PipelineConfig(name="lineage-test"))
            .add_transform(TextNormalizer(fields=["name"]))
            .set_loader(loader)
            .set_lineage_recorder(recorder)
        )

        records = [
            _make_envelope(data={"vesselId": "V1", "name": "  Ship One  "}, record_id="rec-001"),
            _make_envelope(data={"vesselId": "V2", "name": "Ship Two"}, record_id="rec-002"),
        ]

        result = pipeline.run(records, session=mock_session)
        assert result.records_processed == 2

        graph = recorder.get_graph()
        # 2 records x (INGESTION + TRANSFORMATION) = 4 edges
        assert len(graph.edges) == 4
        assert len(graph.nodes) == 2

    def test_pipeline_without_lineage_recorder(self):
        """Pipeline works normally without lineage recorder (backward compat)."""
        mock_session = MagicMock()
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")

        pipeline = (
            ETLPipeline(PipelineConfig(name="no-lineage"))
            .set_loader(loader)
        )

        records = [_make_envelope(data={"vesselId": "V1", "name": "Ship"})]
        result = pipeline.run(records, session=mock_session)
        assert result.records_processed == 1
        assert result.records_failed == 0

    def test_lineage_recorder_failure_does_not_break_pipeline(self):
        """Pipeline completes even if lineage recorder raises."""
        recorder = LineageRecorder()
        mock_session = MagicMock()
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")

        pipeline = (
            ETLPipeline(PipelineConfig(name="lineage-fail"))
            .set_loader(loader)
            .set_lineage_recorder(recorder)
        )

        with patch.object(recorder, "record_event", side_effect=RuntimeError("boom")):
            records = [_make_envelope(data={"vesselId": "V1", "name": "Ship"})]
            result = pipeline.run(records, session=mock_session)

        assert result.records_processed == 1
        assert result.records_failed == 0

    def test_lineage_events_have_correct_type(self):
        """Lineage events recorded are of INGESTION type."""
        policy = LineagePolicy(default_level=RecordingLevel.DETAILED)
        recorder = LineageRecorder(policy=policy)

        pipeline = (
            ETLPipeline(PipelineConfig(name="type-check"))
            .set_lineage_recorder(recorder)
        )

        records = [_make_envelope(data={"id": "1"}, record_id="rec-001")]  # noqa: E501
        pipeline.run(records)

        graph = recorder.get_graph()
        event_types = [e.event_type for e in graph.edges]
        assert LineageEventType.INGESTION in event_types

    def test_lineage_agent_includes_pipeline_name(self):
        """Lineage agent string contains the pipeline name."""
        recorder = LineageRecorder()

        pipeline = (
            ETLPipeline(PipelineConfig(name="my-pipe"))
            .set_lineage_recorder(recorder)
        )

        records = [_make_envelope(data={"id": "1"}, record_id="rec-001")]  # noqa: E501
        pipeline.run(records)

        graph = recorder.get_graph()
        agents = [e.agent for e in graph.edges]
        assert all("my-pipe" in a for a in agents)


# =========================================================================
# Incremental ETL
# =========================================================================


@pytest.mark.unit
class TestIncrementalETL:
    """Test incremental ETL update mode."""

    def test_detect_changes_filters_old_records(self):
        """Records before cutoff are filtered out."""
        config = IncrementalConfig(
            last_update_time="2025-06-01T00:00:00",
            change_field="updatedAt",
        )
        pipeline = ETLPipeline(
            PipelineConfig(name="inc-old"),
            mode=ETLMode.INCREMENTAL,
            incremental_config=config,
        )

        records = [
            _make_envelope(data={"id": "1", "updatedAt": "2025-05-01T00:00:00"}, record_id="old"),
            _make_envelope(data={"id": "2", "updatedAt": "2025-07-01T00:00:00"}, record_id="new"),
        ]

        changed = pipeline.detect_changes(records)
        assert len(changed) == 1
        assert changed[0].record_id == "new"

    def test_detect_changes_includes_new_records(self):
        """Records after cutoff are included."""
        config = IncrementalConfig(
            last_update_time="2025-01-01T00:00:00",
            change_field="updatedAt",
        )
        pipeline = ETLPipeline(
            PipelineConfig(name="inc-new"),
            mode=ETLMode.INCREMENTAL,
            incremental_config=config,
        )

        records = [
            _make_envelope(data={"id": "1", "updatedAt": "2025-03-15T10:00:00"}, record_id="r1"),
            _make_envelope(data={"id": "2", "updatedAt": "2025-06-20T12:00:00"}, record_id="r2"),
        ]

        changed = pipeline.detect_changes(records)
        assert len(changed) == 2

    def test_detect_changes_includes_records_without_field(self):
        """Records missing change field are included (conservative)."""
        config = IncrementalConfig(
            last_update_time="2025-06-01T00:00:00",
            change_field="updatedAt",
        )
        pipeline = ETLPipeline(
            PipelineConfig(name="inc-missing"),
            mode=ETLMode.INCREMENTAL,
            incremental_config=config,
        )

        records = [
            _make_envelope(data={"id": "1"}, record_id="no-field"),
            _make_envelope(data={"id": "2", "updatedAt": "2025-04-01T00:00:00"}, record_id="old"),
        ]

        changed = pipeline.detect_changes(records)
        assert len(changed) == 1
        assert changed[0].record_id == "no-field"

    def test_detect_changes_no_config_returns_all(self):
        """Without incremental config, all records returned."""
        pipeline = ETLPipeline(
            PipelineConfig(name="inc-noconfig"),
            mode=ETLMode.INCREMENTAL,
        )

        records = [
            _make_envelope(data={"id": "1", "updatedAt": "2020-01-01T00:00:00"}, record_id="r1"),
            _make_envelope(data={"id": "2", "updatedAt": "2020-01-01T00:00:00"}, record_id="r2"),
        ]

        changed = pipeline.detect_changes(records)
        assert len(changed) == 2

    def test_detect_changes_no_last_update_time_returns_all(self):
        """With config but no last_update_time, all records returned."""
        config = IncrementalConfig(change_field="updatedAt")  # last_update_time is None
        pipeline = ETLPipeline(
            PipelineConfig(name="inc-notime"),
            mode=ETLMode.INCREMENTAL,
            incremental_config=config,
        )

        records = [
            _make_envelope(data={"id": "1", "updatedAt": "2020-01-01T00:00:00"}, record_id="r1"),
        ]

        changed = pipeline.detect_changes(records)
        assert len(changed) == 1

    def test_full_mode_processes_all(self):
        """FULL mode processes all records without filtering."""
        pipeline = ETLPipeline(PipelineConfig(name="full-all"))

        records = [
            _make_envelope(data={"id": "1"}, record_id="r1"),
            _make_envelope(data={"id": "2"}, record_id="r2"),
            _make_envelope(data={"id": "3"}, record_id="r3"),
        ]

        result = pipeline.run(records)
        assert result.records_processed == 3
        assert result.mode == "full"
        assert result.total_input == 3
        assert result.filtered_count == 0

    def test_incremental_mode_filters_then_processes(self):
        """INCREMENTAL mode filters first, then processes."""
        config = IncrementalConfig(
            last_update_time="2025-06-01T00:00:00",
            change_field="updatedAt",
        )
        pipeline = ETLPipeline(
            PipelineConfig(name="inc-flow"),
            mode=ETLMode.INCREMENTAL,
            incremental_config=config,
        )

        records = [
            _make_envelope(data={"id": "1", "updatedAt": "2025-05-01T00:00:00"}, record_id="old"),
            _make_envelope(data={"id": "2", "updatedAt": "2025-07-01T00:00:00"}, record_id="new1"),
            _make_envelope(data={"id": "3", "updatedAt": "2025-08-01T00:00:00"}, record_id="new2"),
        ]

        result = pipeline.run(records)
        assert result.records_processed == 2
        assert result.mode == "incremental"
        assert result.total_input == 3
        assert result.filtered_count == 1

    def test_orphan_cleanup_cypher_generation(self):
        """build_orphan_cleanup_cypher returns valid Cypher."""
        pipeline = ETLPipeline(PipelineConfig(name="orphan"))
        cypher = pipeline.build_orphan_cleanup_cypher("Vessel")
        assert cypher == "MATCH (n:Vessel) WHERE NOT (n)--() DELETE n"

    def test_orphan_cleanup_cypher_different_label(self):
        """build_orphan_cleanup_cypher works with different labels."""
        pipeline = ETLPipeline(PipelineConfig(name="orphan2"))
        cypher = pipeline.build_orphan_cleanup_cypher("Port")
        assert "n:Port" in cypher
        assert "DELETE n" in cypher

    def test_pipeline_result_includes_mode(self):
        """PipelineResult records the execution mode."""
        result = PipelineResult(mode="incremental", total_input=10, filtered_count=3)
        assert result.mode == "incremental"
        assert result.total_input == 10
        assert result.filtered_count == 3

    def test_etl_mode_enum_values(self):
        """ETLMode has FULL and INCREMENTAL."""
        assert ETLMode.FULL == "full"
        assert ETLMode.FULL.value == "full"
        assert ETLMode.INCREMENTAL == "incremental"
        assert ETLMode.INCREMENTAL.value == "incremental"
        assert isinstance(ETLMode.FULL, str)

    def test_incremental_config_defaults(self):
        """IncrementalConfig has sensible defaults."""
        config = IncrementalConfig()
        assert config.last_update_time is None
        assert config.change_field == "updatedAt"
        assert config.cleanup_orphans is False

    def test_incremental_with_loader(self):
        """Incremental mode works end-to-end with a loader."""
        config = IncrementalConfig(
            last_update_time="2025-06-01T00:00:00",
            change_field="updatedAt",
        )
        mock_session = MagicMock()
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")

        pipeline = (
            ETLPipeline(
                PipelineConfig(name="inc-loader"),
                mode=ETLMode.INCREMENTAL,
                incremental_config=config,
            )
            .set_loader(loader)
        )

        records = [
            _make_envelope(
                data={"vesselId": "V1", "updatedAt": "2025-04-01T00:00:00"},
                record_id="old-v",
            ),
            _make_envelope(
                data={"vesselId": "V2", "updatedAt": "2025-07-15T00:00:00"},
                record_id="new-v",
            ),
        ]

        result = pipeline.run(records, session=mock_session)
        assert result.records_processed == 1
        assert result.total_input == 2
        assert result.filtered_count == 1
        # Only one record should be passed to the loader
        mock_session.run.assert_called_once()

    def test_backward_compatibility_default_mode(self):
        """ETLPipeline defaults to FULL mode for backward compatibility."""
        pipeline = ETLPipeline(PipelineConfig(name="compat"))
        assert pipeline.mode == ETLMode.FULL
