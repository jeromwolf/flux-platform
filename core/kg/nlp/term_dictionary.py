"""Abstract term dictionary protocol for domain-independent NL parsing.

Implementations provide Korean→English mappings for entity labels,
named entities, relationships, and property values.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TermDictionary(Protocol):
    """Protocol for domain-specific term dictionaries.

    Any module providing these four dictionaries satisfies
    the protocol and can be used with NLParser.
    """

    @property
    def entity_synonyms(self) -> dict[str, str]:
        """Korean term -> Neo4j entity label mapping."""
        ...

    @property
    def named_entities(self) -> dict[str, dict[str, str]]:
        """Named entity -> {label, key, value} mapping."""
        ...

    @property
    def relationship_keywords(self) -> dict[str, str]:
        """Korean phrase -> relationship type mapping."""
        ...

    @property
    def property_value_map(self) -> dict[str, dict[str, Any]]:
        """Property name -> {Korean value -> English value} mapping."""
        ...
