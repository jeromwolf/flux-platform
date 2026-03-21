"""Cross-module integration tests: Agent, RAG, and KG interactions.

Validates that modules from different packages (agent/, rag/, core/kg/) can work
together in realistic multi-module workflows. Uses real instances where possible;
MockLLM replaces real LLM calls.

All tests are marked @pytest.mark.unit and require no external services.
PYTHONPATH: .

Test classes:
    TestAgentRAGIntegration     — Agent engines using RAG components as tools
    TestAgentKGIntegration      — Agent engines using KG (CypherBuilder/QualityGate) as tools
    TestRAGKGIntegration        — RAG pipeline interacting with KG query outputs
    TestFullPipelineIntegration — End-to-end scenarios combining all three modules
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Agent modules
# ---------------------------------------------------------------------------
from agent.runtime.models import AgentConfig, AgentState, ExecutionMode, StepType
from agent.runtime.react import ReActEngine
from agent.runtime.pipeline import PipelineEngine
from agent.runtime.batch import BatchEngine, BatchResult
from agent.tools.models import ToolDefinition, ToolResult
from agent.tools.registry import ToolRegistry
from agent.skills.models import SkillDefinition
from agent.skills.registry import SkillRegistry
from agent.llm.bridge import AgentLLMBridge, BridgeConfig, ThinkResult

# ---------------------------------------------------------------------------
# RAG modules
# ---------------------------------------------------------------------------
from rag.documents.models import Document, DocumentType, ChunkingConfig
from rag.documents.chunker import TextChunker
from rag.documents.pipeline import DocumentPipeline
from rag.embeddings.models import EmbeddingConfig
from rag.embeddings.providers import StubEmbeddingProvider
from rag.engines.models import RAGConfig, RetrievalMode
from rag.engines.retriever import SimpleRetriever
from rag.engines.orchestrator import HybridRAGEngine

# ---------------------------------------------------------------------------
# KG modules
# ---------------------------------------------------------------------------
from kg.cypher_builder import CypherBuilder
from kg.quality_gate import QualityGate, GateReport, CheckResult, CheckStatus


# ===========================================================================
# Mock LLM helpers
# ===========================================================================


class MockLLMResponse:
    """Minimal LLM response returned by MockLLM."""

    def __init__(self, text: str, token_count: int = 10) -> None:
        self.text = text
        self.token_count = token_count
        self.provider = "mock"


class MockLLM:
    """Deterministic mock LLM that cycles through a list of pre-defined responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self._call_count = 0

    def generate(self, prompt: str) -> MockLLMResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return MockLLMResponse(resp)
        return MockLLMResponse("FINAL ANSWER: default")


# ===========================================================================
# Shared helpers
# ===========================================================================


def _make_maritime_docs() -> list[Document]:
    """Create a small set of maritime documents for test ingestion."""
    return [
        Document(
            doc_id="doc-vessel-001",
            title="Container Vessel Overview",
            content=(
                "A container vessel is a cargo ship designed to carry intermodal containers. "
                "Large container vessels can carry over 20,000 TEU (twenty-foot equivalent units). "
                "Vessels are identified by their MMSI number and IMO registration."
            ),
            doc_type=DocumentType.TXT,
        ),
        Document(
            doc_id="doc-port-002",
            title="Port of Busan Operations",
            content=(
                "The Port of Busan is the largest port in South Korea and a major transshipment hub. "
                "It handles millions of TEUs annually and operates 24 hours a day. "
                "Vessels dock at designated berths assigned by the port authority."
            ),
            doc_type=DocumentType.TXT,
        ),
        Document(
            doc_id="doc-voyage-003",
            title="Maritime Voyage Planning",
            content=(
                "A voyage plan includes departure port, arrival port, waypoints, and estimated time. "
                "COLREG rules govern vessel behaviour at sea to prevent collisions. "
                "Weather routing optimises the planned route based on forecast conditions."
            ),
            doc_type=DocumentType.TXT,
        ),
    ]


def _build_rag_stack(
    doc_count: int = 3,
    similarity_threshold: float = 0.0,
) -> tuple[DocumentPipeline, SimpleRetriever]:
    """Set up a DocumentPipeline + SimpleRetriever with ingested documents.

    Args:
        doc_count: Number of maritime documents to ingest (1-3).
        similarity_threshold: Minimum cosine similarity for retrieval.

    Returns:
        (pipeline, retriever) tuple — retriever already has chunks indexed.
    """
    embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=64, normalize=True))
    retriever = SimpleRetriever(RAGConfig(similarity_threshold=similarity_threshold))
    chunker = TextChunker(ChunkingConfig(chunk_size=512, chunk_overlap=32))
    pipeline = DocumentPipeline(chunker=chunker, embedder=embedder, retriever=retriever)

    for doc in _make_maritime_docs()[:doc_count]:
        result = pipeline.ingest_document(doc)
        assert result.success, f"Ingestion failed for {doc.doc_id}: {result.error}"

    return pipeline, retriever


# ===========================================================================
# TestAgentRAGIntegration
# ===========================================================================


class TestAgentRAGIntegration:
    """Agent engines use RAG components as tools within their execution."""

    @pytest.mark.unit
    def test_react_engine_with_rag_tool(self) -> None:
        """ReActEngine in stub mode calls rag_search tool; result appears in steps."""
        _, retriever = _build_rag_stack(doc_count=3)

        def rag_search_handler(query: str = "", **kwargs: object) -> str:
            results = retriever.keyword_search(query, top_k=3)
            return f"Found {len(results)} chunks"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="rag_search",
                description="Search maritime documents via keyword retrieval",
                parameters={"query": {"type": "string"}},
            ),
            handler=rag_search_handler,
        )

        engine = ReActEngine(
            config=AgentConfig(name="rag-react-agent", max_steps=5),
            tools=registry,
        )

        result = engine.execute("Find information about vessels")

        assert result.state == AgentState.COMPLETED
        action_steps = [s for s in result.steps if s.step_type == StepType.ACTION]
        assert len(action_steps) >= 1
        assert any(s.tool_name == "rag_search" for s in action_steps)

    @pytest.mark.unit
    def test_pipeline_engine_rag_steps(self) -> None:
        """PipelineEngine executes ingest, search, and format steps using RAG."""
        embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=64, normalize=True))
        retriever = SimpleRetriever(RAGConfig(similarity_threshold=0.0))
        chunker = TextChunker(ChunkingConfig(chunk_size=512, chunk_overlap=32))
        pipeline_doc = DocumentPipeline(
            chunker=chunker, embedder=embedder, retriever=retriever
        )

        def ingest_handler(query: str = "", **kwargs: object) -> str:
            doc = Document(
                doc_id="dynamic-doc",
                title="Dynamic Maritime Doc",
                content=(
                    "Dynamic content about maritime vessel routes and port authorities. "
                    "The IMSP platform monitors vessel positions in real time."
                ),
                doc_type=DocumentType.TXT,
            )
            res = pipeline_doc.ingest_document(doc)
            return f"Ingested {res.chunks_created} chunks"

        def search_handler(query: str = "", prev_output: str = "", **kwargs: object) -> str:
            results = retriever.keyword_search("vessel", top_k=5)
            return f"Search returned {len(results)} results"

        def format_handler(
            query: str = "", prev_output: str = "", **kwargs: object
        ) -> str:
            return f"Formatted output: {prev_output}"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="ingest", description="Ingest a document"),
            handler=ingest_handler,
        )
        registry.register(
            ToolDefinition(name="search", description="Search the retriever"),
            handler=search_handler,
        )
        registry.register(
            ToolDefinition(name="format", description="Format results"),
            handler=format_handler,
        )

        engine = PipelineEngine(
            config=AgentConfig(name="rag-pipeline", mode=ExecutionMode.PIPELINE),
            tools=registry,
        )
        engine.add_step("ingest", description="Ingest document")
        engine.add_step("search", description="Search documents")
        engine.add_step("format", description="Format output")

        result = engine.execute("Maritime vessel query")

        assert result.state == AgentState.COMPLETED
        action_steps = [s for s in result.steps if s.step_type == StepType.ACTION]
        assert len(action_steps) == 3

    @pytest.mark.unit
    def test_batch_rag_queries(self) -> None:
        """BatchEngine processes 3 different RAG keyword queries with > 0 success_rate."""
        _, retriever = _build_rag_stack(doc_count=3)

        def rag_query_handler(query: str = "", **kwargs: object) -> str:
            results = retriever.keyword_search(query, top_k=5)
            return f"Found {len(results)} chunks for query '{query}'"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="rag_query", description="Keyword search over RAG index"),
            handler=rag_query_handler,
        )

        engine = BatchEngine(
            config=AgentConfig(name="batch-rag", mode=ExecutionMode.BATCH),
            tools=registry,
            tool_name="rag_query",
        )

        queries = ["vessel container ship", "port busan operations", "voyage colreg rules"]
        batch_result = engine.execute_batch(queries)

        assert batch_result.total_count == 3
        assert batch_result.success_rate > 0.0

    @pytest.mark.unit
    def test_hybrid_rag_as_agent_tool(self) -> None:
        """ReActEngine uses HybridRAGEngine.query() as a tool; answer includes RAG content."""
        embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=64, normalize=True))
        retriever = SimpleRetriever(RAGConfig(mode=RetrievalMode.KEYWORD, similarity_threshold=0.0))
        chunker = TextChunker(ChunkingConfig(chunk_size=512, chunk_overlap=32))
        doc_pipeline = DocumentPipeline(chunker=chunker, embedder=embedder, retriever=retriever)

        for doc in _make_maritime_docs():
            doc_pipeline.ingest_document(doc)

        hybrid_engine = HybridRAGEngine(
            config=RAGConfig(mode=RetrievalMode.KEYWORD, similarity_threshold=0.0),
            retriever=retriever,
        )

        def hybrid_rag_handler(query: str = "", **kwargs: object) -> str:
            rag_result = hybrid_engine.query(query)
            return f"RAG answer: {rag_result.answer[:120]}"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="hybrid_rag",
                description="Hybrid RAG search over maritime documents",
            ),
            handler=hybrid_rag_handler,
        )

        engine = ReActEngine(
            config=AgentConfig(name="hybrid-rag-agent", max_steps=5),
            tools=registry,
        )

        result = engine.execute("Tell me about vessels and ports")

        assert result.state == AgentState.COMPLETED
        assert result.answer  # answer must be non-empty


# ===========================================================================
# TestAgentKGIntegration
# ===========================================================================


class TestAgentKGIntegration:
    """Agent engines use CypherBuilder and QualityGate components as tools."""

    @pytest.mark.unit
    def test_react_with_cypher_builder_tool(self) -> None:
        """ReActEngine calls cypher_build tool; observation contains MATCH and RETURN."""
        def cypher_build_handler(query: str = "", **kwargs: object) -> str:
            builder = CypherBuilder()
            cypher_query, _params = (
                builder
                .match("(v:Vessel)")
                .where("v.name = $name", {"name": query})
                .return_("v")
                .build()
            )
            return cypher_query

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="cypher_build",
                description="Build a Cypher query for the KG",
            ),
            handler=cypher_build_handler,
        )

        engine = ReActEngine(
            config=AgentConfig(name="cypher-react-agent", max_steps=5),
            tools=registry,
        )

        result = engine.execute("KRISO vessel")

        assert result.state == AgentState.COMPLETED
        # The observation of the tool call must contain the generated Cypher
        obs_steps = [s for s in result.steps if s.step_type == StepType.OBSERVATION]
        assert len(obs_steps) >= 1
        tool_output = obs_steps[0].content
        assert "MATCH" in tool_output
        assert "RETURN" in tool_output

    @pytest.mark.unit
    def test_pipeline_cypher_then_format(self) -> None:
        """PipelineEngine: step 1 builds Cypher, step 2 wraps it in JSON output."""
        def build_cypher_handler(query: str = "", **kwargs: object) -> str:
            builder = CypherBuilder()
            cypher_query, _params = (
                builder
                .match("(v:Vessel)")
                .return_("v.name AS name, v.mmsi AS mmsi")
                .limit(10)
                .build()
            )
            return cypher_query

        def format_output_handler(
            query: str = "", prev_output: str = "", **kwargs: object
        ) -> str:
            return f'{{"cypher": "{prev_output.replace(chr(10), " ")}", "status": "ok"}}'

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="build_cypher", description="Generate Cypher query"),
            handler=build_cypher_handler,
        )
        registry.register(
            ToolDefinition(name="format_output", description="Format Cypher as JSON"),
            handler=format_output_handler,
        )

        engine = PipelineEngine(
            config=AgentConfig(name="cypher-pipeline", mode=ExecutionMode.PIPELINE),
            tools=registry,
        )
        engine.add_step("build_cypher", description="Build Cypher")
        engine.add_step("format_output", description="Format output")

        result = engine.execute("List all vessels")

        assert result.state == AgentState.COMPLETED
        assert "MATCH" in result.answer or "cypher" in result.answer.lower()

    @pytest.mark.unit
    def test_quality_gate_as_validation_tool(self) -> None:
        """ReActEngine uses a QualityGate-based validation tool; execution completes."""
        def validate_handler(query: str = "", **kwargs: object) -> str:
            check = CheckResult(
                name="data_quality",
                status=CheckStatus.PASSED,
                message=f"Validation passed for query: {query}",
                details={"query": query, "score": 1.0},
            )
            report = GateReport(checks=[check])
            verdict = "PASSED" if report.passed else "FAILED"
            return f"Gate {verdict}: {check.message}"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="validate",
                description="Validate data quality using QualityGate",
            ),
            handler=validate_handler,
        )

        engine = ReActEngine(
            config=AgentConfig(name="validation-agent", max_steps=5),
            tools=registry,
        )

        result = engine.execute("Validate vessel dataset")

        assert result.state == AgentState.COMPLETED


# ===========================================================================
# TestRAGKGIntegration
# ===========================================================================


class TestRAGKGIntegration:
    """RAG pipeline interacts with KG query outputs."""

    @pytest.mark.unit
    def test_rag_with_cypher_results_as_documents(self) -> None:
        """Cypher query result text is ingested as a Document; retriever finds it."""
        # Generate Cypher content via CypherBuilder
        builder = CypherBuilder()
        cypher_query, _params = (
            builder
            .match("(v:Vessel)")
            .where("v.vesselType = $type", {"type": "ContainerShip"})
            .return_("v.name AS name, v.mmsi AS mmsi")
            .limit(10)
            .build()
        )

        # Treat the Cypher query as document content
        cypher_doc = Document(
            doc_id="cypher-result-001",
            title="Vessel Cypher Query",
            content=f"KG Query Result:\n{cypher_query}\nVessel data retrieved successfully.",
            doc_type=DocumentType.TXT,
        )

        embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=64, normalize=True))
        retriever = SimpleRetriever(RAGConfig(similarity_threshold=0.0))
        chunker = TextChunker(ChunkingConfig(chunk_size=512, chunk_overlap=32))
        pipeline = DocumentPipeline(chunker=chunker, embedder=embedder, retriever=retriever)

        ingest_result = pipeline.ingest_document(cypher_doc)
        assert ingest_result.success
        assert ingest_result.chunks_created > 0

        # Query by keyword
        results = retriever.keyword_search("vessel", top_k=5)
        assert len(results) > 0
        # At least one chunk should contain Cypher content
        contents = [r.chunk.content for r in results]
        assert any("MATCH" in c or "vessel" in c.lower() for c in contents)

    @pytest.mark.unit
    def test_quality_gate_on_rag_results(self) -> None:
        """Build a GateReport from RAG retrieval metrics; gate passes when docs found."""
        _, retriever = _build_rag_stack(doc_count=3)

        # Run a search to get a RAG-like result
        results = retriever.keyword_search("vessel port voyage", top_k=5)

        # Build quality checks from retrieval metrics
        chunk_count = len(results)
        avg_score = (
            sum(r.score for r in results) / chunk_count if chunk_count > 0 else 0.0
        )

        checks = [
            CheckResult(
                name="rag_chunk_count",
                status=CheckStatus.PASSED if chunk_count > 0 else CheckStatus.FAILED,
                message=f"Retrieved {chunk_count} chunks",
                details={"chunk_count": chunk_count},
            ),
            CheckResult(
                name="rag_avg_score",
                status=CheckStatus.PASSED if avg_score >= 0.0 else CheckStatus.FAILED,
                message=f"Average score: {avg_score:.4f}",
                details={"avg_score": avg_score},
            ),
        ]

        report = GateReport(checks=checks)

        assert report.passed
        assert len(report.checks) == 2
        assert all(c.status == CheckStatus.PASSED for c in report.checks)

    @pytest.mark.unit
    def test_embedding_consistency_across_pipeline(self) -> None:
        """StubEmbeddingProvider is deterministic; identical text yields identical vectors.

        Cosine similarity of a vector with itself must equal 1.0. This validates
        that RAG embeddings are stable enough for KG entity matching use cases.
        """
        embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=64, normalize=True))
        text = "Container vessel MMSI 123456789 at Port of Busan"

        result1 = embedder.embed_texts([text])
        result2 = embedder.embed_texts([text])

        vec1 = result1.vectors[0]
        vec2 = result2.vectors[0]

        assert vec1 == vec2, "Stub embeddings must be deterministic"

        similarity = SimpleRetriever.cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 1e-9, (
            f"Cosine similarity of identical vectors must be 1.0, got {similarity}"
        )


# ===========================================================================
# TestFullPipelineIntegration
# ===========================================================================


class TestFullPipelineIntegration:
    """End-to-end scenarios combining Agent, RAG, and KG modules."""

    @pytest.mark.unit
    def test_document_to_answer_pipeline(self) -> None:
        """Full flow: ingest docs -> agent uses RAG search -> returns non-empty answer."""
        _, retriever = _build_rag_stack(doc_count=3)

        def rag_search_handler(query: str = "", **kwargs: object) -> str:
            results = retriever.keyword_search(query, top_k=3)
            if results:
                return results[0].chunk.content[:200]
            return "No results found"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="rag_search",
                description="Search maritime documents",
            ),
            handler=rag_search_handler,
        )

        engine = ReActEngine(
            config=AgentConfig(name="doc-to-answer", max_steps=5),
            tools=registry,
        )

        result = engine.execute("What are container vessels?")

        assert result.state == AgentState.COMPLETED
        assert result.answer  # must be non-empty

    @pytest.mark.unit
    def test_multi_document_batch_processing(self) -> None:
        """Ingest 5 documents, run 3 batch queries; all succeed (success_rate == 1.0)."""
        embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=64, normalize=True))
        retriever = SimpleRetriever(RAGConfig(similarity_threshold=0.0))
        chunker = TextChunker(ChunkingConfig(chunk_size=512, chunk_overlap=32))
        doc_pipeline = DocumentPipeline(
            chunker=chunker, embedder=embedder, retriever=retriever
        )

        extra_docs = [
            Document(
                doc_id="doc-004",
                title="Maritime Safety Regulations",
                content=(
                    "SOLAS (Safety of Life at Sea) is the primary international treaty. "
                    "Flag state control and port state control are key enforcement mechanisms."
                ),
                doc_type=DocumentType.TXT,
            ),
            Document(
                doc_id="doc-005",
                title="AIS Tracking Systems",
                content=(
                    "AIS (Automatic Identification System) broadcasts vessel position, "
                    "speed, and heading. AIS Class A is mandatory for large vessels."
                ),
                doc_type=DocumentType.MARKDOWN,
            ),
        ]

        for doc in _make_maritime_docs() + extra_docs:
            res = doc_pipeline.ingest_document(doc)
            assert res.success

        def rag_query_handler(query: str = "", **kwargs: object) -> str:
            results = retriever.keyword_search(query, top_k=3)
            return f"Results: {len(results)} chunks found"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="rag_query", description="Batch RAG keyword search"),
            handler=rag_query_handler,
        )

        engine = BatchEngine(
            config=AgentConfig(name="batch-multi-doc", mode=ExecutionMode.BATCH),
            tools=registry,
            tool_name="rag_query",
        )

        queries = ["container vessel TEU", "port busan berth authority", "safety SOLAS flag state"]
        batch_result = engine.execute_batch(queries)

        assert batch_result.total_count == 3
        assert batch_result.success_rate == 1.0

    @pytest.mark.unit
    def test_cypher_generation_and_rag_combined(self) -> None:
        """Agent pipeline: build Cypher -> RAG search -> combine outputs."""
        _, retriever = _build_rag_stack(doc_count=3)

        def build_query_handler(query: str = "", **kwargs: object) -> str:
            builder = CypherBuilder()
            cypher_query, _params = (
                builder
                .match("(v:Vessel)")
                .where("v.name = $name", {"name": query})
                .return_("v")
                .build()
            )
            return cypher_query

        def search_docs_handler(
            query: str = "", prev_output: str = "", **kwargs: object
        ) -> str:
            results = retriever.keyword_search("vessel", top_k=3)
            docs_summary = f"{len(results)} relevant chunks found"
            return docs_summary

        def combine_handler(
            query: str = "", prev_output: str = "", **kwargs: object
        ) -> str:
            return f"Combined: cypher_available=true, {prev_output}"

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="build_query", description="Build Cypher query"),
            handler=build_query_handler,
        )
        registry.register(
            ToolDefinition(name="search_docs", description="Search RAG documents"),
            handler=search_docs_handler,
        )
        registry.register(
            ToolDefinition(name="combine", description="Combine Cypher + RAG results"),
            handler=combine_handler,
        )

        engine = PipelineEngine(
            config=AgentConfig(name="cypher-rag-pipeline", mode=ExecutionMode.PIPELINE),
            tools=registry,
        )
        engine.add_step("build_query", description="Generate Cypher query")
        engine.add_step("search_docs", description="Search relevant documents")
        engine.add_step("combine", description="Combine results")

        result = engine.execute("Find vessel data")

        assert result.state == AgentState.COMPLETED
        assert "cypher_available" in result.answer or "Combined" in result.answer

    @pytest.mark.unit
    def test_skill_wrapping_rag_workflow(self) -> None:
        """SkillRegistry executes a skill that uses StubEmbedder + SimpleRetriever internally."""
        _, retriever = _build_rag_stack(doc_count=3)
        embedder = StubEmbeddingProvider(EmbeddingConfig(dimension=64, normalize=True))

        def maritime_search_handler(query: str = "", **kwargs: object) -> str:
            # Step 1: Embed the query
            query_vec = embedder.embed_query(query)
            # Step 2: Semantic search
            semantic_results = retriever.retrieve(query_vec, top_k=3)
            # Step 3: Keyword search as fallback
            keyword_results = retriever.keyword_search(query, top_k=3)
            total = len(semantic_results) + len(keyword_results)
            return f"Maritime search found {total} results for '{query}'"

        registry = SkillRegistry()
        registry.register(
            SkillDefinition(
                name="maritime_search",
                description="Search maritime documents using embedding + keyword retrieval",
                category="kg",
                required_tools=(),
            ),
            handler=maritime_search_handler,
        )

        skill_result = registry.execute("maritime_search", {"query": "vessel port"})

        assert skill_result.success
        assert "maritime search" in skill_result.output.lower()
        assert "vessel port" in skill_result.output

    @pytest.mark.unit
    def test_error_resilience_across_modules(self) -> None:
        """Pipeline with a failing step using on_error='skip' completes successfully."""
        _, retriever = _build_rag_stack(doc_count=3)

        def rag_search_handler(query: str = "", **kwargs: object) -> str:
            results = retriever.keyword_search("vessel", top_k=3)
            return f"RAG found {len(results)} chunks"

        def failing_tool_handler(query: str = "", **kwargs: object) -> str:
            raise RuntimeError("Simulated tool failure")

        def cypher_build_handler(
            query: str = "", prev_output: str = "", **kwargs: object
        ) -> str:
            builder = CypherBuilder()
            cypher_query, _params = (
                builder
                .match("(v:Vessel)")
                .return_("v")
                .build()
            )
            return cypher_query

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="rag_search", description="RAG keyword search"),
            handler=rag_search_handler,
        )
        registry.register(
            ToolDefinition(name="failing_tool", description="This tool always fails"),
            handler=failing_tool_handler,
        )
        registry.register(
            ToolDefinition(name="cypher_build", description="Build Cypher query"),
            handler=cypher_build_handler,
        )

        engine = PipelineEngine(
            config=AgentConfig(name="resilient-pipeline", mode=ExecutionMode.PIPELINE),
            tools=registry,
        )
        engine.add_step("rag_search", description="RAG search")
        engine.add_step(
            "failing_tool",
            description="Step that fails",
            on_error="skip",
        )
        engine.add_step("cypher_build", description="Build Cypher")

        result = engine.execute("Find maritime data")

        # Pipeline must complete despite step 2 failure (on_error='skip')
        assert result.state == AgentState.COMPLETED
        # Final answer comes from successful steps; Cypher output should be present
        assert "MATCH" in result.answer or "RAG" in result.answer
