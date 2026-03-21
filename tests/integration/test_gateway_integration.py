"""Integration tests for Gateway + WebSocket module interactions.

Validates:
    - WebSocket ConnectionManager with multiple connections, rooms, and broadcasting
    - Gateway configuration (GatewayConfig)
    - API proxy routing (ProxyRoute, APIProxy)

All tests use @pytest.mark.unit and run without external service dependencies.

Test classes:
    TestWebSocketMultiConnectionIntegration — Multiple WebSocket client scenarios
    TestWSMessageIntegration                — Message serialisation/deserialisation
    TestGatewayConfigIntegration           — GatewayConfig defaults and validation
    TestAPIProxyIntegration                — APIProxy route wiring and lookup
"""

from __future__ import annotations

import asyncio

import pytest

from gateway.ws.models import WSConnectionInfo, WSMessage, WSMessageType
from gateway.ws.manager import ConnectionManager
from gateway.config import GatewayConfig
from gateway.routes.proxy import APIProxy, ProxyRoute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_async(coro):
    """Run an async coroutine in a fresh event loop and return its result."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# MockWebSocket
# ---------------------------------------------------------------------------


class MockWebSocket:
    """Minimal WebSocket stand-in for unit/integration tests.

    Attributes:
        accepted: Set to True after accept() is called.
        sent_messages: Ordered list of raw text frames sent by the server.
    """

    def __init__(self) -> None:
        self.accepted: bool = False
        self.sent_messages: list[str] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.sent_messages.append(data)

    async def receive_text(self) -> str:
        return '{"type": "chat", "payload": {}}'


# ---------------------------------------------------------------------------
# TestWebSocketMultiConnectionIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWebSocketMultiConnectionIntegration:
    """Integration tests: ConnectionManager with multiple WebSocket clients."""

    # ------------------------------------------------------------------
    # 1. Multiple connections lifecycle
    # ------------------------------------------------------------------

    def test_multiple_connections_lifecycle(self):
        """Connect 3 clients, disconnect 1, then disconnect all.

        Verifies connection_count reflects each state transition correctly.
        """

        async def _run():
            manager = ConnectionManager()
            ws1, ws2, ws3 = MockWebSocket(), MockWebSocket(), MockWebSocket()

            await manager.connect(ws1, "c1")
            await manager.connect(ws2, "c2")
            await manager.connect(ws3, "c3")
            assert manager.connection_count == 3

            await manager.disconnect("c1")
            assert manager.connection_count == 2

            await manager.disconnect("c2")
            await manager.disconnect("c3")
            assert manager.connection_count == 0

        run_async(_run())

    # ------------------------------------------------------------------
    # 2. Room-based messaging
    # ------------------------------------------------------------------

    def test_room_based_messaging(self):
        """Only clients in the target room receive a broadcast_to_room message."""

        async def _run():
            manager = ConnectionManager()
            ws1, ws2, ws3 = MockWebSocket(), MockWebSocket(), MockWebSocket()

            await manager.connect(ws1, "c1")
            await manager.connect(ws2, "c2")
            await manager.connect(ws3, "c3")

            manager.join_room("c1", "room-A")
            manager.join_room("c2", "room-A")
            manager.join_room("c3", "room-B")

            msg = WSMessage(type=WSMessageType.CHAT, payload={"text": "hello room-A"})
            await manager.broadcast_to_room("room-A", msg)

            assert len(ws1.sent_messages) == 1
            assert len(ws2.sent_messages) == 1
            assert len(ws3.sent_messages) == 0

        run_async(_run())

    # ------------------------------------------------------------------
    # 3. Broadcast to all
    # ------------------------------------------------------------------

    def test_broadcast_to_all(self):
        """broadcast() sends to every connected client and returns correct count."""

        async def _run():
            manager = ConnectionManager()
            ws1, ws2, ws3 = MockWebSocket(), MockWebSocket(), MockWebSocket()

            await manager.connect(ws1, "c1")
            await manager.connect(ws2, "c2")
            await manager.connect(ws3, "c3")

            msg = WSMessage(type=WSMessageType.NOTIFICATION, payload={"text": "all"})
            count = await manager.broadcast(msg)

            assert count == 3
            assert len(ws1.sent_messages) == 1
            assert len(ws2.sent_messages) == 1
            assert len(ws3.sent_messages) == 1

        run_async(_run())

    # ------------------------------------------------------------------
    # 4. Personal message
    # ------------------------------------------------------------------

    def test_personal_message(self):
        """send_personal delivers to the target client only."""

        async def _run():
            manager = ConnectionManager()
            ws1, ws2 = MockWebSocket(), MockWebSocket()

            await manager.connect(ws1, "c1")
            await manager.connect(ws2, "c2")

            msg = WSMessage(type=WSMessageType.CHAT, payload={"text": "private"})
            result = await manager.send_personal("c1", msg)

            assert result is True
            assert len(ws1.sent_messages) == 1
            assert len(ws2.sent_messages) == 0

        run_async(_run())

    # ------------------------------------------------------------------
    # 5. Join multiple rooms
    # ------------------------------------------------------------------

    def test_join_multiple_rooms(self):
        """A client can join multiple rooms; leaving one keeps the other."""

        async def _run():
            manager = ConnectionManager()
            ws1 = MockWebSocket()

            await manager.connect(ws1, "c1")
            manager.join_room("c1", "room-A")
            manager.join_room("c1", "room-B")

            info = manager.get_connection_info("c1")
            assert info is not None
            assert "room-A" in info.rooms
            assert "room-B" in info.rooms

            manager.leave_room("c1", "room-A")
            info = manager.get_connection_info("c1")
            assert "room-A" not in info.rooms
            assert "room-B" in info.rooms

        run_async(_run())

    # ------------------------------------------------------------------
    # 6. Disconnect cleans rooms
    # ------------------------------------------------------------------

    def test_disconnect_cleans_rooms(self):
        """Disconnecting a client removes its room memberships and empty rooms."""

        async def _run():
            manager = ConnectionManager()
            ws1 = MockWebSocket()

            await manager.connect(ws1, "c1")
            manager.join_room("c1", "room-A")
            manager.join_room("c1", "room-B")

            await manager.disconnect("c1")

            # Rooms should be gone entirely since no members remain
            assert manager.room_names == []

        run_async(_run())

    # ------------------------------------------------------------------
    # 7. Room stats
    # ------------------------------------------------------------------

    def test_room_stats(self):
        """get_stats() reports correct member counts per room."""

        async def _run():
            manager = ConnectionManager()
            ws1, ws2, ws3 = MockWebSocket(), MockWebSocket(), MockWebSocket()

            await manager.connect(ws1, "c1")
            await manager.connect(ws2, "c2")
            await manager.connect(ws3, "c3")

            # c1+c2 → room-A; c2+c3 → room-B
            manager.join_room("c1", "room-A")
            manager.join_room("c2", "room-A")
            manager.join_room("c2", "room-B")
            manager.join_room("c3", "room-B")

            stats = manager.get_stats()
            assert stats["connections"] == 3
            assert stats["rooms"] == 2
            assert stats["members_per_room"]["room-A"] == 2
            assert stats["members_per_room"]["room-B"] == 2

        run_async(_run())

    # ------------------------------------------------------------------
    # 8. Broadcast to nonexistent room
    # ------------------------------------------------------------------

    def test_broadcast_to_nonexistent_room(self):
        """Broadcast to a room that has no members returns 0."""

        async def _run():
            manager = ConnectionManager()
            msg = WSMessage(type=WSMessageType.SYSTEM, payload={})
            count = await manager.broadcast_to_room("ghost-room", msg)
            assert count == 0

        run_async(_run())

    # ------------------------------------------------------------------
    # 9. Send personal to disconnected client
    # ------------------------------------------------------------------

    def test_send_personal_to_disconnected(self):
        """Sending to a disconnected connection_id returns False."""

        async def _run():
            manager = ConnectionManager()
            ws1 = MockWebSocket()

            await manager.connect(ws1, "c1")
            await manager.disconnect("c1")

            msg = WSMessage(type=WSMessageType.CHAT, payload={"text": "ghost"})
            result = await manager.send_personal("c1", msg)

            assert result is False

        run_async(_run())

    # ------------------------------------------------------------------
    # 10. Concurrent join/leave
    # ------------------------------------------------------------------

    def test_concurrent_join_leave(self):
        """After 5 clients join and 3 leave the same room, 2 members remain."""

        async def _run():
            manager = ConnectionManager()
            sockets = [MockWebSocket() for _ in range(5)]
            conn_ids = [f"c{i}" for i in range(5)]

            for ws, cid in zip(sockets, conn_ids):
                await manager.connect(ws, cid)
                manager.join_room(cid, "shared-room")

            # Leave first 3
            for cid in conn_ids[:3]:
                manager.leave_room(cid, "shared-room")

            members = manager.get_room_members("shared-room")
            assert len(members) == 2
            assert set(members) == {"c3", "c4"}

        run_async(_run())


# ---------------------------------------------------------------------------
# TestWSMessageIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWSMessageIntegration:
    """Integration tests: WSMessage serialisation, deserialization, and transport."""

    # ------------------------------------------------------------------
    # 11. Serialisation round-trip
    # ------------------------------------------------------------------

    def test_message_serialization_roundtrip(self):
        """WSMessage → to_json() → from_json() preserves all fields."""
        original = WSMessage(
            type=WSMessageType.KG_UPDATE,
            payload={"node_id": "vessel-001", "action": "created"},
            room="graph-updates",
            sender="user-42",
        )

        json_str = original.to_json()
        restored = WSMessage.from_json(json_str)

        assert restored.type == original.type
        assert restored.payload == original.payload
        assert restored.room == original.room
        assert restored.sender == original.sender
        assert restored.timestamp == pytest.approx(original.timestamp, abs=1e-3)
        assert restored.message_id == original.message_id

    # ------------------------------------------------------------------
    # 12. Broadcast message format
    # ------------------------------------------------------------------

    def test_broadcast_message_format(self):
        """Message received by a client after broadcast is a valid WSMessage."""

        async def _run():
            manager = ConnectionManager()
            ws = MockWebSocket()
            await manager.connect(ws, "c1")

            msg = WSMessage(
                type=WSMessageType.NOTIFICATION,
                payload={"event": "vessel_arrived"},
            )
            await manager.broadcast(msg)

            assert len(ws.sent_messages) == 1
            received = WSMessage.from_json(ws.sent_messages[0])
            assert received.type == WSMessageType.NOTIFICATION
            assert received.payload == {"event": "vessel_arrived"}

        run_async(_run())

    # ------------------------------------------------------------------
    # 13. Multiple message types
    # ------------------------------------------------------------------

    def test_multiple_message_types(self):
        """Each WSMessageType variant is received and parsed correctly."""

        async def _run():
            manager = ConnectionManager()
            ws = MockWebSocket()
            await manager.connect(ws, "c1")

            types_to_send = [
                WSMessageType.CHAT,
                WSMessageType.NOTIFICATION,
                WSMessageType.ERROR,
            ]

            for msg_type in types_to_send:
                msg = WSMessage(type=msg_type, payload={"tag": msg_type.value})
                await manager.send_personal("c1", msg)

            assert len(ws.sent_messages) == 3
            for raw, expected_type in zip(ws.sent_messages, types_to_send):
                received = WSMessage.from_json(raw)
                assert received.type == expected_type
                assert received.payload["tag"] == expected_type.value

        run_async(_run())


# ---------------------------------------------------------------------------
# TestGatewayConfigIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGatewayConfigIntegration:
    """Integration tests: GatewayConfig default values and validation."""

    # ------------------------------------------------------------------
    # 14. Default values
    # ------------------------------------------------------------------

    def test_config_default_values(self):
        """GatewayConfig() initialises with expected defaults."""
        cfg = GatewayConfig()

        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8080
        assert cfg.debug is False
        assert cfg.ws_ping_interval == 30.0
        assert cfg.ws_max_connections == 1000
        assert cfg.rate_limit_per_minute == 300
        assert "http://localhost:5180" in cfg.cors_origins
        assert cfg.api_base_url == "http://localhost:8000"

    # ------------------------------------------------------------------
    # 15. Config from env (direct construction)
    # ------------------------------------------------------------------

    def test_config_from_env(self):
        """GatewayConfig constructed with custom values stores them correctly."""
        cfg = GatewayConfig(
            host="127.0.0.1",
            port=9090,
            debug=True,
            api_base_url="http://backend:8000",
            ws_ping_interval=15.0,
            ws_max_connections=500,
            rate_limit_per_minute=100,
            cors_origins=("http://app.example.com",),
        )

        assert cfg.host == "127.0.0.1"
        assert cfg.port == 9090
        assert cfg.debug is True
        assert cfg.api_base_url == "http://backend:8000"
        assert cfg.ws_ping_interval == 15.0
        assert cfg.ws_max_connections == 500
        assert cfg.rate_limit_per_minute == 100
        assert "http://app.example.com" in cfg.cors_origins

    # ------------------------------------------------------------------
    # 16. Config validation
    # ------------------------------------------------------------------

    def test_config_validation(self):
        """validate() returns no errors for a valid config and reports errors for an invalid one."""
        # Valid config
        valid_cfg = GatewayConfig()
        errors = valid_cfg.validate()
        assert errors == [], f"Unexpected validation errors: {errors}"

        # Invalid config: bad port, bad URL, non-positive ping interval
        invalid_cfg = GatewayConfig(
            port=0,
            api_base_url="not-a-url",
            ws_ping_interval=-1.0,
            ws_max_connections=0,
            rate_limit_per_minute=0,
        )
        errors = invalid_cfg.validate()
        assert len(errors) >= 1

        error_text = " ".join(errors).lower()
        # At least one error should mention port or url or interval
        assert any(
            keyword in error_text
            for keyword in ("port", "url", "interval", "connections", "rate")
        )


# ---------------------------------------------------------------------------
# TestAPIProxyIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAPIProxyIntegration:
    """Integration tests: APIProxy pre-wired routes and route management."""

    # ------------------------------------------------------------------
    # 17. Default routes
    # ------------------------------------------------------------------

    def test_proxy_has_default_routes(self):
        """APIProxy() ships with at least 10 pre-wired routes."""
        proxy = APIProxy()
        routes = proxy.get_routes()

        assert len(routes) >= 10
        # All items should be ProxyRoute instances
        for route in routes:
            assert isinstance(route, ProxyRoute)

    # ------------------------------------------------------------------
    # 18. Route lookup by path
    # ------------------------------------------------------------------

    def test_proxy_route_lookup(self):
        """Looking up a known path returns a ProxyRoute with the correct service."""
        proxy = APIProxy(base_url="http://localhost:8000")
        routes = proxy.get_routes()

        # Build a quick index
        route_by_path = {r.path: r for r in routes}

        # Health route is always present
        assert "/health" in route_by_path
        health_route = route_by_path["/health"]
        assert isinstance(health_route, ProxyRoute)
        assert "localhost:8000" in health_route.target_url

        # Graph query route
        assert "/graph/query" in route_by_path
        gq_route = route_by_path["/graph/query"]
        assert "localhost:8000" in gq_route.target_url

    # ------------------------------------------------------------------
    # 19. Add custom route
    # ------------------------------------------------------------------

    def test_proxy_add_custom_route(self):
        """A custom ProxyRoute added to the route list is retrievable by path."""

        # APIProxy routes are generated dynamically by get_routes(); we extend
        # the class in-place by subclassing and overriding get_routes().
        class ExtendedProxy(APIProxy):
            def get_routes(self):
                base_routes = super().get_routes()
                custom = ProxyRoute(
                    path="/custom/endpoint",
                    target_url=f"{self.base_url}/custom/endpoint",
                    methods=("POST",),
                    require_auth=True,
                    timeout=20.0,
                )
                return base_routes + [custom]

        proxy = ExtendedProxy(base_url="http://localhost:8000")
        routes = proxy.get_routes()
        paths = [r.path for r in routes]

        assert "/custom/endpoint" in paths

        # Verify target service is correct
        custom_route = next(r for r in routes if r.path == "/custom/endpoint")
        assert "localhost:8000" in custom_route.target_url

    # ------------------------------------------------------------------
    # 20. Route methods
    # ------------------------------------------------------------------

    def test_proxy_route_methods(self):
        """Each ProxyRoute declares at least one HTTP method from the standard set."""
        proxy = APIProxy()
        allowed_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

        for route in proxy.get_routes():
            assert len(route.methods) >= 1, (
                f"Route '{route.path}' has no HTTP methods"
            )
            for method in route.methods:
                assert method in allowed_methods, (
                    f"Route '{route.path}' has unexpected method '{method}'"
                )
