"""Run all maritime data crawlers.

Usage::
    python -m kg.crawlers.run_crawlers              # all crawlers, sample
    python -m kg.crawlers.run_crawlers --papers      # papers only
    python -m kg.crawlers.run_crawlers --facilities  # facilities only
    python -m kg.crawlers.run_crawlers --weather     # weather only
    python -m kg.crawlers.run_crawlers --accidents   # accidents only
    python -m kg.crawlers.run_crawlers --all         # full crawl
"""

from __future__ import annotations

import argparse
import logging
import time

from kg.crawlers.registry import get_registry

# Registry-based discovery (backward-compatible aliases for direct imports)
_registry = get_registry()
KRISOPapersCrawler = _registry.get("kriso-papers")
KRISOFacilitiesCrawler = _registry.get("kriso-facilities")
KMAMarineCrawler = _registry.get("kma-marine")
MaritimeAccidentsCrawler = _registry.get("maritime-accidents")

logger = logging.getLogger(__name__)


def run_papers(
    *,
    limit: int | None = 50,
    start_id: int = 1,
    end_id: int = 11200,
    delay: float = 1.0,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run the papers crawler and return summary stats."""
    print("\n" + "=" * 60)
    print("  KRISO ScholarWorks Paper Crawler")
    print("=" * 60)

    crawler = KRISOPapersCrawler(delay=delay)
    t0 = time.time()
    records = crawler.crawl(start_id=start_id, end_id=end_id, limit=limit)
    elapsed = time.time() - t0

    saved = 0
    if records and not dry_run:
        saved = crawler.save_to_neo4j(records)

    print(f"  Papers collected: {len(records)}")
    print(f"  Papers saved:     {saved}")
    print(f"  Elapsed:          {elapsed:.1f}s")
    return {"collected": len(records), "saved": saved}


def run_facilities(
    *,
    delay: float = 1.0,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run the facilities crawler and return summary stats."""
    print("\n" + "=" * 60)
    print("  KRISO Facilities Crawler")
    print("=" * 60)

    crawler = KRISOFacilitiesCrawler(delay=delay)
    t0 = time.time()
    records = crawler.crawl()
    elapsed = time.time() - t0

    saved = 0
    if records and not dry_run:
        saved = crawler.save_to_neo4j(records)

    print(f"  Facilities collected: {len(records)}")
    print(f"  Facilities saved:     {saved}")
    print(f"  Elapsed:              {elapsed:.1f}s")
    return {"collected": len(records), "saved": saved}


def run_weather(
    *,
    limit: int = 10,
    delay: float = 0.5,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run the marine weather crawler and return summary stats."""
    print("\n" + "=" * 60)
    print("  KMA Marine Weather Crawler")
    print("=" * 60)

    crawler = KMAMarineCrawler(delay=delay)
    t0 = time.time()
    records = crawler.crawl(limit=limit)
    elapsed = time.time() - t0

    saved = 0
    if records and not dry_run:
        saved = crawler.save_to_neo4j(records)

    print(f"  Weather records generated: {len(records)}")
    print(f"  Weather records saved:     {saved}")
    print(f"  Elapsed:                   {elapsed:.1f}s")
    return {"collected": len(records), "saved": saved}


def run_accidents(
    *,
    limit: int = 10,
    delay: float = 0.5,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run the maritime accidents crawler and return summary stats."""
    print("\n" + "=" * 60)
    print("  Maritime Accidents Crawler")
    print("=" * 60)

    crawler = MaritimeAccidentsCrawler(delay=delay)
    t0 = time.time()
    records = crawler.crawl(limit=limit)
    elapsed = time.time() - t0

    saved = 0
    if records and not dry_run:
        saved = crawler.save_to_neo4j(records)

    print(f"  Accident records generated: {len(records)}")
    print(f"  Accident records saved:     {saved}")
    print(f"  Elapsed:                    {elapsed:.1f}s")
    return {"collected": len(records), "saved": saved}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run KRISO crawlers",
    )
    parser.add_argument(
        "--papers",
        action="store_true",
        help="Run papers crawler only",
    )
    parser.add_argument(
        "--facilities",
        action="store_true",
        help="Run facilities crawler only",
    )
    parser.add_argument(
        "--weather",
        action="store_true",
        help="Run weather crawler only",
    )
    parser.add_argument(
        "--accidents",
        action="store_true",
        help="Run accidents crawler only",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Full crawl (all paper IDs, no limit)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum papers to collect (default: 50, ignored with --all)",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=1,
        help="First paper handle ID (default: 1)",
    )
    parser.add_argument(
        "--end-id",
        type=int,
        default=11200,
        help="Last paper handle ID (default: 11200)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between requests (default: 1.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only; do not write to Neo4j",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Determine which crawlers to run
    specific = args.papers or args.facilities or args.weather or args.accidents
    run_p = args.papers or not specific
    run_f = args.facilities or not specific
    run_w = args.weather or not specific
    run_a = args.accidents or not specific

    limit = None if args.all else args.limit

    summary: dict[str, dict[str, int]] = {}

    if run_p:
        summary["papers"] = run_papers(
            limit=limit,
            start_id=args.start_id,
            end_id=args.end_id,
            delay=args.delay,
            dry_run=args.dry_run,
        )

    if run_f:
        summary["facilities"] = run_facilities(
            delay=args.delay,
            dry_run=args.dry_run,
        )

    if run_w:
        summary["weather"] = run_weather(
            limit=args.limit,
            delay=args.delay,
            dry_run=args.dry_run,
        )

    if run_a:
        summary["accidents"] = run_accidents(
            limit=args.limit,
            delay=args.delay,
            dry_run=args.dry_run,
        )

    # Final summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for name, stats in summary.items():
        print(f"  {name:>12s}: collected={stats['collected']}, saved={stats['saved']}")

    if args.dry_run:
        print("\n  [DRY RUN] No data was written to Neo4j.")

    print()


if __name__ == "__main__":
    main()
