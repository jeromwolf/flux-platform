"""KMA (Korea Meteorological Administration) marine weather data crawler.

Provides sample marine weather data for Korean sea areas.
In production, this would connect to data.kma.go.kr API.

Usage::
    python -m kg.crawlers.kma_marine                 # sample data (10 records)
    python -m kg.crawlers.kma_marine --limit 50      # more records
    python -m kg.crawlers.kma_marine --dry-run       # parse only
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

# Korean sea areas for sample data generation
KOREAN_SEA_AREAS = [
    {"name": "동해 중부", "nameEn": "Central East Sea", "lat": 37.5, "lon": 130.0},
    {"name": "동해 남부", "nameEn": "South East Sea", "lat": 35.5, "lon": 130.5},
    {"name": "서해 중부", "nameEn": "Central West Sea", "lat": 36.5, "lon": 125.0},
    {"name": "서해 남부", "nameEn": "South West Sea", "lat": 34.5, "lon": 125.5},
    {"name": "남해 동부", "nameEn": "East South Sea", "lat": 34.0, "lon": 129.0},
    {"name": "남해 서부", "nameEn": "West South Sea", "lat": 33.5, "lon": 126.5},
    {"name": "제주 해역", "nameEn": "Jeju Sea", "lat": 33.0, "lon": 126.5},
    {"name": "동해 북부", "nameEn": "North East Sea", "lat": 39.0, "lon": 129.5},
    {"name": "울릉도 해역", "nameEn": "Ulleungdo Sea", "lat": 37.5, "lon": 131.0},
    {"name": "이어도 해역", "nameEn": "Ieodo Sea", "lat": 32.0, "lon": 125.0},
]


class KMAMarineCrawler(BaseCrawler):
    """Korea Meteorological Administration marine weather data crawler.

    Currently generates realistic sample data for demonstration.
    In production, connects to data.kma.go.kr marine weather API.
    """

    @classmethod
    def info(cls) -> CrawlerInfo:
        """Return crawler metadata."""
        return CrawlerInfo(
            name="kma-marine",
            display_name="기상청 해양기상",
            description="기상청 해양기상 데이터 크롤러",
        )

    def _generate_sample_record(self, area: dict[str, Any], timestamp: datetime) -> dict[str, Any]:
        """Generate a realistic sample weather record for a sea area."""
        # Seasonal temperature variation (rough approximation)
        month = timestamp.month
        base_temp = 15.0 + 10.0 * (1 - abs(month - 7) / 6.0)

        wind_speed = round(random.uniform(2.0, 25.0), 1)
        wave_height = round(wind_speed * random.uniform(0.05, 0.15), 1)

        # Sea state based on wave height (Douglas scale)
        if wave_height < 0.1:
            sea_state = 0
        elif wave_height < 0.5:
            sea_state = 2
        elif wave_height < 1.25:
            sea_state = 3
        elif wave_height < 2.5:
            sea_state = 4
        elif wave_height < 4.0:
            sea_state = 5
        else:
            sea_state = 6

        risk_level = "LOW"
        if wind_speed > 14 or wave_height > 2.5:
            risk_level = "MODERATE"
        if wind_speed > 20 or wave_height > 4.0:
            risk_level = "HIGH"

        return {
            "weatherId": f"WX-{area['nameEn'].replace(' ', '')}-{timestamp.strftime('%Y%m%d%H')}",
            "areaName": area["name"],
            "areaNameEn": area["nameEn"],
            "lat": area["lat"],
            "lon": area["lon"],
            "timestamp": timestamp.isoformat(),
            "windSpeed": wind_speed,
            "windDirection": round(random.uniform(0, 360), 1),
            "waveHeight": wave_height,
            "wavePeriod": round(random.uniform(4.0, 12.0), 1),
            "visibility": round(random.uniform(1.0, 30.0), 1),
            "seaState": sea_state,
            "temperature": round(base_temp + random.uniform(-3, 3), 1),
            "humidity": round(random.uniform(60, 95), 1),
            "pressure": round(random.uniform(1000, 1030), 1),
            "precipitation": round(random.choice([0, 0, 0, 0, random.uniform(0.1, 20)]), 1),
            "riskLevel": risk_level,
            "forecast": False,
            "source": "kma_sample",
        }

    def crawl(self, limit: int = 10) -> list[dict[str, Any]]:
        """Generate sample marine weather data for Korean sea areas.

        Parameters
        ----------
        limit : int
            Number of weather records to generate.

        Returns
        -------
        list[dict]
            Weather condition records.
        """
        results: list[dict[str, Any]] = []
        now = datetime.now()

        logger.info("Generating %d sample marine weather records", limit)

        for i in range(limit):
            area = KOREAN_SEA_AREAS[i % len(KOREAN_SEA_AREAS)]
            # Go back in time for each batch of areas
            hours_back = (i // len(KOREAN_SEA_AREAS)) * 6
            timestamp = now - timedelta(hours=hours_back)

            record = self._generate_sample_record(area, timestamp)
            results.append(record)

        logger.info("Generated %d weather records", len(results))
        return results

    def save_to_neo4j(self, records: list[dict[str, Any]]) -> int:
        """Save weather records to Neo4j as WeatherCondition nodes with relationships.

        Creates:
        - WeatherCondition nodes with all weather properties
        - AFFECTS relationship to matching SeaArea nodes
        - GeoPoint nodes for observation locations

        Returns the number of nodes written.
        """
        if not records:
            logger.info("No weather records to save.")
            return 0

        query = """\
UNWIND $records AS rec
MERGE (wc:WeatherCondition {weatherId: rec.weatherId})
SET wc.timestamp     = datetime(rec.timestamp),
    wc.windSpeed     = rec.windSpeed,
    wc.windDirection = rec.windDirection,
    wc.waveHeight    = rec.waveHeight,
    wc.wavePeriod    = rec.wavePeriod,
    wc.visibility    = rec.visibility,
    wc.seaState      = rec.seaState,
    wc.temperature   = rec.temperature,
    wc.humidity      = rec.humidity,
    wc.pressure      = rec.pressure,
    wc.precipitation = rec.precipitation,
    wc.riskLevel     = rec.riskLevel,
    wc.forecast      = rec.forecast,
    wc.source        = rec.source,
    wc.crawledAt     = datetime()

WITH wc, rec
// Link to SeaArea if exists
OPTIONAL MATCH (sa:SeaArea)
WHERE sa.name = rec.areaName OR sa.nameEn = rec.areaNameEn
FOREACH (_ IN CASE WHEN sa IS NOT NULL THEN [1] ELSE [] END |
    MERGE (wc)-[:AFFECTS]->(sa)
)

WITH wc, rec
// Create GeoPoint for observation location
MERGE (gp:GeoPoint {lat: rec.lat, lon: rec.lon})
SET gp.name = rec.areaName + ' 관측점'
MERGE (wc)-[:OBSERVED_AT]->(gp)

RETURN count(wc) AS cnt
"""
        driver = get_driver()
        with driver.session(database=get_config().neo4j.database) as session:
            result = session.run(query, records=records)
            cnt = result.single()["cnt"]
            logger.info("Saved %d WeatherCondition nodes", cnt)

        return cnt


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KMA Marine Weather Data Crawler",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of weather records to generate (default: 10)",
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

    crawler = KMAMarineCrawler(delay=args.delay)
    records = crawler.crawl(limit=args.limit)

    if not records:
        print("No weather data generated.")
        sys.exit(0)

    print(f"\nGenerated {len(records)} weather records:")
    for rec in records[:5]:
        print(
            f"  - {rec['areaName']}: "
            f"풍속={rec['windSpeed']}m/s, 파고={rec['waveHeight']}m, "
            f"기온={rec['temperature']}°C, 위험도={rec['riskLevel']}"
        )
    if len(records) > 5:
        print(f"  ... and {len(records) - 5} more")

    if args.dry_run:
        print("\n[DRY RUN] Skipping Neo4j save.")
    else:
        saved = crawler.save_to_neo4j(records)
        print(f"\nSaved {saved} WeatherCondition nodes to Neo4j.")


if __name__ == "__main__":
    main()
