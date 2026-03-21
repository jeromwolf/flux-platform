"""KG consistency checking framework.

Provides ``KGConsistencyChecker`` and seven built-in check classes for
validating a live Neo4j KG against a ``SchemaDefinition``.

Quick start::

    from kg.consistency import KGConsistencyChecker
    from kg.consistency.checks import SchemaDefinition, LabelSchema, PropertySchema

    schema = SchemaDefinition(
        labels={
            "Vessel": LabelSchema(
                properties={
                    "vesselType": PropertySchema(
                        expected_type="str",
                        enum_values=frozenset({"CARGO", "TANKER", "PASSENGER"}),
                    ),
                    "mmsi": PropertySchema(expected_type="str"),
                },
                required_properties=frozenset({"mmsi"}),
            )
        },
        relationship_types=frozenset({"DOCKED_AT", "OPERATED_BY"}),
    )

    checker = KGConsistencyChecker(schema)

    # No Neo4j needed
    offline_report = checker.run_offline()

    # With Neo4j
    with driver.session() as session:
        full_report = checker.run_all(session)
"""

from kg.consistency.checker import KGConsistencyChecker
from kg.consistency.checks import (
    CardinalityCheck,
    ConsistencyCheck,
    DanglingRelationshipCheck,
    EnumValueCheck,
    LabelSchema,
    OrphanNodeCheck,
    PropertySchema,
    PropertyTypeCheck,
    RequiredPropertyCheck,
    SchemaAlignmentCheck,
    SchemaDefinition,
)

__all__ = [
    "KGConsistencyChecker",
    "ConsistencyCheck",
    "SchemaDefinition",
    "LabelSchema",
    "PropertySchema",
    "PropertyTypeCheck",
    "RequiredPropertyCheck",
    "EnumValueCheck",
    "CardinalityCheck",
    "OrphanNodeCheck",
    "DanglingRelationshipCheck",
    "SchemaAlignmentCheck",
]
