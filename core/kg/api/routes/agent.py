"""Agent chat and tool execution endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message")
    mode: str = Field(default="react", pattern="^(react|pipeline)$")
    max_steps: int = Field(default=5, ge=1, le=20)
    session_id: Optional[str] = None


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
        result = engine.execute(request.message, session_id=request.session_id or "default")

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


@router.post("/chat/stream")
async def agent_chat_stream(request: AgentChatRequest) -> StreamingResponse:
    """Stream agent reasoning steps via Server-Sent Events (SSE)."""

    async def event_generator():  # type: ignore[return]
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

            # Stream: thinking started
            yield f"data: {json.dumps({'type': 'start', 'query': request.message}, ensure_ascii=False)}\n\n"

            # Execute and get result
            result = engine.execute(
                request.message,
                session_id=request.session_id or "default",
            )

            # Stream each reasoning step
            for i, step in enumerate(result.steps):
                step_data: dict[str, Any] = {
                    "type": "step",
                    "index": i,
                    "thought": step.content if step.step_type.value == "thought" else "",
                    "action": step.tool_name if step.step_type.value == "action" else "",
                    "observation": step.tool_output if step.step_type.value == "observation" else "",
                }
                yield f"data: {json.dumps(step_data, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.05)

            # Stream final answer
            yield f"data: {json.dumps({'type': 'answer', 'content': result.answer, 'tool_calls': len(result.steps)}, ensure_ascii=False)}\n\n"

            # Stream done signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except ImportError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Agent runtime not available'})}\n\n"
        except Exception as exc:
            logger.exception("Agent stream failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    """List all conversation sessions."""
    try:
        from agent.memory.factory import create_memory_provider

        provider = create_memory_provider()
        sessions = provider.list_sessions() if hasattr(provider, "list_sessions") else []
        return {"sessions": sessions, "count": len(sessions)}
    except Exception:
        return {"sessions": [], "count": 0}


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 50) -> dict[str, Any]:
    """Get conversation history for a session."""
    try:
        from agent.memory.factory import create_memory_provider

        provider = create_memory_provider()
        history = provider.get_history(session_id, limit=limit)
        entries = [
            {
                "role": e.role.value if hasattr(e.role, "value") else str(e.role),
                "content": e.content,
                "memory_type": e.role.value if hasattr(e.role, "value") else str(e.role),
            }
            for e in history
        ]
        return {"session_id": session_id, "messages": entries, "count": len(entries)}
    except Exception:
        return {"session_id": session_id, "messages": [], "count": 0}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """Delete a conversation session."""
    try:
        from agent.memory.factory import create_memory_provider

        provider = create_memory_provider()
        provider.clear(session_id)
        return {"deleted": session_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {exc}") from exc


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
