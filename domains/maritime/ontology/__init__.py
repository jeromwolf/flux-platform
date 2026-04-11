"""Maritime domain ontology definitions."""

from .maritime_loader import load_maritime_ontology
from .maritime_ontology import (
    ENTITY_LABELS,
    PROPERTY_DEFINITIONS,
    RELATIONSHIP_TYPES,
)

__all__ = [
    "ENTITY_LABELS",
    "PROPERTY_DEFINITIONS",
    "RELATIONSHIP_TYPES",
    "load_maritime_ontology",
]
