"""Main ETL/ELT pipeline orchestrator.

Provides:
- ETLPipeline: configurable pipeline that validates, transforms, and loads
  records with Dead Letter Queue support for failures.

Supports both classic ETL mode (backward compat) and ELT mode with raw
store persistence and deferred transforms.
"""

from __future__ import annotations

import json as _json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from kg.etl.dlq import DLQManager
from kg.etl.loader import Neo4jBatchLoader
from kg.etl.models import (
    ETLMode,
    IncrementalConfig,
    PipelineConfig,
    PipelinePhase,
    PipelineResult,
    PipelineStatus,
    RecordEnvelope,
)
from kg.etl.transforms import TransformStep
from kg.etl.validator import RecordValidator
from kg.lineage import LineageEventType, LineageRecorder

logger = logging.getLogger(__name__)


class ETLPipeline:
    """Configurable ETL/ELT pipeline that validates, transforms, and loads records.

    Pipeline flow (classic ETL mode, default):
        1. **Extract** -- records provided by the caller
        2. **Validate** -- run validation rules (if enabled and validator set)
        3. **Transform** -- apply transform steps sequentially
        4. **Load KG** -- batch-write to Neo4j via the loader

    ELT mode (``raw_store_enabled=True``):
        1. **Extract** -- records provided by the caller
        2. **Load Raw** -- persist raw records to the raw store
        3. **Validate / Transform / Load KG** -- skipped when
           ``transform_mode="deferred"``; executed eagerly otherwise.

    Records that fail validation or transformation are routed to the
    Dead Letter Queue (if enabled in config).

    Args:
        config: Immutable pipeline configuration.
        mode: Execution mode (FULL or INCREMENTAL).
        incremental_config: Optional incremental configuration.
        raw_store: Optional RawStore Protocol instance for ELT raw persistence.
            If ``None``, a :class:`~kg.etl.raw_store.NullRawStore` is used
            (no-op, classic ETL behaviour).

    Example::

        pipeline = (
            ETLPipeline(PipelineConfig(name="vessels"))
            .add_transform(TextNormalizer(["name"]))
            .set_validator(RecordValidator([RequiredFieldsRule(["vesselId"])]))
            .set_loader(Neo4jBatchLoader("Vessel", "vesselId"))
        )
        result = pipeline.run(records, session=mock_session)

    ELT example::

        from kg.etl.raw_store import LocalFileStore

        pipeline = (
            ETLPipeline(
                PipelineConfig(
                    name="vessels",
                    raw_store_enabled=True,
                    transform_mode="deferred",
                ),
                raw_store=LocalFileStore(".imsp/raw"),
            )
            .add_transform(TextNormalizer(["name"]))
            .set_loader(Neo4jBatchLoader("Vessel", "vesselId"))
        )
        # Phase 1: extract + raw store only
        result = pipeline.run(records)
        # Phase 2: reprocess from raw store when transforms/ontology change
        result = pipeline.reprocess("vessels")
    """

    def __init__(
        self,
        config: PipelineConfig,
        mode: ETLMode = ETLMode.FULL,
        incremental_config: IncrementalConfig | None = None,
        raw_store: Any | None = None,
    ) -> None:
        self._config = config
        self._mode = mode
        self._incremental_config = incremental_config
        self._transforms: list[TransformStep] = []
        self._validator: RecordValidator | None = None
        self._loader: Neo4jBatchLoader | None = None
        self._lineage_recorder: LineageRecorder | None = None
        self._dlq = DLQManager()
        self._status = PipelineStatus.PENDING

        # ELT raw store setup
        if raw_store is None:
            from kg.etl.raw_store import NullRawStore
            self._raw_store: Any = NullRawStore()
        else:
            self._raw_store = raw_store

    @property
    def config(self) -> PipelineConfig:
        """The pipeline configuration."""
        return self._config

    @property
    def status(self) -> PipelineStatus:
        """Current pipeline status."""
        return self._status

    @property
    def dlq(self) -> DLQManager:
        """The Dead Letter Queue manager."""
        return self._dlq

    @property
    def mode(self) -> ETLMode:
        """The ETL execution mode (FULL or INCREMENTAL)."""
        return self._mode

    def detect_changes(self, records: list[RecordEnvelope]) -> list[RecordEnvelope]:
        """Filter records to only those changed since last update.

        Uses incremental_config.change_field and last_update_time
        to filter. Records without the change field are included
        (conservative: include if uncertain).

        Args:
            records: All candidate record envelopes.

        Returns:
            Filtered list containing only changed or uncertain records.
        """
        if not self._incremental_config or not self._incremental_config.last_update_time:
            return records  # No filter if no config

        cutoff = self._incremental_config.last_update_time
        change_field = self._incremental_config.change_field
        changed: list[RecordEnvelope] = []
        for record in records:
            field_val = record.data.get(change_field)
            if field_val is None or str(field_val) >= cutoff:
                changed.append(record)
        return changed

    def build_orphan_cleanup_cypher(self, label: str) -> str:
        """Generate Cypher to remove orphan nodes of given label.

        An orphan node is one that has no relationships at all.

        Args:
            label: The Neo4j node label to check for orphans.

        Returns:
            Cypher query string: MATCH (n:Label) WHERE NOT (n)--() DELETE n

        Raises:
            ValueError: If label contains invalid characters.
        """
        if not label.isidentifier():
            raise ValueError(f"Invalid Neo4j label: {label!r}")
        return f"MATCH (n:{label}) WHERE NOT (n)--() DELETE n"

    def add_transform(self, step: TransformStep) -> ETLPipeline:
        """Append a transform step to the pipeline.

        Args:
            step: The transform to add.

        Returns:
            Self for fluent chaining.
        """
        self._transforms.append(step)
        return self

    def set_validator(self, validator: RecordValidator) -> ETLPipeline:
        """Set the record validator.

        Args:
            validator: The validator to use for pre-transform checks.

        Returns:
            Self for fluent chaining.
        """
        self._validator = validator
        return self

    def set_loader(self, loader: Neo4jBatchLoader) -> ETLPipeline:
        """Set the Neo4j batch loader.

        Args:
            loader: The loader to use for writing records.

        Returns:
            Self for fluent chaining.
        """
        self._loader = loader
        return self

    def set_lineage_recorder(self, recorder: LineageRecorder) -> ETLPipeline:
        """Set a lineage recorder for provenance tracking.

        When set, the pipeline will record INGESTION and TRANSFORMATION
        lineage events for each successfully processed record.

        Args:
            recorder: The lineage recorder to use.

        Returns:
            Self for fluent chaining.
        """
        self._lineage_recorder = recorder
        return self

    def _record_lineage(
        self,
        envelope: RecordEnvelope,
        had_transforms: bool,
    ) -> None:
        """Record lineage events for a successfully processed record.

        Args:
            envelope: The processed record envelope.
            had_transforms: Whether transform steps were applied.
        """
        if self._lineage_recorder is None:
            return

        entity_label = self._loader._label if self._loader else "Unknown"
        agent = f"ETL:{self._config.name}"

        try:
            self._lineage_recorder.record_event(
                entity_type=entity_label,
                entity_id=envelope.record_id,
                event_type=LineageEventType.INGESTION,
                agent=agent,
                activity=f"Loaded via pipeline '{self._config.name}'",
            )
            if had_transforms:
                self._lineage_recorder.record_event(
                    entity_type=entity_label,
                    entity_id=envelope.record_id,
                    event_type=LineageEventType.TRANSFORMATION,
                    agent=agent,
                    activity=f"Transformed via pipeline '{self._config.name}'",
                )
        except Exception:
            logger.warning(
                "Failed to record lineage for record %s",
                envelope.record_id,
                exc_info=True,
            )

    def run(
        self,
        records: list[RecordEnvelope],
        session: Any = None,
    ) -> PipelineResult:
        """Execute the ELT pipeline over the given records with phase tracking.

        When ``raw_store_enabled=False`` (default) the pipeline behaves
        identically to the classic ETL mode, with phase tracking added as
        metadata on the returned :class:`~kg.etl.models.PipelineResult`.

        When ``raw_store_enabled=True`` raw records are persisted to the
        configured raw store (Phase: ``load_raw``) before any transformation.
        If ``transform_mode="deferred"`` the pipeline stops after raw
        storage and returns immediately; the caller can later invoke
        :meth:`reprocess` to complete the transform + load phases.

        Args:
            records: List of record envelopes to process.
            session: Neo4j session (or mock) passed to the loader.
                Required if a loader is set and ``transform_mode`` is
                not ``"deferred"``.

        Returns:
            A PipelineResult with processing metrics and ``phases_completed``.
        """
        from kg.etl.raw_store import make_raw_key

        result = PipelineResult(
            started_at=datetime.now(timezone.utc),
            mode=self._mode.value,
            total_input=len(records),
        )
        self._status = PipelineStatus.RUNNING
        start_time = time.monotonic()
        phases_completed: list[str] = []

        logger.info("Pipeline '%s' started with %d records", self._config.name, len(records))

        # ------------------------------------------------------------------
        # Phase 1: EXTRACT (records already provided by the caller)
        # ------------------------------------------------------------------
        phases_completed.append(PipelinePhase.EXTRACT.value)

        # ------------------------------------------------------------------
        # Phase 2: LOAD_RAW (persist raw data before any transformation)
        # ------------------------------------------------------------------
        if self._config.raw_store_enabled:
            for env in records:
                try:
                    key = make_raw_key(
                        source=self._config.name,
                        record_id=env.data.get("id", env.record_id),
                    )
                    raw_bytes = _json.dumps(
                        env.data, ensure_ascii=False, default=str
                    ).encode("utf-8")
                    self._raw_store.put(
                        key=key,
                        data=raw_bytes,
                        metadata={"label": self._config.name, "record_id": env.record_id},
                    )
                except Exception as exc:
                    logger.warning(
                        "Raw store write failed for %s: %s", env.record_id, exc
                    )
            phases_completed.append(PipelinePhase.LOAD_RAW.value)

        # Deferred mode: stop after raw load, skip transform + KG load
        if self._config.transform_mode == "deferred":
            elapsed = time.monotonic() - start_time
            result.duration_seconds = round(elapsed, 3)
            result.completed_at = datetime.now(timezone.utc)
            result.records_processed = len(records)
            result.phases_completed = tuple(phases_completed)
            self._status = PipelineStatus.COMPLETED
            logger.info(
                "Pipeline '%s' deferred after raw load (%d records stored)",
                self._config.name,
                len(records),
            )
            return result

        # ------------------------------------------------------------------
        # Phase 3: INCREMENTAL filtering (existing logic, unchanged)
        # ------------------------------------------------------------------
        if self._mode == ETLMode.INCREMENTAL:
            records = self.detect_changes(records)
            result.filtered_count = result.total_input - len(records)
            if result.filtered_count > 0:
                cutoff = (
                    self._incremental_config.last_update_time
                    if self._incremental_config
                    else "N/A"
                )
                logger.info(
                    "Incremental mode: %d of %d records changed since %s",
                    len(records),
                    result.total_input,
                    cutoff,
                )

        loadable: list[dict[str, Any]] = []

        for envelope in records:
            # --- Validation ---
            if self._config.validate and self._validator is not None:
                errors = self._validator.validate(envelope)
                if errors:
                    logger.debug(
                        "Record %s failed validation: %s",
                        envelope.record_id,
                        errors,
                    )
                    result.records_skipped += 1
                    result.errors.extend(errors)
                    if self._config.dlq_enabled:
                        self._dlq.add(envelope, errors)
                    continue

            # --- Transforms ---
            had_transforms = bool(self._transforms)
            try:
                for step in self._transforms:
                    envelope = step.transform(envelope)
            except Exception as exc:
                error_msg = f"Transform error on record {envelope.record_id}: {exc}"
                logger.warning(error_msg)
                result.records_failed += 1
                result.errors.append(error_msg)
                if self._config.dlq_enabled:
                    self._dlq.add(envelope, [error_msg])
                continue

            # --- Lineage ---
            self._record_lineage(envelope, had_transforms)

            loadable.append(envelope.data)

        # Phase tracking: validate + transform completed
        phases_completed.append(PipelinePhase.VALIDATE.value)
        phases_completed.append(PipelinePhase.TRANSFORM.value)

        # --- Load ---
        if self._loader is not None and loadable:
            try:
                loaded = self._loader.load(loadable, session)
                result.records_processed = loaded
            except Exception as exc:
                error_msg = f"Loader error: {exc}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.records_failed += len(loadable)
                self._status = PipelineStatus.FAILED
                result.duration_seconds = time.monotonic() - start_time
                result.completed_at = datetime.now(timezone.utc)
                result.phases_completed = tuple(phases_completed)
                return result
        elif loadable:
            # No loader set -- count records as processed
            result.records_processed = len(loadable)

        # Phase tracking: KG load completed
        phases_completed.append(PipelinePhase.LOAD_KG.value)

        # Lineage 영속화
        if self._lineage_recorder and session:
            try:
                self._lineage_recorder.flush(session)
            except Exception as e:
                logger.warning("Lineage flush warning: %s", e)

        elapsed = time.monotonic() - start_time
        result.duration_seconds = elapsed
        result.completed_at = datetime.now(timezone.utc)
        result.phases_completed = tuple(phases_completed)
        self._status = PipelineStatus.COMPLETED

        logger.info(
            "Pipeline '%s' completed: processed=%d, failed=%d, skipped=%d, "
            "duration=%.3fs",
            self._config.name,
            result.records_processed,
            result.records_failed,
            result.records_skipped,
            elapsed,
        )

        return result

    def reprocess(
        self,
        source: str,
        *,
        session: Any = None,
        prefix: str = "",
    ) -> PipelineResult:
        """Re-process previously stored raw data through validate + transform + load.

        Reads records from the raw store and applies validation,
        transformation, and KG loading. Use this when the ontology or
        transform steps have changed and previously extracted raw records
        need to be re-ingested.

        Args:
            source: Source identifier matching the raw key prefix (typically
                the pipeline name used during the initial ``run()`` call).
            session: Optional Neo4j session passed to the loader.
            prefix: Optional date-partition prefix filter
                (e.g. ``"2026-03-26"``). When provided, only keys under
                ``{source}/{prefix}`` are re-processed.

        Returns:
            A PipelineResult from running the validate + transform + load
            phases on the retrieved raw records.
        """
        search_prefix = f"{source}/{prefix}" if prefix else source
        keys = self._raw_store.list_keys(prefix=search_prefix)

        if not keys:
            return PipelineResult(
                records_processed=0,
                records_failed=0,
                records_skipped=0,
                duration_seconds=0.0,
                phases_completed=(PipelinePhase.LOAD_RAW.value,),
            )

        envelopes: list[RecordEnvelope] = []
        for key in keys:
            raw = self._raw_store.get(key)
            if raw is None:
                continue
            try:
                data = _json.loads(raw.decode("utf-8"))
                env = RecordEnvelope(
                    record_id=data.get("id", key.split("/")[-1].replace(".json", "")),
                    data=data,
                    source=source,
                )
                envelopes.append(env)
            except Exception as exc:
                logger.warning("Failed to parse raw record %s: %s", key, exc)

        # Run validate + transform + load with raw storage disabled
        # (data is already stored; we don't want to re-store it)
        saved_config = self._config
        self._config = PipelineConfig(
            name=saved_config.name,
            batch_size=saved_config.batch_size,
            max_retries=saved_config.max_retries,
            retry_delay=saved_config.retry_delay,
            dlq_enabled=saved_config.dlq_enabled,
            validate=saved_config.validate,
            transform_mode="eager",       # force eager for reprocessing
            raw_store_enabled=False,      # don't re-store raw
        )
        try:
            result = self.run(envelopes, session=session)
        finally:
            self._config = saved_config

        return result
