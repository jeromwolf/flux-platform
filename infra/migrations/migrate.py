"""CLI entry point for Neo4j migrations.

Usage::

    python -m migrations.migrate [--dry-run] [--target VERSION] [--status] [--validate]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Run the migration CLI."""
    parser = argparse.ArgumentParser(
        description="IMSP Neo4j Schema Migration Tool",
        prog="migrations.migrate",
    )
    parser.add_argument(
        "--uri",
        default=None,
        help="Neo4j URI (default: from NEO4J_URI env var)",
    )
    parser.add_argument(
        "--user",
        default=None,
        help="Neo4j username (default: from NEO4J_USER env var)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Neo4j password (default: from NEO4J_PASSWORD env var)",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Neo4j database (default: from NEO4J_DATABASE env var)",
    )
    parser.add_argument(
        "--migrations-dir",
        default=None,
        help="Directory containing migration files (default: same as this script)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print without executing")
    parser.add_argument("--target", default=None, help="Migrate up to this version (e.g. V003)")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--validate", action="store_true", help="Validate migration files")
    parser.add_argument("--env", default="", help="Environment tag (e.g. production)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Determine migrations directory
    migrations_dir = Path(args.migrations_dir) if args.migrations_dir else Path(__file__).parent

    # Get Neo4j connection
    import os

    uri = args.uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = args.user or os.environ.get("NEO4J_USER", "neo4j")
    password = args.password or os.environ.get("NEO4J_PASSWORD", "")
    database = args.database or os.environ.get("NEO4J_DATABASE", "neo4j")

    try:
        import neo4j

        driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
    except ImportError:
        print("ERROR: neo4j Python driver is not installed.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Cannot connect to Neo4j at {uri}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        from migrations.runner import MigrationRunner

        runner = MigrationRunner(driver, database)

        if args.validate:
            errors = runner.validate(migrations_dir)
            if errors:
                print("Validation FAILED:")
                for err in errors:
                    print(f"  - {err}")
                sys.exit(1)
            else:
                print("Validation OK: all migration files are valid.")
            return

        if args.status:
            statuses = runner.status(migrations_dir)
            if not statuses:
                print("No migration files found.")
                return
            print(f"{'Version':<10} {'Description':<35} {'Status':<10} {'Applied At'}")
            print("-" * 80)
            for s in statuses:
                applied = s["applied_at"] or ""
                print(f"{s['version']:<10} {s['description']:<35} {s['status']:<10} {applied}")
            return

        count = runner.run_pending(
            migrations_dir,
            target=args.target,
            dry_run=args.dry_run,
            environment=args.env,
        )
        print(f"\n{'[DRY RUN] ' if args.dry_run else ''}{count} migration(s) applied.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
