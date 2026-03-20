"""Maritime accident data crawler / generator.

Provides sample maritime accident data for Korean waters.
In production, this would connect to KMST (Korea Maritime Safety Tribunal) data.

Usage::
    python -m kg.crawlers.maritime_accidents               # sample (10)
    python -m kg.crawlers.maritime_accidents --limit 20    # more records
    python -m kg.crawlers.maritime_accidents --dry-run     # parse only
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import datetime, timedelta
from typing import Any

from kg.config import get_config, get_driver
from kg.crawlers.base import BaseCrawler, CrawlerInfo

logger = logging.getLogger(__name__)

# Realistic Korean maritime accident templates
ACCIDENT_TEMPLATES = [
    {
        "type": "Collision",
        "description_ko": "{vessel1}과 {vessel2}의 충돌사고",
        "severity_weights": {"MINOR": 0.3, "MODERATE": 0.5, "MAJOR": 0.15, "CRITICAL": 0.05},
    },
    {
        "type": "Grounding",
        "description_ko": "{vessel1} 좌초 사고",
        "severity_weights": {"MINOR": 0.2, "MODERATE": 0.4, "MAJOR": 0.3, "CRITICAL": 0.1},
    },
    {
        "type": "Fire",
        "description_ko": "{vessel1} 기관실 화재 사고",
        "severity_weights": {"MINOR": 0.2, "MODERATE": 0.3, "MAJOR": 0.35, "CRITICAL": 0.15},
    },
    {
        "type": "Capsizing",
        "description_ko": "{vessel1} 전복 사고",
        "severity_weights": {"MINOR": 0.05, "MODERATE": 0.15, "MAJOR": 0.4, "CRITICAL": 0.4},
    },
    {
        "type": "Sinking",
        "description_ko": "{vessel1} 침몰 사고",
        "severity_weights": {"MINOR": 0.0, "MODERATE": 0.1, "MAJOR": 0.4, "CRITICAL": 0.5},
    },
    {
        "type": "MachineFailure",
        "description_ko": "{vessel1} 기관 고장",
        "severity_weights": {"MINOR": 0.4, "MODERATE": 0.4, "MAJOR": 0.15, "CRITICAL": 0.05},
    },
    {
        "type": "PersonOverboard",
        "description_ko": "{vessel1} 선원 추락 사고",
        "severity_weights": {"MINOR": 0.1, "MODERATE": 0.3, "MAJOR": 0.3, "CRITICAL": 0.3},
    },
    {
        "type": "Pollution",
        "description_ko": "{vessel1} 유류 유출 사고",
        "severity_weights": {"MINOR": 0.2, "MODERATE": 0.3, "MAJOR": 0.35, "CRITICAL": 0.15},
    },
]

SAMPLE_VESSELS = [
    "제일호",
    "해성호",
    "동진호",
    "삼양호",
    "금강호",
    "부산호",
    "인천호",
    "여수호",
    "통영호",
    "울산호",
    "대한호",
    "한진호",
    "삼성호",
    "현대호",
    "동해호",
]

SAMPLE_AREAS = [
    {"name": "부산항 인근", "lat": 35.10, "lon": 129.03},
    {"name": "인천항 인근", "lat": 37.45, "lon": 126.60},
    {"name": "여수항 인근", "lat": 34.74, "lon": 127.74},
    {"name": "울산항 인근", "lat": 35.50, "lon": 129.40},
    {"name": "목포항 인근", "lat": 34.79, "lon": 126.38},
    {"name": "동해 중부 해상", "lat": 37.50, "lon": 130.00},
    {"name": "서해 중부 해상", "lat": 36.50, "lon": 125.00},
    {"name": "남해 동부 해상", "lat": 34.00, "lon": 129.00},
    {"name": "제주 해협", "lat": 33.50, "lon": 126.50},
    {"name": "대한해협", "lat": 34.50, "lon": 129.50},
]

INVESTIGATING_ORGS = [
    "해양안전심판원",
    "해양경찰청",
    "한국해양교통안전공단",
]


class MaritimeAccidentsCrawler(BaseCrawler):
    """Maritime accident data crawler.

    Currently generates realistic sample data.
    In production, connects to KMST or 해양안전심판원 data.
    """

    @classmethod
    def info(cls) -> CrawlerInfo:
        """Return crawler metadata."""
        return CrawlerInfo(
            name="maritime-accidents",
            display_name="해양사고",
            description="해양사고 데이터 크롤러",
        )

    @staticmethod
    def _weighted_choice(weights: dict[str, float]) -> str:
        """Select a random key weighted by the values."""
        keys = list(weights.keys())
        vals = list(weights.values())
        return random.choices(keys, weights=vals, k=1)[0]

    def _generate_accident(self, idx: int, base_date: datetime) -> dict[str, Any]:
        """Generate a single realistic accident record."""
        template = random.choice(ACCIDENT_TEMPLATES)
        area = random.choice(SAMPLE_AREAS)
        vessel1 = random.choice(SAMPLE_VESSELS)
        vessel2 = random.choice([v for v in SAMPLE_VESSELS if v != vessel1])

        # Random date within last 2 years
        days_back = random.randint(0, 730)
        incident_date = base_date - timedelta(days=days_back)

        severity = self._weighted_choice(template["severity_weights"])
        casualties = 0
        if severity in ("MAJOR", "CRITICAL"):
            casualties = random.randint(0, 5 if severity == "MAJOR" else 15)

        pollution_amount = 0.0
        if template["type"] == "Pollution":
            pollution_amount = round(random.uniform(0.1, 500.0), 1)

        resolved = random.random() > 0.2  # 80% resolved
        resolved_date = None
        if resolved:
            resolved_date = (incident_date + timedelta(days=random.randint(30, 365))).isoformat()

        description = template["description_ko"].format(vessel1=vessel1, vessel2=vessel2)
        description += f" - {area['name']}에서 발생"

        return {
            "incidentId": f"INC-{incident_date.strftime('%Y%m%d')}-{idx:03d}",
            "incidentType": template["type"],
            "date": incident_date.isoformat(),
            "lat": area["lat"] + random.uniform(-0.1, 0.1),
            "lon": area["lon"] + random.uniform(-0.1, 0.1),
            "areaName": area["name"],
            "severity": severity,
            "description": description,
            "casualties": casualties,
            "pollutionAmount": pollution_amount,
            "resolved": resolved,
            "resolvedDate": resolved_date,
            "involvedVessels": [vessel1] if template["type"] != "Collision" else [vessel1, vessel2],
            "investigatingOrg": random.choice(INVESTIGATING_ORGS),
            "source": "kmst_sample",
        }

    def crawl(self, limit: int = 10) -> list[dict[str, Any]]:
        """Generate sample maritime accident data.

        Parameters
        ----------
        limit : int
            Number of accident records to generate.

        Returns
        -------
        list[dict]
            Accident records.
        """
        results: list[dict[str, Any]] = []
        now = datetime.now()

        logger.info("Generating %d sample maritime accident records", limit)

        for i in range(limit):
            record = self._generate_accident(i + 1, now)
            results.append(record)

        # Sort by date descending
        results.sort(key=lambda r: r["date"], reverse=True)

        logger.info("Generated %d accident records", len(results))
        return results

    def save_to_neo4j(self, records: list[dict[str, Any]]) -> int:
        """Save accident records to Neo4j as Incident nodes with relationships.

        Creates:
        - Incident nodes (and subtype labels like Collision, Grounding)
        - OCCURRED_AT → GeoPoint
        - INVOLVES → Vessel (if matching vessel exists)
        - INVESTIGATED_BY → Organization

        Returns the number of nodes written.
        """
        if not records:
            logger.info("No accident records to save.")
            return 0

        query = """\
UNWIND $records AS rec
MERGE (inc:Incident {incidentId: rec.incidentId})
SET inc.incidentType     = rec.incidentType,
    inc.date             = datetime(rec.date),
    inc.severity         = rec.severity,
    inc.description      = rec.description,
    inc.casualties       = rec.casualties,
    inc.pollutionAmount  = rec.pollutionAmount,
    inc.resolved         = rec.resolved,
    inc.source           = rec.source,
    inc.crawledAt        = datetime()

WITH inc, rec
// Set resolved date if available
FOREACH (_ IN CASE WHEN rec.resolvedDate IS NOT NULL THEN [1] ELSE [] END |
    SET inc.resolvedDate = datetime(rec.resolvedDate)
)

WITH inc, rec
// Create GeoPoint for incident location
MERGE (gp:GeoPoint {lat: toFloat(rec.lat), lon: toFloat(rec.lon)})
SET gp.name = rec.areaName
MERGE (inc)-[:OCCURRED_AT {timestamp: datetime(rec.date)}]->(gp)

WITH inc, rec
// Link to SeaArea if matching
OPTIONAL MATCH (sa:SeaArea)
WHERE sa.name CONTAINS split(rec.areaName, ' ')[0]
FOREACH (_ IN CASE WHEN sa IS NOT NULL THEN [1] ELSE [] END |
    MERGE (inc)-[:OCCURRED_IN]->(sa)
)

WITH inc, rec
// Link to investigating organization
MERGE (org:Organization {name: rec.investigatingOrg})
MERGE (inc)-[:INVESTIGATED_BY]->(org)

WITH inc, rec
// Link to involved vessels (create if not exists)
UNWIND rec.involvedVessels AS vesselName
MERGE (v:Vessel {name: vesselName})
MERGE (inc)-[:INVOLVES]->(v)

RETURN count(DISTINCT inc) AS cnt
"""
        driver = get_driver()
        with driver.session(database=get_config().neo4j.database) as session:
            total = 0
            batch_size = 50
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                result = session.run(query, records=batch)
                cnt = result.single()["cnt"]
                total += cnt
                logger.info("Saved batch %d..%d (%d incidents)", i, i + len(batch) - 1, cnt)

        logger.info("Total saved to Neo4j: %d Incident nodes", total)
        return total


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Maritime Accident Data Crawler",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of accident records to generate (default: 10)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between requests (default: 0.5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate only; do not write to Neo4j",
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

    crawler = MaritimeAccidentsCrawler(delay=args.delay)
    records = crawler.crawl(limit=args.limit)

    if not records:
        print("No accident data generated.")
        sys.exit(0)

    print(f"\nGenerated {len(records)} accident records:")
    for rec in records[:5]:
        print(
            f"  - [{rec['incidentId']}] {rec['description']} "
            f"(심각도: {rec['severity']}, 사상자: {rec['casualties']})"
        )
    if len(records) > 5:
        print(f"  ... and {len(records) - 5} more")

    if args.dry_run:
        print("\n[DRY RUN] Skipping Neo4j save.")
    else:
        saved = crawler.save_to_neo4j(records)
        print(f"\nSaved {saved} Incident nodes to Neo4j.")


if __name__ == "__main__":
    main()
