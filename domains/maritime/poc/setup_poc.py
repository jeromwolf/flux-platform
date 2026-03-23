"""One-click PoC environment setup for the Maritime Knowledge Graph.

Orchestrates schema initialisation, sample data loading, and RBAC seed
data loading in the correct order.  Safe to run multiple times (all
mutations are idempotent via MERGE / IF NOT EXISTS).

Usage::

    python -m poc.setup_poc          # full setup
    python -m poc.setup_poc --skip-rbac   # skip RBAC
    python -m poc.setup_poc --verify-only # verification only
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

logger = logging.getLogger(__name__)


def _banner(text: str) -> None:
    width = 70
    logger.info("\n" + "=" * width)
    logger.info(f"  {text}")
    logger.info("=" * width)


def _step(n: int, total: int, desc: str) -> None:
    logger.info(f"\n  [{n}/{total}] {desc}")
    logger.info("  " + "-" * 50)


def verify_connection() -> bool:
    """Verify Neo4j connectivity."""
    try:
        from kg.config import get_config, get_driver

        _cfg = get_config()
        print(f"  Neo4j URI:      {_cfg.neo4j.uri}")
        print(f"  Database:       {_cfg.neo4j.database}")
        driver = get_driver()
        with driver.session(database=_cfg.neo4j.database) as session:
            result = session.run("RETURN 1 AS ping")
            result.single()
        driver.close()
        print("  Connection:     OK")
        return True
    except Exception as exc:
        print(f"  Connection:     FAILED - {exc}")
        return False


def verify_data() -> None:
    """Print summary of loaded data."""
    from kg.config import get_config, get_driver
    from kg.utils.verification import verify_graph_summary, verify_schema

    driver = get_driver()
    try:
        with driver.session(database=get_config().neo4j.database) as session:
            verify_graph_summary(session)
            verify_schema(session)
    finally:
        driver.close()


def run_setup(skip_rbac: bool = False, verify_only: bool = False) -> None:
    """Execute the full PoC setup sequence."""
    _banner("Maritime Knowledge Graph - PoC Setup")
    start = time.time()

    # Step 0: Verify connection
    _step(0, 4, "Verifying Neo4j connection")
    if not verify_connection():
        print("\n  [ERROR] Cannot connect to Neo4j. Please check:")
        print("    1. Neo4j is running: docker compose up -d")
        print("    2. Environment variables in .env are correct")
        print("    3. NEO4J_URI=bolt://localhost:7687")
        sys.exit(1)

    if verify_only:
        _step(1, 1, "Verifying loaded data")
        verify_data()
        elapsed = time.time() - start
        print(f"\n  [DONE] Verification completed in {elapsed:.1f}s")
        return

    total_steps = 3 if skip_rbac else 4

    # Step 1: Schema
    _step(1, total_steps, "Initializing schema (constraints + indexes)")
    from kg.schema.init_schema import init_schema

    init_schema()

    # Step 2: Sample data
    _step(2, total_steps, "Loading maritime sample data")
    from maritime.schema.load_sample_data import load_sample_data

    load_sample_data()

    # Step 3: RBAC
    if not skip_rbac:
        _step(3, total_steps, "Loading RBAC seed data")
        from maritime.rbac.load_rbac_data import load_rbac_data

        load_rbac_data()

    # Step 4: Verification
    _step(total_steps, total_steps, "Verifying loaded data")
    verify_data()

    elapsed = time.time() - start
    _banner(f"PoC Setup Complete ({elapsed:.1f}s)")
    print("""
  Next steps:
    1. Run NL query demo:
       python poc/langchain_qa.py "부산항 근처 선박 알려줘"

    2. Start visualization API:
       python poc/kg_visualizer_api.py

    3. Run tests:
       PYTHONPATH=. pytest tests/ -m unit -v
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Maritime KG PoC environment setup")
    parser.add_argument(
        "--skip-rbac",
        action="store_true",
        help="Skip RBAC seed data loading",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify loaded data, skip setup",
    )
    args = parser.parse_args()
    run_setup(skip_rbac=args.skip_rbac, verify_only=args.verify_only)


if __name__ == "__main__":
    main()
