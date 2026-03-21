"""Unit tests for WebSocket manager and Gateway app skeleton.

Covers:
    TC-WS01 – WSMessageType
    TC-WS02 – WSMessage
    TC-WS03 – WSConnectionInfo
    TC-WS04 – ConnectionManager
    TC-GW01 – GatewayConfig
    TC-GW02 – WSAuthConfig
    TC-GW03 – WSAuthenticator
    TC-GW04 – ProxyRoute
    TC-GW05 – APIProxy
    TC-GW06 – GatewayApp
"""
from __future__ import annotations

import asyncio
import json

import pytest

from gateway.app import GatewayApp
from gateway.config import GatewayConfig
from gateway.middleware.ws_auth import WSAuthConfig, WSAuthenticator
from gateway.routes.proxy import APIProxy, ProxyRoute
from gateway.ws.manager import ConnectionManager
from gateway.ws.models import WSConnectionInfo, WSMessage, WSMessageType


# ---------------------------------------------------------------------------
# Mock WebSocket
# ---------------------------------------------------------------------------


class MockWebSocket:
    """Minimal WebSocket stub for testing the ConnectionManager."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.accepted: bool = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


# ---------------------------------------------------------------------------
# TC-WS01: WSMessageType
# ---------------------------------------------------------------------------


class TestWSMessageType:
    """TC-WS01: WSMessageType enum tests."""

    @pytest.mark.unit
    def test_all_seven_values_exist(self) -> None:
        """TC-WS01-a: All 7 expected values are present."""
        expected = {"CHAT", "NOTIFICATION", "KG_UPDATE", "SYSTEM", "ERROR", "PING", "PONG"}
        actual = {member.name for member in WSMessageType}
        assert actual == expected

    @pytest.mark.unit
    def test_values_are_strings(self) -> None:
        """TC-WS01-b: Every enum value is a str instance."""
        for member in WSMessageType:
            assert isinstance(member.value, str), (
                f"{member.name}.value should be str, got {type(member.value)}"
            )


# ---------------------------------------------------------------------------
# TC-WS02: WSMessage
# ---------------------------------------------------------------------------


class TestWSMessage:
    """TC-WS02: WSMessage serialisation and construction tests."""

    @pytest.mark.unit
    def test_to_json_produces_valid_json_with_required_keys(self) -> None:
        """TC-WS02-a: to_json() produces valid JSON with all expected keys."""
        msg = WSMessage(type=WSMessageType.CHAT, payload={"text": "hello"}, room="general")
        raw = msg.to_json()
        data = json.loads(raw)
        for key in ("type", "payload", "room", "sender", "timestamp", "message_id"):
            assert key in data, f"Key '{key}' missing from to_json() output"

    @pytest.mark.unit
    def test_from_json_round_trip(self) -> None:
        """TC-WS02-b: from_json(to_json(msg)) preserves all fields."""
        original = WSMessage(
            type=WSMessageType.NOTIFICATION,
            payload={"level": "info"},
            room="ops",
            sender="u-42",
        )
        restored = WSMessage.from_json(original.to_json())
        assert restored.type == original.type
        assert restored.payload == original.payload
        assert restored.room == original.room
        assert restored.sender == original.sender
        assert restored.timestamp == original.timestamp
        assert restored.message_id == original.message_id

    @pytest.mark.unit
    def test_from_json_invalid_type_raises_value_error(self) -> None:
        """TC-WS02-c: from_json() with an unknown type value raises ValueError."""
        bad = json.dumps({"type": "UNKNOWN_TYPE", "payload": {}, "room": "", "sender": ""})
        with pytest.raises(ValueError, match="Unknown WSMessageType"):
            WSMessage.from_json(bad)

    @pytest.mark.unit
    def test_from_json_invalid_json_raises_value_error(self) -> None:
        """TC-WS02-d: from_json() with malformed JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON payload"):
            WSMessage.from_json("{not valid json")

    @pytest.mark.unit
    def test_default_values(self) -> None:
        """TC-WS02-e: payload, room, and sender default to empty values."""
        msg = WSMessage(type=WSMessageType.PING)
        assert msg.payload == {}
        assert msg.room == ""
        assert msg.sender == ""

    @pytest.mark.unit
    def test_message_id_auto_generated_and_not_empty(self) -> None:
        """TC-WS02-f: message_id is auto-generated and non-empty."""
        msg = WSMessage(type=WSMessageType.PONG)
        assert msg.message_id
        assert len(msg.message_id) > 0


# ---------------------------------------------------------------------------
# TC-WS03: WSConnectionInfo
# ---------------------------------------------------------------------------


class TestWSConnectionInfo:
    """TC-WS03: WSConnectionInfo construction and immutability tests."""

    @pytest.mark.unit
    def test_construction_with_required_fields(self) -> None:
        """TC-WS03-a: Can be constructed with only connection_id."""
        info = WSConnectionInfo(connection_id="conn-1")
        assert info.connection_id == "conn-1"

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        """TC-WS03-b: Attempting to mutate a field raises FrozenInstanceError."""
        from dataclasses import FrozenInstanceError

        info = WSConnectionInfo(connection_id="conn-2")
        with pytest.raises(FrozenInstanceError):
            info.connection_id = "changed"  # type: ignore[misc]

    @pytest.mark.unit
    def test_default_rooms_is_empty_tuple(self) -> None:
        """TC-WS03-c: Default rooms attribute is an empty tuple."""
        info = WSConnectionInfo(connection_id="conn-3")
        assert info.rooms == ()
        assert isinstance(info.rooms, tuple)


# ---------------------------------------------------------------------------
# TC-WS04: ConnectionManager
# ---------------------------------------------------------------------------


class TestConnectionManager:
    """TC-WS04: ConnectionManager lifecycle and messaging tests."""

    @pytest.mark.unit
    def test_starts_empty(self) -> None:
        """TC-WS04-a: A new manager has zero connections."""
        mgr = ConnectionManager()
        assert mgr.connection_count == 0

    @pytest.mark.unit
    def test_connect_adds_connection(self) -> None:
        """TC-WS04-b: connect() increments connection_count and accepts the socket."""
        mgr = ConnectionManager()
        ws = MockWebSocket()

        async def _run() -> None:
            await mgr.connect(ws, "c1", user_id="u1")

        asyncio.new_event_loop().run_until_complete(_run())
        assert mgr.connection_count == 1
        assert ws.accepted is True

    @pytest.mark.unit
    def test_disconnect_removes_connection(self) -> None:
        """TC-WS04-c: disconnect() removes the connection so count drops back to 0."""
        mgr = ConnectionManager()
        ws = MockWebSocket()

        async def _run() -> None:
            await mgr.connect(ws, "c2")
            await mgr.disconnect("c2")

        asyncio.new_event_loop().run_until_complete(_run())
        assert mgr.connection_count == 0

    @pytest.mark.unit
    def test_join_room_and_leave_room(self) -> None:
        """TC-WS04-d: join_room and leave_room work correctly."""
        mgr = ConnectionManager()
        ws = MockWebSocket()

        async def _run() -> None:
            await mgr.connect(ws, "c3")
            mgr.join_room("c3", "alpha")
            assert "alpha" in mgr.room_names
            mgr.leave_room("c3", "alpha")
            assert "alpha" not in mgr.room_names

        asyncio.new_event_loop().run_until_complete(_run())

    @pytest.mark.unit
    def test_get_room_members_returns_connection_ids(self) -> None:
        """TC-WS04-e: get_room_members() returns the correct connection IDs."""
        mgr = ConnectionManager()
        ws_a = MockWebSocket()
        ws_b = MockWebSocket()

        async def _run() -> None:
            await mgr.connect(ws_a, "ca")
            await mgr.connect(ws_b, "cb")
            mgr.join_room("ca", "beta")
            mgr.join_room("cb", "beta")

        asyncio.new_event_loop().run_until_complete(_run())
        members = mgr.get_room_members("beta")
        assert set(members) == {"ca", "cb"}

    @pytest.mark.unit
    def test_send_personal_calls_send_text(self) -> None:
        """TC-WS04-f: send_personal() delivers the serialised message to the socket."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        msg = WSMessage(type=WSMessageType.CHAT, payload={"text": "hi"})

        async def _run() -> None:
            await mgr.connect(ws, "c4")
            result = await mgr.send_personal("c4", msg)
            assert result is True

        asyncio.new_event_loop().run_until_complete(_run())
        assert len(ws.sent) == 1
        sent_data = json.loads(ws.sent[0])
        assert sent_data["type"] == "chat"

    @pytest.mark.unit
    def test_broadcast_sends_to_all_connections(self) -> None:
        """TC-WS04-g: broadcast() sends the message to every connected socket."""
        mgr = ConnectionManager()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        msg = WSMessage(type=WSMessageType.SYSTEM, payload={"notice": "shutdown"})

        async def _run() -> None:
            await mgr.connect(ws1, "d1")
            await mgr.connect(ws2, "d2")
            sent = await mgr.broadcast(msg)
            assert sent == 2

        asyncio.new_event_loop().run_until_complete(_run())
        assert len(ws1.sent) == 1
        assert len(ws2.sent) == 1

    @pytest.mark.unit
    def test_broadcast_to_room_only_sends_to_room_members(self) -> None:
        """TC-WS04-h: broadcast_to_room() skips connections not in the room."""
        mgr = ConnectionManager()
        ws_in = MockWebSocket()
        ws_out = MockWebSocket()
        msg = WSMessage(type=WSMessageType.KG_UPDATE)

        async def _run() -> None:
            await mgr.connect(ws_in, "in1")
            await mgr.connect(ws_out, "out1")
            mgr.join_room("in1", "kg-room")
            sent = await mgr.broadcast_to_room("kg-room", msg)
            assert sent == 1

        asyncio.new_event_loop().run_until_complete(_run())
        assert len(ws_in.sent) == 1
        assert len(ws_out.sent) == 0

    @pytest.mark.unit
    def test_get_stats_returns_dict_with_counts(self) -> None:
        """TC-WS04-i: get_stats() returns a dict with 'connections' and 'rooms' keys."""
        mgr = ConnectionManager()
        ws = MockWebSocket()

        async def _run() -> None:
            await mgr.connect(ws, "s1")
            mgr.join_room("s1", "stats-room")

        asyncio.new_event_loop().run_until_complete(_run())
        stats = mgr.get_stats()
        assert isinstance(stats, dict)
        assert "connections" in stats
        assert "rooms" in stats
        assert stats["connections"] == 1
        assert stats["rooms"] == 1

    @pytest.mark.unit
    def test_room_names_property(self) -> None:
        """TC-WS04-j: room_names returns a list of active room names."""
        mgr = ConnectionManager()
        ws = MockWebSocket()

        async def _run() -> None:
            await mgr.connect(ws, "r1")
            mgr.join_room("r1", "room-x")
            mgr.join_room("r1", "room-y")

        asyncio.new_event_loop().run_until_complete(_run())
        names = mgr.room_names
        assert isinstance(names, list)
        assert "room-x" in names
        assert "room-y" in names


# ---------------------------------------------------------------------------
# TC-GW01: GatewayConfig
# ---------------------------------------------------------------------------


class TestGatewayConfig:
    """TC-GW01: GatewayConfig defaults, env loading, and validation."""

    @pytest.mark.unit
    def test_default_values(self) -> None:
        """TC-GW01-a: Default field values match documented defaults."""
        cfg = GatewayConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8080
        assert cfg.api_base_url == "http://localhost:8000"
        assert cfg.ws_ping_interval == 30.0
        assert cfg.ws_max_connections == 1000
        assert cfg.rate_limit_per_minute == 300
        assert cfg.debug is False

    @pytest.mark.unit
    def test_from_env_reads_gateway_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-GW01-b: from_env() reads GATEWAY_* environment variables."""
        monkeypatch.setenv("GATEWAY_HOST", "127.0.0.1")
        monkeypatch.setenv("GATEWAY_PORT", "9090")
        monkeypatch.setenv("GATEWAY_API_BASE_URL", "http://backend:8000")
        monkeypatch.setenv("GATEWAY_WS_PING_INTERVAL", "60.0")
        monkeypatch.setenv("GATEWAY_WS_MAX_CONNECTIONS", "500")
        monkeypatch.setenv("GATEWAY_RATE_LIMIT_PER_MINUTE", "100")
        monkeypatch.setenv("GATEWAY_DEBUG", "true")

        cfg = GatewayConfig.from_env()
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 9090
        assert cfg.api_base_url == "http://backend:8000"
        assert cfg.ws_ping_interval == 60.0
        assert cfg.ws_max_connections == 500
        assert cfg.rate_limit_per_minute == 100
        assert cfg.debug is True

    @pytest.mark.unit
    def test_validate_catches_invalid_port_zero(self) -> None:
        """TC-GW01-c: validate() returns errors for port=0."""
        from dataclasses import replace

        cfg = replace(GatewayConfig(), port=0)
        errors = cfg.validate()
        assert any("port" in e for e in errors)

    @pytest.mark.unit
    def test_validate_catches_invalid_port_too_high(self) -> None:
        """TC-GW01-c: validate() returns errors for port=99999."""
        from dataclasses import replace

        cfg = replace(GatewayConfig(), port=99999)
        errors = cfg.validate()
        assert any("port" in e for e in errors)

    @pytest.mark.unit
    def test_validate_catches_invalid_api_base_url(self) -> None:
        """TC-GW01-d: validate() returns errors for a non-URL api_base_url."""
        from dataclasses import replace

        cfg = replace(GatewayConfig(), api_base_url="not-a-url")
        errors = cfg.validate()
        assert any("api_base_url" in e for e in errors)

    @pytest.mark.unit
    def test_validate_returns_empty_list_for_valid_config(self) -> None:
        """TC-GW01-e: validate() returns [] for a fully valid configuration."""
        cfg = GatewayConfig()
        errors = cfg.validate()
        assert errors == []


# ---------------------------------------------------------------------------
# TC-GW02: WSAuthConfig
# ---------------------------------------------------------------------------


class TestWSAuthConfig:
    """TC-GW02: WSAuthConfig defaults and env loading."""

    @pytest.mark.unit
    def test_default_values(self) -> None:
        """TC-GW02-a: Default field values match documented defaults."""
        cfg = WSAuthConfig()
        assert cfg.require_auth is True
        assert cfg.token_param == "token"
        assert cfg.secret_key == ""

    @pytest.mark.unit
    def test_from_env_reads_gateway_ws_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-GW02-b: from_env() reads GATEWAY_WS_* environment variables."""
        monkeypatch.setenv("GATEWAY_WS_REQUIRE_AUTH", "false")
        monkeypatch.setenv("GATEWAY_WS_TOKEN_PARAM", "auth_token")
        monkeypatch.setenv("GATEWAY_WS_SECRET_KEY", "super-secret")

        cfg = WSAuthConfig.from_env()
        assert cfg.require_auth is False
        assert cfg.token_param == "auth_token"
        assert cfg.secret_key == "super-secret"


# ---------------------------------------------------------------------------
# TC-GW03: WSAuthenticator
# ---------------------------------------------------------------------------


class TestWSAuthenticator:
    """TC-GW03: WSAuthenticator token extraction and JWT validation."""

    @pytest.mark.unit
    def test_extract_token_from_query_parses_token_param(self) -> None:
        """TC-GW03-a: extract_token_from_query parses 'token=abc123'."""
        cfg = WSAuthConfig(secret_key="secret")
        auth = WSAuthenticator(config=cfg)
        token = auth.extract_token_from_query("token=abc123")
        assert token == "abc123"

    @pytest.mark.unit
    def test_extract_token_from_query_raises_when_no_token_param(self) -> None:
        """TC-GW03-b: extract_token_from_query raises ValueError when token param absent."""
        cfg = WSAuthConfig(secret_key="secret")
        auth = WSAuthenticator(config=cfg)
        with pytest.raises(ValueError):
            auth.extract_token_from_query("foo=bar&baz=qux")

    @pytest.mark.unit
    def test_authenticate_with_valid_hs256_jwt(self) -> None:
        """TC-GW03-c: authenticate() decodes a valid HS256 JWT and returns claims."""
        import jwt as pyjwt

        secret = "test-secret-key"
        payload = {"sub": "user-123", "name": "Test User"}
        token = pyjwt.encode(payload, secret, algorithm="HS256")

        cfg = WSAuthConfig(secret_key=secret)
        auth = WSAuthenticator(config=cfg)
        claims = auth.authenticate(token)
        assert claims["sub"] == "user-123"
        assert claims["name"] == "Test User"

    @pytest.mark.unit
    def test_authenticate_with_invalid_token_raises_value_error(self) -> None:
        """TC-GW03-d: authenticate() raises ValueError for an invalid token."""
        cfg = WSAuthConfig(secret_key="correct-secret")
        auth = WSAuthenticator(config=cfg)
        with pytest.raises(ValueError):
            auth.authenticate("not.a.valid.jwt.token")


# ---------------------------------------------------------------------------
# TC-GW04: ProxyRoute
# ---------------------------------------------------------------------------


class TestProxyRoute:
    """TC-GW04: ProxyRoute construction and immutability."""

    @pytest.mark.unit
    def test_construction_with_required_fields(self) -> None:
        """TC-GW04-a: ProxyRoute can be constructed with path and target_url."""
        route = ProxyRoute(path="/api/test", target_url="http://backend/api/test")
        assert route.path == "/api/test"
        assert route.target_url == "http://backend/api/test"

    @pytest.mark.unit
    def test_default_methods_is_get_tuple(self) -> None:
        """TC-GW04-b: Default methods is ('GET',)."""
        route = ProxyRoute(path="/x", target_url="http://b/x")
        assert route.methods == ("GET",)

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """TC-GW04-c: ProxyRoute is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError

        route = ProxyRoute(path="/y", target_url="http://b/y")
        with pytest.raises(FrozenInstanceError):
            route.path = "/z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-GW05: APIProxy
# ---------------------------------------------------------------------------


class TestAPIProxy:
    """TC-GW05: APIProxy route list validation."""

    @pytest.mark.unit
    def test_get_routes_returns_non_empty_list(self) -> None:
        """TC-GW05-a: get_routes() returns at least one route."""
        proxy = APIProxy(base_url="http://localhost:8000")
        routes = proxy.get_routes()
        assert isinstance(routes, list)
        assert len(routes) > 0

    @pytest.mark.unit
    def test_all_routes_have_paths_starting_with_slash(self) -> None:
        """TC-GW05-b: Every route path starts with '/'."""
        proxy = APIProxy(base_url="http://localhost:8000")
        for route in proxy.get_routes():
            assert route.path.startswith("/"), (
                f"Route path '{route.path}' does not start with '/'"
            )

    @pytest.mark.unit
    def test_health_route_exists_and_no_auth_required(self) -> None:
        """TC-GW05-c: A /health route exists and does not require authentication."""
        proxy = APIProxy(base_url="http://localhost:8000")
        health_routes = [r for r in proxy.get_routes() if r.path == "/health"]
        assert health_routes, "No /health route found in proxy routes"
        health_route = health_routes[0]
        assert health_route.require_auth is False


# ---------------------------------------------------------------------------
# TC-GW06: GatewayApp
# ---------------------------------------------------------------------------


class TestGatewayApp:
    """TC-GW06: GatewayApp factory and descriptor."""

    @pytest.mark.unit
    def test_create_returns_gateway_app_with_all_components(self) -> None:
        """TC-GW06-a: GatewayApp.create() returns an instance with all components."""
        cfg = GatewayConfig()
        app = GatewayApp.create(config=cfg)
        assert isinstance(app, GatewayApp)
        assert app.config is cfg
        assert isinstance(app.proxy, APIProxy)
        assert isinstance(app.ws_auth, WSAuthenticator)
        assert isinstance(app.routes, list)
        assert len(app.routes) > 0

    @pytest.mark.unit
    def test_describe_returns_dict_with_config_and_routes_count(self) -> None:
        """TC-GW06-b: describe() returns a dict including config fields and routes list."""
        cfg = GatewayConfig()
        app = GatewayApp.create(config=cfg)
        description = app.describe()
        assert isinstance(description, dict)
        assert "host" in description
        assert "port" in description
        assert "api_base_url" in description
        assert "routes" in description
        assert isinstance(description["routes"], list)
        assert len(description["routes"]) > 0
