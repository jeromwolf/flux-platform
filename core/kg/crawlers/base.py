"""Base crawler with HTTP session management, rate limiting, and retries."""

from __future__ import annotations

import abc
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from kg.etl.models import PipelineResult
    from kg.etl.pipeline import ETLPipeline

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CrawlerInfo:
    """Metadata describing a crawler.

    Attributes
    ----------
    name : str
        Machine-readable identifier (e.g. ``"kriso-papers"``).
    display_name : str
        Human-readable name shown in UIs and logs.
    description : str
        Short description of what the crawler collects.
    version : str
        Semantic version string.  Defaults to ``"1.0.0"``.
    """

    name: str
    display_name: str
    description: str
    version: str = field(default="1.0.0")


class BaseCrawler(abc.ABC):
    """Abstract base crawler providing HTTP helpers and Neo4j integration.

    Parameters
    ----------
    delay : float
        Minimum seconds to wait between consecutive HTTP requests.
        Defaults to ``1.0``.
    max_retries : int
        Maximum number of retry attempts for transient failures.
        Defaults to ``3``.
    """

    def __init__(self, delay: float = 1.0, max_retries: int = 3) -> None:
        self.delay = delay
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; KRISOCrawler/1.0; "
                    "+https://github.com/blockmeta/flux-n8n)"
                ),
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Crawler metadata
    # ------------------------------------------------------------------

    @classmethod
    def info(cls) -> CrawlerInfo:
        """Return metadata for this crawler.

        The default implementation derives a kebab-case name from the class
        name (e.g. ``KRISOPapersCrawler`` -> ``"kriso-papers-crawler"``).
        Subclasses should override to provide accurate metadata.
        """
        # Convert CamelCase to kebab-case
        raw = re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", cls.__name__)
        raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", raw)
        name = raw.lower()
        return CrawlerInfo(
            name=name,
            display_name=cls.__name__,
            description=cls.__doc__.strip().split("\n")[0] if cls.__doc__ else "",
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """Block until *delay* seconds have passed since the last request."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            sleep_for = self.delay - elapsed
            logger.debug("Rate-limiting: sleeping %.2f s", sleep_for)
            time.sleep(sleep_for)

    def fetch(self, url: str) -> requests.Response | None:
        """Fetch *url* with retries, rate limiting, and error handling.

        Returns
        -------
        requests.Response | None
            The response on success, or ``None`` if the resource is
            permanently unavailable (e.g. 404).
        """
        for attempt in range(1, self.max_retries + 1):
            self._rate_limit()
            try:
                self._last_request_time = time.time()
                resp = self.session.get(url, timeout=30)

                if resp.status_code == 404:
                    logger.debug("404 Not Found: %s", url)
                    return None

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    logger.warning(
                        "429 Too Many Requests for %s  -- backing off %d s (attempt %d/%d)",
                        url,
                        retry_after,
                        attempt,
                        self.max_retries,
                    )
                    time.sleep(retry_after)
                    continue

                if resp.status_code >= 500:
                    logger.warning(
                        "Server error %d for %s (attempt %d/%d)",
                        resp.status_code,
                        url,
                        attempt,
                        self.max_retries,
                    )
                    time.sleep(2**attempt)
                    continue

                resp.raise_for_status()
                return resp

            except requests.RequestException as exc:
                logger.warning(
                    "Request failed for %s: %s (attempt %d/%d)",
                    url,
                    exc,
                    attempt,
                    self.max_retries,
                )
                if attempt < self.max_retries:
                    time.sleep(2**attempt)

        logger.error("All %d attempts failed for %s", self.max_retries, url)
        return None

    # ------------------------------------------------------------------
    # ETL pipeline integration
    # ------------------------------------------------------------------

    def run_through_etl(
        self,
        records: list[dict[str, Any]],
        pipeline: ETLPipeline,
        session: Any = None,
    ) -> PipelineResult:
        """Route crawled records through an ETL pipeline for validation and loading.

        Wraps raw record dicts into RecordEnvelope objects and passes them
        to the pipeline's ``run()`` method, enabling validation, transformation,
        DLQ routing, and lineage tracking.

        Args:
            records: Raw record dicts from the crawler.
            pipeline: Configured ETLPipeline instance.
            session: Neo4j session passed to the pipeline loader.

        Returns:
            PipelineResult with processing metrics.
        """
        from kg.etl.models import RecordEnvelope

        info = self.info()
        envelopes = [
            RecordEnvelope(
                data=record,
                source=info.name,
                record_id=record.get(
                    "id", record.get("documentId", f"{info.name}-{i}")
                ),
            )
            for i, record in enumerate(records)
        ]
        return pipeline.run(envelopes, session=session)

    # ------------------------------------------------------------------
    # Neo4j persistence (subclass must implement)
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def save_to_neo4j(self, records: list[dict[str, Any]]) -> int:
        """Persist *records* to Neo4j and return the number written."""
        ...
