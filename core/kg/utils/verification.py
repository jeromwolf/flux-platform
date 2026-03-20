"""Shared data verification utilities for the Maritime KG.

Provides reusable functions to verify node/relationship counts,
RBAC access matrices, and schema status after data loading.

Usage::

    from kg.utils.verification import verify_graph_summary, verify_rbac

    with driver.session(database=db) as session:
        verify_graph_summary(session)
        verify_rbac(session)
"""

from __future__ import annotations

from typing import Any


def _header(title: str) -> None:
    print(f"\n  {'=' * 55}")
    print(f"  {title}")
    print(f"  {'=' * 55}")


def verify_graph_summary(session: Any) -> tuple[int, int]:
    """Print node and relationship counts. Returns (total_nodes, total_rels)."""
    _header("Graph Summary")

    print("\n  Node counts by label:")
    print(f"  {'Label':<28s} {'Count':>6s}")
    print(f"  {'-' * 28} {'-' * 6}")
    result = session.run(
        "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC"
    )
    total_nodes = 0
    for record in result:
        label = record["label"] or "(unlabeled)"
        count = record["count"]
        total_nodes += count
        print(f"  {label:<28s} {count:>6d}")
    print(f"  {'TOTAL':<28s} {total_nodes:>6d}")

    print("\n  Relationship counts by type:")
    print(f"  {'Type':<28s} {'Count':>6s}")
    print(f"  {'-' * 28} {'-' * 6}")
    result = session.run(
        "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC"
    )
    total_rels = 0
    for record in result:
        rel_type = record["type"]
        count = record["count"]
        total_rels += count
        print(f"  {rel_type:<28s} {count:>6d}")
    print(f"  {'TOTAL':<28s} {total_rels:>6d}")

    print(f"\n  [SUMMARY] {total_nodes} nodes, {total_rels} relationships")
    return total_nodes, total_rels


def verify_schema(session: Any) -> tuple[int, int]:
    """Print schema statistics. Returns (constraint_count, index_count)."""
    result = session.run("SHOW CONSTRAINTS")
    constraints = list(result)
    result = session.run("SHOW INDEXES")
    indexes = list(result)
    print(f"\n  Schema: {len(constraints)} constraints, {len(indexes)} indexes")
    return len(constraints), len(indexes)


def verify_rbac(session: Any) -> None:
    """Print RBAC-specific verification (nodes, relationships, access matrix)."""
    _header("RBAC Verification")

    # Node counts
    print("\n  RBAC Node Counts:")
    print(f"  {'Label':<20s} {'Count':>6s}")
    print(f"  {'-' * 20} {'-' * 6}")
    for label in ["User", "Role", "DataClass", "Permission"]:
        result = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
        cnt = result.single()["cnt"]
        print(f"  {label:<20s} {cnt:>6d}")

    # Relationship counts
    print("\n  RBAC Relationship Counts:")
    print(f"  {'Type':<25s} {'Count':>6s}")
    print(f"  {'-' * 25} {'-' * 6}")
    for rel_type in ["HAS_ROLE", "CAN_ACCESS", "GRANTS", "BELONGS_TO"]:
        result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt")
        cnt = result.single()["cnt"]
        print(f"  {rel_type:<25s} {cnt:>6d}")

    # Access matrix
    print("\n  Access Matrix (Role -> DataClass):")
    print(f"  {'Role':<20s} {'Accessible Data Classes'}")
    print(f"  {'-' * 20} {'-' * 40}")
    result = session.run("""
        MATCH (r:Role)
        OPTIONAL MATCH (r)-[:CAN_ACCESS]->(dc:DataClass)
        WITH r, collect(dc.name) AS classes
        RETURN r.name AS roleName, r.level AS level, classes
        ORDER BY r.level DESC
    """)
    for record in result:
        role_name = record["roleName"]
        classes = record["classes"]
        class_str = ", ".join(classes) if classes else "(none)"
        print(f"  {role_name:<20s} {class_str}")

    # User assignments
    print("\n  User -> Role Assignments:")
    print(f"  {'User':<25s} {'Role':<20s} {'Max Level':>10s}")
    print(f"  {'-' * 25} {'-' * 20} {'-' * 10}")
    result = session.run("""
        MATCH (u:User)-[:HAS_ROLE]->(r:Role)
        OPTIONAL MATCH (r)-[:CAN_ACCESS]->(dc:DataClass)
        WITH u, r, max(dc.level) AS maxLevel
        RETURN u.name AS userName, r.name AS roleName, maxLevel
        ORDER BY maxLevel DESC
    """)
    for record in result:
        user_name = record["userName"]
        role_name = record["roleName"]
        max_level = record["maxLevel"]
        print(f"  {user_name:<25s} {role_name:<20s} {max_level or 0:>10d}")

    print("\n  [DONE] RBAC verification complete.")
