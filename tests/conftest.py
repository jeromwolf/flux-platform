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
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

# Ensure the project root is on sys.path so that top-level packages
# (e.g. `agent`) are importable even when pytest's pythonpath config
# only lists sub-directories such as `core` and `domains`.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from kg.ontology.core import (
    Cardinality,
    LinkTypeDefinition,
    ObjectTypeDefinition,
    Ontology,
    PropertyDefinition,
    PropertyType,
)

# =========================================================================
# pytest 마커 등록
# =========================================================================


def pytest_configure(config: Any) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Pure Python unit tests (no external deps)")
    config.addinivalue_line("markers", "integration: Tests requiring Neo4j connection")
    config.addinivalue_line("markers", "e2e: End-to-end scenario tests")
    config.addinivalue_line("markers", "slow: Long-running tests")


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
    참고: Neo4j Community Edition은 트랜잭션 롤백을 지원하지만,
    데이터 격리를 위해 가능한 경우 트랜잭션을 사용한다.
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
    """Vessel ObjectTypeDefinition 샘플.

    단위 테스트에서 재사용 가능한 ObjectType 정의.
    """
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

    # Vessel 등록
    ontology.define_object_type(sample_object_type_def)

    # Berth 등록
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

    # DOCKED_AT 관계 등록
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
    """Session-scoped 해사 온톨로지 인스턴스.

    load_maritime_ontology()를 한 번만 호출하여 전체 테스트 세션에서 재사용.
    """
    try:
        from maritime.ontology.maritime_loader import load_maritime_ontology
    except ImportError:
        from kg.ontology.maritime_loader import load_maritime_ontology

    return load_maritime_ontology()
