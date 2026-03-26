"""Tests for Phase 3: ETL → ELT transition.

Tests raw store, phase tracking, deferred transforms, and reprocessing.
"""
from __future__ import annotations

import json
import pytest

from kg.etl.raw_store import RawStore, NullRawStore, LocalFileStore, make_raw_key
from kg.etl.models import (
    PipelinePhase,
    PipelineConfig,
    PipelineResult,
    PipelineStatus,
    RecordEnvelope,
)


# =========================================================================
# RawStore Protocol
# =========================================================================


@pytest.mark.unit
class TestRawStoreProtocol:
    """Test RawStore Protocol conformance."""

    def test_null_store_is_protocol(self) -> None:
        """NullRawStore satisfies the RawStore Protocol."""
        assert isinstance(NullRawStore(), RawStore)

    def test_local_store_is_protocol(self, tmp_path) -> None:
        """LocalFileStore satisfies the RawStore Protocol."""
        assert isinstance(LocalFileStore(base_dir=str(tmp_path)), RawStore)


# =========================================================================
# NullRawStore
# =========================================================================


@pytest.mark.unit
class TestNullRawStore:
    """Test NullRawStore no-op behavior."""

    def test_put_returns_key(self) -> None:
        store = NullRawStore()
        assert store.put("k", b"data") == "k"

    def test_get_returns_none(self) -> None:
        assert NullRawStore().get("k") is None

    def test_exists_false(self) -> None:
        assert NullRawStore().exists("k") is False

    def test_list_keys_empty(self) -> None:
        assert NullRawStore().list_keys() == []

    def test_list_keys_with_prefix_empty(self) -> None:
        assert NullRawStore().list_keys(prefix="ships") == []

    def test_delete_false(self) -> None:
        assert NullRawStore().delete("k") is False

    def test_get_metadata_none(self) -> None:
        assert NullRawStore().get_metadata("k") is None

    def test_put_with_metadata_returns_key(self) -> None:
        store = NullRawStore()
        assert store.put("k", b"data", metadata={"source": "test"}) == "k"


# =========================================================================
# LocalFileStore
# =========================================================================


@pytest.mark.unit
class TestLocalFileStore:
    """Test LocalFileStore filesystem operations."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path) -> None:
        self.store = LocalFileStore(base_dir=str(tmp_path / "raw"))

    def test_put_and_get(self) -> None:
        data = b'{"id": "test", "name": "vessel"}'
        key = "ships/2026-03-26/test.json"
        self.store.put(key, data)
        assert self.store.get(key) == data

    def test_put_with_metadata_stores_meta(self) -> None:
        self.store.put("k.json", b"data", metadata={"source": "test"})
        meta = self.store.get_metadata("k.json")
        assert meta is not None
        assert meta["source"] == "test"

    def test_put_without_metadata_no_meta_file(self) -> None:
        self.store.put("noMeta.json", b"data")
        assert self.store.get_metadata("noMeta.json") is None

    def test_exists_false_before_put(self) -> None:
        assert self.store.exists("nope") is False

    def test_exists_true_after_put(self) -> None:
        self.store.put("yes.json", b"data")
        assert self.store.exists("yes.json") is True

    def test_list_keys_with_prefix(self) -> None:
        self.store.put("src/2026-01-01/a.json", b"a")
        self.store.put("src/2026-01-01/b.json", b"b")
        self.store.put("other/2026-01-01/c.json", b"c")
        keys = self.store.list_keys(prefix="src")
        assert len(keys) == 2
        assert all("src/" in k for k in keys)

    def test_list_keys_no_prefix_returns_all(self) -> None:
        self.store.put("a/2026-01-01/r1.json", b"r1")
        self.store.put("b/2026-01-01/r2.json", b"r2")
        keys = self.store.list_keys()
        assert len(keys) == 2

    def test_list_keys_excludes_meta_files(self) -> None:
        self.store.put("src/2026-01-01/a.json", b"a", metadata={"x": 1})
        keys = self.store.list_keys(prefix="src")
        # .meta.json files must not appear
        assert all(".meta.json" not in k for k in keys)

    def test_list_keys_sorted(self) -> None:
        self.store.put("src/2026-01-01/b.json", b"b")
        self.store.put("src/2026-01-01/a.json", b"a")
        keys = self.store.list_keys(prefix="src")
        assert keys == sorted(keys)

    def test_delete_removes_data(self) -> None:
        self.store.put("del.json", b"data")
        assert self.store.delete("del.json") is True
        assert self.store.exists("del.json") is False

    def test_delete_removes_metadata(self) -> None:
        self.store.put("del.json", b"data", metadata={"x": 1})
        self.store.delete("del.json")
        assert self.store.get_metadata("del.json") is None

    def test_delete_nonexistent_returns_false(self) -> None:
        assert self.store.delete("nope") is False

    def test_get_nonexistent_returns_none(self) -> None:
        assert self.store.get("nope") is None

    def test_get_metadata_nonexistent_returns_none(self) -> None:
        assert self.store.get_metadata("nope") is None

    def test_put_creates_parent_dirs(self, tmp_path) -> None:
        store = LocalFileStore(base_dir=str(tmp_path / "deeply/nested/raw"))
        store.put("src/2026-01-01/r1.json", b"data")
        assert store.exists("src/2026-01-01/r1.json")


# =========================================================================
# make_raw_key
# =========================================================================


@pytest.mark.unit
class TestMakeRawKey:
    """Test raw key generation."""

    def test_key_format(self) -> None:
        key = make_raw_key("ships", "vessel-123")
        parts = key.split("/")
        assert len(parts) == 3
        assert parts[0] == "ships"
        # Middle part should be YYYY-MM-DD (len=10)
        assert len(parts[1]) == 10
        assert parts[1][4] == "-" and parts[1][7] == "-"
        assert parts[2] == "vessel-123.json"

    def test_default_extension_is_json(self) -> None:
        key = make_raw_key("weather", "report-1")
        assert key.endswith(".json")

    def test_custom_extension(self) -> None:
        key = make_raw_key("weather", "report-1", ext=".grib2")
        assert key.endswith(".grib2")
        assert not key.endswith(".json")

    def test_source_in_key_prefix(self) -> None:
        key = make_raw_key("vessels", "v-001")
        assert key.startswith("vessels/")

    def test_record_id_in_key(self) -> None:
        key = make_raw_key("ports", "busan-1")
        assert "busan-1" in key


# =========================================================================
# PipelinePhase
# =========================================================================


@pytest.mark.unit
class TestPipelinePhase:
    """Test PipelinePhase enum."""

    def test_all_phases_present(self) -> None:
        phases = [p.value for p in PipelinePhase]
        assert "extract" in phases
        assert "load_raw" in phases
        assert "validate" in phases
        assert "transform" in phases
        assert "load_kg" in phases

    def test_phase_count(self) -> None:
        assert len(list(PipelinePhase)) == 5

    def test_phases_are_strings(self) -> None:
        for phase in PipelinePhase:
            assert isinstance(phase, str)

    def test_phase_values(self) -> None:
        assert PipelinePhase.EXTRACT.value == "extract"
        assert PipelinePhase.LOAD_RAW.value == "load_raw"
        assert PipelinePhase.VALIDATE.value == "validate"
        assert PipelinePhase.TRANSFORM.value == "transform"
        assert PipelinePhase.LOAD_KG.value == "load_kg"


# =========================================================================
# PipelineConfig ELT fields
# =========================================================================


@pytest.mark.unit
class TestPipelineConfigELT:
    """Test updated PipelineConfig with ELT fields."""

    def test_default_is_eager_mode(self) -> None:
        cfg = PipelineConfig(name="test")
        assert cfg.transform_mode == "eager"

    def test_default_raw_store_disabled(self) -> None:
        cfg = PipelineConfig(name="test")
        assert cfg.raw_store_enabled is False

    def test_elt_config_deferred_mode(self) -> None:
        cfg = PipelineConfig(name="test", transform_mode="deferred", raw_store_enabled=True)
        assert cfg.transform_mode == "deferred"
        assert cfg.raw_store_enabled is True

    def test_frozen_transform_mode(self) -> None:
        cfg = PipelineConfig(name="test")
        with pytest.raises(AttributeError):
            cfg.transform_mode = "deferred"  # type: ignore[misc]

    def test_frozen_raw_store_enabled(self) -> None:
        cfg = PipelineConfig(name="test")
        with pytest.raises(AttributeError):
            cfg.raw_store_enabled = True  # type: ignore[misc]


# =========================================================================
# PipelineResult phases_completed
# =========================================================================


@pytest.mark.unit
class TestPipelineResultPhases:
    """Test PipelineResult with phases_completed."""

    def test_default_phases_completed_is_empty_tuple(self) -> None:
        result = PipelineResult()
        assert result.phases_completed == ()
        assert isinstance(result.phases_completed, tuple)

    def test_phases_completed_can_be_set(self) -> None:
        result = PipelineResult(
            phases_completed=("extract", "load_raw", "validate", "transform", "load_kg"),
        )
        assert len(result.phases_completed) == 5
        assert result.phases_completed[0] == "extract"
        assert result.phases_completed[-1] == "load_kg"

    def test_phases_completed_is_tuple_not_list(self) -> None:
        result = PipelineResult(phases_completed=("extract", "load_raw"))
        assert isinstance(result.phases_completed, tuple)

    def test_result_is_mutable(self) -> None:
        result = PipelineResult()
        result.phases_completed = ("extract",)
        assert result.phases_completed == ("extract",)


# =========================================================================
# ETLRunRecord phase fields
# =========================================================================


@pytest.mark.unit
class TestETLRunRecordPhases:
    """Test updated ETLRunRecord with phase tracking."""

    def test_default_current_phase_empty_string(self) -> None:
        from kg.etl.state import ETLRunRecord
        rec = ETLRunRecord(run_id="r1", pipeline_name="test", status="running", started_at=1.0)
        assert rec.current_phase == ""

    def test_default_phases_completed_empty_tuple(self) -> None:
        from kg.etl.state import ETLRunRecord
        rec = ETLRunRecord(run_id="r1", pipeline_name="test", status="running", started_at=1.0)
        assert rec.phases_completed == ()

    def test_with_phase_data(self) -> None:
        from kg.etl.state import ETLRunRecord
        rec = ETLRunRecord(
            run_id="r1",
            pipeline_name="test",
            status="completed",
            started_at=1.0,
            completed_at=2.0,
            current_phase="load_kg",
            phases_completed=("extract", "validate", "transform", "load_kg"),
        )
        assert rec.current_phase == "load_kg"
        assert len(rec.phases_completed) == 4
        assert "extract" in rec.phases_completed

    def test_frozen_dataclass(self) -> None:
        from kg.etl.state import ETLRunRecord
        rec = ETLRunRecord(run_id="r1", pipeline_name="test", status="running", started_at=1.0)
        with pytest.raises((AttributeError, TypeError)):
            rec.current_phase = "load_kg"  # type: ignore[misc]


# =========================================================================
# ETLStateStore phase tracking
# =========================================================================


@pytest.mark.unit
class TestETLStateStorePhases:
    """Test ETLStateStore with phase tracking columns."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path) -> None:
        from kg.etl.state import ETLStateStore
        self.store = ETLStateStore(db_path=str(tmp_path / "test.db"))

    def test_save_and_get_with_phases(self) -> None:
        from kg.etl.state import ETLRunRecord
        rec = ETLRunRecord(
            run_id="r1",
            pipeline_name="test",
            status="completed",
            started_at=1.0,
            completed_at=2.0,
            current_phase="load_kg",
            phases_completed=("extract", "validate"),
        )
        self.store.save_run(rec)
        loaded = self.store.get_run("r1")
        assert loaded is not None
        assert loaded.current_phase == "load_kg"
        assert loaded.phases_completed == ("extract", "validate")

    def test_save_default_phase_fields(self) -> None:
        from kg.etl.state import ETLRunRecord
        rec = ETLRunRecord(run_id="r2", pipeline_name="test", status="running", started_at=1.0)
        self.store.save_run(rec)
        loaded = self.store.get_run("r2")
        assert loaded is not None
        assert loaded.current_phase == ""
        assert loaded.phases_completed == ()

    def test_update_status_with_phase_kwargs(self) -> None:
        from kg.etl.state import ETLRunRecord
        rec = ETLRunRecord(run_id="r3", pipeline_name="test", status="running", started_at=1.0)
        self.store.save_run(rec)
        self.store.update_status(
            "r3",
            "completed",
            current_phase="load_kg",
            phases_completed=("extract", "load_raw", "validate"),
        )
        loaded = self.store.get_run("r3")
        assert loaded is not None
        assert loaded.status == "completed"
        assert loaded.current_phase == "load_kg"
        assert len(loaded.phases_completed) == 3
        assert "extract" in loaded.phases_completed

    def test_update_status_without_phase_kwargs(self) -> None:
        from kg.etl.state import ETLRunRecord
        rec = ETLRunRecord(
            run_id="r4",
            pipeline_name="test",
            status="running",
            started_at=1.0,
            current_phase="validate",
            phases_completed=("extract",),
        )
        self.store.save_run(rec)
        # Update status only; phase fields should remain unchanged
        self.store.update_status("r4", "completed")
        loaded = self.store.get_run("r4")
        assert loaded is not None
        assert loaded.status == "completed"
        # Phases unchanged since we didn't pass them
        assert loaded.current_phase == "validate"
        assert loaded.phases_completed == ("extract",)

    def test_phases_completed_roundtrip_all_phases(self) -> None:
        from kg.etl.state import ETLRunRecord
        all_phases = ("extract", "load_raw", "validate", "transform", "load_kg")
        rec = ETLRunRecord(
            run_id="r5",
            pipeline_name="test",
            status="completed",
            started_at=1.0,
            phases_completed=all_phases,
        )
        self.store.save_run(rec)
        loaded = self.store.get_run("r5")
        assert loaded is not None
        assert loaded.phases_completed == all_phases


# =========================================================================
# ETLPipeline phase tracking
# =========================================================================


@pytest.mark.unit
class TestELTPipelinePhases:
    """Test ETLPipeline with ELT phase tracking."""

    def test_classic_etl_includes_extract_phase(self) -> None:
        """Classic ETL mode should track extract phase."""
        from kg.etl.pipeline import ETLPipeline
        pipeline = ETLPipeline(config=PipelineConfig(name="classic"))
        result = pipeline.run([])
        assert "extract" in result.phases_completed

    def test_classic_etl_all_phases_on_empty_records(self) -> None:
        """Classic ETL with empty records completes extract+validate+transform+load_kg."""
        from kg.etl.pipeline import ETLPipeline
        pipeline = ETLPipeline(config=PipelineConfig(name="classic-empty"))
        result = pipeline.run([])
        # Empty records still complete all classic ETL phases
        assert "extract" in result.phases_completed
        assert "validate" in result.phases_completed
        assert "transform" in result.phases_completed
        assert "load_kg" in result.phases_completed

    def test_classic_etl_no_load_raw_phase(self) -> None:
        """Classic ETL mode should NOT include load_raw phase."""
        from kg.etl.pipeline import ETLPipeline
        pipeline = ETLPipeline(config=PipelineConfig(name="classic-no-raw"))
        result = pipeline.run([])
        assert "load_raw" not in result.phases_completed

    def test_deferred_mode_stops_after_raw_load(self, tmp_path) -> None:
        """Deferred ELT mode: only extract + load_raw, no transform or load_kg."""
        from kg.etl.pipeline import ETLPipeline
        store = LocalFileStore(base_dir=str(tmp_path / "raw"))
        config = PipelineConfig(
            name="deferred-pipe",
            transform_mode="deferred",
            raw_store_enabled=True,
        )
        pipeline = ETLPipeline(config=config, raw_store=store)

        records = [
            RecordEnvelope(
                record_id="r1",
                data={"id": "r1", "name": "Test Vessel"},
                source="test",
            ),
        ]
        result = pipeline.run(records)

        assert "extract" in result.phases_completed
        assert "load_raw" in result.phases_completed
        assert "transform" not in result.phases_completed
        assert "load_kg" not in result.phases_completed
        assert result.records_processed == 1

    def test_deferred_mode_stores_raw_data(self, tmp_path) -> None:
        """Deferred mode actually persists raw records to the raw store."""
        from kg.etl.pipeline import ETLPipeline
        store = LocalFileStore(base_dir=str(tmp_path / "raw"))
        config = PipelineConfig(
            name="deferred-store",
            transform_mode="deferred",
            raw_store_enabled=True,
        )
        pipeline = ETLPipeline(config=config, raw_store=store)

        records = [
            RecordEnvelope(record_id="r1", data={"id": "r1"}, source="test"),
            RecordEnvelope(record_id="r2", data={"id": "r2"}, source="test"),
        ]
        pipeline.run(records)

        # Keys are stored under config.name prefix
        keys = store.list_keys(prefix="deferred-store")
        assert len(keys) == 2

    def test_eager_with_raw_store_runs_all_phases(self, tmp_path) -> None:
        """Eager mode with raw_store_enabled runs all 5 phases."""
        from kg.etl.pipeline import ETLPipeline
        store = LocalFileStore(base_dir=str(tmp_path / "raw"))
        config = PipelineConfig(
            name="eager-with-raw",
            transform_mode="eager",
            raw_store_enabled=True,
        )
        pipeline = ETLPipeline(config=config, raw_store=store)

        records = [
            RecordEnvelope(record_id="r1", data={"id": "r1"}, source="test"),
        ]
        result = pipeline.run(records)

        # All phases completed
        assert "extract" in result.phases_completed
        assert "load_raw" in result.phases_completed
        assert "validate" in result.phases_completed
        assert "transform" in result.phases_completed
        assert "load_kg" in result.phases_completed

    def test_reprocess_returns_result_with_no_raw_keys(self, tmp_path) -> None:
        """Reprocess with no matching keys returns empty result with load_raw phase."""
        from kg.etl.pipeline import ETLPipeline
        store = LocalFileStore(base_dir=str(tmp_path / "raw"))
        config = PipelineConfig(name="reprocess-empty", raw_store_enabled=True)
        pipeline = ETLPipeline(config=config, raw_store=store)

        result = pipeline.reprocess(source="nonexistent-source")
        assert result.records_processed == 0
        assert PipelinePhase.LOAD_RAW.value in result.phases_completed

    def test_reprocess_from_stored_raw_data(self, tmp_path) -> None:
        """Reprocess reads from raw store and runs validate+transform+load."""
        from kg.etl.pipeline import ETLPipeline
        store = LocalFileStore(base_dir=str(tmp_path / "raw"))

        # Pre-store some raw data
        raw_data = json.dumps({"id": "v1", "name": "Test Vessel"}).encode()
        store.put("test-pipe/2026-03-26/v1.json", raw_data)
        raw_data2 = json.dumps({"id": "v2", "name": "Another Vessel"}).encode()
        store.put("test-pipe/2026-03-26/v2.json", raw_data2)

        config = PipelineConfig(name="test-pipe", raw_store_enabled=True)
        pipeline = ETLPipeline(config=config, raw_store=store)

        result = pipeline.reprocess(source="test-pipe")
        # 2 raw records should be processed (no loader = counts as processed)
        assert result.records_processed == 2
        assert result.records_failed == 0

    def test_reprocess_with_prefix_filter(self, tmp_path) -> None:
        """Reprocess with date prefix only processes matching keys."""
        from kg.etl.pipeline import ETLPipeline
        store = LocalFileStore(base_dir=str(tmp_path / "raw"))

        store.put("pipe/2026-03-25/old.json", json.dumps({"id": "old"}).encode())
        store.put("pipe/2026-03-26/new.json", json.dumps({"id": "new"}).encode())

        config = PipelineConfig(name="pipe", raw_store_enabled=True)
        pipeline = ETLPipeline(config=config, raw_store=store)

        result = pipeline.reprocess(source="pipe", prefix="2026-03-26")
        assert result.records_processed == 1

    def test_reprocess_restores_config_after_run(self, tmp_path) -> None:
        """Reprocess restores original pipeline config after execution."""
        from kg.etl.pipeline import ETLPipeline
        store = LocalFileStore(base_dir=str(tmp_path / "raw"))
        store.put("cfg-pipe/2026-03-26/r1.json", json.dumps({"id": "r1"}).encode())

        config = PipelineConfig(
            name="cfg-pipe",
            transform_mode="deferred",
            raw_store_enabled=True,
        )
        pipeline = ETLPipeline(config=config, raw_store=store)
        pipeline.reprocess(source="cfg-pipe")

        # Config should be restored to original deferred mode
        assert pipeline.config.transform_mode == "deferred"
        assert pipeline.config.raw_store_enabled is True

    def test_phases_completed_is_tuple(self) -> None:
        """phases_completed on PipelineResult is always a tuple."""
        from kg.etl.pipeline import ETLPipeline
        pipeline = ETLPipeline(config=PipelineConfig(name="tuple-check"))
        result = pipeline.run([])
        assert isinstance(result.phases_completed, tuple)

    def test_pipeline_status_completed_after_deferred(self, tmp_path) -> None:
        """Pipeline status is COMPLETED even in deferred mode."""
        from kg.etl.pipeline import ETLPipeline
        store = LocalFileStore(base_dir=str(tmp_path / "raw"))
        config = PipelineConfig(
            name="status-deferred",
            transform_mode="deferred",
            raw_store_enabled=True,
        )
        pipeline = ETLPipeline(config=config, raw_store=store)
        pipeline.run([])
        assert pipeline.status == PipelineStatus.COMPLETED
