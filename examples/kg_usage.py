#!/usr/bin/env python3
"""Examples demonstrating Knowledge Graph module usage.

This example shows how to use:
- Ontology core classes for schema definition
- CypherBuilder for fluent Neo4j query construction
- QueryGenerator for multi-language query generation
"""

from kg.ontology import (
    Ontology,
    ObjectTypeDefinition,
    LinkTypeDefinition,
    PropertyDefinition,
    PropertyType,
    Cardinality,
)
from kg.cypher_builder import CypherBuilder, QueryOptions, QueryFilter
from kg.query_generator import (
    QueryGenerator,
    StructuredQuery,
    QueryIntent,
    ExtractedFilter,
    Pagination,
    SortSpec,
    RelationshipSpec,
    AggregationSpec,
    QueryIntentType,
)


def example_ontology():
    """Example: Define maritime ontology schema."""
    print("=" * 60)
    print("Example 1: Maritime Ontology Definition")
    print("=" * 60)

    ontology = Ontology(name="maritime")

    # Define Vessel ObjectType
    vessel = ontology.define_object_type(
        ObjectTypeDefinition(
            name="Vessel",
            display_name="선박",
            description="Any watercraft or ship operating at sea",
            properties={
                "mmsi": PropertyDefinition(
                    type=PropertyType.INTEGER,
                    required=True,
                    primary_key=True,
                    description="Maritime Mobile Service Identity",
                ),
                "name": PropertyDefinition(
                    type=PropertyType.STRING,
                    required=True,
                    indexed=True,
                ),
                "vesselType": PropertyDefinition(
                    type=PropertyType.STRING,
                    enum_values=["ContainerShip", "Tanker", "BulkCarrier", "RoRo", "PassengerShip"],
                ),
                "length": PropertyDefinition(
                    type=PropertyType.FLOAT,
                    min_value=0,
                    max_value=500,
                ),
                "flag": PropertyDefinition(type=PropertyType.STRING),
                "location": PropertyDefinition(type=PropertyType.POINT),
            },
        )
    )

    # Define Port ObjectType
    port = ontology.define_object_type(
        ObjectTypeDefinition(
            name="Port",
            display_name="항구",
            description="Maritime port or harbor",
            properties={
                "unlocode": PropertyDefinition(
                    type=PropertyType.STRING,
                    required=True,
                    primary_key=True,
                ),
                "name": PropertyDefinition(type=PropertyType.STRING, required=True),
                "country": PropertyDefinition(type=PropertyType.STRING),
                "location": PropertyDefinition(type=PropertyType.POINT),
            },
        )
    )

    # Define DOCKED_AT LinkType
    ontology.define_link_type(
        LinkTypeDefinition(
            name="DOCKED_AT",
            from_type="Vessel",
            to_type="Port",
            cardinality=Cardinality.MANY_TO_ONE,
            description="Vessel is currently docked at this port",
            properties={
                "since": PropertyDefinition(type=PropertyType.DATETIME),
                "berth": PropertyDefinition(type=PropertyType.STRING),
            },
        )
    )

    # Validate and print schema
    is_valid, errors = ontology.validate()
    print(f"Schema valid: {is_valid}")
    if errors:
        print(f"Errors: {errors}")

    print("\n" + ontology.get_schema_summary())

    # Test validation
    print("\n--- Data Validation ---")
    valid_data = {"mmsi": 123456789, "name": "Ever Given", "vesselType": "ContainerShip"}
    is_valid, errors = vessel.validate(valid_data)
    print(f"Valid vessel data: {is_valid}")

    invalid_data = {"name": "Missing MMSI"}
    is_valid, errors = vessel.validate(invalid_data)
    print(f"Invalid vessel data: {is_valid}, errors: {errors}")


def example_cypher_builder():
    """Example: Build Cypher queries fluently."""
    print("\n" + "=" * 60)
    print("Example 2: CypherBuilder - Fluent Query Construction")
    print("=" * 60)

    # Simple query
    query, params = (
        CypherBuilder()
        .match("(v:Vessel)")
        .where("v.vesselType = $type", {"type": "ContainerShip"})
        .return_("v.name AS name, v.mmsi AS mmsi")
        .order_by("name", "asc", "v")
        .limit(10)
        .build()
    )
    print("\n--- Simple Query ---")
    print(query)
    print(f"Parameters: {params}")

    # Using QueryOptions
    query, params = CypherBuilder.from_query_options(
        QueryOptions(
            type="Vessel",
            filter={
                "vesselType": QueryFilter(equals="ContainerShip"),
                "length": QueryFilter(gte=200),
            },
            order_by={"name": "asc"},
            limit=10,
            properties=["name", "mmsi", "length"],
        )
    ).build()
    print("\n--- QueryOptions Based ---")
    print(query)
    print(f"Parameters: {params}")

    # Spatial query
    query, params = CypherBuilder.nearby_entities(
        entity_type="Port",
        center_lat=35.0,
        center_lon=129.0,
        radius_km=50,
        limit=5,
    )
    print("\n--- Spatial Query (Nearby Ports) ---")
    print(query)
    print(f"Parameters: {params}")

    # Fulltext search
    query, params = CypherBuilder.fulltext_search(
        index_name="vesselNameIndex",
        search_term="Ever",
        limit=5,
    )
    print("\n--- Fulltext Search ---")
    print(query)
    print(f"Parameters: {params}")


def example_query_generator():
    """Example: Generate queries in multiple languages."""
    print("\n" + "=" * 60)
    print("Example 3: QueryGenerator - Multi-Language Query Generation")
    print("=" * 60)

    generator = QueryGenerator()

    # Simple FIND query
    structured = StructuredQuery(
        intent=QueryIntent(intent=QueryIntentType.FIND, confidence=0.95),
        object_types=["Vessel"],
        properties=["name", "mmsi", "vesselType"],
        filters=[
            ExtractedFilter(field="vesselType", operator="equals", value="ContainerShip"),
            ExtractedFilter(field="length", operator="greater_than", value=200),
        ],
        sorting=[SortSpec(field="length", direction="DESC")],
        pagination=Pagination(limit=10),
    )

    print("\n--- Cypher ---")
    cypher = generator.generate_cypher(structured)
    print(cypher.query)
    print(f"Parameters: {cypher.parameters}")
    print(f"Complexity: {cypher.estimated_complexity}")

    print("\n--- SQL (PostgreSQL) ---")
    sql = generator.generate_sql(structured)
    print(sql.query)
    print(f"Parameters: {sql.parameters}")

    print("\n--- MongoDB ---")
    mongo = generator.generate_mongodb(structured)
    print(mongo.query)

    # Aggregation query
    print("\n" + "-" * 40)
    print("Aggregation Query Example")
    print("-" * 40)

    agg_structured = StructuredQuery(
        intent=QueryIntent(intent=QueryIntentType.AGGREGATE),
        object_types=["Vessel"],
        filters=[],
        aggregations=[
            AggregationSpec(function="COUNT", alias="total"),
            AggregationSpec(function="AVG", field="length", alias="avg_length"),
        ],
        group_by=["vesselType"],
    )

    print("\n--- Cypher Aggregation ---")
    result = generator.generate_cypher(agg_structured)
    print(result.query)

    print("\n--- SQL Aggregation ---")
    result = generator.generate_sql(agg_structured)
    print(result.query)

    print("\n--- MongoDB Aggregation ---")
    result = generator.generate_mongodb(agg_structured)
    print(result.query)


def example_relationship_query():
    """Example: Query with relationship traversal."""
    print("\n" + "=" * 60)
    print("Example 4: Relationship Traversal Queries")
    print("=" * 60)

    generator = QueryGenerator()

    # Find vessels docked at Korean ports
    structured = StructuredQuery(
        intent=QueryIntent(intent=QueryIntentType.FIND),
        object_types=["Vessel"],
        properties=["name", "mmsi"],
        filters=[],
        relationships=[
            RelationshipSpec(
                type="DOCKED_AT",
                direction="outgoing",
                target_entity="Port",
            )
        ],
    )

    print("\n--- Vessel with Port Relationship ---")
    result = generator.generate_cypher(structured)
    print(result.query)

    # Path finding
    query, params = CypherBuilder.find_shortest_path(
        from_id="vessel-12345",
        to_id="port-KRPUS",
        max_depth=4,
    )
    print("\n--- Shortest Path ---")
    print(query)

    # Related objects
    query, params = CypherBuilder.find_related_objects(
        object_id="vessel-12345",
        relationship_type="DOCKED_AT",
        direction="outgoing",
    )
    print("\n--- Related Objects ---")
    print(query)


if __name__ == "__main__":
    example_ontology()
    example_cypher_builder()
    example_query_generator()
    example_relationship_query()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
