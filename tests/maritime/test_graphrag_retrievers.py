"""Unit tests for poc.graphrag_retrievers module.

All tests mock neo4j_graphrag imports so no running services needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestConstants:
    """Verify constants match the schema definitions."""

    def test_vector_index_name(self) -> None:
        from poc.graphrag_retrievers import VECTOR_INDEX_NAME
        assert VECTOR_INDEX_NAME == "text_embedding"

    def test_fulltext_index_name(self) -> None:
        from poc.graphrag_retrievers import FULLTEXT_INDEX_NAME
        assert FULLTEXT_INDEX_NAME == "document_search"

    def test_default_llm_model(self) -> None:
        from poc.graphrag_retrievers import DEFAULT_LLM_MODEL
        assert DEFAULT_LLM_MODEL == "qwen2.5:7b"

    def test_document_return_properties(self) -> None:
        from poc.graphrag_retrievers import DOCUMENT_RETURN_PROPERTIES
        assert "docId" in DOCUMENT_RETURN_PROPERTIES
        assert "title" in DOCUMENT_RETURN_PROPERTIES
        assert "content" in DOCUMENT_RETURN_PROPERTIES
        assert len(DOCUMENT_RETURN_PROPERTIES) >= 5


@pytest.mark.unit
class TestSchemaText:
    """Verify the schema text contains key elements."""

    def test_contains_key_node_labels(self) -> None:
        from poc.graphrag_retrievers import NEO4J_SCHEMA_TEXT
        for label in ["Vessel", "Port", "Document", "TestFacility", "Experiment", "Incident"]:
            assert label in NEO4J_SCHEMA_TEXT, f"Missing label: {label}"

    def test_contains_key_relationships(self) -> None:
        from poc.graphrag_retrievers import NEO4J_SCHEMA_TEXT
        for rel in ["DOCKED_AT", "ISSUED_BY", "CONDUCTED_AT", "ON_VOYAGE", "HAS_FACILITY"]:
            assert rel in NEO4J_SCHEMA_TEXT, f"Missing relationship: {rel}"

    def test_contains_key_properties(self) -> None:
        from poc.graphrag_retrievers import NEO4J_SCHEMA_TEXT
        for prop in ["vesselId", "portId", "docId", "textEmbedding"]:
            assert prop in NEO4J_SCHEMA_TEXT, f"Missing property: {prop}"


@pytest.mark.unit
class TestText2CypherExamples:
    """Verify few-shot examples are valid."""

    def test_examples_not_empty(self) -> None:
        from poc.graphrag_retrievers import TEXT2CYPHER_EXAMPLES
        assert len(TEXT2CYPHER_EXAMPLES) >= 3

    def test_examples_contain_cypher(self) -> None:
        from poc.graphrag_retrievers import TEXT2CYPHER_EXAMPLES
        for example in TEXT2CYPHER_EXAMPLES:
            assert "CYPHER:" in example or "MATCH" in example

    def test_examples_contain_korean(self) -> None:
        from poc.graphrag_retrievers import TEXT2CYPHER_EXAMPLES
        for example in TEXT2CYPHER_EXAMPLES:
            assert any('\uAC00' <= c <= '\uD7A3' for c in example)


@pytest.mark.unit
class TestCreateVectorRetriever:
    """Test vector retriever factory."""

    @patch("neo4j_graphrag.retrievers.VectorRetriever")
    def test_uses_correct_index(self, mock_vr_class: MagicMock) -> None:
        from poc.graphrag_retrievers import create_vector_retriever
        driver = MagicMock()
        embedder = MagicMock()
        create_vector_retriever(driver, embedder)
        mock_vr_class.assert_called_once()
        kwargs = mock_vr_class.call_args.kwargs
        assert kwargs["index_name"] == "text_embedding"

    @patch("neo4j_graphrag.retrievers.VectorRetriever")
    def test_passes_return_properties(self, mock_vr_class: MagicMock) -> None:
        from poc.graphrag_retrievers import DOCUMENT_RETURN_PROPERTIES, create_vector_retriever
        driver = MagicMock()
        embedder = MagicMock()
        create_vector_retriever(driver, embedder)
        kwargs = mock_vr_class.call_args.kwargs
        assert kwargs["return_properties"] == DOCUMENT_RETURN_PROPERTIES

    @patch("neo4j_graphrag.retrievers.VectorRetriever")
    def test_custom_return_properties(self, mock_vr_class: MagicMock) -> None:
        from poc.graphrag_retrievers import create_vector_retriever
        driver = MagicMock()
        embedder = MagicMock()
        create_vector_retriever(driver, embedder, return_properties=["title"])
        kwargs = mock_vr_class.call_args.kwargs
        assert kwargs["return_properties"] == ["title"]

    @patch("neo4j_graphrag.retrievers.VectorRetriever")
    def test_passes_database(self, mock_vr_class: MagicMock) -> None:
        from poc.graphrag_retrievers import create_vector_retriever
        driver = MagicMock()
        embedder = MagicMock()
        create_vector_retriever(driver, embedder, neo4j_database="testdb")
        kwargs = mock_vr_class.call_args.kwargs
        assert kwargs["neo4j_database"] == "testdb"


@pytest.mark.unit
class TestCreateVectorCypherRetriever:
    """Test vector cypher retriever factory."""

    @patch("neo4j_graphrag.retrievers.VectorCypherRetriever")
    def test_uses_default_retrieval_query(self, mock_vcr_class: MagicMock) -> None:
        from poc.graphrag_retrievers import create_vector_cypher_retriever
        driver = MagicMock()
        embedder = MagicMock()
        create_vector_cypher_retriever(driver, embedder)
        kwargs = mock_vcr_class.call_args.kwargs
        assert "ISSUED_BY" in kwargs["retrieval_query"]
        assert "score" in kwargs["retrieval_query"]

    @patch("neo4j_graphrag.retrievers.VectorCypherRetriever")
    def test_custom_retrieval_query(self, mock_vcr_class: MagicMock) -> None:
        from poc.graphrag_retrievers import create_vector_cypher_retriever
        custom_query = "RETURN node.title AS title, score"
        create_vector_cypher_retriever(
            MagicMock(), MagicMock(), retrieval_query=custom_query
        )
        kwargs = mock_vcr_class.call_args.kwargs
        assert kwargs["retrieval_query"] == custom_query


@pytest.mark.unit
class TestCreateText2CypherRetriever:
    """Test text2cypher retriever factory."""

    @patch("neo4j_graphrag.llm.OllamaLLM")
    @patch("neo4j_graphrag.retrievers.Text2CypherRetriever")
    def test_creates_default_llm(self, mock_t2c_class: MagicMock, mock_llm_class: MagicMock) -> None:
        from poc.graphrag_retrievers import create_text2cypher_retriever
        create_text2cypher_retriever(MagicMock())
        mock_llm_class.assert_called_once_with(model_name="qwen2.5:7b")

    @patch("neo4j_graphrag.retrievers.Text2CypherRetriever")
    def test_uses_provided_llm(self, mock_t2c_class: MagicMock) -> None:
        from poc.graphrag_retrievers import create_text2cypher_retriever
        custom_llm = MagicMock()
        create_text2cypher_retriever(MagicMock(), custom_llm)
        kwargs = mock_t2c_class.call_args.kwargs
        assert kwargs["llm"] is custom_llm

    @patch("neo4j_graphrag.llm.OllamaLLM")
    @patch("neo4j_graphrag.retrievers.Text2CypherRetriever")
    def test_passes_schema(self, mock_t2c_class: MagicMock, mock_llm_class: MagicMock) -> None:
        from poc.graphrag_retrievers import NEO4J_SCHEMA_TEXT, create_text2cypher_retriever
        create_text2cypher_retriever(MagicMock())
        kwargs = mock_t2c_class.call_args.kwargs
        assert kwargs["neo4j_schema"] == NEO4J_SCHEMA_TEXT

    @patch("neo4j_graphrag.llm.OllamaLLM")
    @patch("neo4j_graphrag.retrievers.Text2CypherRetriever")
    def test_passes_examples(self, mock_t2c_class: MagicMock, mock_llm_class: MagicMock) -> None:
        from poc.graphrag_retrievers import TEXT2CYPHER_EXAMPLES, create_text2cypher_retriever
        create_text2cypher_retriever(MagicMock())
        kwargs = mock_t2c_class.call_args.kwargs
        assert kwargs["examples"] == TEXT2CYPHER_EXAMPLES


@pytest.mark.unit
class TestCreateHybridRetriever:
    """Test hybrid retriever factory."""

    @patch("neo4j_graphrag.retrievers.HybridRetriever")
    def test_uses_both_indexes(self, mock_hr_class: MagicMock) -> None:
        from poc.graphrag_retrievers import create_hybrid_retriever
        create_hybrid_retriever(MagicMock(), MagicMock())
        kwargs = mock_hr_class.call_args.kwargs
        assert kwargs["vector_index_name"] == "text_embedding"
        assert kwargs["fulltext_index_name"] == "document_search"


@pytest.mark.unit
class TestCreateToolsRetriever:
    """Test tools retriever factory (agentic)."""

    @patch("neo4j_graphrag.retrievers.HybridRetriever")
    @patch("neo4j_graphrag.retrievers.Text2CypherRetriever")
    @patch("neo4j_graphrag.retrievers.VectorCypherRetriever")
    @patch("neo4j_graphrag.retrievers.VectorRetriever")
    @patch("neo4j_graphrag.retrievers.ToolsRetriever")
    def test_registers_four_tools(
        self,
        mock_tools_class: MagicMock,
        mock_vr: MagicMock,
        mock_vcr: MagicMock,
        mock_t2c: MagicMock,
        mock_hr: MagicMock,
    ) -> None:
        from poc.graphrag_retrievers import create_tools_retriever

        # Setup mock convert_to_tool
        for mock_cls in [mock_vr, mock_vcr, mock_t2c, mock_hr]:
            instance = mock_cls.return_value
            instance.convert_to_tool.return_value = MagicMock()

        create_tools_retriever(MagicMock(), MagicMock(), MagicMock())
        kwargs = mock_tools_class.call_args.kwargs
        assert len(kwargs["tools"]) == 4

    @patch("neo4j_graphrag.retrievers.HybridRetriever")
    @patch("neo4j_graphrag.retrievers.Text2CypherRetriever")
    @patch("neo4j_graphrag.retrievers.VectorCypherRetriever")
    @patch("neo4j_graphrag.retrievers.VectorRetriever")
    @patch("neo4j_graphrag.retrievers.ToolsRetriever")
    def test_tool_names_are_unique(
        self,
        mock_tools_class: MagicMock,
        mock_vr: MagicMock,
        mock_vcr: MagicMock,
        mock_t2c: MagicMock,
        mock_hr: MagicMock,
    ) -> None:
        from poc.graphrag_retrievers import create_tools_retriever

        tool_names: list[str] = []
        for mock_cls in [mock_vr, mock_vcr, mock_t2c, mock_hr]:
            instance = mock_cls.return_value
            def capture_tool(name: str, description: str, _names=tool_names) -> MagicMock:
                _names.append(name)
                return MagicMock()
            instance.convert_to_tool.side_effect = capture_tool

        create_tools_retriever(MagicMock(), MagicMock(), MagicMock())
        assert len(tool_names) == len(set(tool_names)), f"Duplicate tool names: {tool_names}"

    @patch("neo4j_graphrag.retrievers.HybridRetriever")
    @patch("neo4j_graphrag.retrievers.Text2CypherRetriever")
    @patch("neo4j_graphrag.retrievers.VectorCypherRetriever")
    @patch("neo4j_graphrag.retrievers.VectorRetriever")
    @patch("neo4j_graphrag.retrievers.ToolsRetriever")
    def test_tool_descriptions_are_korean(
        self,
        mock_tools_class: MagicMock,
        mock_vr: MagicMock,
        mock_vcr: MagicMock,
        mock_t2c: MagicMock,
        mock_hr: MagicMock,
    ) -> None:
        from poc.graphrag_retrievers import create_tools_retriever

        descriptions: list[str] = []
        for mock_cls in [mock_vr, mock_vcr, mock_t2c, mock_hr]:
            instance = mock_cls.return_value
            def capture_desc(name: str, description: str, _descs=descriptions) -> MagicMock:
                _descs.append(description)
                return MagicMock()
            instance.convert_to_tool.side_effect = capture_desc

        create_tools_retriever(MagicMock(), MagicMock(), MagicMock())
        for desc in descriptions:
            assert any('\uAC00' <= c <= '\uD7A3' for c in desc), f"Not Korean: {desc}"


@pytest.mark.unit
class TestModuleImportability:
    """Test that the module imports correctly."""

    def test_import_all_factories(self) -> None:
        from poc.graphrag_retrievers import (
            create_hybrid_retriever,
            create_text2cypher_retriever,
            create_tools_retriever,
            create_vector_cypher_retriever,
            create_vector_retriever,
        )
        assert callable(create_vector_retriever)
        assert callable(create_vector_cypher_retriever)
        assert callable(create_text2cypher_retriever)
        assert callable(create_hybrid_retriever)
        assert callable(create_tools_retriever)
