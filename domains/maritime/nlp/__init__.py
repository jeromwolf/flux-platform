"""Maritime NLP term dictionary."""

from maritime.nlp.maritime_terms import (
    ENTITY_SYNONYMS,
    NAMED_ENTITIES,
    PROPERTY_VALUE_MAP,
    RELATIONSHIP_KEYWORDS,
    get_term_context_for_llm,
    resolve_entity,
    resolve_named_entity,
    resolve_property_value,
)

__all__ = [
    "ENTITY_SYNONYMS",
    "NAMED_ENTITIES",
    "PROPERTY_VALUE_MAP",
    "RELATIONSHIP_KEYWORDS",
    "get_term_context_for_llm",
    "resolve_entity",
    "resolve_named_entity",
    "resolve_property_value",
]
