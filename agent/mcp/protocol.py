"""MCP protocol types and interfaces."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class MCPMethod(str, Enum):
    """MCP 지원 메서드 목록."""

    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    PING = "ping"


@dataclass(frozen=True)
class MCPRequest:
    """MCP 요청 메시지.

    Attributes:
        method: 요청 메서드 (MCPMethod enum 또는 문자열).
        params: 메서드별 매개변수 딕셔너리.
        request_id: 요청 식별자 (클라이언트 추적용).
    """

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""


@dataclass(frozen=True)
class MCPResponse:
    """MCP 응답 메시지.

    Attributes:
        result: 성공 시 반환 데이터.
        error: 실패 시 오류 메시지.
        request_id: 요청 식별자 (echo).
    """

    result: Any = None
    error: str = ""
    request_id: str = ""

    @property
    def success(self) -> bool:
        """오류가 없으면 True."""
        return not self.error


@runtime_checkable
class MCPHandler(Protocol):
    """MCP 요청을 처리하는 핸들러 프로토콜."""

    async def handle(self, request: MCPRequest) -> MCPResponse:
        """MCP 요청을 처리하고 응답을 반환한다.

        Args:
            request: 처리할 MCP 요청.

        Returns:
            처리 결과를 담은 MCPResponse.
        """
        ...
