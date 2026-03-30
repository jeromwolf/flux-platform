#!/usr/bin/env python3
"""One-time migration: stamp existing nodes with KG_default project label.

Usage:
    PYTHONPATH=. python3 scripts/migrate_project_labels.py

This script is idempotent — safe to run multiple times.
Nodes already tagged with :KG_default are skipped.
"""

from __future__ import annotations

import sys

from kg.config import get_driver, get_config
from kg.project import DEFAULT_PROJECT, project_label


def migrate(batch_size: int = 5000) -> int:
    """Stamp all untagged nodes with the default project label.

    Args:
        batch_size: Number of nodes to process per transaction.

    Returns:
        Total number of migrated nodes.
    """
    driver = get_driver()
    cfg = get_config()
    label = project_label(DEFAULT_PROJECT)
    total = 0

    with driver.session(database=cfg.neo4j.database) as session:
        while True:
            result = session.run(
                f"MATCH (n) WHERE NOT n:{label} "
                f"WITH n LIMIT $batch "
                f"SET n:{label}, n._kg_project = $project "
                "RETURN count(n) AS migrated",
                {"batch": batch_size, "project": DEFAULT_PROJECT},
            )
            record = result.single()
            batch = record["migrated"] if record else 0
            total += batch
            print(f"  Migrated {batch} nodes (total: {total})")
            if batch == 0:
                break

    return total


def main() -> None:
    """Run the migration."""
    print(f"=== KG Project Label Migration ===")
    print(f"Target label: :{project_label(DEFAULT_PROJECT)}")
    print(f"Target property: _kg_project = '{DEFAULT_PROJECT}'")
    print()

    try:
        total = migrate()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print()
    if total > 0:
        print(f"Migration complete: {total} nodes stamped with :{project_label(DEFAULT_PROJECT)}")
    else:
        print("No migration needed — all nodes already tagged.")


if __name__ == "__main__":
    main()
