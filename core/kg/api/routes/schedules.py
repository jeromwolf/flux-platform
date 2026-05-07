"""Schedule and webhook trigger API routes."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["schedules"])


# --- Models ---


class ScheduleCreateRequest(BaseModel):
    workflow_id: str
    cron_expression: str = ""
    interval_seconds: int | None = None
    enabled: bool = True
    description: str = ""


class ScheduleResponse(BaseModel):
    schedule_id: str
    workflow_id: str
    cron_expression: str = ""
    interval_seconds: int | None = None
    enabled: bool = True
    description: str = ""
    created_at: str


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleResponse] = Field(default_factory=list)


class WebhookCreateResponse(BaseModel):
    workflow_id: str
    token: str
    webhook_url: str


# --- Helpers ---


def get_scheduler(request: Request):
    return getattr(request.app.state, "workflow_scheduler", None)


def get_webhook_manager(request: Request):
    return getattr(request.app.state, "webhook_manager", None)


# --- Schedule Routes ---


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    body: ScheduleCreateRequest,
    request: Request,
):
    """Create a new schedule for a workflow."""
    scheduler = get_scheduler(request)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    from core.workflow.scheduler import ScheduleConfig

    config = ScheduleConfig(
        workflow_id=body.workflow_id,
        cron_expression=body.cron_expression,
        interval_seconds=body.interval_seconds,
        enabled=body.enabled,
        description=body.description,
    )

    try:
        result = await scheduler.add_schedule(config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ScheduleResponse(
        schedule_id=result.schedule_id,
        workflow_id=result.workflow_id,
        cron_expression=result.cron_expression,
        interval_seconds=result.interval_seconds,
        enabled=result.enabled,
        description=result.description,
        created_at=result.created_at.isoformat(),
    )


@router.get("/workflows/{workflow_id}/schedules", response_model=ScheduleListResponse)
async def list_schedules(
    workflow_id: str,
    request: Request,
):
    """List schedules for a workflow."""
    scheduler = get_scheduler(request)
    if scheduler is None:
        return ScheduleListResponse(schedules=[])

    schedules = scheduler.list_schedules(workflow_id=workflow_id)
    return ScheduleListResponse(
        schedules=[
            ScheduleResponse(
                schedule_id=s.schedule_id,
                workflow_id=s.workflow_id,
                cron_expression=s.cron_expression,
                interval_seconds=s.interval_seconds,
                enabled=s.enabled,
                description=s.description,
                created_at=s.created_at.isoformat(),
            )
            for s in schedules
        ]
    )


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    request: Request,
):
    """Delete a schedule."""
    scheduler = get_scheduler(request)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    if not await scheduler.remove_schedule(schedule_id):
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    return {"deleted": schedule_id}


@router.post("/schedules/{schedule_id}/enable")
async def enable_schedule(schedule_id: str, request: Request):
    """Enable a paused schedule."""
    scheduler = get_scheduler(request)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not available")
    if not await scheduler.enable_schedule(schedule_id):
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"status": "enabled", "schedule_id": schedule_id}


@router.post("/schedules/{schedule_id}/disable")
async def disable_schedule(schedule_id: str, request: Request):
    """Disable a schedule."""
    scheduler = get_scheduler(request)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not available")
    if not await scheduler.disable_schedule(schedule_id):
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"status": "disabled", "schedule_id": schedule_id}


# --- Webhook Routes ---


@router.post(
    "/workflows/{workflow_id}/webhooks",
    response_model=WebhookCreateResponse,
    status_code=201,
)
async def create_webhook(
    workflow_id: str,
    request: Request,
):
    """Create a webhook trigger URL for a workflow."""
    webhook_mgr = get_webhook_manager(request)
    if webhook_mgr is None:
        raise HTTPException(status_code=503, detail="Webhook manager not available")

    token = await webhook_mgr.create_token(workflow_id)
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/webhooks/{workflow_id}/{token}"

    return WebhookCreateResponse(
        workflow_id=workflow_id,
        token=token,
        webhook_url=webhook_url,
    )


@router.post("/webhooks/{workflow_id}/{token}")
async def trigger_webhook(
    workflow_id: str,
    token: str,
    request: Request,
):
    """External webhook endpoint — triggers workflow execution.

    The request body is passed as initial_data to the first node.
    """
    webhook_mgr = get_webhook_manager(request)
    if webhook_mgr is None:
        raise HTTPException(status_code=503, detail="Webhook not available")

    if not await webhook_mgr.validate_token(workflow_id, token):
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    # Parse request body as initial data
    try:
        body = await request.json()
    except Exception:
        body = {}

    initial_data = body if isinstance(body, list) else [body] if body else []

    # Get workflow repo and execute
    workflow_repo = getattr(request.app.state, "workflow_repo", None)
    if workflow_repo is None:
        raise HTTPException(status_code=503, detail="Workflow repository not available")

    wf = await workflow_repo.get(workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    # Execute (fire-and-forget)
    from core.workflow.models import ExecutionResult, TriggerType

    exec_result = ExecutionResult(
        workflow_id=workflow_id, trigger_type=TriggerType.WEBHOOK
    )

    execution_repo = getattr(request.app.state, "execution_repo", None)
    if execution_repo:
        await execution_repo.create(exec_result.to_dict())

    execution_worker = getattr(request.app.state, "execution_worker", None)
    if execution_worker:
        await execution_worker.enqueue(
            execution_id=exec_result.execution_id,
            workflow_id=workflow_id,
            trigger_type="webhook",
            initial_data=initial_data,
        )
    else:
        # Fallback: in-process execution when worker not available
        from core.workflow.executor import WorkflowExecutor

        executor = WorkflowExecutor()

        async def run():
            result = await executor.execute(wf, TriggerType.WEBHOOK, initial_data)
            if execution_repo:
                await execution_repo.update(
                    exec_result.execution_id,
                    {
                        "status": result.status.value,
                        "finished_at": (
                            result.finished_at.isoformat() if result.finished_at else None
                        ),
                        "error_message": result.error_message,
                        "node_results": {
                            nid: nr.to_dict() for nid, nr in result.node_results.items()
                        },
                    },
                )

        asyncio.create_task(run())

    return {
        "execution_id": exec_result.execution_id,
        "status": "accepted",
        "workflow_id": workflow_id,
    }


@router.get("/workflows/{workflow_id}/webhooks")
async def list_webhooks(
    workflow_id: str,
    request: Request,
):
    """List webhook tokens for a workflow."""
    webhook_mgr = get_webhook_manager(request)
    if webhook_mgr is None:
        return {"tokens": []}

    tokens = await webhook_mgr.get_workflow_tokens(workflow_id)
    base_url = str(request.base_url).rstrip("/")
    return {
        "tokens": [
            {
                "token": t,
                "webhook_url": f"{base_url}/api/v1/webhooks/{workflow_id}/{t}",
            }
            for t in tokens
        ]
    }


@router.delete("/webhooks/{token}")
async def revoke_webhook(
    token: str,
    request: Request,
):
    """Revoke a webhook token."""
    webhook_mgr = get_webhook_manager(request)
    if webhook_mgr is None:
        raise HTTPException(status_code=503, detail="Webhook not available")

    if not await webhook_mgr.revoke_token(token):
        raise HTTPException(status_code=404, detail="Token not found")

    return {"revoked": token}
