"""Agent chat and tool execution endpoints."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message")
    mode: str = Field(default="react", pattern="^(react|pipeline)$")
    max_steps: int = Field(default=5, ge=1, le=20)


class AgentChatResponse(BaseModel):
    message: str
    answer: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    mode: str


class ToolExecuteRequest(BaseModel):
    tool_name: str = Field(..., min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolExecuteResponse(BaseModel):
    tool_name: str
    success: bool
    output: str
    error: str | None = None


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    """Chat with the agent using ReAct or Pipeline mode."""
    try:
        from agent.runtime.models import AgentConfig, ExecutionMode
        from agent.runtime.react import ReActEngine
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        config = AgentConfig(
            mode=ExecutionMode.REACT,
            max_steps=request.max_steps,
        )
        engine = ReActEngine(config=config, tools=registry)
        result = engine.execute(request.message)

        steps = [
            {
                "thought": s.content if s.step_type.value == "thought" else "",
                "action": s.tool_name if s.step_type.value == "action" else "",
                "observation": s.tool_output if s.step_type.value == "observation" else "",
            }
            for s in result.steps
        ]

        tools_used = list(
            {s.tool_name for s in result.steps if s.tool_name}
        )

        return AgentChatResponse(
            message=request.message,
            answer=result.answer,
            steps=steps,
            tools_used=tools_used,
            mode=request.mode,
        )
    except ImportError:
        raise HTTPException(status_code=503, detail="Agent runtime not available")
    except Exception as exc:
        logger.exception("Agent chat failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/tools/execute", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest) -> ToolExecuteResponse:
    """Execute a specific agent tool directly."""
    try:
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        tool = registry.get(request.tool_name)
        if tool is None:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{request.tool_name}' not found",
            )

        result = registry.execute(request.tool_name, request.parameters)

        return ToolExecuteResponse(
            tool_name=request.tool_name,
            success=result.success,
            output=result.output,
            error=result.error if not result.success else None,
        )
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=503, detail="Agent tools not available")
    except Exception as exc:
        logger.exception("Tool execution failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tools")
async def list_tools() -> dict[str, Any]:
    """List available agent tools."""
    try:
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        tools = registry.list_tools()
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
                for t in tools
            ]
        }
    except ImportError:
        return {"tools": [], "error": "Agent tools not available"}


@router.get("/status")
async def agent_status() -> dict[str, Any]:
    """Check agent runtime status."""
    status: dict[str, Any] = {
        "available": False,
        "engines": [],
        "tools_count": 0,
    }
    try:
        from agent.runtime.react import ReActEngine  # noqa: F401

        status["engines"].append("react")
        try:
            from agent.runtime.pipeline import PipelineEngine  # noqa: F401

            status["engines"].append("pipeline")
        except ImportError:
            pass
        try:
            from agent.runtime.batch import BatchEngine  # noqa: F401

            status["engines"].append("batch")
        except ImportError:
            pass
        from agent.tools.builtins import create_builtin_registry

        registry = create_builtin_registry()
        status["tools_count"] = len(registry.list_tools())
        status["available"] = True
    except ImportError:
        pass
    return status
