"""MCP JSON-RPC endpoint for remote tool access.

Exposes MCP protocol over HTTP for remote agent/client connections.
Two modes:
- POST /mcp/      -- standard JSON-RPC request/response
- POST /mcp/stream -- SSE streaming response
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp"])


def _get_mcp_server() -> Any:
    """Lazy-load MCP server with the builtin tool registry.

    Returns a new MCPServer on each call. In production this could be
    cached, but the registry creation is lightweight.
    """
    from agent.mcp.server import MCPServer
    from agent.tools.builtins import create_builtin_registry

    registry = create_builtin_registry()
    return MCPServer(tool_registry=registry)


@router.post("/")
async def mcp_jsonrpc(request: Request) -> JSONResponse:
    """Handle MCP JSON-RPC requests.

    Accepts a standard JSON-RPC 2.0 payload and dispatches to the
    MCPServer for processing.
    """
    try:
        body: dict[str, Any] = await request.json()

        from agent.mcp.protocol import MCPMethod, MCPRequest

        method_str = body.get("method", "")
        try:
            MCPMethod(method_str)
        except ValueError:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {"code": -32601, "message": f"Unknown method: {method_str}"},
                },
                status_code=400,
            )

        mcp_request = MCPRequest(
            method=method_str,
            params=body.get("params", {}),
            request_id=str(body.get("id", "1")),
        )

        server = _get_mcp_server()
        response = await server.handle(mcp_request)

        result: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": response.request_id,
        }
        if response.error:
            result["error"] = {"code": -32000, "message": response.error}
        else:
            result["result"] = response.result

        return JSONResponse(result)
    except Exception as e:
        logger.exception("MCP endpoint error")
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            },
            status_code=500,
        )


@router.post("/stream", response_model=None)
async def mcp_stream(request: Request):
    """Handle MCP requests with SSE streaming response.

    Returns a ``text/event-stream`` response with structured events:
    - ``start``  -- indicates processing has begun
    - ``result`` -- contains the MCP response data
    - ``error``  -- sent if the handler fails
    - ``done``   -- signals end of stream
    """
    try:
        body: dict[str, Any] = await request.json()

        from agent.mcp.protocol import MCPMethod, MCPRequest

        method_str = body.get("method", "")
        try:
            MCPMethod(method_str)
        except ValueError:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {"code": -32601, "message": f"Unknown method: {method_str}"},
                },
                status_code=400,
            )

        mcp_request = MCPRequest(
            method=method_str,
            params=body.get("params", {}),
            request_id=str(body.get("id", "1")),
        )

        server = _get_mcp_server()

        async def event_generator():  # type: ignore[no-untyped-def]
            yield f"data: {json.dumps({'type': 'start', 'method': method_str})}\n\n"

            response = await server.handle(mcp_request)

            if response.error:
                yield f"data: {json.dumps({'type': 'error', 'message': response.error})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'result', 'data': response.result}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except Exception as e:
        logger.exception("MCP stream endpoint error")
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            },
            status_code=500,
        )
