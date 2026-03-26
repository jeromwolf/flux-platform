"""Workflow CRUD routes."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from kg.api.deps import get_workflow_repo
from kg.db.protocols import WorkflowRepository

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


@router.post("/", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    data: WorkflowData,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> WorkflowResponse:
    """Create a new workflow.

    Args:
        data: Workflow name, description, nodes, edges, and viewport state.
        repo: Injected workflow repository.

    Returns:
        WorkflowResponse with assigned ID and timestamps.
    """
    wf_id = str(uuid.uuid4())[:8]
    wf = await repo.create(
        wf_id=wf_id,
        name=data.name,
        description=data.description,
        nodes=data.nodes,
        edges=data.edges,
        viewport=data.viewport,
    )
    return WorkflowResponse(**wf)


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> WorkflowListResponse:
    """List all saved workflows.

    Args:
        repo: Injected workflow repository.

    Returns:
        WorkflowListResponse with all stored workflows and total count.
    """
    wfs = await repo.list_all()
    return WorkflowListResponse(
        workflows=[WorkflowResponse(**w) for w in wfs],
        total=len(wfs),
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> WorkflowResponse:
    """Retrieve a single workflow by ID.

    Args:
        workflow_id: Short UUID assigned at creation time.
        repo: Injected workflow repository.

    Returns:
        WorkflowResponse for the matching workflow.

    Raises:
        HTTPException: 404 if no workflow with that ID exists.
    """
    wf = await repo.get(workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return WorkflowResponse(**wf)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    data: WorkflowData,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> WorkflowResponse:
    """Update an existing workflow (full replace semantics).

    Args:
        workflow_id: Short UUID of the workflow to update.
        data: New workflow content (name, nodes, edges, viewport).
        repo: Injected workflow repository.

    Returns:
        WorkflowResponse with updated content and ``updated_at`` timestamp.

    Raises:
        HTTPException: 404 if no workflow with that ID exists.
    """
    updated = await repo.update(
        wf_id=workflow_id,
        name=data.name,
        description=data.description,
        nodes=data.nodes,
        edges=data.edges,
        viewport=data.viewport,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return WorkflowResponse(**updated)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> dict[str, str]:
    """Delete a workflow by ID.

    Args:
        workflow_id: Short UUID of the workflow to delete.
        repo: Injected workflow repository.

    Returns:
        Dict with ``deleted`` key containing the removed workflow_id.

    Raises:
        HTTPException: 404 if no workflow with that ID exists.
    """
    deleted = await repo.delete(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return {"deleted": workflow_id}
