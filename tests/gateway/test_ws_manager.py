"""Unit tests for gateway.ws.manager.ConnectionManager."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gateway.ws.manager import ConnectionManager
from gateway.ws.models import WSMessage, WSMessageType

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self, fail_send: bool = False) -> None:
        self.accept = AsyncMock()
        self.send_text = AsyncMock()
        if fail_send:
            self.send_text.side_effect = Exception("Connection closed")
        self.close = AsyncMock()


@pytest.fixture
def manager():
    return ConnectionManager()


@pytest.fixture
def msg():
    return WSMessage(type=WSMessageType.SYSTEM, payload={"text": "hello"}, sender="test")


class TestConnectionLifecycle:
    async def test_connect_accepts_websocket(self, manager):
        ws = MockWebSocket()
        info = await manager.connect(ws, "c1", user_id="u1")
        ws.accept.assert_awaited_once()
        assert info.connection_id == "c1"
        assert info.user_id == "u1"
        assert manager.connection_count == 1

    async def test_connect_multiple(self, manager):
        for i in range(3):
            await manager.connect(MockWebSocket(), f"c{i}")
        assert manager.connection_count == 3

    async def test_disconnect_removes_connection(self, manager):
        await manager.connect(MockWebSocket(), "c1")
        await manager.disconnect("c1")
        assert manager.connection_count == 0

    async def test_disconnect_unknown_id_is_noop(self, manager):
        await manager.disconnect("nonexistent")  # should not raise
        assert manager.connection_count == 0

    async def test_disconnect_cleans_rooms(self, manager):
        await manager.connect(MockWebSocket(), "c1")
        manager.join_room("c1", "room1")
        assert "room1" in manager.room_names
        await manager.disconnect("c1")
        assert "room1" not in manager.room_names


class TestRoomManagement:
    async def test_join_room(self, manager):
        await manager.connect(MockWebSocket(), "c1")
        manager.join_room("c1", "room1")
        assert "room1" in manager.room_names
        assert "c1" in manager.get_room_members("room1")

    async def test_join_room_unknown_connection_ignored(self, manager):
        manager.join_room("nonexistent", "room1")
        assert "room1" not in manager.room_names

    async def test_leave_room(self, manager):
        await manager.connect(MockWebSocket(), "c1")
        manager.join_room("c1", "room1")
        manager.leave_room("c1", "room1")
        assert "room1" not in manager.room_names

    async def test_leave_room_multiple_members(self, manager):
        await manager.connect(MockWebSocket(), "c1")
        await manager.connect(MockWebSocket(), "c2")
        manager.join_room("c1", "room1")
        manager.join_room("c2", "room1")
        manager.leave_room("c1", "room1")
        assert "room1" in manager.room_names
        assert manager.get_room_members("room1") == ["c2"]

    async def test_connection_info_tracks_rooms(self, manager):
        await manager.connect(MockWebSocket(), "c1")
        manager.join_room("c1", "r1")
        manager.join_room("c1", "r2")
        info = manager.get_connection_info("c1")
        assert "r1" in info.rooms
        assert "r2" in info.rooms


class TestMessaging:
    async def test_send_personal(self, manager, msg):
        ws = MockWebSocket()
        await manager.connect(ws, "c1")
        result = await manager.send_personal("c1", msg)
        assert result is True
        ws.send_text.assert_awaited_once()

    async def test_send_personal_unknown_returns_false(self, manager, msg):
        result = await manager.send_personal("nonexistent", msg)
        assert result is False

    async def test_send_personal_failure_returns_false(self, manager, msg):
        ws = MockWebSocket(fail_send=True)
        await manager.connect(ws, "c1")
        result = await manager.send_personal("c1", msg)
        assert result is False

    async def test_broadcast(self, manager, msg):
        for i in range(3):
            await manager.connect(MockWebSocket(), f"c{i}")
        sent = await manager.broadcast(msg)
        assert sent == 3

    async def test_broadcast_disconnects_dead(self, manager, msg):
        await manager.connect(MockWebSocket(), "c1")
        await manager.connect(MockWebSocket(fail_send=True), "c2")
        await manager.connect(MockWebSocket(), "c3")
        sent = await manager.broadcast(msg)
        assert sent == 2
        assert manager.connection_count == 2  # c2 disconnected

    async def test_broadcast_to_room(self, manager, msg):
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        ws3 = MockWebSocket()
        await manager.connect(ws1, "c1")
        await manager.connect(ws2, "c2")
        await manager.connect(ws3, "c3")
        manager.join_room("c1", "room1")
        manager.join_room("c2", "room1")
        sent = await manager.broadcast_to_room("room1", msg)
        assert sent == 2
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()
        ws3.send_text.assert_not_awaited()

    async def test_broadcast_to_room_disconnects_dead(self, manager, msg):
        await manager.connect(MockWebSocket(), "c1")
        await manager.connect(MockWebSocket(fail_send=True), "c2")
        manager.join_room("c1", "room1")
        manager.join_room("c2", "room1")
        sent = await manager.broadcast_to_room("room1", msg)
        assert sent == 1
        assert manager.connection_count == 1  # c2 disconnected

    async def test_broadcast_to_empty_room(self, manager, msg):
        sent = await manager.broadcast_to_room("nonexistent", msg)
        assert sent == 0


class TestHeartbeat:
    async def test_ping_all_removes_dead(self, manager):
        await manager.connect(MockWebSocket(), "c1")
        await manager.connect(MockWebSocket(fail_send=True), "c2")
        dead = await manager._ping_all()
        assert dead == 1
        assert manager.connection_count == 1

    async def test_ping_all_all_healthy(self, manager):
        await manager.connect(MockWebSocket(), "c1")
        await manager.connect(MockWebSocket(), "c2")
        dead = await manager._ping_all()
        assert dead == 0
        assert manager.connection_count == 2


class TestStats:
    async def test_get_stats(self, manager):
        await manager.connect(MockWebSocket(), "c1")
        await manager.connect(MockWebSocket(), "c2")
        manager.join_room("c1", "room1")
        manager.join_room("c2", "room1")
        stats = manager.get_stats()
        assert stats["connections"] == 2
        assert stats["rooms"] == 1
        assert stats["members_per_room"]["room1"] == 2

    async def test_connection_info_none_for_unknown(self, manager):
        assert manager.get_connection_info("nonexistent") is None
