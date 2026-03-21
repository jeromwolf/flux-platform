"""Backward compatibility shim — use maritime.ontology.maritime_ontology instead."""
import warnings

warnings.warn(
    "Importing from 'kg.ontology.maritime_ontology' is deprecated. "
    "Use 'maritime.ontology.maritime_ontology' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.ontology.maritime_ontology import *  # noqa: F401,F403
from maritime.ontology.maritime_ontology import (  # noqa: F401
    ENTITY_LABELS,
    PROPERTY_DEFINITIONS,
    RELATIONSHIP_TYPES,
)
