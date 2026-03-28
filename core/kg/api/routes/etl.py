"""ETL pipeline trigger endpoints.

Provides REST API routes for triggering, monitoring, and managing
ETL pipeline executions.  Run history is persisted to a SQLite store
(see :class:`~kg.etl.state.ETLStateStore`).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from kg.api.deps import get_async_neo4j_session
from kg.etl.models import ETLMode, PipelineConfig
from kg.etl.pipeline import ETLPipeline
from kg.etl.state import ETLRunRecord, ETLStateStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["etl"])

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ETLTriggerRequest(BaseModel):
    """ETL 파이프라인 트리거 요청."""

    source: str = Field(..., description="트리거 소스 (schedule, webhook, manual, file_watcher)")
    pipeline_name: str = Field(..., description="파이프라인 이름 (papers, facilities, weather, accidents)")
    mode: str = Field(default="incremental", description="ETL 모드 (full, incremental)")
    force_full: bool = Field(default=False, description="증분 무시하고 전체 재구축")


class ETLTriggerResponse(BaseModel):
    """ETL 트리거 응답."""

    run_id: str
    pipeline_name: str
    status: str
    message: str


class ETLStatusResponse(BaseModel):
    """ETL 실행 상태 응답."""

    run_id: str
    pipeline_name: str
    status: str
    records_processed: int = 0
    records_failed: int = 0
    records_skipped: int = 0
    duration_seconds: float = 0.0
    started_at: Optional[str] = None  # noqa: UP045
    completed_at: Optional[str] = None  # noqa: UP045
    errors: list[str] = Field(default_factory=list)
    phases_completed: list[str] = Field(default_factory=list)  # ELT phase tracking


class ETLHistoryResponse(BaseModel):
    """ETL 실행 이력 응답."""

    runs: list[ETLStatusResponse] = Field(default_factory=list)
    total: int = 0


class WebhookPayload(BaseModel):
    """외부 시스템 웹훅 페이로드."""

    event: str = Field(..., description="이벤트 유형 (data_changed, file_created)")
    entity_type: Optional[str] = None  # noqa: UP045
    data: dict[str, Any] = Field(default_factory=dict)


class PipelineInfo(BaseModel):
    """파이프라인 정보."""

    name: str
    description: str
    schedule: str
    entity_type: str
    supports_elt: bool = False  # ELT mode support flag


# ---------------------------------------------------------------------------
# State (SQLite-backed via ETLStateStore, with in-memory fallback for PoC)
# ---------------------------------------------------------------------------

# 모듈 레벨 실행 이력 (인메모리, PoC) — kept for backward-compatibility with tests
_run_history: dict[str, ETLStatusResponse] = {}

# SQLite-backed persistent store
_state_store: ETLStateStore | None = None


def _get_state_store() -> ETLStateStore:
    """Return the module-level ETLStateStore singleton, creating it on demand.

    Returns:
        The active :class:`~kg.etl.state.ETLStateStore` instance.
    """
    global _state_store  # noqa: PLW0603
    if _state_store is None:
        _state_store = ETLStateStore()
    return _state_store

# 파이프라인 레지스트리
_PIPELINE_REGISTRY = {
    "papers": {
        "description": "KRISO ScholarWorks 논문 크롤링",
        "schedule": "0 2 * * 6",  # 매주 토 02:00
        "entity_type": "Document",
    },
    "facilities": {
        "description": "KRISO 시험시설 정보 크롤링",
        "schedule": "0 3 1 * *",  # 매월 1일 03:00
        "entity_type": "TestFacility",
    },
    "weather": {
        "description": "기상청 해양기상 데이터 수집",
        "schedule": "0 */3 * * *",  # 매 3시간
        "entity_type": "WeatherCondition",
    },
    "accidents": {
        "description": "해양사고 데이터 수집",
        "schedule": "0 4 * * *",  # 매일 04:00
        "entity_type": "Incident",
    },
    "relations": {
        "description": "관계 추출 배치 처리",
        "schedule": "0 5 * * 1",  # 매주 월 05:00
        "entity_type": "Relationship",
    },
    "facility_data": {
        "description": "시험시설 실험 데이터 적재",
        "schedule": "manual",  # 수동 트리거
        "entity_type": "Experiment",
    },
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _build_pipeline(pipeline_name: str, mode: ETLMode) -> ETLPipeline:
    """파이프라인 이름으로 ETLPipeline 인스턴스를 구성한다.

    Args:
        pipeline_name: Pipeline name from the registry.
        mode: ETL execution mode (FULL or INCREMENTAL).

    Returns:
        Configured ETLPipeline instance.

    Raises:
        ValueError: If pipeline_name is not in the registry.
    """
    info = _PIPELINE_REGISTRY.get(pipeline_name)
    if not info:
        raise ValueError(f"Unknown pipeline: {pipeline_name}")

    config = PipelineConfig(name=pipeline_name)
    pipeline = ETLPipeline(config, mode=mode)
    # 기본 변환/검증/로더 설정은 실제 구현 시 확장
    return pipeline


def _create_run_record(
    run_id: str,
    pipeline_name: str,
    status: str,
) -> ETLStatusResponse:
    """Create a new run record in the history (in-memory + SQLite).

    Saves the record to the in-memory dict for fast access and also
    persists it to the SQLite store for durability across restarts.

    Args:
        run_id: Unique run identifier (UUID).
        pipeline_name: Name of the pipeline.
        status: Initial status (e.g., "RUNNING").

    Returns:
        ETLStatusResponse record.
    """
    import time

    started_at_iso = datetime.now(timezone.utc).isoformat()
    record = ETLStatusResponse(
        run_id=run_id,
        pipeline_name=pipeline_name,
        status=status,
        started_at=started_at_iso,
    )
    _run_history[run_id] = record

    # Persist to SQLite (best-effort — do not let DB errors break the API)
    try:
        _get_state_store().save_run(
            ETLRunRecord(
                run_id=run_id,
                pipeline_name=pipeline_name,
                status=status,
                started_at=time.time(),
            )
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to persist ETL run %s to SQLite store", run_id)

    return record


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/etl/trigger", response_model=ETLTriggerResponse)
async def trigger_etl(
    body: ETLTriggerRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> ETLTriggerResponse:
    """ETL 파이프라인을 수동 또는 자동으로 트리거한다.

    Args:
        body: Trigger request containing pipeline name and mode.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        ETLTriggerResponse with run ID and status.

    Raises:
        HTTPException: 400 if pipeline name is unknown.
    """
    if body.pipeline_name not in _PIPELINE_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown pipeline: {body.pipeline_name}",
        )

    # Generate run ID
    run_id = str(uuid.uuid4())

    # Determine ETL mode
    if body.force_full:
        mode = ETLMode.FULL
    else:
        mode = ETLMode.FULL if body.mode == "full" else ETLMode.INCREMENTAL

    # Create run record
    record = _create_run_record(run_id, body.pipeline_name, "RUNNING")

    try:
        # Build and execute pipeline (synchronous PoC version)
        pipeline = _build_pipeline(body.pipeline_name, mode)

        # ELT mode: attach a raw store so raw records are persisted before transform
        if body.mode == "elt":
            from kg.etl.raw_store import LocalFileStore
            pipeline._raw_store = LocalFileStore()
            # Rebuild config with raw_store_enabled so Phase 2 (LOAD_RAW) runs
            pipeline._config = PipelineConfig(
                name=pipeline._config.name,
                batch_size=pipeline._config.batch_size,
                max_retries=pipeline._config.max_retries,
                retry_delay=pipeline._config.retry_delay,
                dlq_enabled=pipeline._config.dlq_enabled,
                validate=pipeline._config.validate,
                transform_mode=pipeline._config.transform_mode,
                raw_store_enabled=True,
            )

        # For PoC, we run with empty records (actual crawler integration later)
        result = pipeline.run([], session=session)

        # Update in-memory record with results
        record.status = "COMPLETED"
        record.records_processed = result.records_processed
        record.records_failed = result.records_failed
        record.records_skipped = result.records_skipped
        record.duration_seconds = result.duration_seconds
        record.completed_at = datetime.now(timezone.utc).isoformat()
        record.errors = result.errors
        record.phases_completed = list(result.phases_completed)

        # Persist completion to SQLite (best-effort)
        try:
            _get_state_store().update_status(
                run_id,
                "COMPLETED",
                record_count=result.records_processed,
                phases_completed=result.phases_completed,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Failed to update SQLite state for run %s", run_id)

        logger.info(
            "ETL run %s for pipeline %s completed: processed=%d, failed=%d",
            run_id,
            body.pipeline_name,
            result.records_processed,
            result.records_failed,
        )

        return ETLTriggerResponse(
            run_id=run_id,
            pipeline_name=body.pipeline_name,
            status="COMPLETED",
            message=f"Pipeline {body.pipeline_name} completed successfully",
        )
    except Exception as exc:
        record.status = "FAILED"
        record.errors = [str(exc)]
        record.completed_at = datetime.now(timezone.utc).isoformat()

        # Persist failure to SQLite (best-effort)
        try:
            _get_state_store().update_status(run_id, "FAILED", error=str(exc))
        except Exception:  # noqa: BLE001
            logger.warning("Failed to update SQLite state for failed run %s", run_id)

        logger.exception("ETL run %s failed", run_id)
        return ETLTriggerResponse(
            run_id=run_id,
            pipeline_name=body.pipeline_name,
            status="FAILED",
            message=f"Pipeline {body.pipeline_name} failed: {exc}",
        )


@router.post("/etl/webhook/{source}", response_model=ETLTriggerResponse)
async def webhook_trigger(
    source: str = Path(..., description="Webhook source (pipeline name)"),  # noqa: B008
    payload: WebhookPayload = ...,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> ETLTriggerResponse:
    """외부 시스템 웹훅을 수신하여 ETL을 트리거한다.

    Args:
        source: Pipeline name derived from URL path.
        payload: Webhook event payload.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        ETLTriggerResponse with run ID and status.

    Raises:
        HTTPException: 400 if source is unknown.
    """
    if source not in _PIPELINE_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown webhook source: {source}",
        )

    logger.info("Webhook received: source=%s, event=%s", source, payload.event)

    # Convert to trigger request
    trigger_request = ETLTriggerRequest(
        source="webhook",
        pipeline_name=source,
        mode="incremental",
        force_full=False,
    )

    # Delegate to main trigger endpoint
    return await trigger_etl(trigger_request, session)


@router.get("/etl/status/{run_id}", response_model=ETLStatusResponse)
async def get_status(
    run_id: str = Path(..., description="Run identifier (UUID)"),  # noqa: B008
) -> ETLStatusResponse:
    """특정 실행의 상태를 조회한다.

    Args:
        run_id: Unique run identifier.

    Returns:
        ETLStatusResponse with run details.

    Raises:
        HTTPException: 404 if run_id is not found.
    """
    record = _run_history.get(run_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found",
        )

    # Enrich phases_completed from SQLite if not already set on the in-memory record
    if not record.phases_completed:
        try:
            state_run = _get_state_store().get_run(run_id)
            if state_run and state_run.phases_completed:
                record.phases_completed = list(state_run.phases_completed)
        except Exception:  # noqa: BLE001
            logger.debug("SQLite state store read failed for run %s", run_id, exc_info=True)

    return record


@router.get("/etl/history", response_model=ETLHistoryResponse)
async def get_history(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of runs to return"),  # noqa: B008
) -> ETLHistoryResponse:
    """실행 이력을 최신순으로 조회한다.

    Args:
        limit: Maximum number of runs to return.

    Returns:
        ETLHistoryResponse with list of runs.
    """
    # Sort by started_at descending (most recent first)
    sorted_runs = sorted(
        _run_history.values(),
        key=lambda r: r.started_at or "",
        reverse=True,
    )
    limited_runs = sorted_runs[:limit]

    return ETLHistoryResponse(
        runs=limited_runs,
        total=len(_run_history),
    )


@router.get("/etl/pipelines", response_model=list[PipelineInfo])
async def list_pipelines() -> list[PipelineInfo]:
    """사용 가능한 파이프라인 목록을 반환한다.

    Returns:
        List of PipelineInfo with name, description, and schedule.
    """
    pipelines = [
        PipelineInfo(
            name=name,
            description=info["description"],
            schedule=info["schedule"],
            entity_type=info["entity_type"],
            supports_elt=True,  # All pipelines now support ELT mode
        )
        for name, info in _PIPELINE_REGISTRY.items()
    ]
    return pipelines


@router.post("/etl/reprocess/{run_id}", response_model=ETLTriggerResponse)
async def reprocess_from_raw(
    run_id: str = Path(..., description="Original run ID whose raw data to reprocess"),  # noqa: B008
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> ETLTriggerResponse:
    """Re-process a previous run from stored raw data.

    Reads raw records from the local store and re-applies
    validation, transformation, and KG loading.

    Args:
        run_id: Identifier of the original ETL run whose raw records to reprocess.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        ETLTriggerResponse with a new run ID and completion status.

    Raises:
        HTTPException: 404 if the original run or its pipeline cannot be found.
    """
    from kg.etl.raw_store import LocalFileStore

    # ------------------------------------------------------------------
    # Resolve pipeline name from original run
    # ------------------------------------------------------------------
    pipeline_name: str | None = None

    # Try SQLite store first
    try:
        original_run = _get_state_store().get_run(run_id)
        if original_run is not None:
            pipeline_name = original_run.pipeline_name
    except Exception:  # noqa: BLE001 S110
        pass

    # Fall back to in-memory history
    if pipeline_name is None:
        mem_record = _run_history.get(run_id)
        if mem_record is not None:
            pipeline_name = mem_record.pipeline_name

    if pipeline_name is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if pipeline_name not in _PIPELINE_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline '{pipeline_name}' from run {run_id} not in registry",
        )

    # ------------------------------------------------------------------
    # Create new run record
    # ------------------------------------------------------------------
    new_run_id = f"reprocess-{str(uuid.uuid4())[:8]}"
    record = _create_run_record(new_run_id, pipeline_name, "RUNNING")

    # ------------------------------------------------------------------
    # Build pipeline with LocalFileStore for reading previously stored raw data
    # ------------------------------------------------------------------
    raw_store = LocalFileStore()
    config = PipelineConfig(
        name=pipeline_name,
        raw_store_enabled=False,  # don't re-store; we're reading existing raw data
        transform_mode="eager",
    )
    pipeline = ETLPipeline(config=config, raw_store=raw_store)

    try:
        result = pipeline.reprocess(source=pipeline_name, session=session)

        status_value = result.status.value if hasattr(result, "status") and hasattr(result.status, "value") else "COMPLETED"

        record.status = status_value
        record.records_processed = result.records_processed
        record.records_failed = result.records_failed
        record.records_skipped = result.records_skipped
        record.duration_seconds = result.duration_seconds
        record.completed_at = datetime.now(timezone.utc).isoformat()
        record.errors = result.errors
        record.phases_completed = list(result.phases_completed)

        # Persist to SQLite (best-effort)
        try:
            _get_state_store().update_status(
                new_run_id,
                status_value,
                record_count=result.records_processed,
                phases_completed=result.phases_completed,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Failed to update SQLite state for reprocess run %s", new_run_id)

        logger.info(
            "Reprocess run %s for pipeline %s completed: processed=%d, phases=%s",
            new_run_id,
            pipeline_name,
            result.records_processed,
            result.phases_completed,
        )

        return ETLTriggerResponse(
            run_id=new_run_id,
            pipeline_name=pipeline_name,
            status=status_value,
            message=f"Reprocessed from raw data of run {run_id}",
        )
    except Exception as exc:
        record.status = "FAILED"
        record.errors = [str(exc)]
        record.completed_at = datetime.now(timezone.utc).isoformat()

        try:
            _get_state_store().update_status(new_run_id, "FAILED", error=str(exc))
        except Exception:  # noqa: BLE001
            logger.warning("Failed to update SQLite state for failed reprocess run %s", new_run_id)

        logger.exception("Reprocess run %s failed", new_run_id)
        return ETLTriggerResponse(
            run_id=new_run_id,
            pipeline_name=pipeline_name,
            status="FAILED",
            message=f"Reprocess of run {run_id} failed: {exc}",
        )
