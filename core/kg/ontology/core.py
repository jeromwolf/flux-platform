"""Ontology Core - Palantir Foundry-style ontology definition classes.

Ported from flux-ontology-local's TypeScript ontology-core package.
Provides structured definition of ObjectTypes, LinkTypes, and Functions.

Usage::
    from kg.ontology.core import Ontology, ObjectTypeDefinition, PropertyDefinition

    ontology = Ontology()

    # Define an ObjectType
    vessel = ontology.define_object_type(ObjectTypeDefinition(
        name="Vessel",
        display_name="선박",
        description="Any watercraft or ship operating at sea",
        properties={
            "mmsi": PropertyDefinition(type="INTEGER", required=True, primary_key=True),
            "name": PropertyDefinition(type="STRING", required=True),
            "vesselType": PropertyDefinition(type="STRING"),
        }
    ))

    # Define a LinkType
    ontology.define_link_type(LinkTypeDefinition(
        name="DOCKED_AT",
        from_type="Vessel",
        to_type="Berth",
        cardinality="MANY_TO_ONE",
        properties={"since": PropertyDefinition(type="DATETIME")}
    ))
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PropertyType(str, Enum):
    """Supported property types in the ontology."""

    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    POINT = "POINT"
    LIST_STRING = "LIST<STRING>"
    LIST_FLOAT = "LIST<FLOAT>"
    LIST_INTEGER = "LIST<INTEGER>"


class Cardinality(str, Enum):
    """Relationship cardinality types."""

    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


@dataclass
class PropertyDefinition:
    """Definition of a property on an ObjectType or LinkType."""

    type: str | PropertyType
    required: bool = False
    primary_key: bool = False
    indexed: bool = False
    unique: bool = False
    default: Any = None
    description: str | None = None
    format: str | None = None  # e.g., "email", "uri", "iso8601"
    min_value: float | None = None
    max_value: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None  # regex pattern for validation
    enum_values: list[str] | None = None


@dataclass
class ObjectTypeDefinition:
    """Definition of an ObjectType (entity/node type)."""

    name: str
    display_name: str | None = None
    description: str | None = None
    properties: dict[str, PropertyDefinition] = field(default_factory=dict)
    interfaces: list[str] = field(default_factory=list)
    abstract: bool = False
    parent_type: str | None = None  # for inheritance


@dataclass
class LinkTypeDefinition:
    """Definition of a LinkType (relationship type)."""

    name: str
    from_type: str
    to_type: str
    cardinality: str | Cardinality = Cardinality.MANY_TO_MANY
    description: str | None = None
    properties: dict[str, PropertyDefinition] = field(default_factory=dict)
    bidirectional: bool = False
    required: bool = False


@dataclass
class ActionDefinition:
    """Definition of an Action that can be performed on objects."""

    name: str
    display_name: str | None = None
    description: str | None = None
    target_types: list[str] = field(default_factory=list)
    parameters: dict[str, PropertyDefinition] = field(default_factory=dict)
    returns: str | None = None


@dataclass
class FunctionParameter:
    """Parameter definition for a function."""

    name: str
    type: str
    required: bool = True
    default: Any = None
    description: str | None = None


@dataclass
class FunctionDefinition:
    """Definition of a data transformation function."""

    name: str
    display_name: str | None = None
    description: str | None = None
    parameters: list[FunctionParameter] = field(default_factory=list)
    return_type: str = "any"
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    implementation: Callable[..., Any] | Callable[..., Awaitable[Any]] | None = None


@dataclass
class InterfaceDefinition:
    """Definition of an interface that ObjectTypes can implement."""

    name: str
    description: str | None = None
    properties: dict[str, PropertyDefinition] = field(default_factory=dict)
    methods: dict[str, Callable[..., Any]] = field(default_factory=dict)


class ObjectType:
    """Runtime representation of an ObjectType."""

    def __init__(self, definition: ObjectTypeDefinition):
        self._definition = definition

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def display_name(self) -> str:
        return self._definition.display_name or self._definition.name

    @property
    def description(self) -> str | None:
        return self._definition.description

    @property
    def properties(self) -> dict[str, PropertyDefinition]:
        return self._definition.properties

    @property
    def interfaces(self) -> list[str]:
        return self._definition.interfaces

    def implements_interface(self, interface_name: str) -> bool:
        return interface_name in self._definition.interfaces

    def get_property(self, name: str) -> PropertyDefinition | None:
        return self._definition.properties.get(name)

    def get_primary_key(self) -> str | None:
        for prop_name, prop_def in self._definition.properties.items():
            if prop_def.primary_key:
                return prop_name
        return None

    def get_required_properties(self) -> list[str]:
        return [name for name, prop in self._definition.properties.items() if prop.required]

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate data against this ObjectType's schema.

        Args:
            data: Data dictionary to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: list[str] = []

        # Check required properties
        for name, prop in self._definition.properties.items():
            if prop.required and name not in data:
                errors.append(f"Missing required property: {name}")

        # Check property types and constraints
        for name, value in data.items():
            prop = self._definition.properties.get(name)
            if not prop:
                continue  # Allow extra properties

            # Type checking would go here
            # For now, just check constraints
            if prop.enum_values and value not in prop.enum_values:
                errors.append(f"Property {name} must be one of: {prop.enum_values}")
            if prop.min_length and isinstance(value, str) and len(value) < prop.min_length:
                errors.append(f"Property {name} must have at least {prop.min_length} characters")
            if prop.max_length and isinstance(value, str) and len(value) > prop.max_length:
                errors.append(f"Property {name} must have at most {prop.max_length} characters")

        return len(errors) == 0, errors

    def to_dict(self) -> dict[str, Any]:
        """Export ObjectType definition as dictionary."""
        return {
            "name": self.name,
            "displayName": self.display_name,
            "description": self.description,
            "properties": {
                name: {
                    "type": str(
                        prop.type.value if isinstance(prop.type, PropertyType) else prop.type
                    ),
                    "required": prop.required,
                    "primaryKey": prop.primary_key,
                    "indexed": prop.indexed,
                    "unique": prop.unique,
                    "description": prop.description,
                }
                for name, prop in self._definition.properties.items()
            },
            "interfaces": self.interfaces,
        }


class LinkType:
    """Runtime representation of a LinkType."""

    def __init__(self, definition: LinkTypeDefinition):
        self._definition = definition

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def from_type(self) -> str:
        return self._definition.from_type

    @property
    def to_type(self) -> str:
        return self._definition.to_type

    @property
    def cardinality(self) -> str:
        card = self._definition.cardinality
        return card.value if isinstance(card, Cardinality) else card

    @property
    def description(self) -> str | None:
        return self._definition.description

    @property
    def properties(self) -> dict[str, PropertyDefinition]:
        return self._definition.properties

    def to_dict(self) -> dict[str, Any]:
        """Export LinkType definition as dictionary."""
        return {
            "name": self.name,
            "fromType": self.from_type,
            "toType": self.to_type,
            "cardinality": self.cardinality,
            "description": self.description,
            "properties": {
                name: {"type": str(prop.type), "required": prop.required}
                for name, prop in self._definition.properties.items()
            },
        }


class Action:
    """Runtime representation of an Action."""

    def __init__(self, definition: ActionDefinition):
        self._definition = definition

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def display_name(self) -> str:
        return self._definition.display_name or self._definition.name

    @property
    def target_types(self) -> list[str]:
        return self._definition.target_types

    def get_definition(self) -> ActionDefinition:
        return self._definition


class OntologyFunction:
    """Runtime representation of a Function."""

    def __init__(self, definition: FunctionDefinition):
        self._definition = definition

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def display_name(self) -> str:
        return self._definition.display_name or self._definition.name

    @property
    def description(self) -> str | None:
        return self._definition.description

    @property
    def category(self) -> str | None:
        return self._definition.category

    @property
    def tags(self) -> list[str]:
        return self._definition.tags

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the function with given parameters."""
        if self._definition.implementation is None:
            raise NotImplementedError(f"Function {self.name} has no implementation")

        result = self._definition.implementation(**kwargs)
        if hasattr(result, "__await__"):
            return await result
        return result

    def to_dict(self) -> dict[str, Any]:
        """Export function definition (without implementation)."""
        return {
            "name": self.name,
            "displayName": self.display_name,
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "required": p.required,
                    "description": p.description,
                }
                for p in self._definition.parameters
            ],
            "returnType": self._definition.return_type,
            "category": self.category,
            "tags": self.tags,
        }


class FunctionRegistry:
    """Registry for managing ontology functions."""

    def __init__(self) -> None:
        self._functions: dict[str, OntologyFunction] = {}

    def register(self, definition: FunctionDefinition) -> OntologyFunction:
        """Register a new function."""
        if definition.name in self._functions:
            raise ValueError(f"Function '{definition.name}' already exists")
        func = OntologyFunction(definition)
        self._functions[definition.name] = func
        return func

    def get(self, name: str) -> OntologyFunction | None:
        return self._functions.get(name)

    def has(self, name: str) -> bool:
        return name in self._functions

    def remove(self, name: str) -> bool:
        if name in self._functions:
            del self._functions[name]
            return True
        return False

    def get_all(self) -> list[OntologyFunction]:
        return list(self._functions.values())

    def get_by_category(self, category: str) -> list[OntologyFunction]:
        return [f for f in self._functions.values() if f.category == category]

    def get_by_tag(self, tag: str) -> list[OntologyFunction]:
        return [f for f in self._functions.values() if tag in f.tags]

    def get_categories(self) -> list[str]:
        categories = set()
        for f in self._functions.values():
            if f.category:
                categories.add(f.category)
        return sorted(categories)

    def get_tags(self) -> list[str]:
        tags = set()
        for f in self._functions.values():
            tags.update(f.tags)
        return sorted(tags)

    def search(self, query: str) -> list[OntologyFunction]:
        query_lower = query.lower()
        results = []
        for func in self._functions.values():
            if (
                query_lower in func.name.lower()
                or (func.display_name and query_lower in func.display_name.lower())
                or (func.description and query_lower in func.description.lower())
            ):
                results.append(func)
        return results

    def export_all(self) -> list[dict[str, Any]]:
        return [f.to_dict() for f in self._functions.values()]


class Ontology:
    """Main ontology container managing all types and definitions.

    This is the central class for defining and managing the ontology schema.
    """

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._object_types: dict[str, ObjectType] = {}
        self._link_types: dict[str, LinkType] = {}
        self._actions: dict[str, Action] = {}
        self._interfaces: dict[str, InterfaceDefinition] = {}
        self._functions = FunctionRegistry()

    @property
    def name(self) -> str:
        return self._name

    # =========================================================================
    # ObjectType Methods
    # =========================================================================

    def define_object_type(self, definition: ObjectTypeDefinition) -> ObjectType:
        """Define a new ObjectType.

        Args:
            definition: ObjectType definition

        Returns:
            Created ObjectType

        Raises:
            ValueError: If ObjectType already exists
        """
        if definition.name in self._object_types:
            raise ValueError(f"ObjectType '{definition.name}' already exists")

        object_type = ObjectType(definition)
        self._object_types[definition.name] = object_type
        return object_type

    def get_object_type(self, name: str) -> ObjectType | None:
        return self._object_types.get(name)

    def get_all_object_types(self) -> list[ObjectType]:
        return list(self._object_types.values())

    def get_object_types_by_interface(self, interface_name: str) -> list[ObjectType]:
        return [ot for ot in self._object_types.values() if ot.implements_interface(interface_name)]

    # =========================================================================
    # LinkType Methods
    # =========================================================================

    def define_link_type(self, definition: LinkTypeDefinition) -> LinkType:
        """Define a new LinkType.

        Args:
            definition: LinkType definition

        Returns:
            Created LinkType

        Raises:
            ValueError: If LinkType already exists or references unknown ObjectTypes
        """
        if definition.name in self._link_types:
            raise ValueError(f"LinkType '{definition.name}' already exists")

        if definition.from_type not in self._object_types:
            raise ValueError(f"ObjectType '{definition.from_type}' does not exist")
        if definition.to_type not in self._object_types:
            raise ValueError(f"ObjectType '{definition.to_type}' does not exist")

        link_type = LinkType(definition)
        self._link_types[definition.name] = link_type
        return link_type

    def get_link_type(self, name: str) -> LinkType | None:
        return self._link_types.get(name)

    def get_all_link_types(self) -> list[LinkType]:
        return list(self._link_types.values())

    def get_link_types_for_object(self, object_type_name: str) -> dict[str, list[LinkType]]:
        """Get all LinkTypes connected to an ObjectType.

        Returns:
            Dict with 'outgoing' and 'incoming' lists
        """
        outgoing = []
        incoming = []

        for lt in self._link_types.values():
            if lt.from_type == object_type_name:
                outgoing.append(lt)
            if lt.to_type == object_type_name:
                incoming.append(lt)

        return {"outgoing": outgoing, "incoming": incoming}

    # =========================================================================
    # Action Methods
    # =========================================================================

    def define_action(self, definition: ActionDefinition) -> Action:
        if definition.name in self._actions:
            raise ValueError(f"Action '{definition.name}' already exists")

        action = Action(definition)
        self._actions[definition.name] = action
        return action

    def get_action(self, name: str) -> Action | None:
        return self._actions.get(name)

    def get_all_actions(self) -> list[Action]:
        return list(self._actions.values())

    # =========================================================================
    # Interface Methods
    # =========================================================================

    def define_interface(self, definition: InterfaceDefinition) -> None:
        if definition.name in self._interfaces:
            raise ValueError(f"Interface '{definition.name}' already exists")
        self._interfaces[definition.name] = definition

    def get_interface(self, name: str) -> InterfaceDefinition | None:
        return self._interfaces.get(name)

    def get_all_interfaces(self) -> list[InterfaceDefinition]:
        return list(self._interfaces.values())

    # =========================================================================
    # Function Methods
    # =========================================================================

    def define_function(self, definition: FunctionDefinition) -> OntologyFunction:
        return self._functions.register(definition)

    def get_function(self, name: str) -> OntologyFunction | None:
        return self._functions.get(name)

    def get_all_functions(self) -> list[OntologyFunction]:
        return self._functions.get_all()

    def get_function_registry(self) -> FunctionRegistry:
        return self._functions

    # =========================================================================
    # Validation & Export
    # =========================================================================

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the entire ontology for consistency.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: list[str] = []

        # Validate LinkTypes reference existing ObjectTypes
        for lt in self._link_types.values():
            if lt.from_type not in self._object_types:
                errors.append(
                    f"LinkType '{lt.name}' references non-existent ObjectType '{lt.from_type}'"
                )
            if lt.to_type not in self._object_types:
                errors.append(
                    f"LinkType '{lt.name}' references non-existent ObjectType '{lt.to_type}'"
                )

        # Validate ObjectTypes implement existing interfaces
        for ot in self._object_types.values():
            for interface_name in ot.interfaces:
                if interface_name not in self._interfaces:
                    errors.append(
                        f"ObjectType '{ot.name}' implements non-existent "
                        f"interface '{interface_name}'"
                    )

        return len(errors) == 0, errors

    def export(self) -> dict[str, Any]:
        """Export the entire ontology as a dictionary.

        Returns:
            Dictionary representation of the ontology
        """
        return {
            "name": self._name,
            "objectTypes": [ot.to_dict() for ot in self._object_types.values()],
            "linkTypes": [lt.to_dict() for lt in self._link_types.values()],
            "actions": [a.get_definition().__dict__ for a in self._actions.values()],
            "interfaces": [
                {"name": i.name, "description": i.description} for i in self._interfaces.values()
            ],
            "functions": self._functions.export_all(),
        }

    def get_schema_summary(self) -> str:
        """Get a human-readable summary of the ontology schema.

        Useful for LLM prompts.
        """
        lines = [f"Ontology: {self._name}", ""]

        lines.append(f"ObjectTypes ({len(self._object_types)}):")
        for ot in self._object_types.values():
            props = ", ".join(ot.properties.keys())
            lines.append(f"  - {ot.name}: {props}")

        lines.append("")
        lines.append(f"LinkTypes ({len(self._link_types)}):")
        for lt in self._link_types.values():
            lines.append(f"  - ({lt.from_type})-[:{lt.name}]->({lt.to_type})")

        return "\n".join(lines)
