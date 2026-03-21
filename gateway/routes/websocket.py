"""WebSocket route types and helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WSRoute:
    """WebSocket route definition.

    Attributes:
        path: URL path for the WebSocket endpoint.
        require_auth: Whether connections must be authenticated.
        max_connections: Maximum simultaneous connections for this route.
    """
    path: str = "/ws"
    require_auth: bool = False
    max_connections: int = 1000


def get_ws_routes() -> list[WSRoute]:
    """Return configured WebSocket routes."""
    return [
        WSRoute(path="/ws", require_auth=False, max_connections=1000),
    ]
