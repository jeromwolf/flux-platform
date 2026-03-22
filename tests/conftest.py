"""Shared pytest fixtures for the Maritime KG test suite.

Provides:
    - neo4j_driver: module-scoped Neo4j driver (skips if unavailable)
    - neo4j_session: function-scoped session with automatic rollback
    - sample_ontology: pre-loaded maritime ontology instance
    - sample_object_type_def: reusable ObjectTypeDefinition for Vessel
    - sample_link_type_def: reusable LinkTypeDefinition for DOCKED_AT
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any

import pytest

from kg.ontology.core import (
    Cardinality,
    LinkTypeDefinition,
    ObjectTypeDefinition,
    Ontology,
    PropertyDefinition,
    PropertyType,
)

# =========================================================================
# Neo4j Fixtures (통합/E2E 테스트용)
# =========================================================================


@pytest.fixture(scope="module")
def neo4j_driver() -> Generator[Any, None, None]:
    """Module-scoped Neo4j driver.

    Neo4j 연결이 불가능한 경우 자동으로 테스트를 skip한다.
    """
    try:
        from kg.config import NEO4J_DATABASE, get_driver

        driver = get_driver()
        # 연결 확인
        with driver.session(database=NEO4J_DATABASE) as session:
            session.run("RETURN 1")
        yield driver
    except Exception as exc:
        pytest.skip(f"Neo4j 연결 실패 (skip): {exc}")
        yield None  # type: ignore[misc]
    finally:
        with contextlib.suppress(Exception):
            driver.close()  # type: ignore[possibly-undefined]


@pytest.fixture(scope="function")
def neo4j_session(neo4j_driver: Any) -> Generator[Any, None, None]:
    """Function-scoped Neo4j session.

    각 테스트 함수마다 새 세션을 생성하고, 테스트 후 세션을 닫는다.
    """
    from kg.config import NEO4J_DATABASE

    session = neo4j_driver.session(database=NEO4J_DATABASE)
    yield session
    session.close()


# =========================================================================
# Ontology Fixtures (단위 테스트용)
# =========================================================================


@pytest.fixture
def sample_object_type_def() -> ObjectTypeDefinition:
    """Vessel ObjectTypeDefinition 샘플."""
    return ObjectTypeDefinition(
        name="Vessel",
        display_name="선박",
        description="Any watercraft or ship operating at sea",
        properties={
            "mmsi": PropertyDefinition(
                type=PropertyType.INTEGER,
                required=True,
                primary_key=True,
                indexed=True,
            ),
            "name": PropertyDefinition(
                type=PropertyType.STRING,
                required=True,
                indexed=True,
            ),
            "vesselType": PropertyDefinition(
                type=PropertyType.STRING,
                required=False,
                enum_values=["ContainerShip", "Tanker", "BulkCarrier", "PassengerShip"],
            ),
            "grossTonnage": PropertyDefinition(
                type=PropertyType.FLOAT,
                required=False,
                min_value=0.0,
            ),
            "flag": PropertyDefinition(
                type=PropertyType.STRING,
                required=False,
                min_length=2,
                max_length=3,
            ),
        },
    )


@pytest.fixture
def sample_link_type_def() -> LinkTypeDefinition:
    """DOCKED_AT LinkTypeDefinition 샘플."""
    return LinkTypeDefinition(
        name="DOCKED_AT",
        from_type="Vessel",
        to_type="Berth",
        cardinality=Cardinality.MANY_TO_ONE,
        description="Vessel is currently docked at a specific berth",
        properties={
            "since": PropertyDefinition(type=PropertyType.DATETIME),
            "until": PropertyDefinition(type=PropertyType.DATETIME),
        },
    )


@pytest.fixture
def minimal_ontology(
    sample_object_type_def: ObjectTypeDefinition,
) -> Ontology:
    """2개 ObjectType + 1개 LinkType을 가진 최소 온톨로지."""
    ontology = Ontology(name="test")

    ontology.define_object_type(sample_object_type_def)

    ontology.define_object_type(
        ObjectTypeDefinition(
            name="Berth",
            display_name="선석",
            description="Designated mooring position within a port",
            properties={
                "berthId": PropertyDefinition(
                    type=PropertyType.STRING,
                    required=True,
                    primary_key=True,
                ),
            },
        )
    )

    ontology.define_link_type(
        LinkTypeDefinition(
            name="DOCKED_AT",
            from_type="Vessel",
            to_type="Berth",
            cardinality=Cardinality.MANY_TO_ONE,
            description="Vessel is currently docked at a specific berth",
        )
    )

    return ontology


@pytest.fixture(scope="session")
def sample_ontology() -> Ontology:
    """Session-scoped 해사 온톨로지 인스턴스."""
    from maritime.ontology.maritime_loader import load_maritime_ontology

    return load_maritime_ontology()
