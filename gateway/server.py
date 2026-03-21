"""IMSP API Gateway — FastAPI ASGI server.

Usage:
    uvicorn gateway.server:app --port 8080
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from gateway.app import create_gateway_app, GatewayApp
from gateway.config import GatewayConfig
from gateway.ws.manager import ConnectionManager
from gateway.ws.models import WSMessage, WSMessageType

logger = logging.getLogger(__name__)

# Singleton instances
_gateway: GatewayApp | None = None
_ws_manager = ConnectionManager()


def get_gateway() -> GatewayApp:
    global _gateway
    if _gateway is None:
        _gateway = create_gateway_app()
    return _gateway


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("IMSP Gateway starting — port %s", get_gateway().config.port)
    yield
    logger.info("IMSP Gateway shutting down")


def create_server(config: GatewayConfig | None = None) -> FastAPI:
    global _gateway
    _gateway = create_gateway_app(config)
    gw = _gateway

    app = FastAPI(
        title="IMSP API Gateway",
        version="0.1.0",
        description="API Gateway for the Interactive Maritime Service Platform",
        lifespan=_lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(gw.config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Keycloak JWT middleware (optional — skipped if not configured)
    keycloak_url = os.getenv("KEYCLOAK_URL", "")
    if keycloak_url:
        from gateway.middleware.keycloak import KeycloakMiddleware
        app.add_middleware(
            KeycloakMiddleware,
            keycloak_url=keycloak_url,
            realm=os.getenv("KEYCLOAK_REALM", "imsp"),
            client_id=os.getenv("KEYCLOAK_CLIENT_ID", "imsp-api"),
            public_paths=["/health", "/ready", "/docs", "/openapi.json", "/ws"],
        )

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
        return {"status": "ready"}

    # --- API Proxy endpoints ---
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_api(request: Request, path: str):
        """Proxy all /api/* requests to the core KG API backend."""
        proxy = gw.proxy
        method = request.method

        # Build target URL
        target_url = f"{proxy.base_url}/api/{path}"
        query = str(request.query_params)
        if query:
            target_url = f"{target_url}?{query}"

        # Forward headers
        headers = dict(request.headers)
        headers.pop("host", None)

        # Forward body
        body = await request.body() if method in ("POST", "PUT", "PATCH") else None

        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            url=target_url,
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                resp_body = resp.read()
                resp_headers = dict(resp.headers)
                content_type = resp_headers.get("Content-Type", "application/json")
                return Response(
                    content=resp_body,
                    status_code=resp.status,
                    media_type=content_type,
                )
        except urllib.error.HTTPError as exc:
            error_body = exc.read() if exc.fp else b""
            return Response(
                content=error_body,
                status_code=exc.code,
                media_type="application/json",
            )
        except urllib.error.URLError:
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
