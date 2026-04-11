"""Maritime Ontology Loader - Convert legacy definitions to Ontology core.

This module provides utilities to load the maritime ontology definitions
from maritime_ontology.py into the new Ontology core structure.
"""

from __future__ import annotations

from kg.ontology.core import (
    LinkTypeDefinition,
    ObjectTypeDefinition,
    Ontology,
    PropertyDefinition,
    PropertyType,
)
from .maritime_ontology import (
    ENTITY_LABELS,
    PROPERTY_DEFINITIONS,
    RELATIONSHIP_TYPES,
)


def _map_property_type(type_str: str) -> PropertyType:
    """Map string type to PropertyType enum."""
    mapping = {
        "STRING": PropertyType.STRING,
        "INTEGER": PropertyType.INTEGER,
        "FLOAT": PropertyType.FLOAT,
        "BOOLEAN": PropertyType.BOOLEAN,
        "DATE": PropertyType.DATE,
        "DATETIME": PropertyType.DATETIME,
        "POINT": PropertyType.POINT,
        "LIST<STRING>": PropertyType.LIST_STRING,
        "LIST<FLOAT>": PropertyType.LIST_FLOAT,
        "LIST<INTEGER>": PropertyType.LIST_INTEGER,
    }
    return mapping.get(type_str, PropertyType.STRING)


def load_maritime_ontology() -> Ontology:
    """Load the complete maritime ontology into Ontology core.

    Returns:
        Fully populated Ontology instance with all maritime types
    """
    ontology = Ontology(name="maritime")

    # Define all ObjectTypes from ENTITY_LABELS
    for label, description in ENTITY_LABELS.items():
        # Get property definitions if available
        prop_defs = PROPERTY_DEFINITIONS.get(label, {})

        properties: dict[str, PropertyDefinition] = {}
        for prop_name, prop_type in prop_defs.items():
            properties[prop_name] = PropertyDefinition(
                type=_map_property_type(prop_type),
                required=False,  # Could enhance with required info
                indexed=prop_name in ("mmsi", "imo", "unlocode", "name"),
                primary_key=prop_name in ("mmsi", "unlocode", "experimentId"),
            )

        ontology.define_object_type(
            ObjectTypeDefinition(
                name=label,
                description=description,
                properties=properties,
            )
        )

    # Define all LinkTypes from RELATIONSHIP_TYPES
    skipped_links = []
    for rel in RELATIONSHIP_TYPES:
        from_label = rel["from_label"]
        to_label = rel["to_label"]

        # Skip if referenced types don't exist (e.g., abstract base types)
        if ontology.get_object_type(from_label) is None:
            skipped_links.append((rel["type"], from_label))
            continue
        if ontology.get_object_type(to_label) is None:
            skipped_links.append((rel["type"], to_label))
            continue

        # Create property definitions for relationship properties
        rel_properties: dict[str, PropertyDefinition] = {}
        for prop_name in rel.get("properties", []):
            # Infer type from common property names
            if prop_name in ("timestamp", "since", "until", "startTime", "endTime", "eta", "ata"):
                prop_type = PropertyType.DATETIME
            elif prop_name in ("confidence", "similarity", "severity"):
                prop_type = PropertyType.FLOAT
            elif prop_name in ("order", "casualties"):
                prop_type = PropertyType.INTEGER
            else:
                prop_type = PropertyType.STRING

            rel_properties[prop_name] = PropertyDefinition(type=prop_type)

        # Skip duplicate link type names (same Neo4j rel type can connect
        # different node pairs; the ontology core uses name as unique key).
        if ontology.get_link_type(rel["type"]) is not None:
            continue

        ontology.define_link_type(
            LinkTypeDefinition(
                name=rel["type"],
                from_type=from_label,
                to_type=to_label,
                description=rel.get("description", ""),
                properties=rel_properties,
            )
        )

    if skipped_links:
        import warnings

        names = [f"{rel_type}({label})" for rel_type, label in skipped_links]
        warnings.warn(
            f"Skipped {len(skipped_links)} link types with unresolved endpoints: "
            f"{', '.join(names[:5])}{'...' if len(names) > 5 else ''}",
            stacklevel=2,
        )

    return ontology


def export_ontology_to_cypher(ontology: Ontology) -> str:
    """Export ontology as Neo4j constraint/index creation statements.

    Args:
        ontology: Ontology instance to export

    Returns:
        Cypher statements for creating constraints and indexes
    """
    statements: list[str] = []

    # Create constraints for primary keys
    for ot in ontology.get_all_object_types():
        pk = ot.get_primary_key()
        if pk:
            statements.append(
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{ot.name}) REQUIRE n.{pk} IS UNIQUE;"
            )

    # Create indexes for indexed properties
    for ot in ontology.get_all_object_types():
        for prop_name, prop in ot.properties.items():
            if prop.indexed and not prop.primary_key:
                statements.append(
                    f"CREATE INDEX IF NOT EXISTS FOR (n:{ot.name}) ON (n.{prop_name});"
                )

    return "\n".join(statements)


def get_schema_for_llm(ontology: Ontology | None = None) -> str:
    """Get a schema summary suitable for LLM prompts.

    Args:
        ontology: Optional ontology instance, loads maritime if None

    Returns:
        Human-readable schema summary
    """
    if ontology is None:
        ontology = load_maritime_ontology()

    lines = [
        "# Maritime Knowledge Graph Schema",
        "",
        "## Entity Types",
        "",
    ]

    # Group entities by category
    categories = {
        "Physical": ["Vessel", "Port", "Waterway", "Cargo", "Sensor"],
        "Spatial": ["SeaArea", "EEZ", "GeoPoint"],
        "Temporal": ["Voyage", "PortCall", "Incident", "Activity", "WeatherCondition"],
        "Observation": ["AISObservation", "SARObservation", "RadarObservation"],
        "Information": ["Regulation", "Document", "DataSource", "Service"],
        "Organization": ["Organization", "ShippingCompany", "GovernmentAgency"],
        "KRISO": ["Experiment", "TestFacility", "ModelShip", "TestCondition"],
    }

    for category, entity_names in categories.items():
        lines.append(f"### {category}")
        for name in entity_names:
            ot = ontology.get_object_type(name)
            if ot:
                props = ", ".join(ot.properties.keys())[:80]
                lines.append(f"- **{name}**: {ot.description or 'N/A'}")
                if props:
                    lines.append(f"  - Properties: {props}...")
        lines.append("")

    lines.append("## Relationships")
    lines.append("")

    for lt in ontology.get_all_link_types():
        lines.append(f"- `(:{lt.from_type})-[:{lt.name}]->(:{lt.to_type})`")
        if lt.description:
            lines.append(f"  - {lt.description}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Demo loading and export
    ontology = load_maritime_ontology()
    is_valid, errors = ontology.validate()

    print(f"Loaded maritime ontology: {ontology.name}")
    print(f"  ObjectTypes: {len(ontology.get_all_object_types())}")
    print(f"  LinkTypes: {len(ontology.get_all_link_types())}")
    print(f"  Valid: {is_valid}")
    if errors:
        print(f"  Errors: {errors[:5]}...")  # Show first 5 errors

    print("\n--- Cypher Constraints (first 5) ---")
    cypher = export_ontology_to_cypher(ontology)
    for line in cypher.split("\n")[:5]:
        print(line)
