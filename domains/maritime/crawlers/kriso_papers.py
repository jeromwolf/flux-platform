"""KRISO ScholarWorks paper metadata crawler.

Crawls individual paper pages from ScholarWorks@KRISO and stores
metadata as Document nodes in Neo4j.

Usage::
    python -m kg.crawlers.kriso_papers              # crawl sample (50)
    python -m kg.crawlers.kriso_papers --limit 100  # crawl 100
    python -m kg.crawlers.kriso_papers --all         # crawl all ~11,200
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from bs4 import BeautifulSoup

from kg.config import get_config, get_driver
from kg.crawlers.base import BaseCrawler, CrawlerInfo

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kriso.re.kr/sciwatch/handle/2021.sw.kriso/"


class KRISOPapersCrawler(BaseCrawler):
    """Crawl ScholarWorks@KRISO individual paper pages.

    Each paper lives at ``{BASE_URL}{id}`` where *id* is a numeric handle
    in the range [1, ~11 200].  The HTML ``<head>`` contains Dublin Core
    and citation meta tags which are the most reliable data source.
    """

    @classmethod
    def info(cls) -> CrawlerInfo:
        """Return crawler metadata."""
        return CrawlerInfo(
            name="kriso-papers",
            display_name="KRISO ScholarWorks",
            description="KRISO 학술논문 크롤러",
        )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _meta(soup: BeautifulSoup, *names: str) -> str | None:
        """Return the ``content`` of the first matching ``<meta>`` tag."""
        for name in names:
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content", "").strip():
                return tag["content"].strip()
        return None

    @staticmethod
    def _meta_list(soup: BeautifulSoup, *names: str) -> list[str]:
        """Return a list of ``content`` values from all matching ``<meta>`` tags."""
        values: list[str] = []
        for name in names:
            for tag in soup.find_all("meta", attrs={"name": name}):
                val = tag.get("content", "").strip()
                if val and val not in values:
                    values.append(val)
        return values

    def parse_paper(self, html: str, url: str) -> dict[str, Any] | None:
        """Parse a single paper page and return a record dict.

        Returns ``None`` when essential fields (title) are missing,
        indicating the page is not a valid paper entry.
        """
        soup = BeautifulSoup(html, "html.parser")

        title = self._meta(soup, "citation_title", "DC.title")
        if not title:
            # Fall back to <h2> or <title>
            h2 = soup.find("h2")
            if h2:
                title = h2.get_text(strip=True)
            else:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True)

        if not title:
            logger.debug("No title found for %s -- skipping", url)
            return None

        authors = self._meta_list(soup, "citation_author", "DC.creator")
        keywords = self._meta_list(soup, "citation_keywords", "DC.subject")

        record: dict[str, Any] = {
            "docId": f"SW-KRISO-{url.rstrip('/').split('/')[-1]}",
            "title": title,
            "authors": authors,
            "abstract": self._meta(soup, "DC.description", "DCTERMS.abstract"),
            "issueDate": self._meta(soup, "citation_date", "DC.date", "DCTERMS.issued"),
            "keywords": keywords,
            "doi": self._meta(soup, "citation_doi"),
            "journal": self._meta(soup, "citation_journal_title"),
            "docType": self._meta(soup, "DC.type"),
            "language": self._meta(soup, "DC.language"),
            "publisher": self._meta(soup, "citation_publisher", "DC.publisher"),
            "sourceUrl": url,
        }
        return record

    # ------------------------------------------------------------------
    # Crawl loop
    # ------------------------------------------------------------------

    def crawl(
        self,
        start_id: int = 1,
        end_id: int = 11200,
        limit: int | None = 50,
    ) -> list[dict[str, Any]]:
        """Iterate through handle IDs and collect paper metadata.

        Parameters
        ----------
        start_id, end_id : int
            Inclusive range of numeric IDs to attempt.
        limit : int | None
            Stop after collecting this many papers.  ``None`` means
            crawl the entire range.

        Returns
        -------
        list[dict]
            Parsed paper records.
        """
        results: list[dict[str, Any]] = []
        attempted = 0
        skipped_404 = 0

        logger.info(
            "Starting crawl: IDs %d..%d, limit=%s",
            start_id,
            end_id,
            limit if limit is not None else "ALL",
        )

        for paper_id in range(start_id, end_id + 1):
            if limit is not None and len(results) >= limit:
                break

            url = f"{BASE_URL}{paper_id}"
            attempted += 1

            resp = self.fetch(url)
            if resp is None:
                skipped_404 += 1
                continue

            record = self.parse_paper(resp.text, url)
            if record is None:
                continue

            results.append(record)

            if len(results) % 10 == 0:
                logger.info(
                    "Progress: %d papers collected (%d attempted, %d skipped)",
                    len(results),
                    attempted,
                    skipped_404,
                )

        logger.info(
            "Crawl complete: %d papers collected from %d attempts (%d 404s)",
            len(results),
            attempted,
            skipped_404,
        )
        return results

    # ------------------------------------------------------------------
    # Neo4j persistence
    # ------------------------------------------------------------------

    def save_to_neo4j(self, records: list[dict[str, Any]]) -> int:
        """Merge crawled paper records as Document nodes in Neo4j.

        Returns the number of nodes written.
        """
        if not records:
            logger.info("No records to save.")
            return 0

        query = """\
UNWIND $records AS rec
MERGE (d:Document {docId: rec.docId})
SET d.title     = rec.title,
    d.content   = rec.abstract,
    d.docType   = rec.docType,
    d.language  = rec.language,
    d.issueDate = rec.issueDate,
    d.source    = 'scholarworks_crawl',
    d.sourceUrl = rec.sourceUrl,
    d.journal   = rec.journal,
    d.publisher = rec.publisher,
    d.doi       = rec.doi,
    d.keywords  = rec.keywords,
    d.authors   = rec.authors,
    d.crawledAt = datetime()
WITH d, rec
MATCH (org:Organization {orgId: 'ORG-KRISO'})
MERGE (d)-[:ISSUED_BY]->(org)
RETURN count(d) AS cnt
"""
        driver = get_driver()
        with driver.session(database=get_config().neo4j.database) as session:
            # Process in batches of 100 to avoid oversized transactions
            total = 0
            batch_size = 100
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                result = session.run(query, records=batch)
                cnt = result.single()["cnt"]
                total += cnt
                logger.info(
                    "Saved batch %d..%d (%d nodes)",
                    i,
                    i + len(batch) - 1,
                    cnt,
                )

        logger.info("Total saved to Neo4j: %d Document nodes", total)
        return total


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl KRISO ScholarWorks paper metadata",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum papers to collect (default: 50)",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=1,
        help="First handle ID to try (default: 1)",
    )
    parser.add_argument(
        "--end-id",
        type=int,
        default=11200,
        help="Last handle ID to try (default: 11200)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Crawl the entire ID range (overrides --limit)",
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

    limit = None if args.all else args.limit

    crawler = KRISOPapersCrawler(delay=args.delay)
    records = crawler.crawl(
        start_id=args.start_id,
        end_id=args.end_id,
        limit=limit,
    )

    if not records:
        print("No papers found.")
        sys.exit(0)

    print(f"\nCollected {len(records)} papers.")
    # Show a sample
    for rec in records[:3]:
        print(f"  - [{rec['docId']}] {rec['title']}")
    if len(records) > 3:
        print(f"  ... and {len(records) - 3} more")

    if args.dry_run:
        print("\n[DRY RUN] Skipping Neo4j save.")
    else:
        saved = crawler.save_to_neo4j(records)
        print(f"\nSaved {saved} Document nodes to Neo4j.")


if __name__ == "__main__":
    main()
