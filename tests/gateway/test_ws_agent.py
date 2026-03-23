"""Unit tests for WebSocket agent message types.

Covers:
    TC-WSA01 – WSMessageType.AGENT_QUERY exists
    TC-WSA02 – WSMessageType.AGENT_RESPONSE exists
    TC-WSA03 – WSMessage agent_query round-trip serialisation
    TC-WSA04 – WSMessage agent_response round-trip serialisation
"""
from __future__ import annotations

import json

import pytest

from gateway.ws.models import WSMessage, WSMessageType


class TestAgentQueryMessageType:
    """TC-WSA01: AGENT_QUERY message type."""

    @pytest.mark.unit
    def test_agent_query_message_type_exists(self) -> None:
        """TC-WSA01-a: WSMessageType.AGENT_QUERY is defined with value 'agent_query'."""
        assert WSMessageType.AGENT_QUERY == "agent_query"
        assert WSMessageType.AGENT_QUERY in WSMessageType


class TestAgentResponseMessageType:
    """TC-WSA02: AGENT_RESPONSE message type."""

    @pytest.mark.unit
    def test_agent_response_message_type_exists(self) -> None:
        """TC-WSA02-a: WSMessageType.AGENT_RESPONSE is defined with value 'agent_response'."""
        assert WSMessageType.AGENT_RESPONSE == "agent_response"
        assert WSMessageType.AGENT_RESPONSE in WSMessageType


class TestWSMessageAgentQueryRoundtrip:
    """TC-WSA03: agent_query message serialisation / deserialisation."""

    @pytest.mark.unit
    def test_ws_message_agent_roundtrip(self) -> None:
        """TC-WSA03-a: Create, serialise, and deserialise an agent_query message."""
        original = WSMessage(
            type=WSMessageType.AGENT_QUERY,
            payload={"text": "부산항 인근 선박을 조회해줘", "mode": "react"},
            room="",
            sender="client-abc123",
        )

        json_str = original.to_json()

        # Verify JSON contains expected fields
        raw = json.loads(json_str)
        assert raw["type"] == "agent_query"
        assert raw["payload"]["text"] == "부산항 인근 선박을 조회해줘"
        assert raw["payload"]["mode"] == "react"
        assert raw["sender"] == "client-abc123"

        # Deserialise and verify equality of key fields
        restored = WSMessage.from_json(json_str)
        assert restored.type == WSMessageType.AGENT_QUERY
        assert restored.payload == original.payload
        assert restored.sender == original.sender
        assert restored.room == original.room
        assert restored.message_id == original.message_id

    @pytest.mark.unit
    def test_ws_message_agent_query_default_mode(self) -> None:
        """TC-WSA03-b: agent_query without explicit mode field round-trips cleanly."""
        msg = WSMessage(
            type=WSMessageType.AGENT_QUERY,
            payload={"text": "최근 사고 선박 목록"},
        )
        restored = WSMessage.from_json(msg.to_json())
        assert restored.type == WSMessageType.AGENT_QUERY
        assert restored.payload["text"] == "최근 사고 선박 목록"


class TestWSMessageAgentResponseRoundtrip:
    """TC-WSA04: agent_response message serialisation / deserialisation."""

    @pytest.mark.unit
    def test_ws_message_agent_response_roundtrip(self) -> None:
        """TC-WSA04-a: Create, serialise, and deserialise an agent_response message."""
        original = WSMessage(
            type=WSMessageType.AGENT_RESPONSE,
            payload={
                "answer": "부산항 인근에 12척의 선박이 있습니다.",
                "steps": [
                    {
                        "thought": "사용자가 부산항 인근 선박을 묻고 있다.",
                        "action": "MATCH (v:Vessel)-[:NEAR]->(p:Port {name:'부산항'}) RETURN v",
                        "observation": "12개 결과 반환",
                    }
                ],
                "tools_used": ["kg_query", "vessel_lookup"],
                "mode": "react",
            },
            room="",
            sender="system",
        )

        json_str = original.to_json()

        raw = json.loads(json_str)
        assert raw["type"] == "agent_response"
        assert raw["payload"]["answer"] == "부산항 인근에 12척의 선박이 있습니다."
        assert len(raw["payload"]["steps"]) == 1
        assert raw["payload"]["tools_used"] == ["kg_query", "vessel_lookup"]

        restored = WSMessage.from_json(json_str)
        assert restored.type == WSMessageType.AGENT_RESPONSE
        assert restored.payload == original.payload
        assert restored.sender == "system"
        assert restored.message_id == original.message_id

    @pytest.mark.unit
    def test_ws_message_agent_response_minimal(self) -> None:
        """TC-WSA04-b: Minimal agent_response (answer only) round-trips cleanly."""
        msg = WSMessage(
            type=WSMessageType.AGENT_RESPONSE,
            payload={"answer": "결과 없음"},
            sender="system",
        )
        restored = WSMessage.from_json(msg.to_json())
        assert restored.type == WSMessageType.AGENT_RESPONSE
        assert restored.payload["answer"] == "결과 없음"
        assert restored.sender == "system"

    @pytest.mark.unit
    def test_agent_response_type_not_accepted_as_agent_query(self) -> None:
        """TC-WSA04-c: agent_response and agent_query are distinct enum members."""
        assert WSMessageType.AGENT_QUERY != WSMessageType.AGENT_RESPONSE
        assert WSMessageType.AGENT_QUERY.value != WSMessageType.AGENT_RESPONSE.value
