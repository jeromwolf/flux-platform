"""Maritime ontology definitions.

This package provides:
- Core ontology classes (ObjectType, LinkType, Ontology) from flux-ontology-local pattern
- Maritime domain-specific ontology definitions
"""

from kg.ontology.core import (
    Action,
    ActionDefinition,
    Cardinality,
    FunctionDefinition,
    FunctionParameter,
    FunctionRegistry,
    InterfaceDefinition,
    LinkType,
    LinkTypeDefinition,
    ObjectType,
    ObjectTypeDefinition,
    # Core classes
    Ontology,
    OntologyFunction,
    # Definition dataclasses
    PropertyDefinition,
    # Enums
    PropertyType,
)

__all__ = [
    # Core classes
    "Ontology",
    "ObjectType",
    "LinkType",
    "Action",
    "OntologyFunction",
    "FunctionRegistry",
    # Definitions
    "PropertyDefinition",
    "ObjectTypeDefinition",
    "LinkTypeDefinition",
    "ActionDefinition",
    "FunctionDefinition",
    "FunctionParameter",
    "InterfaceDefinition",
    # Enums
    "PropertyType",
    "Cardinality",
]
