"""Cross-module integration tests with REAL Neo4j.

Covers:
- Agent ToolRegistry executing Cypher against a live Neo4j instance
- RAG Document/Chunk construction from KG query results
- PipelineEngine and BatchEngine end-to-end with KG tools
- Full-stack path: create graph → agent query → RAG retrieval

All tests:
- Require NEO4J_TEST_URI to be set (skipped otherwise)
- Are marked @pytest.mark.integration
- Use the _Test label prefix for every node to ensure clean isolation
"""
from __future__ import annotations

import json
import os

import pytest
from neo4j import GraphDatabase

from agent.runtime.batch import BatchEngine
from agent.runtime.models import AgentConfig, AgentState, ExecutionMode
from agent.runtime.pipeline import PipelineEngine
from agent.tools.models import ToolDefinition, ToolResult
from agent.tools.registry import ToolRegistry
from kg.cypher_builder import CypherBuilder
from rag.documents.models import Document, DocumentChunk, DocumentType
from rag.engines.retriever import SimpleRetriever

# ---------------------------------------------------------------------------
# Module-level pytest markers
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("NEO4J_TEST_URI"),
        reason="NEO4J_TEST_URI not set",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def neo4j_driver():
    """Return a live Neo4j driver for the test session."""
    uri = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
    driver = GraphDatabase.driver(
        uri,
        auth=(
            os.environ.get("NEO4J_TEST_USER", "neo4j"),
            os.environ.get("NEO4J_TEST_PASSWORD", "fluxrag2026"),
        ),
    )
    driver.verify_connectivity()
    yield driver
    driver.close()


@pytest.fixture(autouse=True)
def clean(neo4j_driver):
    """Delete all _Test-labelled nodes before and after every test."""
    with neo4j_driver.session() as s:
        s.run("MATCH (n:_Test) DETACH DELETE n")
    yield
    with neo4j_driver.session() as s:
        s.run("MATCH (n:_Test) DETACH DELETE n")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _make_dummy_embedding(seed: int, dim: int = 8) -> tuple[float, ...]:
    """Return a deterministic, non-zero unit-ish embedding for testing."""
    import math

    raw = tuple(math.sin(seed * (i + 1) * 0.3) for i in range(dim))
    mag = math.sqrt(sum(x * x for x in raw)) or 1.0
    return tuple(x / mag for x in raw)


# ---------------------------------------------------------------------------
# TestAgentKGRealIntegration
# ---------------------------------------------------------------------------


class TestAgentKGRealIntegration:
    """Agent ToolRegistry executing real Cypher against Neo4j."""

    def test_tool_executes_real_cypher(self, neo4j_driver):
        """Register a KG tool, create _Test:Vessel nodes, verify ToolResult contains real data."""

        def kg_handler(query: str) -> str:
            with neo4j_driver.session() as session:
                # Create a _Test:Vessel node then query it back
                session.run(
                    "CREATE (:_Test:Vessel {name: 'Aurora', mmsi: '123456789'})"
                )
                records = session.run(
                    "MATCH (v:_Test:Vessel) RETURN v.name AS name"
                ).data()
            names = [r["name"] for r in records]
            return json.dumps(names)

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="kg_query",
                description="Execute Cypher against Neo4j",
                required_params=("query",),
            ),
            handler=kg_handler,
        )

        result: ToolResult = registry.execute("kg_query", {"query": "get vessels"})

        assert result.success is True
        assert result.tool_name == "kg_query"
        names = json.loads(result.output)
        assert "Aurora" in names

    def test_tool_creates_and_queries(self, neo4j_driver):
        """Two sequential tool calls: create_vessel then query_vessels."""

        def create_vessel_handler(name: str, mmsi: str) -> str:
            with neo4j_driver.session() as session:
                session.run(
                    "CREATE (:_Test:Vessel {name: $name, mmsi: $mmsi})",
                    name=name,
                    mmsi=mmsi,
                )
            return f"Created vessel {name}"

        def query_vessels_handler(query: str) -> str:
            with neo4j_driver.session() as session:
                records = session.run(
                    "MATCH (v:_Test:Vessel) RETURN v.name AS name, v.mmsi AS mmsi"
                ).data()
            return json.dumps(records)

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="create_vessel",
                description="Create a _Test:Vessel node",
                required_params=("name", "mmsi"),
            ),
            handler=create_vessel_handler,
        )
        registry.register(
            ToolDefinition(
                name="query_vessels",
                description="Query all _Test:Vessel nodes",
                required_params=("query",),
            ),
            handler=query_vessels_handler,
        )

        create_result = registry.execute(
            "create_vessel", {"name": "Poseidon", "mmsi": "987654321"}
        )
        assert create_result.success is True

        query_result = registry.execute("query_vessels", {"query": "list all"})
        assert query_result.success is True

        vessels = json.loads(query_result.output)
        names = [v["name"] for v in vessels]
        assert "Poseidon" in names

    def test_cypher_builder_with_tool(self, neo4j_driver):
        """Tool uses CypherBuilder to build and run a query; verify correct results."""

        def cypher_builder_handler(vessel_type: str) -> str:
            query, params = (
                CypherBuilder()
                .match("(v:_Test:Vessel)")
                .where("v.vesselType = $vtype", {"vtype": vessel_type})
                .return_("v.name AS name")
                .limit(10)
                .build()
            )
            with neo4j_driver.session() as session:
                records = session.run(query, params).data()
            return json.dumps([r["name"] for r in records])

        # Pre-seed data
        with neo4j_driver.session() as session:
            session.run(
                "CREATE (:_Test:Vessel {name: 'ContainerKing', vesselType: 'ContainerShip'})"
            )
            session.run(
                "CREATE (:_Test:Vessel {name: 'TankerQueen', vesselType: 'Tanker'})"
            )

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="filter_vessels",
                description="Filter vessels by type using CypherBuilder",
                required_params=("vessel_type",),
            ),
            handler=cypher_builder_handler,
        )

        result = registry.execute(
            "filter_vessels", {"vessel_type": "ContainerShip"}
        )

        assert result.success is True
        names = json.loads(result.output)
        assert "ContainerKing" in names
        assert "TankerQueen" not in names

    def test_tool_error_handling(self, neo4j_driver):
        """Tool that runs invalid Cypher → ToolResult.success is False."""

        def bad_cypher_handler(query: str) -> str:
            with neo4j_driver.session() as session:
                # Intentionally malformed Cypher
                session.run("MATCH (n:_Test) INVALID SYNTAX RETURN n").data()
            return "should not reach here"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="bad_tool",
                description="Tool with bad Cypher",
                required_params=("query",),
            ),
            handler=bad_cypher_handler,
        )

        result = registry.execute("bad_tool", {"query": "anything"})

        assert result.success is False
        assert result.error != ""


# ---------------------------------------------------------------------------
# TestRAGWithKGData
# ---------------------------------------------------------------------------


class TestRAGWithKGData:
    """RAG Document/Chunk construction from live Neo4j query results."""

    def test_kg_results_to_rag_documents(self, neo4j_driver):
        """Query _Test nodes, convert results to RAG Document objects, verify fields."""
        with neo4j_driver.session() as session:
            session.run(
                "CREATE (:_Test:Vessel {name: 'SeaWolf', mmsi: '111222333', vesselType: 'Tanker'})"
            )
            records = session.run(
                "MATCH (v:_Test:Vessel) RETURN v.name AS name, v.mmsi AS mmsi, v.vesselType AS vesselType"
            ).data()

        documents = [
            Document(
                doc_id=f"vessel-{r['mmsi']}",
                title=r["name"],
                content=f"Vessel {r['name']} (MMSI: {r['mmsi']}) is a {r.get('vesselType', 'unknown')} vessel.",
                doc_type=DocumentType.TXT,
                source="neo4j:_Test:Vessel",
                metadata={"mmsi": r["mmsi"], "vesselType": r.get("vesselType")},
            )
            for r in records
        ]

        assert len(documents) >= 1
        doc = documents[0]
        assert doc.doc_id != ""
        assert doc.title != ""
        assert doc.content != ""
        assert doc.doc_type == DocumentType.TXT
        assert doc.source == "neo4j:_Test:Vessel"
        assert doc.metadata["mmsi"] is not None
        assert doc.word_count > 0
        assert doc.char_count > 0

    def test_kg_data_to_chunks_to_retrieval(self, neo4j_driver):
        """Create _Test nodes, convert to DocumentChunks, add to SimpleRetriever, search."""
        with neo4j_driver.session() as session:
            session.run(
                "CREATE (:_Test:Vessel {name: 'Nordic Star', mmsi: '444555666'})"
            )
            session.run(
                "CREATE (:_Test:Vessel {name: 'Pacific Horizon', mmsi: '777888999'})"
            )
            records = session.run(
                "MATCH (v:_Test:Vessel) RETURN v.name AS name, v.mmsi AS mmsi"
            ).data()

        chunks = []
        for idx, r in enumerate(records):
            content = f"Vessel {r['name']} MMSI {r['mmsi']}"
            chunk = DocumentChunk(
                chunk_id=f"chunk-{r['mmsi']}",
                doc_id=f"doc-{r['mmsi']}",
                content=content,
                chunk_index=idx,
                embedding=_make_dummy_embedding(idx),
                metadata={"name": r["name"]},
            )
            chunks.append(chunk)

        retriever = SimpleRetriever()
        added = retriever.add_chunks(chunks)
        assert added == len(chunks)

        results = retriever.keyword_search("Nordic", top_k=5)
        assert len(results) >= 1
        contents = [r.chunk.content for r in results]
        assert any("Nordic" in c for c in contents)

    def test_rag_hybrid_with_kg_content(self, neo4j_driver):
        """Diverse _Test nodes (Vessel, Port, Organization) → search for each type."""
        with neo4j_driver.session() as session:
            session.run("CREATE (:_Test:Vessel {name: 'Iron Maiden', mmsi: '100200300'})")
            session.run("CREATE (:_Test:Port {name: 'Busan Terminal', code: 'KRPUS'})")
            session.run(
                "CREATE (:_Test:Organization {name: 'Korea Shipping Corp', orgType: 'Carrier'})"
            )

            vessels = session.run("MATCH (v:_Test:Vessel) RETURN 'Vessel' AS type, v.name AS name").data()
            ports = session.run("MATCH (p:_Test:Port) RETURN 'Port' AS type, p.name AS name").data()
            orgs = session.run("MATCH (o:_Test:Organization) RETURN 'Organization' AS type, o.name AS name").data()

        all_records = vessels + ports + orgs
        chunks = []
        for idx, r in enumerate(all_records):
            chunk = DocumentChunk(
                chunk_id=f"chunk-{idx}",
                doc_id=f"doc-{idx}",
                content=f"{r['type']}: {r['name']}",
                chunk_index=idx,
                embedding=_make_dummy_embedding(idx + 10),
                metadata={"node_type": r["type"]},
            )
            chunks.append(chunk)

        retriever = SimpleRetriever()
        retriever.add_chunks(chunks)

        port_results = retriever.keyword_search("Port Terminal", top_k=3)
        assert len(port_results) >= 1
        assert any("Port" in r.chunk.content for r in port_results)

        vessel_results = retriever.keyword_search("Vessel Iron", top_k=3)
        assert len(vessel_results) >= 1
        assert any("Vessel" in r.chunk.content for r in vessel_results)

    def test_empty_kg_result_handling(self, neo4j_driver):
        """Query for non-existent _Test nodes → RAG handles empty results gracefully."""
        with neo4j_driver.session() as session:
            records = session.run(
                "MATCH (v:_Test:NonExistentType) RETURN v.name AS name"
            ).data()

        # Empty DB result → no chunks
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{i}",
                doc_id=f"doc-{i}",
                content=r.get("name", ""),
                chunk_index=i,
                embedding=_make_dummy_embedding(i),
            )
            for i, r in enumerate(records)
        ]

        retriever = SimpleRetriever()
        added = retriever.add_chunks(chunks)
        assert added == 0
        assert retriever.chunk_count == 0

        results = retriever.keyword_search("anything", top_k=5)
        assert results == []


# ---------------------------------------------------------------------------
# TestAgentPipelineWithKG
# ---------------------------------------------------------------------------


class TestAgentPipelineWithKG:
    """PipelineEngine and BatchEngine running real KG operations."""

    def test_pipeline_parse_query_format(self, neo4j_driver):
        """3-step pipeline: parse → kg_query → format with real Neo4j data."""

        def parse_handler(query: str, **_: object) -> str:
            keywords = [w.lower() for w in query.split() if len(w) > 3]
            return json.dumps({"keywords": keywords})

        def kg_query_handler(query: str, prev_output: str = "", **_: object) -> str:
            with neo4j_driver.session() as session:
                session.run(
                    "MERGE (:_Test:Vessel {name: 'Pipeline Vessel', mmsi: '321321321'})"
                )
                records = session.run(
                    "MATCH (v:_Test:Vessel) RETURN v.name AS name"
                ).data()
            return json.dumps([r["name"] for r in records])

        def format_handler(query: str, prev_output: str = "", **_: object) -> str:
            names = json.loads(prev_output) if prev_output else []
            return f"Found vessels: {', '.join(names)}"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="parse", description="Parse query to keywords"),
            handler=parse_handler,
        )
        registry.register(
            ToolDefinition(name="kg_query", description="Query Neo4j"),
            handler=kg_query_handler,
        )
        registry.register(
            ToolDefinition(name="format", description="Format output"),
            handler=format_handler,
        )

        engine = PipelineEngine(
            config=AgentConfig(name="test-pipeline", mode=ExecutionMode.PIPELINE),
            tools=registry,
        )
        engine.add_step("parse")
        engine.add_step("kg_query")
        engine.add_step("format")

        result = engine.execute("find all vessels")

        assert result.success is True
        assert result.state == AgentState.COMPLETED
        assert "Pipeline Vessel" in result.answer

    def test_pipeline_with_real_data(self, neo4j_driver):
        """Pipeline queries a maritime graph (_Test:Vessel DOCKED_AT _Test:Port)."""

        with neo4j_driver.session() as session:
            session.run(
                """
                CREATE (v:_Test:Vessel {name: 'Sea Eagle', mmsi: '555666777'})
                CREATE (p:_Test:Port {name: 'Incheon Port', code: 'KRICN'})
                CREATE (v)-[:DOCKED_AT]->(p)
                """
            )

        def query_maritime_graph(query: str, **_: object) -> str:
            with neo4j_driver.session() as session:
                records = session.run(
                    """
                    MATCH (v:_Test:Vessel)-[:DOCKED_AT]->(p:_Test:Port)
                    RETURN v.name AS vessel, p.name AS port
                    """
                ).data()
            return json.dumps(records)

        def summarise(query: str, prev_output: str = "", **_: object) -> str:
            if not prev_output:
                return "No data found."
            pairs = json.loads(prev_output)
            lines = [f"{r['vessel']} → {r['port']}" for r in pairs]
            return "; ".join(lines)

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="query_graph", description="Query maritime graph"),
            handler=query_maritime_graph,
        )
        registry.register(
            ToolDefinition(name="summarise", description="Summarise results"),
            handler=summarise,
        )

        engine = PipelineEngine(tools=registry)
        engine.add_step("query_graph")
        engine.add_step("summarise")

        result = engine.execute("maritime graph query")

        assert result.success is True
        assert "Sea Eagle" in result.answer
        assert "Incheon Port" in result.answer

    def test_batch_execution_with_kg(self, neo4j_driver):
        """BatchEngine runs 3 queries against real Neo4j; all should succeed."""

        with neo4j_driver.session() as session:
            session.run("CREATE (:_Test:Vessel {name: 'Batch Alpha', mmsi: '100000001'})")
            session.run("CREATE (:_Test:Vessel {name: 'Batch Beta', mmsi: '100000002'})")
            session.run("CREATE (:_Test:Vessel {name: 'Batch Gamma', mmsi: '100000003'})")

        def count_vessels_handler(query: str, **_: object) -> str:
            with neo4j_driver.session() as session:
                record = session.run(
                    "MATCH (v:_Test:Vessel) RETURN count(v) AS cnt"
                ).single()
            return str(record["cnt"])

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="count_vessels", description="Count _Test:Vessel nodes"),
            handler=count_vessels_handler,
        )

        engine = BatchEngine(
            config=AgentConfig(name="batch-kg", mode=ExecutionMode.BATCH),
            tools=registry,
            tool_name="count_vessels",
        )

        queries = [
            "count vessels query 1",
            "count vessels query 2",
            "count vessels query 3",
        ]
        batch_result = engine.execute_batch(queries)

        assert batch_result.total_count == 3
        assert batch_result.success_count == 3
        assert batch_result.failure_count == 0
        assert batch_result.success_rate == 1.0

        for item_result in batch_result.items:
            assert item_result.success is True
            count = int(item_result.answer)
            assert count >= 3


# ---------------------------------------------------------------------------
# TestFullStackIntegration
# ---------------------------------------------------------------------------


class TestFullStackIntegration:
    """Full-stack: graph creation → Agent ToolRegistry → RAG retrieval."""

    def test_create_graph_then_agent_query(self, neo4j_driver):
        """Create a 5-node maritime subgraph, then use ToolRegistry to query paths."""

        with neo4j_driver.session() as session:
            session.run(
                """
                CREATE (v1:_Test:Vessel {name: 'Alpha', mmsi: '001'})
                CREATE (v2:_Test:Vessel {name: 'Beta', mmsi: '002'})
                CREATE (p1:_Test:Port {name: 'PortA', code: 'PA'})
                CREATE (p2:_Test:Port {name: 'PortB', code: 'PB'})
                CREATE (org:_Test:Organization {name: 'Operator', orgType: 'Carrier'})
                CREATE (v1)-[:DOCKED_AT]->(p1)
                CREATE (v2)-[:DOCKED_AT]->(p2)
                CREATE (org)-[:OPERATES]->(v1)
                CREATE (org)-[:OPERATES]->(v2)
                """
            )

        def find_path_handler(from_vessel: str, **_: object) -> str:
            with neo4j_driver.session() as session:
                records = session.run(
                    """
                    MATCH (v:_Test:Vessel {name: $vname})-[:DOCKED_AT]->(p:_Test:Port)
                    RETURN v.name AS vessel, p.name AS port
                    """,
                    vname=from_vessel,
                ).data()
            return json.dumps(records)

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="find_path",
                description="Find vessel→port path",
                required_params=("from_vessel",),
            ),
            handler=find_path_handler,
        )

        result = registry.execute("find_path", {"from_vessel": "Alpha"})

        assert result.success is True
        paths = json.loads(result.output)
        assert len(paths) >= 1
        assert paths[0]["vessel"] == "Alpha"
        assert paths[0]["port"] == "PortA"

    def test_kg_to_rag_to_answer(self, neo4j_driver):
        """Create nodes, extract as RAG chunks, search, verify correct documents returned."""

        node_data = [
            ("_Test:Vessel", "Iron Goliath", "mmsi", "300000001"),
            ("_Test:Port", "Gwangyang Terminal", "code", "KRGWG"),
            ("_Test:Organization", "Blue Ocean Lines", "orgType", "Liner"),
        ]

        with neo4j_driver.session() as session:
            session.run(
                "CREATE (:_Test:Vessel {name: 'Iron Goliath', mmsi: '300000001'})"
            )
            session.run(
                "CREATE (:_Test:Port {name: 'Gwangyang Terminal', code: 'KRGWG'})"
            )
            session.run(
                "CREATE (:_Test:Organization {name: 'Blue Ocean Lines', orgType: 'Liner'})"
            )

        # Query each type and build chunks
        chunks: list[DocumentChunk] = []
        chunk_idx = 0

        with neo4j_driver.session() as session:
            for label, expected_name, _, _ in node_data:
                clean_label = label.replace(":_Test:", "").replace("_Test:", "").replace(":", "")
                records = session.run(
                    f"MATCH (n:{label}) RETURN n.name AS name",
                ).data()
                for r in records:
                    chunk = DocumentChunk(
                        chunk_id=f"chunk-{chunk_idx}",
                        doc_id=f"doc-{clean_label}-{chunk_idx}",
                        content=f"{clean_label}: {r['name']}",
                        chunk_index=chunk_idx,
                        embedding=_make_dummy_embedding(chunk_idx + 100),
                        metadata={"node_type": clean_label, "name": r["name"]},
                    )
                    chunks.append(chunk)
                    chunk_idx += 1

        retriever = SimpleRetriever()
        added = retriever.add_chunks(chunks)
        assert added == len(chunks)

        # Search for vessel
        vessel_results = retriever.keyword_search("Iron Goliath", top_k=5)
        assert len(vessel_results) >= 1
        assert any("Iron Goliath" in r.chunk.content for r in vessel_results)

        # Search for port
        port_results = retriever.keyword_search("Gwangyang Terminal", top_k=5)
        assert len(port_results) >= 1
        assert any("Gwangyang" in r.chunk.content for r in port_results)

        # Search for organization
        org_results = retriever.keyword_search("Blue Ocean Lines", top_k=5)
        assert len(org_results) >= 1
        assert any("Blue Ocean Lines" in r.chunk.content for r in org_results)
