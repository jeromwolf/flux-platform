"""RBAC schema definitions for Neo4j constraints and indexes.

RBAC constraints and indexes are now maintained in the main schema files:
  - ``kg/schema/constraints.cypher`` (lines 19-23)
  - ``kg/schema/indexes.cypher`` (lines 40-49)

This module provides a helper to extract the RBAC-specific statements
for use in ``load_rbac_data.py`` without duplicating them.

Usage::

    from kg.rbac.schema import get_rbac_schema_statements

    for stmt in get_rbac_schema_statements():
        session.run(stmt)
"""

from __future__ import annotations

from pathlib import Path

from kg.utils.cypher_parser import parse_cypher_file

_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "domains" / "maritime" / "schema"


def _filter_rbac_statements(statements: list[str]) -> list[str]:
    """Keep only statements that reference RBAC labels."""
    rbac_labels = {"User", "Role", "DataClass", "Permission"}
    result = []
    for stmt in statements:
        for label in rbac_labels:
            if f":{label}" in stmt or f"({label}" in stmt:
                result.append(stmt)
                break
    return result


def get_rbac_schema_statements() -> list[str]:
    """Return all RBAC schema statements (constraints + indexes).

    Extracts RBAC-specific statements from the main schema files,
    ensuring a single source of truth.

    Returns:
        Combined list of Cypher statements for RBAC constraints and indexes.
    """
    constraints = parse_cypher_file(_SCHEMA_DIR / "constraints.cypher")
    indexes = parse_cypher_file(_SCHEMA_DIR / "indexes.cypher")

    rbac_constraints = _filter_rbac_statements(constraints)
    rbac_indexes = _filter_rbac_statements(indexes)

    return rbac_constraints + rbac_indexes
