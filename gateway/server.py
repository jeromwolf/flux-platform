"""IMSP API Gateway — FastAPI ASGI server.

Usage:
    uvicorn gateway.server:app --port 8080
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from gateway.app import create_gateway_app, GatewayApp
from gateway.config import GatewayConfig
from gateway.middleware.access_log import AccessLogMiddleware
from gateway.middleware.cache import ResponseCache
from gateway.middleware.circuit_breaker import CircuitBreaker
from gateway.middleware.metrics import gateway_metrics
from gateway.middleware.rate_limit import RateLimitConfig, RateLimitMiddleware
from gateway.middleware.request_id import RequestIDMiddleware
from gateway.middleware.tracing import GatewayTracingMiddleware
from gateway.ws.manager import ConnectionManager
from gateway.ws.models import WSMessage, WSMessageType

logger = logging.getLogger(__name__)

# Singleton instances
_gateway: GatewayApp | None = None
_ws_manager = ConnectionManager()

# Shared async HTTP client (created in lifespan, closed on shutdown)
_http_client: httpx.AsyncClient | None = None

# Circuit breaker for upstream API proxy
_circuit_breaker = CircuitBreaker()

# Response cache for GET requests
_response_cache = ResponseCache(ttl=60.0, max_entries=256)


def get_gateway() -> GatewayApp:
    global _gateway
    if _gateway is None:
        _gateway = create_gateway_app()
    return _gateway


def get_http_client() -> httpx.AsyncClient:
    """Return the shared :class:`httpx.AsyncClient` instance.

    Raises:
        RuntimeError: If called before the lifespan startup has completed.
    """
    if _http_client is None:
        raise RuntimeError("HTTP client not initialised — call create_server() first")
    return _http_client


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    import asyncio

    global _http_client

    gw = get_gateway()
    logger.info("IMSP Gateway starting — port %s", gw.config.port)

    # httpx AsyncClient 초기화 — 공유 커넥션 풀
    # Only create if not already set (allows tests to inject a mock client before startup)
    _client_owned = _http_client is None
    if _client_owned:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=30.0,
                pool=5.0,
            ),
            follow_redirects=True,
        )
        logger.info("HTTP client initialised")
    else:
        logger.info("HTTP client already set — using existing instance")

    # Start WebSocket heartbeat background task
    heartbeat_task = asyncio.create_task(
        _ws_manager.start_heartbeat(interval=gw.config.ws_ping_interval)
    )
    logger.info("WebSocket heartbeat task started")

    yield

    # Cancel heartbeat task
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass

    # 종료 시 클라이언트 닫기 — only close if we created it
    if _client_owned and _http_client is not None:
        await _http_client.aclose()
        _http_client = None
    logger.info("IMSP Gateway shutting down")


def create_server(config: GatewayConfig | None = None) -> FastAPI:
    global _gateway, _http_client
    _gateway = create_gateway_app(config)
    gw = _gateway

    app = FastAPI(
        title="IMSP API Gateway",
        version="0.1.0",
        description="API Gateway for the Interactive Maritime Service Platform",
        lifespan=_lifespan,
    )

    # Middleware registration order note:
    # Starlette applies add_middleware in LIFO order — last added = outermost (executes first).
    # To make AccessLogMiddleware innermost (executes last on request path, sees all prior state),
    # it must be registered FIRST before CORS, RequestID, Tracing, etc.

    # 0. Structured JSON access logging — registered first so it runs innermost,
    #    after RequestID and Tracing have set request.state.request_id / trace_id.
    app.add_middleware(AccessLogMiddleware)

    # 1. CORS (가장 바깥쪽 — 나중에 등록, LIFO 이므로 최외곽에 위치)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(gw.config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-KG-Project"],
    )

    # 2. Request ID
    app.add_middleware(RequestIDMiddleware)

    # 3. Distributed Tracing (W3C Traceparent + Zipkin export)
    app.add_middleware(GatewayTracingMiddleware)

    # 4. Rate Limit
    rate_config = RateLimitConfig(
        requests_per_minute=gw.config.rate_limit_per_minute,
        exclude_paths=["/health", "/ready", "/docs", "/openapi.json"],
    )
    app.add_middleware(RateLimitMiddleware, config=rate_config)

    # 5. Keycloak JWT middleware (optional — skipped if not configured)
    keycloak_url = os.getenv("KEYCLOAK_URL", "")
    if keycloak_url:
        from gateway.middleware.keycloak import KeycloakMiddleware
        app.add_middleware(
            KeycloakMiddleware,
            keycloak_url=keycloak_url,
            realm=os.getenv("KEYCLOAK_REALM", "imsp"),
            client_id=os.getenv("KEYCLOAK_CLIENT_ID", "imsp-api"),
            public_paths=["/health", "/ready", "/metrics", "/docs", "/openapi.json", "/ws"],
        )

    # 7. Metrics request-tracking middleware
    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        # Skip recording metrics for the /metrics scrape endpoint itself
        if request.url.path != "/metrics":
            gateway_metrics.record_request(duration, response.status_code)
        return response

    # --- Health endpoints ---
    @app.get("/health")
    async def health():
        stats = _ws_manager.get_stats()
        return {
            "status": "healthy",
            "service": "imsp-gateway",
            "websocket": stats,
        }

    @app.get("/ready")
    async def readiness():
        """Readiness probe — checks gateway and upstream Core API health."""
        upstream_url = gw.config.api_base_url + "/api/v1/health"
        upstream_status = "unreachable"
        http_status = 503

        try:
            client = get_http_client()
            resp = await client.get(upstream_url, timeout=5.0)
            if resp.status_code < 500:
                upstream_status = "healthy"
                http_status = 200
        except Exception:
            logger.debug("Upstream health check failed", exc_info=True)

        body = {"status": "ready" if http_status == 200 else "degraded", "upstream": upstream_status}
        return Response(
            content=json.dumps(body),
            status_code=http_status,
            media_type="application/json",
        )

    # --- Metrics endpoint ---
    @app.get("/metrics")
    async def metrics():
        """Prometheus-format metrics scrape endpoint."""
        payload = gateway_metrics.to_prometheus(
            active_connections=_ws_manager.connection_count
        )
        return PlainTextResponse(content=payload, media_type="text/plain; version=0.0.4")

    # Paths that must never be cached (infra probes)
    _CACHE_SKIP_PATHS = ("/health", "/ready", "/metrics")

    # --- API Proxy endpoints ---
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_api(request: Request, path: str):
        """Proxy all /api/* requests to the core KG API backend using httpx."""
        proxy = gw.proxy
        method = request.method
        req_path = request.url.path
        query = str(request.query_params)

        # POST/PUT/DELETE/PATCH invalidate the cache so stale reads are evicted
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            _response_cache.invalidate()

        # Build target URL
        target_url = f"{proxy.base_url}/api/{path}"
        if query:
            target_url = f"{target_url}?{query}"

        # Serve from cache for GET requests (skip infra probe paths)
        skip_cache = any(skip in req_path for skip in _CACHE_SKIP_PATHS)
        if method == "GET" and not skip_cache:
            cached = _response_cache.get(req_path, query)
            if cached is not None:
                return Response(
                    content=cached.body,
                    status_code=cached.status_code,
                    media_type=cached.headers.get("content-type", "application/json"),
                    headers={**cached.headers, "X-Cache": "HIT"},
                )

        # Forward headers (drop hop-by-hop headers)
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length", "transfer-encoding")
        }

        # Forward body for mutation methods
        body = await request.body() if method in ("POST", "PUT", "PATCH") else None

        # Circuit breaker check — reject early if upstream is known-bad
        if not _circuit_breaker.allow_request():
            logger.warning("Circuit breaker OPEN — rejecting proxy request to %s", target_url)
            return Response(
                content='{"error": "Service temporarily unavailable", "detail": "Circuit breaker is open"}',
                status_code=503,
                media_type="application/json",
            )

        client = get_http_client()

        try:
            resp = await client.request(
                method=method,
                url=target_url,
                headers=headers,
                content=body,
            )
            content_type = resp.headers.get("content-type", "application/json")

            # 5xx from upstream counts as a failure; 2xx/4xx are client-driven successes
            if resp.status_code >= 500:
                _circuit_breaker.record_failure()
            else:
                _circuit_breaker.record_success()

            # Store successful GET responses in cache
            if method == "GET" and not skip_cache:
                _response_cache.put(
                    path=req_path,
                    query=query,
                    body=resp.content,
                    status_code=resp.status_code,
                    headers={"content-type": content_type},
                )

            cache_header = "MISS" if method == "GET" and not skip_cache else None
            extra_headers: dict[str, str] = {}
            if cache_header:
                extra_headers["X-Cache"] = cache_header

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=content_type,
                headers=extra_headers if extra_headers else None,
            )
        except httpx.HTTPStatusError as exc:
            _circuit_breaker.record_failure()
            return Response(
                content=exc.response.content,
                status_code=exc.response.status_code,
                media_type="application/json",
            )
        except httpx.RequestError:
            _circuit_breaker.record_failure()
            raise HTTPException(status_code=502, detail="Backend service unavailable")

    # --- WebSocket endpoint ---
    @app.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        token: str = Query(default=""),
    ):
        connection_id = uuid4().hex[:12]
        user_id = ""

        # Authenticate if token provided
        if token:
            try:
                claims = gw.ws_auth.authenticate(token)
                user_id = claims.get("sub", "")
            except ValueError as exc:
                await websocket.close(code=4001, reason=str(exc))
                return

        info = await _ws_manager.connect(websocket, connection_id, user_id=user_id)

        # Send welcome message
        welcome = WSMessage(
            type=WSMessageType.SYSTEM,
            payload={"message": "Connected to IMSP Gateway", "connection_id": connection_id},
            sender="system",
        )
        await _ws_manager.send_personal(connection_id, welcome)

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = WSMessage.from_json(data)
                except (ValueError, KeyError) as exc:
                    error_msg = WSMessage(
                        type=WSMessageType.ERROR,
                        payload={"error": str(exc)},
                        sender="system",
                    )
                    await _ws_manager.send_personal(connection_id, error_msg)
                    continue

                # Handle ping
                if msg.type == WSMessageType.PING:
                    pong = WSMessage(type=WSMessageType.PONG, sender="system")
                    await _ws_manager.send_personal(connection_id, pong)
                    continue

                # Handle agent query — forward to agent chat API and return response
                if msg.type == WSMessageType.AGENT_QUERY:
                    try:
                        client = get_http_client()
                        agent_resp = await client.post(
                            f"{gw.config.api_base_url}/api/v1/agent/chat",
                            json={
                                "message": msg.payload.get("text", ""),
                                "mode": msg.payload.get("mode", "react"),
                            },
                        )
                        result = agent_resp.json()
                        response_msg = WSMessage(
                            type=WSMessageType.AGENT_RESPONSE,
                            payload=result,
                            room=msg.room,
                            sender="system",
                        )
                        await _ws_manager.send_personal(connection_id, response_msg)
                    except Exception as exc:
                        error_msg = WSMessage(
                            type=WSMessageType.ERROR,
                            payload={"error": str(exc)},
                            sender="system",
                        )
                        await _ws_manager.send_personal(connection_id, error_msg)
                    continue

                # Route to room or broadcast
                if msg.room:
                    _ws_manager.join_room(connection_id, msg.room)
                    await _ws_manager.broadcast_to_room(msg.room, msg)
                else:
                    await _ws_manager.broadcast(msg)

        except WebSocketDisconnect:
            await _ws_manager.disconnect(connection_id)

    # --- WebSocket room management ---
    @app.post("/ws/rooms/{room}/join")
    async def join_room(room: str, connection_id: str = Query(...)):
        _ws_manager.join_room(connection_id, room)
        return {"status": "joined", "room": room}

    @app.post("/ws/rooms/{room}/leave")
    async def leave_room(room: str, connection_id: str = Query(...)):
        _ws_manager.leave_room(connection_id, room)
        return {"status": "left", "room": room}

    @app.get("/ws/stats")
    async def ws_stats():
        return _ws_manager.get_stats()

    return app


# Module-level instance for uvicorn
app = create_server()
