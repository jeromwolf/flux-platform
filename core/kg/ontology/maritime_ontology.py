"""Backward compatibility shim — use maritime.ontology.maritime_ontology instead."""
from maritime.ontology.maritime_ontology import *  # noqa: F401,F403
from maritime.ontology.maritime_ontology import (  # noqa: F401
    ENTITY_LABELS,
    PROPERTY_DEFINITIONS,
    RELATIONSHIP_TYPES,
)
