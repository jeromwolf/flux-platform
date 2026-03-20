"""ETL pipeline trigger endpoints.

Provides REST API routes for triggering, monitoring, and managing
ETL pipeline executions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from kg.api.deps import get_async_neo4j_session
from kg.etl.models import ETLMode, PipelineConfig
from kg.etl.pipeline import ETLPipeline

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


# ---------------------------------------------------------------------------
# In-memory state (PoC only)
# ---------------------------------------------------------------------------

# 모듈 레벨 실행 이력 (인메모리, PoC)
_run_history: dict[str, ETLStatusResponse] = {}

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
    """Create a new run record in the history.

    Args:
        run_id: Unique run identifier (UUID).
        pipeline_name: Name of the pipeline.
        status: Initial status (e.g., "RUNNING").

    Returns:
        ETLStatusResponse record.
    """
    record = ETLStatusResponse(
        run_id=run_id,
        pipeline_name=pipeline_name,
        status=status,
        started_at=datetime.now().isoformat(),
    )
    _run_history[run_id] = record
    return record


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/api/etl/trigger", response_model=ETLTriggerResponse)
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
        # For PoC, we run with empty records (actual crawler integration later)
        result = pipeline.run([], session=session)

        # Update record with results
        record.status = "COMPLETED"
        record.records_processed = result.records_processed
        record.records_failed = result.records_failed
        record.records_skipped = result.records_skipped
        record.duration_seconds = result.duration_seconds
        record.completed_at = datetime.now().isoformat()
        record.errors = result.errors

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
        record.completed_at = datetime.now().isoformat()
        logger.exception("ETL run %s failed", run_id)
        return ETLTriggerResponse(
            run_id=run_id,
            pipeline_name=body.pipeline_name,
            status="FAILED",
            message=f"Pipeline {body.pipeline_name} failed: {exc}",
        )


@router.post("/api/etl/webhook/{source}", response_model=ETLTriggerResponse)
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


@router.get("/api/etl/status/{run_id}", response_model=ETLStatusResponse)
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
    return record


@router.get("/api/etl/history", response_model=ETLHistoryResponse)
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


@router.get("/api/etl/pipelines", response_model=list[PipelineInfo])
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
        )
        for name, info in _PIPELINE_REGISTRY.items()
    ]
    return pipelines
