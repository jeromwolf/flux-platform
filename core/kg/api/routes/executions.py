"""Workflow execution API routes."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from kg.api.deps import get_workflow_repo
from kg.db.protocols import WorkflowRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["executions"])


# --- Pydantic models ---


class ExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    trigger_type: str
    started_at: str
    finished_at: str | None = None
    error_message: str = ""
    node_results: dict[str, Any] = Field(default_factory=dict)


class ExecutionListResponse(BaseModel):
    executions: list[ExecutionResponse] = Field(default_factory=list)
    total: int = 0


class ExecuteRequest(BaseModel):
    initial_data: list[dict[str, Any]] | None = None


class NodeTypeInfo(BaseModel):
    name: str
    display_name: str
    description: str
    category: str
    parameter_schema: dict[str, Any] = Field(default_factory=dict)


# --- Dependency ---


def get_execution_repo(request: Request):
    """Get execution repository from app state."""
    return getattr(request.app.state, "execution_repo", None)


def get_ws_manager(request: Request):
    """Get WebSocket manager from app state (optional)."""
    return getattr(request.app.state, "ws_manager", None)


# --- Background task ---


async def run_execution_task(executor, workflow, initial_data, exec_result, execution_repo):
    """Background task for workflow execution."""
    from core.workflow.models import ExecutionStatus

    try:
        result = await executor.execute(workflow, exec_result.trigger_type, initial_data)
        if execution_repo:
            await execution_repo.update(exec_result.execution_id, {
                "status": result.status.value,
                "finished_at": result.finished_at.isoformat() if result.finished_at else None,
                "error_message": result.error_message,
                "node_results": {nid: nr.to_dict() for nid, nr in result.node_results.items()},
            })
    except Exception as exc:
        logger.exception("Execution task failed: %s", exc)
        if execution_repo:
            await execution_repo.update(exec_result.execution_id, {
                "status": "error",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error_message": str(exc),
            })


# --- Routes ---


@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionResponse, status_code=202)
async def execute_workflow(
    workflow_id: str,
    body: ExecuteRequest | None = None,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repo),
    request: Request = None,
):
    """Trigger workflow execution.

    Returns immediately with execution ID; execution runs in background.
    """
    from core.workflow.models import ExecutionResult, TriggerType

    # Load workflow
    wf = await workflow_repo.get(workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    if not wf.get("nodes"):
        raise HTTPException(status_code=400, detail="Workflow has no nodes")

    # Get repos
    execution_repo = get_execution_repo(request)
    ws_manager = get_ws_manager(request)

    # Concurrency limits
    MAX_PER_WORKFLOW = 3
    MAX_TOTAL = 10

    if execution_repo:
        running_count = await execution_repo.count_running_by_workflow(workflow_id)
        if running_count >= MAX_PER_WORKFLOW:
            raise HTTPException(
                status_code=429,
                detail=f"Workflow {workflow_id} already has {running_count} running executions (max {MAX_PER_WORKFLOW})"
            )

        total_running = await execution_repo.count_running_total()
        if total_running >= MAX_TOTAL:
            raise HTTPException(
                status_code=429,
                detail=f"System has {total_running} running executions (max {MAX_TOTAL})"
            )

    # Create execution record
    exec_result = ExecutionResult(workflow_id=workflow_id, trigger_type=TriggerType.MANUAL)

    if execution_repo:
        await execution_repo.create(exec_result.to_dict())

    # Enqueue via execution worker
    initial_data = body.initial_data if body else None
    execution_worker = getattr(request.app.state, "execution_worker", None)
    if execution_worker:
        await execution_worker.enqueue(
            execution_id=exec_result.execution_id,
            workflow_id=workflow_id,
            trigger_type="manual",
            initial_data=initial_data,
        )
    else:
        # Fallback: in-process (for testing / when worker not initialized)
        from core.workflow.executor import WorkflowExecutor
        from core.workflow.models import NodeStatus

        async def on_status_change(execution_id: str, node_id: str, status: NodeStatus, extra: dict):
            if ws_manager:
                from gateway.ws.models import WSMessage, WSMessageType
                msg = WSMessage(
                    type=WSMessageType.NODE_STATUS,
                    payload={
                        "execution_id": execution_id,
                        "node_id": node_id,
                        "status": status.value,
                        **extra,
                    },
                    room=f"execution:{execution_id}",
                )
                await ws_manager.broadcast_to_room(f"workflow:{workflow_id}", msg)

        executor = WorkflowExecutor(on_status_change=on_status_change)
        asyncio.create_task(run_execution_task(executor, wf, initial_data, exec_result, execution_repo))

    return ExecutionResponse(**exec_result.to_dict())


@router.get("/workflows/{workflow_id}/executions", response_model=ExecutionListResponse)
async def list_executions(
    workflow_id: str,
    limit: int = 20,
    offset: int = 0,
    request: Request = None,
):
    """List execution history for a workflow."""
    execution_repo = get_execution_repo(request)
    if execution_repo is None:
        return ExecutionListResponse(executions=[], total=0)

    executions = await execution_repo.list_by_workflow(workflow_id, limit=min(limit, 100), offset=offset)
    total = await execution_repo.count_by_workflow(workflow_id)

    return ExecutionListResponse(
        executions=[ExecutionResponse(**e) for e in executions],
        total=total,
    )


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: str,
    request: Request = None,
):
    """Get execution detail with per-node results."""
    execution_repo = get_execution_repo(request)
    if execution_repo is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    execution = await execution_repo.get(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")

    return ExecutionResponse(**execution)


@router.delete("/executions/{execution_id}")
async def delete_execution(
    execution_id: str,
    request: Request = None,
):
    """Delete an execution record."""
    execution_repo = get_execution_repo(request)
    if execution_repo is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    deleted = await execution_repo.delete(execution_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")

    return {"deleted": execution_id}


@router.get("/nodes/types", response_model=list[NodeTypeInfo])
async def list_node_types():
    """List all available workflow node types."""
    from core.workflow.registry import NodeRegistry
    # Ensure nodes are loaded
    import core.workflow.nodes  # noqa: F401

    return [NodeTypeInfo(**nt) for nt in NodeRegistry.list_types()]


@router.get("/nodes/types/{node_type}/schema")
async def get_node_type_schema(node_type: str):
    """Get parameter schema for a specific node type."""
    from core.workflow.registry import NodeRegistry
    import core.workflow.nodes  # noqa: F401

    if not NodeRegistry.has(node_type):
        raise HTTPException(status_code=404, detail=f"Node type '{node_type}' not found")

    node = NodeRegistry.get(node_type)
    return {
        "name": node.name,
        "display_name": node.display_name,
        "parameter_schema": node.get_parameter_schema(),
    }
