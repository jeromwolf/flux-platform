"""KRISO test facilities crawler.

Crawls facility pages from KRISO homepage and updates
TestFacility nodes in Neo4j.

Usage::
    python -m kg.crawlers.kriso_facilities
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

# Known KRISO facility pages -- only ~10 so hardcoded is sensible.
FACILITY_URLS: dict[str, str] = {
    "TF-LTT": "https://www.kriso.re.kr/menu.es?mid=a20203010000",  # Large Towing Tank
    "TF-OEB": "https://www.kriso.re.kr/menu.es?mid=a20203040000",  # Ocean Engineering Basin
    "TF-ICE": "https://www.kriso.re.kr/menu.es?mid=a20203030000",  # Ice Tank
    "TF-DOB": "https://www.kriso.re.kr/menu.es?mid=a20202030000",  # Deep Ocean Basin
    "TF-WET": "https://www.kriso.re.kr/menu.es?mid=a20203060000",  # Wave Energy Test Site
    "TF-HPC": "https://www.kriso.re.kr/menu.es?mid=a20203070000",  # Hyperbaric Chamber
}


class KRISOFacilitiesCrawler(BaseCrawler):
    """Crawl KRISO facility pages and extract descriptions / specs."""

    @classmethod
    def info(cls) -> CrawlerInfo:
        """Return crawler metadata."""
        return CrawlerInfo(
            name="kriso-facilities",
            display_name="KRISO 시험시설",
            description="KRISO 시험시설 데이터 크롤러",
        )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_facility(html: str, facility_id: str, url: str) -> dict[str, Any]:
        """Extract facility description and specs from *html*.

        Because these are general CMS pages (not DSpace), we rely on
        the main content area rather than meta tags.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Try to extract the page title
        title = None
        title_tag = soup.find("h3", class_="sub_title") or soup.find("h2")
        if title_tag:
            title = title_tag.get_text(strip=True)
        if not title:
            og_title = soup.find("meta", attrs={"property": "og:title"})
            if og_title:
                title = og_title.get("content", "").strip()

        # Extract main content text -- look for the primary content div
        description_parts: list[str] = []
        for selector in [
            ".cont_area",
            ".sub_content",
            "#contents",
            ".content_area",
            "article",
        ]:
            container = soup.select_one(selector)
            if container:
                for p in container.find_all(["p", "li", "dd"]):
                    text = p.get_text(strip=True)
                    if text and len(text) > 5:
                        description_parts.append(text)
                break

        # Fall back to all <p> tags if nothing was found
        if not description_parts:
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if text and len(text) > 10:
                    description_parts.append(text)

        description = "\n".join(description_parts[:20])  # cap at 20 paragraphs

        # Try to extract table specs (common on facility pages)
        specs: dict[str, str] = {}
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["th", "td"])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    val = cells[1].get_text(strip=True)
                    if key and val:
                        specs[key] = val

        return {
            "facilityId": facility_id,
            "title": title,
            "description": description or None,
            "specs": specs or None,
            "sourceUrl": url,
        }

    # ------------------------------------------------------------------
    # Crawl
    # ------------------------------------------------------------------

    def crawl(self) -> list[dict[str, Any]]:
        """Fetch and parse all known facility pages."""
        results: list[dict[str, Any]] = []

        for facility_id, url in FACILITY_URLS.items():
            logger.info("Fetching facility %s: %s", facility_id, url)
            resp = self.fetch(url)
            if resp is None:
                logger.warning("Failed to fetch %s", url)
                continue

            record = self.parse_facility(resp.text, facility_id, url)
            results.append(record)
            logger.info(
                "Parsed %s: title=%s, desc_len=%d, specs=%d",
                facility_id,
                record.get("title"),
                len(record.get("description") or ""),
                len(record.get("specs") or {}),
            )

        logger.info("Collected %d facility records", len(results))
        return results

    # ------------------------------------------------------------------
    # Neo4j persistence
    # ------------------------------------------------------------------

    def save_to_neo4j(self, records: list[dict[str, Any]]) -> int:
        """Update existing TestFacility nodes with crawled descriptions.

        Returns the number of nodes updated.
        """
        if not records:
            logger.info("No facility records to save.")
            return 0

        query = """\
UNWIND $records AS rec
MERGE (tf:TestFacility {facilityId: rec.facilityId})
SET tf.crawledDescription = rec.description,
    tf.crawledTitle       = rec.title,
    tf.sourceUrl          = rec.sourceUrl,
    tf.source             = 'kriso_web_crawl',
    tf.crawledAt          = datetime()
RETURN count(tf) AS cnt
"""
        driver = get_driver()
        with driver.session(database=get_config().neo4j.database) as session:
            result = session.run(query, records=records)
            cnt = result.single()["cnt"]
            logger.info("Updated %d TestFacility nodes", cnt)

        return cnt


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl KRISO test facility pages",
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

    crawler = KRISOFacilitiesCrawler(delay=args.delay)
    records = crawler.crawl()

    if not records:
        print("No facility data collected.")
        sys.exit(0)

    print(f"\nCollected {len(records)} facility records:")
    for rec in records:
        desc_len = len(rec.get("description") or "")
        specs_count = len(rec.get("specs") or {})
        print(
            f"  - {rec['facilityId']}: {rec.get('title') or '(no title)'} "
            f"({desc_len} chars, {specs_count} specs)"
        )

    if args.dry_run:
        print("\n[DRY RUN] Skipping Neo4j save.")
    else:
        saved = crawler.save_to_neo4j(records)
        print(f"\nUpdated {saved} TestFacility nodes in Neo4j.")


if __name__ == "__main__":
    main()
