"""WebSocket message models and connection metadata."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class WSMessageType(str, Enum):
    """Types of WebSocket messages exchanged between server and clients."""

    CHAT = "chat"
    NOTIFICATION = "notification"
    KG_UPDATE = "kg_update"
    SYSTEM = "system"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    AGENT_QUERY = "agent_query"
    AGENT_RESPONSE = "agent_response"


@dataclass(frozen=True)
class WSMessage:
    """Immutable WebSocket message envelope.

    Attributes:
        type: Message type discriminator.
        payload: Arbitrary JSON-serialisable payload dict.
        room: Target room name. Empty string means broadcast to all.
        sender: Connection ID or user ID of the originator.
        timestamp: Unix timestamp of message creation.
        message_id: Short unique identifier (12 hex chars).
    """

    type: WSMessageType
    payload: dict[str, Any] = field(default_factory=dict)
    room: str = ""
    sender: str = ""
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: uuid4().hex[:12])

    def to_json(self) -> str:
        """Serialise the message to a JSON string.

        Returns:
            JSON-encoded string representation of the message.
        """
        return json.dumps(
            {
                "type": self.type.value,
                "payload": self.payload,
                "room": self.room,
                "sender": self.sender,
                "timestamp": self.timestamp,
                "message_id": self.message_id,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> WSMessage:
        """Deserialise a message from a JSON string.

        Args:
            data: JSON string produced by :meth:`to_json`.

        Returns:
            A new :class:`WSMessage` instance.

        Raises:
            ValueError: If *data* is not valid JSON or contains an unknown type.
            KeyError: If required fields are missing from *data*.
        """
        try:
            raw: dict[str, Any] = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON payload: {exc}") from exc

        raw_type = raw.get("type")
        try:
            msg_type = WSMessageType(raw_type)
        except ValueError:
            valid = [t.value for t in WSMessageType]
            raise ValueError(
                f"Unknown WSMessageType '{raw_type}'. Valid values: {valid}"
            )

        return cls(
            type=msg_type,
            payload=raw.get("payload", {}),
            room=raw.get("room", ""),
            sender=raw.get("sender", ""),
            timestamp=raw.get("timestamp", time.time()),
            message_id=raw.get("message_id", uuid4().hex[:12]),
        )


@dataclass(frozen=True)
class WSConnectionInfo:
    """Immutable metadata snapshot for a single WebSocket connection.

    Attributes:
        connection_id: Unique identifier assigned at connection time.
        user_id: Authenticated user identifier (empty if anonymous).
        rooms: Tuple of room names the connection has joined.
        connected_at: Unix timestamp of when the connection was established.
    """

    connection_id: str
    user_id: str = ""
    rooms: tuple[str, ...] = ()
    connected_at: float = field(default_factory=time.time)
