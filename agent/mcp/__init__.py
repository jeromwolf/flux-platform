"""MCP (Model Context Protocol) client/server with pluggable transports."""
from agent.mcp.client import MCPClient
from agent.mcp.protocol import MCPHandler, MCPMethod, MCPRequest, MCPResponse
from agent.mcp.server import MCPServer
from agent.mcp.transport import (
    HttpTransport,
    InProcessTransport,
    MCPTransport,
    SseTransport,
    TransportConfig,
    create_transport,
)

__all__ = [
    "MCPClient",
    "MCPHandler",
    "MCPMethod",
    "MCPRequest",
    "MCPResponse",
    "MCPServer",
    "MCPTransport",
    "InProcessTransport",
    "HttpTransport",
    "SseTransport",
    "TransportConfig",
    "create_transport",
]
