"""Backward compatibility shim — use maritime.nlp.maritime_terms instead."""
from maritime.nlp.maritime_terms import *  # noqa: F401,F403
from maritime.nlp.maritime_terms import (  # noqa: F401
    ENTITY_SYNONYMS,
    NAMED_ENTITIES,
    PROPERTY_VALUE_MAP,
    RELATIONSHIP_KEYWORDS,
    get_term_context_for_llm,
    resolve_entity,
    resolve_named_entity,
    resolve_property_value,
)
