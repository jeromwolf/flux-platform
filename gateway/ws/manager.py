"""WebSocket connection manager with room-based messaging."""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from gateway.ws.models import WSConnectionInfo, WSMessage

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with room-based messaging.

    Supports:
    - Connection tracking with unique IDs
    - Room-based grouping (join/leave)
    - Broadcast to all, to room, to specific connection
    - Connection statistics

    All mutations to internal state are protected by a :class:`threading.Lock`
    so the manager is safe to use from concurrent asyncio tasks running in the
    same thread as well as from multiple OS threads (e.g. background workers).

    Example::

        manager = ConnectionManager()

        @app.websocket("/ws/{connection_id}")
        async def ws_endpoint(websocket: WebSocket, connection_id: str):
            info = await manager.connect(websocket, connection_id, user_id="u1")
            manager.join_room(connection_id, "general")
            try:
                while True:
                    data = await websocket.receive_text()
                    msg = WSMessage.from_json(data)
                    await manager.broadcast_to_room("general", msg)
            finally:
                await manager.disconnect(connection_id)
    """

    def __init__(self) -> None:
        # Maps connection_id -> raw websocket object
        self._connections: dict[str, Any] = {}
        # Maps connection_id -> WSConnectionInfo
        self._connection_info: dict[str, WSConnectionInfo] = {}
        # Maps room_name -> set of connection_ids
        self._rooms: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(
        self,
        websocket: Any,
        connection_id: str,
        user_id: str = "",
    ) -> WSConnectionInfo:
        """Register a new WebSocket connection.

        Calls ``websocket.accept()`` and stores the connection under
        *connection_id*.

        Args:
            websocket: The raw WebSocket object (Starlette/FastAPI).
            connection_id: Unique identifier for this connection.
            user_id: Optional authenticated user identifier.

        Returns:
            A :class:`WSConnectionInfo` snapshot for the new connection.
        """
        await websocket.accept()
        info = WSConnectionInfo(connection_id=connection_id, user_id=user_id)
        with self._lock:
            self._connections[connection_id] = websocket
            self._connection_info[connection_id] = info
        logger.info(
            "WebSocket connected: connection_id=%s user_id=%s",
            connection_id,
            user_id or "<anonymous>",
        )
        return info

    async def disconnect(self, connection_id: str) -> None:
        """Remove a connection and clean up all room memberships.

        Args:
            connection_id: The ID of the connection to remove.
        """
        with self._lock:
            if connection_id not in self._connections:
                return
            del self._connections[connection_id]
            del self._connection_info[connection_id]
            # Remove from every room
            empty_rooms: list[str] = []
            for room_name, members in self._rooms.items():
                members.discard(connection_id)
                if not members:
                    empty_rooms.append(room_name)
            for room_name in empty_rooms:
                del self._rooms[room_name]
        logger.info("WebSocket disconnected: connection_id=%s", connection_id)

    # ------------------------------------------------------------------
    # Room management
    # ------------------------------------------------------------------

    def join_room(self, connection_id: str, room: str) -> None:
        """Add a connection to a room.

        Creates the room if it does not yet exist.  If *connection_id* is not
        registered this call is silently ignored.

        Args:
            connection_id: The connection to add.
            room: Room name.
        """
        with self._lock:
            if connection_id not in self._connections:
                logger.warning(
                    "join_room called for unknown connection_id=%s", connection_id
                )
                return
            if room not in self._rooms:
                self._rooms[room] = set()
            self._rooms[room].add(connection_id)

            # Rebuild immutable WSConnectionInfo with updated rooms tuple
            old_info = self._connection_info[connection_id]
            if room not in old_info.rooms:
                self._connection_info[connection_id] = WSConnectionInfo(
                    connection_id=old_info.connection_id,
                    user_id=old_info.user_id,
                    rooms=old_info.rooms + (room,),
                    connected_at=old_info.connected_at,
                )
        logger.debug("connection_id=%s joined room=%s", connection_id, room)

    def leave_room(self, connection_id: str, room: str) -> None:
        """Remove a connection from a room.

        Deletes the room entry if it becomes empty.  If *connection_id* is not
        a member of *room* this call is silently ignored.

        Args:
            connection_id: The connection to remove.
            room: Room name.
        """
        with self._lock:
            if room not in self._rooms:
                return
            self._rooms[room].discard(connection_id)
            if not self._rooms[room]:
                del self._rooms[room]

            # Rebuild immutable WSConnectionInfo without the room
            if connection_id in self._connection_info:
                old_info = self._connection_info[connection_id]
                if room in old_info.rooms:
                    self._connection_info[connection_id] = WSConnectionInfo(
                        connection_id=old_info.connection_id,
                        user_id=old_info.user_id,
                        rooms=tuple(r for r in old_info.rooms if r != room),
                        connected_at=old_info.connected_at,
                    )
        logger.debug("connection_id=%s left room=%s", connection_id, room)

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def send_personal(
        self, connection_id: str, message: WSMessage
    ) -> bool:
        """Send a message to a single connection.

        Args:
            connection_id: Target connection ID.
            message: The message to send.

        Returns:
            ``True`` if the message was delivered, ``False`` if the connection
            was not found or an error occurred.
        """
        with self._lock:
            websocket = self._connections.get(connection_id)

        if websocket is None:
            logger.warning(
                "send_personal: unknown connection_id=%s", connection_id
            )
            return False

        try:
            await websocket.send_text(message.to_json())
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "send_personal failed for connection_id=%s: %s",
                connection_id,
                exc,
            )
            return False

    async def broadcast(self, message: WSMessage) -> int:
        """Send a message to every connected client.

        Failures for individual connections are logged but do not abort the
        broadcast to remaining connections.

        Args:
            message: The message to broadcast.

        Returns:
            Number of connections that received the message successfully.
        """
        with self._lock:
            targets = list(self._connections.items())

        sent = 0
        json_payload = message.to_json()
        for connection_id, websocket in targets:
            try:
                await websocket.send_text(json_payload)
                sent += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "broadcast failed for connection_id=%s: %s",
                    connection_id,
                    exc,
                )
        return sent

    async def broadcast_to_room(self, room: str, message: WSMessage) -> int:
        """Send a message to every member of a room.

        Failures for individual connections are logged but do not abort the
        broadcast to remaining members.

        Args:
            room: Target room name.
            message: The message to broadcast.

        Returns:
            Number of connections that received the message successfully.
            Returns 0 if the room does not exist.
        """
        with self._lock:
            member_ids = set(self._rooms.get(room, set()))
            targets = [
                (cid, ws)
                for cid, ws in self._connections.items()
                if cid in member_ids
            ]

        if not targets:
            return 0

        sent = 0
        json_payload = message.to_json()
        for connection_id, websocket in targets:
            try:
                await websocket.send_text(json_payload)
                sent += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "broadcast_to_room(room=%s) failed for connection_id=%s: %s",
                    room,
                    connection_id,
                    exc,
                )
        return sent

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def connection_count(self) -> int:
        """Total number of active connections."""
        with self._lock:
            return len(self._connections)

    @property
    def room_names(self) -> list[str]:
        """Sorted list of currently active room names."""
        with self._lock:
            return sorted(self._rooms.keys())

    def get_room_members(self, room: str) -> list[str]:
        """Return the list of connection IDs that belong to *room*.

        Args:
            room: Room name to query.

        Returns:
            List of connection IDs (may be empty if room does not exist).
        """
        with self._lock:
            return sorted(self._rooms.get(room, set()))

    def get_connection_info(
        self, connection_id: str
    ) -> Optional[WSConnectionInfo]:
        """Return metadata for a single connection.

        Args:
            connection_id: The connection to look up.

        Returns:
            :class:`WSConnectionInfo` if found, otherwise ``None``.
        """
        with self._lock:
            return self._connection_info.get(connection_id)

    def get_stats(self) -> dict[str, Any]:
        """Return a statistics snapshot of the manager's current state.

        Returns:
            Dictionary with keys:

            - ``connections`` (int): total active connections.
            - ``rooms`` (int): total active rooms.
            - ``members_per_room`` (dict[str, int]): member count per room.
        """
        with self._lock:
            members_per_room = {
                room: len(members) for room, members in self._rooms.items()
            }
            return {
                "connections": len(self._connections),
                "rooms": len(self._rooms),
                "members_per_room": members_per_room,
            }
