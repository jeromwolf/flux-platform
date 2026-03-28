"""API proxy route definitions and request forwarding."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProxyRoute:
    """Definition of a proxied API route.

    Attributes:
        path: Gateway-side path pattern (e.g. ``"/graph/query"``).
        target_url: Full backend URL this route forwards to.
        methods: HTTP methods accepted by this route.
        require_auth: Whether requests must carry a valid auth token.
        timeout: Per-request timeout in seconds.
    """

    path: str
    target_url: str
    methods: tuple[str, ...] = ("GET",)
    require_auth: bool = True
    timeout: float = 30.0


class APIProxy:
    """Proxies REST requests to backend services.

    In Y1, this is a simple pass-through configurator that resolves
    route definitions and forwards requests via :mod:`urllib.request`.

    In Y2+, this will grow request transformation, response caching,
    and circuit-breaker logic.

    Args:
        base_url: Base URL of the Core KG API backend.
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def base_url(self) -> str:
        """Return the configured backend base URL."""
        return self._base_url

    def get_routes(self) -> list[ProxyRoute]:
        """Return all configured proxy routes.

        Standard routes exposed by the gateway cover health checks,
        graph operations, query execution, schema inspection, data
        lineage, and ETL pipeline management.

        Returns:
            Ordered list of :class:`ProxyRoute` instances.
        """
        base = self._base_url
        return [
            # Health / readiness
            ProxyRoute(
                path="/health",
                target_url=f"{base}/health",
                methods=("GET",),
                require_auth=False,
                timeout=5.0,
            ),
            ProxyRoute(
                path="/ready",
                target_url=f"{base}/ready",
                methods=("GET",),
                require_auth=False,
                timeout=5.0,
            ),
            # Graph operations
            ProxyRoute(
                path="/graph/query",
                target_url=f"{base}/graph/query",
                methods=("GET", "POST"),
                require_auth=True,
                timeout=30.0,
            ),
            ProxyRoute(
                path="/graph/node",
                target_url=f"{base}/graph/node",
                methods=("GET", "POST", "PUT", "DELETE"),
                require_auth=True,
                timeout=30.0,
            ),
            ProxyRoute(
                path="/graph/relationship",
                target_url=f"{base}/graph/relationship",
                methods=("GET", "POST", "PUT", "DELETE"),
                require_auth=True,
                timeout=30.0,
            ),
            # Natural-language query
            ProxyRoute(
                path="/query/nl",
                target_url=f"{base}/query/nl",
                methods=("POST",),
                require_auth=True,
                timeout=60.0,
            ),
            ProxyRoute(
                path="/query/cypher",
                target_url=f"{base}/query/cypher",
                methods=("POST",),
                require_auth=True,
                timeout=60.0,
            ),
            # Schema inspection
            ProxyRoute(
                path="/schema",
                target_url=f"{base}/schema",
                methods=("GET",),
                require_auth=True,
                timeout=15.0,
            ),
            ProxyRoute(
                path="/schema/labels",
                target_url=f"{base}/schema/labels",
                methods=("GET",),
                require_auth=True,
                timeout=15.0,
            ),
            ProxyRoute(
                path="/schema/relationships",
                target_url=f"{base}/schema/relationships",
                methods=("GET",),
                require_auth=True,
                timeout=15.0,
            ),
            # Data lineage
            ProxyRoute(
                path="/lineage",
                target_url=f"{base}/lineage",
                methods=("GET", "POST"),
                require_auth=True,
                timeout=30.0,
            ),
            ProxyRoute(
                path="/lineage/trace",
                target_url=f"{base}/lineage/trace",
                methods=("POST",),
                require_auth=True,
                timeout=30.0,
            ),
            # ETL / ELT pipeline management
            ProxyRoute(
                path="/etl/jobs",
                target_url=f"{base}/etl/jobs",
                methods=("GET", "POST"),
                require_auth=True,
                timeout=30.0,
            ),
            ProxyRoute(
                path="/etl/jobs/status",
                target_url=f"{base}/etl/jobs/status",
                methods=("GET",),
                require_auth=True,
                timeout=15.0,
            ),
            # Node CRUD
            ProxyRoute(
                path="/nodes",
                target_url=f"{base}/nodes",
                methods=("GET", "POST", "PUT", "DELETE"),
                require_auth=True,
                timeout=30.0,
            ),
            # Relationship CRUD
            ProxyRoute(
                path="/relationships",
                target_url=f"{base}/relationships",
                methods=("GET", "POST", "PUT", "DELETE"),
                require_auth=True,
                timeout=30.0,
            ),
            # Cypher execution
            ProxyRoute(
                path="/cypher/execute",
                target_url=f"{base}/cypher/execute",
                methods=("POST",),
                require_auth=True,
                timeout=60.0,
            ),
            ProxyRoute(
                path="/cypher/validate",
                target_url=f"{base}/cypher/validate",
                methods=("POST",),
                require_auth=True,
                timeout=15.0,
            ),
            ProxyRoute(
                path="/cypher/explain",
                target_url=f"{base}/cypher/explain",
                methods=("POST",),
                require_auth=True,
                timeout=30.0,
            ),
            # Embeddings
            ProxyRoute(
                path="/embeddings",
                target_url=f"{base}/embeddings",
                methods=("POST",),
                require_auth=True,
                timeout=30.0,
            ),
            # Algorithms
            ProxyRoute(
                path="/algorithms",
                target_url=f"{base}/algorithms",
                methods=("GET", "POST"),
                require_auth=True,
                timeout=60.0,
            ),
            # RAG
            ProxyRoute(
                path="/rag/query",
                target_url=f"{base}/rag/query",
                methods=("POST",),
                require_auth=True,
                timeout=60.0,
            ),
            ProxyRoute(
                path="/rag/documents",
                target_url=f"{base}/rag/documents",
                methods=("POST",),
                require_auth=True,
                timeout=60.0,
            ),
            ProxyRoute(
                path="/rag/status",
                target_url=f"{base}/rag/status",
                methods=("GET",),
                require_auth=True,
                timeout=10.0,
            ),
            # Agent
            ProxyRoute(
                path="/agent/chat",
                target_url=f"{base}/agent/chat",
                methods=("POST",),
                require_auth=True,
                timeout=60.0,
            ),
            ProxyRoute(
                path="/agent/chat/stream",
                target_url=f"{base}/agent/chat/stream",
                methods=("POST",),
                require_auth=True,
                timeout=120.0,
            ),
            ProxyRoute(
                path="/agent/tools",
                target_url=f"{base}/agent/tools",
                methods=("GET",),
                require_auth=True,
                timeout=10.0,
            ),
            ProxyRoute(
                path="/agent/tools/execute",
                target_url=f"{base}/agent/tools/execute",
                methods=("POST",),
                require_auth=True,
                timeout=30.0,
            ),
            ProxyRoute(
                path="/agent/sessions",
                target_url=f"{base}/agent/sessions",
                methods=("GET",),
                require_auth=True,
                timeout=10.0,
            ),
            ProxyRoute(
                path="/agent/status",
                target_url=f"{base}/agent/status",
                methods=("GET",),
                require_auth=True,
                timeout=10.0,
            ),
            # Documents
            ProxyRoute(
                path="/documents",
                target_url=f"{base}/documents",
                methods=("GET", "POST"),
                require_auth=True,
                timeout=60.0,
            ),
            # Workflows
            ProxyRoute(
                path="/workflows",
                target_url=f"{base}/workflows",
                methods=("GET", "POST", "PUT", "DELETE"),
                require_auth=True,
                timeout=30.0,
            ),
            # MCP
            ProxyRoute(
                path="/mcp",
                target_url=f"{base}/mcp",
                methods=("GET", "POST"),
                require_auth=True,
                timeout=30.0,
            ),
        ]

    async def forward_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> dict[str, Any]:
        """Forward a request to the target service.

        Looks up the matching :class:`ProxyRoute` for *path*, then
        issues the request using :mod:`urllib.request` (stdlib only,
        no httpx dependency in Y1).

        Args:
            method: HTTP method (e.g. ``"GET"``, ``"POST"``).
            path: Gateway-side path that maps to a configured route.
            headers: Request headers to forward (dict of str -> str).
            body: Raw request body bytes, or ``None`` for bodyless methods.

        Returns:
            Dictionary with keys:
            - ``status_code`` (int): HTTP response status code.
            - ``headers`` (dict[str, str]): Response headers.
            - ``body`` (str): Response body decoded as UTF-8.

        Raises:
            ValueError: If *path* does not match any configured route or
                *method* is not allowed for the matched route.
            RuntimeError: If the upstream service returns an unexpected
                network error.
        """
        route = self._match_route(path, method)

        req = urllib.request.Request(
            url=route.target_url,
            data=body,
            headers={k: v for k, v in headers.items()},
            method=method.upper(),
        )

        try:
            with urllib.request.urlopen(req, timeout=route.timeout) as resp:
                resp_body = resp.read().decode("utf-8", errors="replace")
                resp_headers: dict[str, str] = dict(resp.headers)
                return {
                    "status_code": resp.status,
                    "headers": resp_headers,
                    "body": resp_body,
                }
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return {
                "status_code": exc.code,
                "headers": dict(exc.headers) if exc.headers else {},
                "body": error_body,
            }
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Upstream service unreachable at '{route.target_url}': {exc.reason}"
            ) from exc

    def _match_route(self, path: str, method: str) -> ProxyRoute:
        """Find the :class:`ProxyRoute` that matches *path* and *method*.

        Args:
            path: Gateway request path.
            method: HTTP method.

        Returns:
            The matching :class:`ProxyRoute`.

        Raises:
            ValueError: If no route matches *path*, or the route does not
                allow *method*.
        """
        normalized_path = path.rstrip("/") or "/"
        for route in self.get_routes():
            if route.path.rstrip("/") == normalized_path:
                if method.upper() not in route.methods:
                    raise ValueError(
                        f"Method {method.upper()} not allowed for path '{path}'. "
                        f"Allowed: {list(route.methods)}"
                    )
                return route
        raise ValueError(
            f"No proxy route configured for path '{path}'"
        )
