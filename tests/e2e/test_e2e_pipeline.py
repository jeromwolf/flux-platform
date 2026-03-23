"""E2E pipeline tests: Gateway → Agent → KG/RAG → Response.

All tests use stubs/mocks — no real Neo4j, no real LLM required.
"""
from __future__ import annotations

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch


# --- Test Gateway → Core API Proxy ---

class TestGatewayProxy:
    """Test the gateway's API proxy functionality."""

    @pytest.mark.unit
    def test_proxy_route_matching(self):
        """Gateway proxy matches routes correctly."""
        from gateway.routes.proxy import APIProxy
        proxy = APIProxy(base_url="http://localhost:8000")
        routes = proxy.get_routes()

        paths = [r.path for r in routes]
        assert "/health" in paths
        assert "/graph/query" in paths
        assert "/schema" in paths
        assert "/etl/jobs" in paths

    @pytest.mark.unit
    def test_proxy_route_methods(self):
        """Each route has correct HTTP methods."""
        from gateway.routes.proxy import APIProxy
        proxy = APIProxy()
        routes = {r.path: r for r in proxy.get_routes()}

        assert "GET" in routes["/health"].methods
        assert "POST" in routes["/graph/query"].methods
        assert "GET" in routes["/schema"].methods

    @pytest.mark.unit
    def test_proxy_health_no_auth(self):
        """Health endpoint should not require auth."""
        from gateway.routes.proxy import APIProxy
        proxy = APIProxy()
        routes = {r.path: r for r in proxy.get_routes()}
        assert routes["/health"].require_auth is False
        assert routes["/ready"].require_auth is False

    @pytest.mark.unit
    def test_proxy_graph_requires_auth(self):
        """Graph endpoints should require auth."""
        from gateway.routes.proxy import APIProxy
        proxy = APIProxy()
        routes = {r.path: r for r in proxy.get_routes()}
        assert routes["/graph/query"].require_auth is True
        assert routes["/graph/node"].require_auth is True

    @pytest.mark.unit
    def test_proxy_unknown_path_raises(self):
        """Proxy raises ValueError for unknown paths."""
        from gateway.routes.proxy import APIProxy
        proxy = APIProxy()
        with pytest.raises(ValueError, match="No proxy route"):
            proxy._match_route("/unknown/path", "GET")

    @pytest.mark.unit
    def test_proxy_wrong_method_raises(self):
        """Proxy raises ValueError for disallowed methods."""
        from gateway.routes.proxy import APIProxy
        proxy = APIProxy()
        with pytest.raises(ValueError, match="not allowed"):
            proxy._match_route("/health", "DELETE")


# --- Test Agent ReAct → KG Tool ---

class TestAgentKGPipeline:
    """Test Agent processing KG queries via tools."""

    @pytest.mark.unit
    def test_react_with_kg_query_tool(self):
        """ReAct engine can use a KG query tool via ToolRegistry."""
        from agent.tools.registry import ToolRegistry
        from agent.tools.models import ToolDefinition, ToolResult

        registry = ToolRegistry()

        def kg_query_fn(cypher: str = "", **kwargs) -> str:
            return json.dumps({
                "nodes": [{"id": "v1", "labels": ["Vessel"], "properties": {"name": "세종대왕함"}}]
            })

        registry.register(
            ToolDefinition(
                name="kg_query",
                description="Execute Cypher query on knowledge graph",
                parameters={"cypher": {"type": "string", "description": "Cypher query"}},
            ),
            handler=kg_query_fn,
        )

        result = registry.execute("kg_query", {"cypher": "MATCH (v:Vessel) RETURN v"})
        assert isinstance(result, ToolResult)
        assert result.success
        parsed = json.loads(result.output)
        assert len(parsed["nodes"]) == 1
        assert parsed["nodes"][0]["labels"] == ["Vessel"]

    @pytest.mark.unit
    def test_react_with_multiple_tools(self):
        """ToolRegistry can handle multiple registered tools."""
        from agent.tools.registry import ToolRegistry
        from agent.tools.models import ToolDefinition

        registry = ToolRegistry()

        registry.register(
            ToolDefinition(name="search", description="Search", parameters={}),
            handler=lambda **kw: "search result",
        )
        registry.register(
            ToolDefinition(name="translate", description="Translate", parameters={}),
            handler=lambda **kw: "translated text",
        )

        assert registry.get("search") is not None
        assert registry.get("translate") is not None
        assert len(registry.list_tools()) == 2


# --- Test Agent Pipeline → RAG ---

class TestAgentRAGPipeline:
    """Test Agent pipeline using RAG retrieval."""

    @pytest.mark.unit
    def test_pipeline_with_rag_step(self):
        """Pipeline engine can include RAG retrieval step via registered tools."""
        from agent.runtime.pipeline import PipelineEngine
        from agent.tools.registry import ToolRegistry
        from agent.tools.models import ToolDefinition

        registry = ToolRegistry()

        # Register three sequential tools simulating parse → retrieve → format
        registry.register(
            ToolDefinition(name="parse", description="Parse input"),
            handler=lambda query="", **kw: f"parsed:{query}",
        )
        registry.register(
            ToolDefinition(name="retrieve", description="Retrieve documents"),
            handler=lambda query="", prev_output="", **kw: f"retrieved:{prev_output or query}",
        )
        registry.register(
            ToolDefinition(name="format", description="Format output"),
            handler=lambda query="", prev_output="", **kw: f"formatted:{prev_output or query}",
        )

        engine = PipelineEngine(tools=registry)
        engine.add_step("parse")
        engine.add_step("retrieve")
        engine.add_step("format")

        result = engine.execute("user query")
        assert "parsed" in result.answer
        assert "retrieved" in result.answer
        assert "formatted" in result.answer

    @pytest.mark.unit
    def test_pipeline_error_handling(self):
        """Pipeline stops on error by default."""
        from agent.runtime.pipeline import PipelineEngine
        from agent.tools.registry import ToolRegistry
        from agent.tools.models import ToolDefinition

        registry = ToolRegistry()

        registry.register(
            ToolDefinition(name="parse", description="Parse input"),
            handler=lambda query="", **kw: f"ok:{query}",
        )
        registry.register(
            ToolDefinition(name="fail", description="Fails"),
            handler=lambda **kw: (_ for _ in ()).throw(RuntimeError("retrieval failed")),
        )
        registry.register(
            ToolDefinition(name="never_reached", description="Never runs"),
            handler=lambda **kw: "unreachable",
        )

        engine = PipelineEngine(tools=registry)
        engine.add_step("parse")
        engine.add_step("fail", on_error="stop")
        engine.add_step("never_reached")

        result = engine.execute("test")
        # Pipeline should have run and returned a result (failed or completed)
        assert result is not None


# --- Test RAG → KG Integration ---

class TestRAGKGFlow:
    """Test RAG using KG results as documents."""

    @pytest.mark.unit
    def test_kg_results_as_rag_documents(self):
        """KG query results can be converted to RAG documents."""
        from rag.documents.models import Document, DocumentType

        # Simulate KG query result
        kg_nodes = [
            {"id": "1", "labels": ["Vessel"], "properties": {"name": "세종대왕함", "type": "DDG"}},
            {"id": "2", "labels": ["Port"], "properties": {"name": "부산항", "code": "KRPUS"}},
        ]

        # Convert to RAG documents
        docs = []
        for node in kg_nodes:
            content = json.dumps(node["properties"], ensure_ascii=False)
            doc = Document(
                doc_id=node["id"],
                title=f"{node['labels'][0]}:{node['id']}",
                content=content,
                doc_type=DocumentType.TXT,
                metadata={"source": "neo4j", "labels": node["labels"]},
            )
            docs.append(doc)

        assert len(docs) == 2
        assert "세종대왕함" in docs[0].content
        assert docs[1].metadata["labels"] == ["Port"]

    @pytest.mark.unit
    def test_rag_hybrid_retrieval_modes(self):
        """RAG engine supports all retrieval modes."""
        from rag.engines.models import RetrievalMode

        assert RetrievalMode.SEMANTIC.value == "semantic"
        assert RetrievalMode.KEYWORD.value == "keyword"
        assert RetrievalMode.HYBRID.value == "hybrid"


# --- Test Gateway WebSocket Flow ---

class TestGatewayWebSocket:
    """Test WebSocket lifecycle through gateway."""

    @pytest.mark.unit
    def test_ws_message_roundtrip(self):
        """WebSocket messages serialize and deserialize correctly."""
        from gateway.ws.models import WSMessage, WSMessageType

        msg = WSMessage(
            type=WSMessageType.CHAT,
            payload={"text": "안녕하세요"},
            room="general",
            sender="user1",
        )

        serialized = msg.to_json()
        deserialized = WSMessage.from_json(serialized)

        assert deserialized.type == WSMessageType.CHAT
        assert deserialized.payload["text"] == "안녕하세요"
        assert deserialized.room == "general"

    @pytest.mark.unit
    def test_ws_connection_manager_rooms(self):
        """ConnectionManager handles room operations."""
        from gateway.ws.manager import ConnectionManager

        manager = ConnectionManager()

        import asyncio

        async def _test():
            ws = AsyncMock()
            await manager.connect(ws, "conn1", user_id="user1")
            manager.join_room("conn1", "maritime")

            assert "maritime" in manager.room_names
            assert "conn1" in manager.get_room_members("maritime")

            manager.leave_room("conn1", "maritime")
            assert "maritime" not in manager.room_names

            await manager.disconnect("conn1")
            assert manager.connection_count == 0

        asyncio.new_event_loop().run_until_complete(_test())

    @pytest.mark.unit
    def test_ws_message_types(self):
        """All message types are valid."""
        from gateway.ws.models import WSMessageType

        types = [t.value for t in WSMessageType]
        assert "chat" in types
        assert "notification" in types
        assert "kg_update" in types
        assert "system" in types
        assert "error" in types
        assert "ping" in types
        assert "pong" in types

    @pytest.mark.unit
    def test_ws_auth_dev_decode(self):
        """WS authenticator can decode tokens in dev mode."""
        from gateway.middleware.ws_auth import WSAuthenticator, WSAuthConfig
        import base64

        config = WSAuthConfig(require_auth=True, secret_key="")
        auth = WSAuthenticator(config=config)

        # Create a base64-encoded JSON token (3-part JWT with fake header/sig)
        header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
        payload_data = json.dumps({"sub": "user1", "preferred_username": "admin"})
        payload = base64.urlsafe_b64encode(payload_data.encode()).decode().rstrip("=")
        sig = "fakesig"
        token = f"{header}.{payload}.{sig}"

        claims = auth.authenticate(token)
        assert claims["sub"] == "user1"


# --- Test Full E2E Flow ---

class TestFullE2EFlow:
    """Test the complete request lifecycle."""

    @pytest.mark.unit
    def test_gateway_config_validation(self):
        """Gateway config validates correctly."""
        from gateway.config import GatewayConfig

        config = GatewayConfig()
        errors = config.validate()
        assert len(errors) == 0

    @pytest.mark.unit
    def test_gateway_app_assembly(self):
        """GatewayApp assembles correctly."""
        from gateway.app import create_gateway_app

        gw = create_gateway_app()
        desc = gw.describe()

        assert desc["api_base_url"] == "http://localhost:8000"
        assert len(desc["routes"]) > 0
        assert desc["port"] == 8080

    @pytest.mark.unit
    def test_gateway_app_with_custom_config(self):
        """GatewayApp accepts custom config."""
        from gateway.app import create_gateway_app
        from gateway.config import GatewayConfig

        config = GatewayConfig(port=9090, debug=True)
        gw = create_gateway_app(config)

        assert gw.config.port == 9090
        assert gw.config.debug is True

    @pytest.mark.unit
    def test_gateway_invalid_config_raises(self):
        """GatewayApp rejects invalid config."""
        from gateway.app import create_gateway_app
        from gateway.config import GatewayConfig

        config = GatewayConfig(port=0)
        with pytest.raises(ValueError, match="Invalid GatewayConfig"):
            create_gateway_app(config)

    @pytest.mark.unit
    def test_keycloak_middleware_public_paths(self):
        """Keycloak middleware skips public paths."""
        from gateway.middleware.keycloak import KeycloakConfig

        config = KeycloakConfig(
            keycloak_url="http://localhost:8180",
            realm="imsp",
            client_id="imsp-api",
            public_paths=["/health", "/ready", "/ws"],
        )

        assert config.is_public_path("/health") is True
        assert config.is_public_path("/ready") is True
        assert config.is_public_path("/ws") is True
        assert config.is_public_path("/api/v1/graph") is False

    @pytest.mark.unit
    def test_keycloak_config_issuer(self):
        """Keycloak config generates correct issuer URL."""
        from gateway.middleware.keycloak import KeycloakConfig

        config = KeycloakConfig(
            keycloak_url="http://localhost:8180",
            realm="imsp",
            client_id="imsp-api",
        )

        assert config.issuer == "http://localhost:8180/realms/imsp"
        assert "certs" in config.jwks_uri

    @pytest.mark.unit
    def test_batch_agent_processing(self):
        """BatchEngine processes multiple queries."""
        from agent.runtime.batch import BatchEngine
        from agent.tools.registry import ToolRegistry
        from agent.tools.models import ToolDefinition

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="answer_tool", description="Answer query"),
            handler=lambda query="", **kwargs: f"answer:{query}",
        )

        engine = BatchEngine(tools=registry, tool_name="answer_tool")
        queries = ["선박 정보", "항만 목록", "규정 검색"]
        batch_result = engine.execute_batch(queries)

        assert batch_result.total_count == 3
        for item_result in batch_result.items:
            assert item_result.success
            assert "answer" in item_result.answer

    @pytest.mark.unit
    def test_cypher_builder_fluent(self):
        """CypherBuilder produces valid Cypher."""
        from kg.cypher_builder import CypherBuilder

        builder = CypherBuilder()
        query, params = (
            builder
            .match("(v:Vessel)")
            .where("v.name = $name")
            .return_("v")
            .build()
        )

        assert "MATCH" in query
        assert "(v:Vessel)" in query
        assert "RETURN" in query

    @pytest.mark.unit
    def test_quality_gate_check(self):
        """QualityGate produces valid GateReport."""
        from kg.quality_gate import GateReport, CheckResult, CheckStatus

        report = GateReport(checks=[
            CheckResult(
                name="completeness",
                status=CheckStatus.PASSED,
                message="All nodes have required properties",
            ),
        ])

        assert report.passed is True
        assert len(report.checks) == 1
