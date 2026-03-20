"""Run the full Maritime KG PoC demonstration.

Executes a guided demo that showcases all PoC capabilities:
  1. Environment check (Neo4j + Ollama)
  2. Schema and data setup (via setup_poc)
  3. Graph statistics
  4. Sample Cypher queries
  5. RBAC access control demo
  6. KRISO experiment data exploration
  7. (Optional) NL query via LangChain

Usage::

    python -m poc.run_poc_demo           # full demo
    python -m poc.run_poc_demo --no-llm  # skip LangChain NL queries
"""

from __future__ import annotations

import argparse
import sys
import time


def _banner(text: str) -> None:
    w = 70
    print(f"\n{'=' * w}")
    print(f"  {text}")
    print(f"{'=' * w}")


def _section(title: str) -> None:
    print(f"\n  --- {title} ---\n")


def _run_query(session, query: str, title: str) -> list:
    """Run a Cypher query, print results, and return records."""
    _section(title)
    print(f"  Cypher: {query[:120]}...")
    result = session.run(query)
    records = list(result)
    if not records:
        print("  (no results)")
        return records

    # Print as table
    keys = records[0].keys()
    header = "  " + " | ".join(f"{k:<25s}" for k in keys)
    print(header)
    print("  " + "-" * len(header))
    for rec in records[:10]:
        row = "  " + " | ".join(f"{str(rec[k]):<25s}" for k in keys)
        print(row)
    if len(records) > 10:
        print(f"  ... ({len(records)} total)")
    return records


def check_neo4j() -> bool:
    """Check Neo4j connectivity."""
    try:
        from kg.config import get_config, get_driver

        _cfg = get_config()
        print(f"  Neo4j: {_cfg.neo4j.uri} (db={_cfg.neo4j.database})")
        driver = get_driver()
        with driver.session(database=_cfg.neo4j.database) as session:
            session.run("RETURN 1")
        driver.close()
        print("  Status: Connected")
        return True
    except Exception as exc:
        print(f"  Status: FAILED ({exc})")
        return False


def check_ollama() -> bool:
    """Check Ollama availability."""
    try:
        import requests

        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            qwen_available = any("qwen" in m for m in models)
            print(f"  Ollama: Connected ({len(models)} models)")
            if qwen_available:
                print("  qwen2.5:7b: Available")
            else:
                print("  qwen2.5:7b: Not found (NL queries will fail)")
            return qwen_available
        return False
    except Exception:
        print("  Ollama: Not available (NL queries disabled)")
        return False


def demo_graph_stats(session) -> None:
    """Show graph statistics."""
    _run_query(
        session,
        "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC LIMIT 15",
        "Node Statistics (Top 15)",
    )
    _run_query(
        session,
        "MATCH ()-[r]->() RETURN type(r) AS relationship, count(*) AS count "
        "ORDER BY count DESC LIMIT 15",
        "Relationship Statistics (Top 15)",
    )


def demo_vessel_queries(session) -> None:
    """Demo vessel-related queries."""
    _run_query(
        session,
        "MATCH (v:Vessel) "
        "RETURN v.name AS name, v.vesselType AS type, "
        "v.grossTonnage AS tonnage, v.currentStatus AS status "
        "ORDER BY v.grossTonnage DESC",
        "All Vessels",
    )
    _run_query(
        session,
        "MATCH (p:Port {unlocode: 'KRPUS'}) "
        "MATCH (v:Vessel) "
        "WHERE point.distance(v.currentLocation, p.location) < 50000 "
        "RETURN v.name AS vessel, v.vesselType AS type, "
        "round(point.distance(v.currentLocation, p.location)/1000.0, 1) AS dist_km "
        "ORDER BY dist_km",
        "Vessels within 50km of Busan Port (Spatial Query)",
    )


def demo_kriso_experiments(session) -> None:
    """Demo KRISO experiment data queries."""
    _run_query(
        session,
        "MATCH (o:Organization {orgId: 'ORG-KRISO'})-[:HAS_FACILITY]->(tf:TestFacility) "
        "RETURN tf.facilityId AS id, tf.name AS name, tf.nameEn AS name_en, "
        "tf.facilityType AS type "
        "ORDER BY tf.facilityId",
        "KRISO Test Facilities (All 10)",
    )
    _run_query(
        session,
        "MATCH (exp:Experiment)-[:CONDUCTED_AT]->(tf:TestFacility) "
        "OPTIONAL MATCH (exp)-[:PRODUCED]->(ds:ExperimentalDataset) "
        "RETURN exp.experimentId AS id, exp.title AS title, "
        "tf.name AS facility, ds.title AS dataset, exp.status AS status "
        "ORDER BY exp.date",
        "Experiments with Datasets",
    )
    _run_query(
        session,
        "MATCH (exp:Experiment {experimentId: 'EXP-2024-001'})"
        "-[:PRODUCED]->(ds:ExperimentalDataset)"
        "-[:CONTAINS]->(m:Measurement) "
        "RETURN m.measurementType AS type, m.value AS value, "
        "m.unit AS unit, m.description AS description "
        "ORDER BY m.testSpeed",
        "EXP-2024-001 Measurement Results",
    )


def demo_rbac(session) -> None:
    """Demo RBAC access control."""
    _run_query(
        session,
        "MATCH (r:Role)-[:CAN_ACCESS]->(dc:DataClass) "
        "RETURN r.name AS role, r.level AS level, "
        "collect(dc.name) AS accessible_data "
        "ORDER BY r.level DESC",
        "RBAC: Role Access Matrix",
    )


def demo_nl_queries() -> None:
    """Demo NL-to-Cypher queries via LangChain."""
    _section("Natural Language Queries (LangChain + Ollama)")
    try:
        from poc.langchain_qa import ask

        questions = [
            "부산항 근처 선박 알려줘",
            "KRISO 시험설비 목록을 보여줘",
        ]
        for q in questions:
            ask(q)
    except Exception as exc:
        print(f"  [ERROR] NL query failed: {exc}")
        print("  Make sure Ollama is running with qwen2.5:7b model.")


def run_demo(use_llm: bool = True) -> None:
    """Execute the full PoC demo."""
    _banner("Maritime Knowledge Graph - PoC Demo")
    start = time.time()

    # 1. Environment check
    _section("1. Environment Check")
    neo4j_ok = check_neo4j()
    if not neo4j_ok:
        print("\n  [FATAL] Neo4j is required. Run: docker compose up -d")
        sys.exit(1)

    ollama_ok = False
    if use_llm:
        ollama_ok = check_ollama()

    # 2. Setup
    _section("2. Running PoC Setup")
    print("  Loading schema, sample data, and RBAC data...")
    from poc.setup_poc import run_setup

    run_setup()

    # 3. Graph stats
    from kg.config import get_config, get_driver

    driver = get_driver()
    try:
        with driver.session(database=get_config().neo4j.database) as session:
            _banner("3. Graph Statistics")
            demo_graph_stats(session)

            _banner("4. Vessel Queries")
            demo_vessel_queries(session)

            _banner("5. KRISO Experiments")
            demo_kriso_experiments(session)

            _banner("6. RBAC Access Control")
            demo_rbac(session)

    finally:
        driver.close()

    # 7. NL Queries
    if use_llm and ollama_ok:
        _banner("7. Natural Language Queries")
        demo_nl_queries()
    else:
        print("\n  [SKIP] NL queries (--no-llm or Ollama not available)")

    elapsed = time.time() - start
    _banner(f"PoC Demo Complete ({elapsed:.1f}s)")
    print("""
  Summary:
    - Neo4j schema initialized with constraints + indexes
    - Maritime sample data loaded (vessels, ports, KRISO facilities, experiments)
    - RBAC access control configured (5 roles, 5 data classes)
    - All query patterns demonstrated

  To explore further:
    - Interactive NL queries: python poc/langchain_qa.py
    - Visualization:         python poc/kg_visualizer_api.py
    - Run tests:             PYTHONPATH=. python3 -m pytest tests/ -m unit -v
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Maritime KG PoC Demo")
    parser.add_argument("--no-llm", action="store_true", help="Skip LangChain NL queries")
    args = parser.parse_args()
    run_demo(use_llm=not args.no_llm)


if __name__ == "__main__":
    main()
