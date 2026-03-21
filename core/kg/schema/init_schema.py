"""Initialise the Maritime Knowledge Graph schema in Neo4j.

Reads constraints.cypher and indexes.cypher, executes each statement,
and verifies the result by listing all constraints and indexes.

Usage::

    python -m kg.schema.init_schema
"""

from __future__ import annotations

import sys
from pathlib import Path

from kg.config import get_config, get_driver
from kg.utils.cypher_parser import parse_cypher_file

_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "maritime" / "schema"


def _execute_statements(
    tx,  # neo4j.ManagedTransaction
    statements: list[str],
    label: str,
) -> tuple[int, int]:
    """Execute a list of Cypher statements inside a transaction.

    Returns (success_count, error_count).
    """
    ok = 0
    err = 0
    for stmt in statements:
        short = stmt[:90].replace("\n", " ")
        try:
            tx.run(stmt)
            print(f"  [OK]  {short}")
            ok += 1
        except Exception as exc:
            print(f"  [ERR] {short}")
            print(f"        {exc}")
            err += 1
    return ok, err


def init_schema() -> None:
    """Connect to Neo4j and apply all constraints and indexes."""
    driver = get_driver()
    try:
        with driver.session(database=get_config().neo4j.database) as session:
            # --- Constraints ---
            constraints_file = _SCHEMA_DIR / "constraints.cypher"
            constraints = parse_cypher_file(constraints_file)
            print(f"\n=== Applying {len(constraints)} constraints ===")
            c_ok, c_err = session.execute_write(_execute_statements, constraints, "constraints")

            # --- Indexes ---
            indexes_file = _SCHEMA_DIR / "indexes.cypher"
            indexes = parse_cypher_file(indexes_file)
            print(f"\n=== Applying {len(indexes)} indexes ===")
            i_ok, i_err = session.execute_write(_execute_statements, indexes, "indexes")

            # --- Summary ---
            total_ok = c_ok + i_ok
            total_err = c_err + i_err
            print("\n=== Summary ===")
            print(f"  Constraints: {c_ok} applied, {c_err} errors")
            print(f"  Indexes:     {i_ok} applied, {i_err} errors")
            print(f"  Total:       {total_ok} applied, {total_err} errors")

            # --- Verification ---
            print("\n=== Verification: Current constraints ===")
            result = session.run("SHOW CONSTRAINTS")
            for record in result:
                print(
                    f"  {record['name']:30s}  {record['type']:20s}  {record.get('labelsOrTypes', '')}"
                )

            print("\n=== Verification: Current indexes ===")
            result = session.run("SHOW INDEXES")
            for record in result:
                print(
                    f"  {record['name']:30s}  {record['type']:20s}  {record['state']:10s}  {record.get('labelsOrTypes', '')}"
                )

            if total_err > 0:
                print(f"\n[WARN] {total_err} statement(s) failed. Review errors above.")
                sys.exit(1)
            else:
                print("\n[DONE] Schema initialised successfully.")

    finally:
        driver.close()


def main() -> None:
    """Entry point."""
    init_schema()


if __name__ == "__main__":
    main()
