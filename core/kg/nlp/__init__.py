"""Natural language processing utilities for knowledge graph domains."""

from kg.nlp.maritime_terms import (
    ENTITY_SYNONYMS,
    NAMED_ENTITIES,
    PROPERTY_VALUE_MAP,
    RELATIONSHIP_KEYWORDS,
    get_term_context_for_llm,
    resolve_entity,
    resolve_named_entity,
    resolve_property_value,
)
from kg.nlp.nl_parser import NLParser, ParseResult
from kg.nlp.term_dictionary import TermDictionary

__all__ = [
    "ENTITY_SYNONYMS",
    "RELATIONSHIP_KEYWORDS",
    "PROPERTY_VALUE_MAP",
    "NAMED_ENTITIES",
    "resolve_entity",
    "resolve_property_value",
    "resolve_named_entity",
    "get_term_context_for_llm",
    "NLParser",
    "ParseResult",
    "TermDictionary",
]
