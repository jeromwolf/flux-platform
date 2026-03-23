"""Workflow CRUD routes."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowData(BaseModel):
    name: str = "Untitled Workflow"
    description: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    viewport: dict[str, Any] = Field(default_factory=dict)


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    viewport: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowResponse] = Field(default_factory=list)
    total: int = 0


# In-memory store (Y2: migrate to PostgreSQL)
_workflows: dict[str, dict[str, Any]] = {}


@router.post("/", response_model=WorkflowResponse, status_code=201)
async def create_workflow(data: WorkflowData) -> WorkflowResponse:
    """Create a new workflow.

    Args:
        data: Workflow name, description, nodes, edges, and viewport state.

    Returns:
        WorkflowResponse with assigned ID and timestamps.
    """
    wf_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    wf: dict[str, Any] = {
        "id": wf_id,
        "name": data.name,
        "description": data.description,
        "nodes": data.nodes,
        "edges": data.edges,
        "viewport": data.viewport,
        "created_at": now,
        "updated_at": now,
    }
    _workflows[wf_id] = wf
    return WorkflowResponse(**wf)


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows() -> WorkflowListResponse:
    """List all saved workflows.

    Returns:
        WorkflowListResponse with all stored workflows and total count.
    """
    return WorkflowListResponse(
        workflows=[WorkflowResponse(**wf) for wf in _workflows.values()],
        total=len(_workflows),
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str) -> WorkflowResponse:
    """Retrieve a single workflow by ID.

    Args:
        workflow_id: Short UUID assigned at creation time.

    Returns:
        WorkflowResponse for the matching workflow.

    Raises:
        HTTPException: 404 if no workflow with that ID exists.
    """
    wf = _workflows.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return WorkflowResponse(**wf)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, data: WorkflowData) -> WorkflowResponse:
    """Update an existing workflow (full replace semantics).

    Args:
        workflow_id: Short UUID of the workflow to update.
        data: New workflow content (name, nodes, edges, viewport).

    Returns:
        WorkflowResponse with updated content and ``updated_at`` timestamp.

    Raises:
        HTTPException: 404 if no workflow with that ID exists.
    """
    wf = _workflows.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    wf.update(
        {
            "name": data.name,
            "description": data.description,
            "nodes": data.nodes,
            "edges": data.edges,
            "viewport": data.viewport,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return WorkflowResponse(**wf)


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str) -> dict[str, str]:
    """Delete a workflow by ID.

    Args:
        workflow_id: Short UUID of the workflow to delete.

    Returns:
        Dict with ``deleted`` key containing the removed workflow_id.

    Raises:
        HTTPException: 404 if no workflow with that ID exists.
    """
    if workflow_id not in _workflows:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    del _workflows[workflow_id]
    return {"deleted": workflow_id}
