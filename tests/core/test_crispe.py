"""Unit tests for the CRISPE prompt framework (kg.crispe)."""

from __future__ import annotations

import pytest

from kg.crispe import (
    CRISPEConfig,
    CRISPEPromptBuilder,
    LLMCypherGenerator,
    SchemaContext,
    _extract_cypher,
    _looks_like_cypher,
    get_default_maritime_schema,
)


# Marker for all tests in this file
pytestmark = pytest.mark.unit


# =============================================================================
# Mock helpers
# =============================================================================


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, response_text: str = "MATCH (v:Vessel) RETURN v"):
        self._response = response_text

    def generate(self, prompt: str, **kwargs) -> object:
        class MockResponse:
            def __init__(self, text: str):
                self.text = text

        return MockResponse(self._response)

    def is_available(self) -> bool:
        return True


@pytest.fixture
def simple_schema() -> SchemaContext:
    """Minimal SchemaContext for prompt builder tests."""
    return SchemaContext(
        node_labels=["Vessel", "Port"],
        relationship_types=["DOCKED_AT"],
        properties={"Vessel": ["name", "mmsi"]},
        sample_queries=[
            ("Find all vessels", "MATCH (v:Vessel) RETURN v"),
        ],
    )


@pytest.fixture
def maritime_schema() -> SchemaContext:
    """Full maritime schema from the module default factory."""
    return get_default_maritime_schema()


# =============================================================================
# CRISPEConfig tests
# =============================================================================


@pytest.mark.unit
def test_crispe_config_defaults() -> None:
    """Default config has 'maritime' domain and non-empty string fields."""
    cfg = CRISPEConfig()

    assert cfg.domain == "maritime"
    assert cfg.capacity != ""
    assert cfg.role != ""
    assert cfg.personality != ""
    assert cfg.experiment != ""


@pytest.mark.unit
def test_crispe_config_custom() -> None:
    """Custom config preserves all fields exactly."""
    cfg = CRISPEConfig(
        capacity="expert",
        role="translator",
        personality="terse",
        experiment="try twice",
        domain="aviation",
    )

    assert cfg.capacity == "expert"
    assert cfg.role == "translator"
    assert cfg.personality == "terse"
    assert cfg.experiment == "try twice"
    assert cfg.domain == "aviation"


@pytest.mark.unit
def test_crispe_config_frozen() -> None:
    """CRISPEConfig is immutable — attribute assignment raises FrozenInstanceError."""
    from dataclasses import FrozenInstanceError

    cfg = CRISPEConfig()
    with pytest.raises(FrozenInstanceError):
        cfg.domain = "changed"  # type: ignore[misc]


# =============================================================================
# SchemaContext tests
# =============================================================================


@pytest.mark.unit
def test_schema_context_stores_tuples() -> None:
    """Lists passed to SchemaContext are stored as tuples."""
    schema = SchemaContext(
        node_labels=["Vessel", "Port"],
        relationship_types=["DOCKED_AT"],
        properties={"Vessel": ["name"]},
        sample_queries=[("Q", "MATCH (n) RETURN n")],
    )

    assert isinstance(schema.node_labels, tuple)
    assert isinstance(schema.relationship_types, tuple)
    assert isinstance(schema.sample_queries, tuple)
    # Each sample query pair must also be a tuple
    assert isinstance(schema.sample_queries[0], tuple)


@pytest.mark.unit
def test_schema_context_properties_accessible() -> None:
    """Dict properties can be read back after construction."""
    props = {"Vessel": ["name", "mmsi"], "Port": ["name", "unlocode"]}
    schema = SchemaContext(
        node_labels=["Vessel", "Port"],
        relationship_types=["DOCKED_AT"],
        properties=props,
        sample_queries=[],
    )

    assert schema.properties["Vessel"] == ["name", "mmsi"]
    assert schema.properties["Port"] == ["name", "unlocode"]


@pytest.mark.unit
def test_schema_context_frozen() -> None:
    """SchemaContext is immutable — attribute assignment raises FrozenInstanceError."""
    from dataclasses import FrozenInstanceError

    schema = SchemaContext(
        node_labels=["Vessel"],
        relationship_types=["DOCKED_AT"],
        properties={},
        sample_queries=[],
    )
    with pytest.raises(FrozenInstanceError):
        schema.node_labels = ("NewLabel",)  # type: ignore[misc]


# =============================================================================
# CRISPEPromptBuilder tests
# =============================================================================


@pytest.mark.unit
def test_prompt_has_all_sections(simple_schema: SchemaContext) -> None:
    """Generated prompt contains all six CRISPE section headers."""
    builder = CRISPEPromptBuilder()
    prompt = builder.build_prompt("Find all vessels", simple_schema)

    for section in ("[Capacity]", "[Role]", "[Insight]", "[Statement]", "[Personality]", "[Experiment]"):
        assert section in prompt, f"Missing section: {section}"


@pytest.mark.unit
def test_prompt_contains_query(simple_schema: SchemaContext) -> None:
    """The user query text appears verbatim in the generated prompt."""
    builder = CRISPEPromptBuilder()
    query = "List all container ships docked at Busan"
    prompt = builder.build_prompt(query, simple_schema)

    assert query in prompt


@pytest.mark.unit
def test_prompt_contains_schema_info(simple_schema: SchemaContext) -> None:
    """Node labels and relationship types from the schema appear in the prompt."""
    builder = CRISPEPromptBuilder()
    prompt = builder.build_prompt("Find vessels", simple_schema)

    assert "Vessel" in prompt
    assert "Port" in prompt
    assert "DOCKED_AT" in prompt


@pytest.mark.unit
def test_prompt_contains_sample_queries(simple_schema: SchemaContext) -> None:
    """Sample queries from the schema appear in the prompt output."""
    builder = CRISPEPromptBuilder()
    prompt = builder.build_prompt("Find vessels", simple_schema)

    assert "Find all vessels" in prompt
    assert "MATCH (v:Vessel) RETURN v" in prompt


@pytest.mark.unit
def test_prompt_custom_config(simple_schema: SchemaContext) -> None:
    """Custom domain name appears inside the [Role] section."""
    config = CRISPEConfig(domain="aviation")
    builder = CRISPEPromptBuilder(config=config)
    prompt = builder.build_prompt("Find all aircraft", simple_schema)

    # The [Role] section references the domain
    role_start = prompt.index("[Role]")
    role_block = prompt[role_start : role_start + 300]
    assert "aviation" in role_block


@pytest.mark.unit
def test_prompt_with_history_has_history_section(simple_schema: SchemaContext) -> None:
    """When history is provided, the prompt includes a [History] section."""
    builder = CRISPEPromptBuilder()
    history = [
        ("Previous question", "MATCH (v:Vessel) RETURN v"),
    ]
    prompt = builder.build_prompt_with_history("Next question", simple_schema, history)

    assert "[History]" in prompt


@pytest.mark.unit
def test_prompt_with_empty_history(simple_schema: SchemaContext) -> None:
    """Empty history list does NOT add a [History] section to the prompt."""
    builder = CRISPEPromptBuilder()
    prompt = builder.build_prompt_with_history("Find vessels", simple_schema, history=[])

    assert "[History]" not in prompt


# =============================================================================
# _extract_cypher tests
# =============================================================================


@pytest.mark.unit
def test_extract_raw_cypher() -> None:
    """Raw Cypher without fencing is returned as-is."""
    raw = "MATCH (v:Vessel) RETURN v"
    result = _extract_cypher(raw)
    assert result == raw


@pytest.mark.unit
def test_extract_cypher_fenced() -> None:
    """Cypher wrapped in ```cypher fences is extracted cleanly."""
    fenced = "```cypher\nMATCH (v:Vessel) RETURN v\n```"
    result = _extract_cypher(fenced)
    assert result == "MATCH (v:Vessel) RETURN v"


@pytest.mark.unit
def test_extract_generic_fenced() -> None:
    """Cypher wrapped in generic ``` fences is extracted when it looks like Cypher."""
    fenced = "```\nMATCH (v:Vessel) RETURN v\n```"
    result = _extract_cypher(fenced)
    assert result == "MATCH (v:Vessel) RETURN v"


@pytest.mark.unit
def test_extract_cypher_with_explanation() -> None:
    """Cypher preceded by an explanation line is extracted without the explanation."""
    text = "Here is the query:\nMATCH (v:Vessel)\nRETURN v\n\nThis query finds all vessels."
    result = _extract_cypher(text)

    assert "MATCH" in result
    assert "RETURN" in result
    # Explanation text after blank line should be stripped
    assert "This query finds" not in result


@pytest.mark.unit
def test_extract_cypher_multiline() -> None:
    """Multiline Cypher with WHERE, ORDER BY, LIMIT is extracted intact."""
    cypher = (
        "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port)\n"
        "WHERE p.name = 'Busan'\n"
        "RETURN v.name, v.mmsi\n"
        "ORDER BY v.name ASC\n"
        "LIMIT 10"
    )
    result = _extract_cypher(cypher)

    assert "MATCH" in result
    assert "WHERE" in result
    assert "ORDER BY" in result
    assert "LIMIT" in result


@pytest.mark.unit
def test_extract_non_cypher() -> None:
    """Non-Cypher text is returned as-is (fallback behaviour)."""
    text = "Hello world"
    result = _extract_cypher(text)
    assert result == text


# =============================================================================
# _looks_like_cypher tests
# =============================================================================


@pytest.mark.unit
def test_looks_like_cypher_true() -> None:
    """'MATCH (n) RETURN n' is recognised as Cypher."""
    assert _looks_like_cypher("MATCH (n) RETURN n") is True


@pytest.mark.unit
def test_looks_like_cypher_false() -> None:
    """Plain prose is not recognised as Cypher."""
    assert _looks_like_cypher("Hello world") is False


# =============================================================================
# LLMCypherGenerator tests
# =============================================================================


@pytest.mark.unit
def test_llm_generator_basic(simple_schema: SchemaContext) -> None:
    """Mock LLM that returns raw Cypher produces a valid GeneratedQuery."""
    llm = MockLLMProvider("MATCH (v:Vessel) RETURN v")
    generator = LLMCypherGenerator(llm_provider=llm)
    result = generator.generate("Find all vessels", simple_schema)

    assert result is not None
    assert "MATCH" in result.query
    assert "RETURN" in result.query


@pytest.mark.unit
def test_llm_generator_fenced_response(simple_schema: SchemaContext) -> None:
    """Mock LLM that returns a ```cypher fenced response is extracted correctly."""
    llm = MockLLMProvider("```cypher\nMATCH (v:Vessel) RETURN v\n```")
    generator = LLMCypherGenerator(llm_provider=llm)
    result = generator.generate("Find all vessels", simple_schema)

    assert result.query == "MATCH (v:Vessel) RETURN v"


@pytest.mark.unit
def test_llm_generator_with_history(simple_schema: SchemaContext) -> None:
    """generate_with_history produces a GeneratedQuery from conversation history."""
    llm = MockLLMProvider("MATCH (v:Vessel) WHERE v.status = 'ANCHORED' RETURN v")
    generator = LLMCypherGenerator(llm_provider=llm)
    history = [("Previous query", "MATCH (v:Vessel) RETURN v")]
    result = generator.generate_with_history(
        "Now filter by anchored status", simple_schema, history
    )

    assert result is not None
    assert "MATCH" in result.query


@pytest.mark.unit
def test_llm_generator_returns_cypher_language(simple_schema: SchemaContext) -> None:
    """The language field of the returned GeneratedQuery is always 'cypher'."""
    llm = MockLLMProvider("MATCH (v:Vessel) RETURN v")
    generator = LLMCypherGenerator(llm_provider=llm)
    result = generator.generate("Find vessels", simple_schema)

    assert result.language == "cypher"


# =============================================================================
# get_default_maritime_schema tests
# =============================================================================


@pytest.mark.unit
def test_default_schema_has_vessel(maritime_schema: SchemaContext) -> None:
    """'Vessel' is present in node_labels of the default maritime schema."""
    assert "Vessel" in maritime_schema.node_labels


@pytest.mark.unit
def test_default_schema_has_relationships(maritime_schema: SchemaContext) -> None:
    """'DOCKED_AT' is present in relationship_types of the default maritime schema."""
    assert "DOCKED_AT" in maritime_schema.relationship_types


@pytest.mark.unit
def test_default_schema_has_sample_queries(maritime_schema: SchemaContext) -> None:
    """The default maritime schema has at least 3 sample query pairs."""
    assert len(maritime_schema.sample_queries) >= 3


@pytest.mark.unit
def test_default_schema_properties(maritime_schema: SchemaContext) -> None:
    """'Vessel' is in properties and has both 'name' and 'mmsi' fields."""
    assert "Vessel" in maritime_schema.properties
    vessel_props = maritime_schema.properties["Vessel"]
    assert "name" in vessel_props
    assert "mmsi" in vessel_props
