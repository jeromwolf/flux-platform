"""MCP Transport abstractions for different communication channels.

Provides pluggable transport layers for MCP communication:
- InProcessTransport: direct in-memory calls to MCPServer.handle()
- HttpTransport: HTTP POST JSON-RPC for remote MCP servers
- SseTransport: Server-Sent Events for streaming MCP responses

All transports use stdlib only -- no external HTTP dependencies.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from agent.mcp.protocol import MCPRequest, MCPResponse

logger = logging.getLogger(__name__)


@runtime_checkable
class MCPTransport(Protocol):
    """Protocol for MCP message transport."""

    async def send(self, request: MCPRequest) -> MCPResponse:
        """Send a request and return the response."""
        ...

    def close(self) -> None:
        """Close the transport connection."""
        ...


@dataclass
class InProcessTransport:
    """In-process transport -- directly calls MCPServer.handle().

    This is the default transport used when client and server live in the
    same Python process.  Zero serialization overhead.
    """

    server: Any = None  # MCPServer instance (Any to avoid circular import)

    async def send(self, request: MCPRequest) -> MCPResponse:
        """Delegate to the server's async handle method."""
        if self.server is None:
            return MCPResponse(error="No server configured", request_id=request.request_id)
        return await self.server.handle(request)

    def close(self) -> None:
        pass


@dataclass
class HttpTransport:
    """HTTP POST transport for remote MCP servers.

    Sends JSON-RPC requests via HTTP POST and parses responses.
    Uses stdlib urllib -- no external HTTP dependencies.
    """

    url: str = ""
    api_key: str = ""
    timeout: float = 30.0
    _headers: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"

    async def send(self, request: MCPRequest) -> MCPResponse:
        """Send JSON-RPC request over HTTP POST and return parsed response."""
        if not self.url:
            return MCPResponse(error="No URL configured", request_id=request.request_id)

        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        try:
            method_val = request.method
            if hasattr(method_val, "value"):
                method_val = method_val.value

            payload = json.dumps({
                "jsonrpc": "2.0",
                "id": request.request_id,
                "method": method_val,
                "params": request.params,
            }).encode("utf-8")

            http_req = Request(self.url, data=payload, headers=self._headers, method="POST")
            resp = urlopen(http_req, timeout=self.timeout)  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))

            if "error" in data:
                err = data["error"]
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                return MCPResponse(error=msg, request_id=request.request_id)

            return MCPResponse(result=data.get("result"), request_id=request.request_id)
        except HTTPError as e:
            return MCPResponse(error=f"HTTP {e.code}: {e.reason}", request_id=request.request_id)
        except URLError as e:
            return MCPResponse(error=f"Connection failed: {e.reason}", request_id=request.request_id)
        except Exception as e:
            return MCPResponse(error=f"Transport error: {e}", request_id=request.request_id)

    def close(self) -> None:
        pass


@dataclass
class SseTransport:
    """Server-Sent Events transport for streaming MCP communication.

    Sends requests via HTTP POST and receives streaming responses via SSE.
    Useful for long-running operations like tool execution.
    """

    url: str = ""
    api_key: str = ""
    timeout: float = 60.0

    async def send(self, request: MCPRequest) -> MCPResponse:
        """Send request and collect SSE response stream into a single response."""
        if not self.url:
            return MCPResponse(error="No URL configured", request_id=request.request_id)

        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        try:
            method_val = request.method
            if hasattr(method_val, "value"):
                method_val = method_val.value

            payload = json.dumps({
                "jsonrpc": "2.0",
                "id": request.request_id,
                "method": method_val,
                "params": request.params,
            }).encode("utf-8")

            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            http_req = Request(self.url, data=payload, headers=headers, method="POST")
            resp = urlopen(http_req, timeout=self.timeout)  # noqa: S310

            # Parse SSE stream
            collected_data: list[str] = []
            final_result: Any = None

            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue

                data_str = line[6:]
                try:
                    event_data = json.loads(data_str)
                    event_type = event_data.get("type", "")

                    if event_type == "result":
                        final_result = event_data.get("data")
                    elif event_type == "error":
                        return MCPResponse(
                            error=event_data.get("message", "SSE error"),
                            request_id=request.request_id,
                        )
                    elif event_type == "chunk":
                        collected_data.append(event_data.get("data", ""))
                    elif event_type == "done":
                        break
                except json.JSONDecodeError:
                    collected_data.append(data_str)

            if final_result is not None:
                return MCPResponse(result=final_result, request_id=request.request_id)
            elif collected_data:
                return MCPResponse(
                    result={"chunks": collected_data},
                    request_id=request.request_id,
                )
            else:
                return MCPResponse(result=None, request_id=request.request_id)

        except HTTPError as e:
            return MCPResponse(error=f"HTTP {e.code}: {e.reason}", request_id=request.request_id)
        except URLError as e:
            return MCPResponse(error=f"Connection failed: {e.reason}", request_id=request.request_id)
        except Exception as e:
            return MCPResponse(error=f"SSE transport error: {e}", request_id=request.request_id)

    def close(self) -> None:
        pass


@dataclass(frozen=True)
class TransportConfig:
    """Configuration for transport selection.

    Attributes:
        transport_type: One of ``"in_process"``, ``"http"``, ``"sse"``.
        url: Remote server URL (for http/sse).
        api_key: Bearer token for authentication (for http/sse).
        timeout: Request timeout in seconds.
    """

    transport_type: str = "in_process"  # "in_process", "http", "sse"
    url: str = ""
    api_key: str = ""
    timeout: float = 30.0


def create_transport(config: TransportConfig, server: Any = None) -> MCPTransport:
    """Factory to create appropriate transport from config.

    Args:
        config: Transport configuration.
        server: MCPServer instance (only used for in_process).

    Returns:
        An MCPTransport implementation.
    """
    if config.transport_type == "http":
        return HttpTransport(url=config.url, api_key=config.api_key, timeout=config.timeout)
    elif config.transport_type == "sse":
        return SseTransport(url=config.url, api_key=config.api_key, timeout=config.timeout)
    else:
        return InProcessTransport(server=server)
