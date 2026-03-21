"""Unit tests for crawler modules.

Tests for BaseCrawler, KMAMarineCrawler, MaritimeAccidentsCrawler,
KRISOPapersCrawler, KRISOFacilitiesCrawler, and RelationExtractor
using mocked HTTP requests and time.sleep.

Test Coverage:
- BaseCrawler initialization (5 tests)
- BaseCrawler rate limiting (3 tests)
- BaseCrawler fetch() with HTTP mocking (11 tests)
- KMAMarineCrawler crawl() method (9 tests)
- MaritimeAccidentsCrawler crawl() method (14 tests)
- KRISOPapersCrawler _meta, parse_paper, crawl (15 tests)
- KRISOFacilitiesCrawler parse_facility, crawl (10 tests)
- RelationExtractor all extraction methods (22 tests)

Total: 89 tests
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import requests as req

from maritime.crawlers.kma_marine import KMAMarineCrawler
from maritime.crawlers.maritime_accidents import MaritimeAccidentsCrawler

# ==============================================================================
# BaseCrawler Tests
# ==============================================================================


@pytest.mark.unit
class TestBaseCrawlerInit:
    """Tests for BaseCrawler initialization."""

    def test_default_parameters(self):
        """BaseCrawler has correct defaults (delay=1.0, max_retries=3)."""
        # Need concrete subclass since BaseCrawler is abstract
        crawler = KMAMarineCrawler()
        assert crawler.delay == 1.0
        assert crawler.max_retries == 3

    def test_custom_parameters(self):
        """BaseCrawler accepts custom delay and max_retries."""
        crawler = KMAMarineCrawler(delay=2.0, max_retries=5)
        assert crawler.delay == 2.0
        assert crawler.max_retries == 5

    def test_session_created(self):
        """BaseCrawler creates session with User-Agent header."""
        crawler = KMAMarineCrawler()
        assert crawler.session is not None
        assert "User-Agent" in crawler.session.headers
        assert "KRISOCrawler" in crawler.session.headers["User-Agent"]

    def test_last_request_time_initialized(self):
        """BaseCrawler initializes _last_request_time to 0.0."""
        crawler = KMAMarineCrawler()
        assert crawler._last_request_time == 0.0

    def test_session_has_accept_language(self):
        """BaseCrawler session includes Accept-Language header."""
        crawler = KMAMarineCrawler()
        assert "Accept-Language" in crawler.session.headers
        assert "ko-KR" in crawler.session.headers["Accept-Language"]


@pytest.mark.unit
class TestBaseCrawlerRateLimit:
    """Tests for rate limiting."""

    def test_rate_limit_sleeps_when_needed(self):
        """Rate limiter sleeps when called too quickly."""
        crawler = KMAMarineCrawler(delay=1.0)
        crawler._last_request_time = time.time()  # just now
        with patch("time.sleep") as mock_sleep:
            crawler._rate_limit()
            mock_sleep.assert_called_once()

    def test_rate_limit_no_sleep_when_enough_time(self):
        """Rate limiter does not sleep when enough time has passed."""
        crawler = KMAMarineCrawler(delay=1.0)
        crawler._last_request_time = 0.0  # long ago
        with patch("time.sleep") as mock_sleep:
            crawler._rate_limit()
            mock_sleep.assert_not_called()

    def test_rate_limit_sleep_duration_correct(self):
        """Rate limiter sleeps for correct duration."""
        crawler = KMAMarineCrawler(delay=2.0)
        crawler._last_request_time = time.time() - 0.5  # 0.5 seconds ago
        with patch("time.sleep") as mock_sleep:
            crawler._rate_limit()
            # Should sleep for approximately 1.5 seconds (2.0 - 0.5)
            call_args = mock_sleep.call_args[0][0]
            assert 1.4 < call_args < 1.6


@pytest.mark.unit
class TestBaseCrawlerFetch:
    """Tests for fetch() method with mocked HTTP."""

    def test_fetch_success(self):
        """Successful fetch returns response."""
        crawler = KMAMarineCrawler(delay=0)
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch.object(crawler.session, "get", return_value=mock_response):
            result = crawler.fetch("http://example.com")
            assert result == mock_response

    def test_fetch_404_returns_none(self):
        """404 response returns None (no retry)."""
        crawler = KMAMarineCrawler(delay=0)
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch.object(crawler.session, "get", return_value=mock_response):
            result = crawler.fetch("http://example.com/missing")
            assert result is None

    def test_fetch_429_retries(self):
        """429 causes retry with backoff."""
        crawler = KMAMarineCrawler(delay=0, max_retries=2)
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "1"}
        mock_200 = MagicMock()
        mock_200.status_code = 200

        with (
            patch.object(crawler.session, "get", side_effect=[mock_429, mock_200]),
            patch("time.sleep"),
        ):
            result = crawler.fetch("http://example.com")
            assert result == mock_200

    def test_fetch_429_without_retry_after_header(self):
        """429 without Retry-After header uses default 5 seconds."""
        crawler = KMAMarineCrawler(delay=0, max_retries=2)
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {}  # No Retry-After header
        mock_200 = MagicMock()
        mock_200.status_code = 200

        with (
            patch.object(crawler.session, "get", side_effect=[mock_429, mock_200]),
            patch("time.sleep") as mock_sleep,
        ):
            result = crawler.fetch("http://example.com")
            assert result == mock_200
            # Should sleep for 5 seconds (default)
            assert any(call[0][0] == 5 for call in mock_sleep.call_args_list)

    def test_fetch_500_retries(self):
        """500 server error causes retry with exponential backoff."""
        crawler = KMAMarineCrawler(delay=0, max_retries=2)
        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_200 = MagicMock()
        mock_200.status_code = 200

        with (
            patch.object(crawler.session, "get", side_effect=[mock_500, mock_200]),
            patch("time.sleep"),
        ):
            result = crawler.fetch("http://example.com")
            assert result == mock_200

    def test_fetch_503_retries(self):
        """503 service unavailable causes retry."""
        crawler = KMAMarineCrawler(delay=0, max_retries=2)
        mock_503 = MagicMock()
        mock_503.status_code = 503
        mock_200 = MagicMock()
        mock_200.status_code = 200

        with (
            patch.object(crawler.session, "get", side_effect=[mock_503, mock_200]),
            patch("time.sleep"),
        ):
            result = crawler.fetch("http://example.com")
            assert result == mock_200

    def test_fetch_all_retries_exhausted(self):
        """Returns None when all retries fail."""
        crawler = KMAMarineCrawler(delay=0, max_retries=2)
        mock_500 = MagicMock()
        mock_500.status_code = 500

        with patch.object(crawler.session, "get", return_value=mock_500), patch("time.sleep"):
            result = crawler.fetch("http://example.com")
            assert result is None

    def test_fetch_request_exception_retries(self):
        """RequestException causes retry."""
        crawler = KMAMarineCrawler(delay=0, max_retries=2)
        mock_200 = MagicMock()
        mock_200.status_code = 200

        with (
            patch.object(
                crawler.session, "get", side_effect=[req.ConnectionError("fail"), mock_200]
            ),
            patch("time.sleep"),
        ):
            result = crawler.fetch("http://example.com")
            assert result == mock_200

    def test_fetch_timeout_exception_retries(self):
        """Timeout exception causes retry."""
        crawler = KMAMarineCrawler(delay=0, max_retries=2)
        mock_200 = MagicMock()
        mock_200.status_code = 200

        with (
            patch.object(crawler.session, "get", side_effect=[req.Timeout("timeout"), mock_200]),
            patch("time.sleep"),
        ):
            result = crawler.fetch("http://example.com")
            assert result == mock_200

    def test_fetch_exponential_backoff(self):
        """Exponential backoff increases with each retry."""
        crawler = KMAMarineCrawler(delay=0, max_retries=3)
        mock_500 = MagicMock()
        mock_500.status_code = 500

        with (
            patch.object(crawler.session, "get", return_value=mock_500),
            patch("time.sleep") as mock_sleep,
        ):
            crawler.fetch("http://example.com")
            # Should sleep 2^1, 2^2, 2^3 seconds for exponential backoff
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert 2 in sleep_calls  # 2^1
            assert 4 in sleep_calls  # 2^2
            assert 8 in sleep_calls  # 2^3

    def test_fetch_raise_for_status_called(self):
        """Successful fetch calls raise_for_status."""
        crawler = KMAMarineCrawler(delay=0)
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch.object(crawler.session, "get", return_value=mock_response):
            crawler.fetch("http://example.com")
            mock_response.raise_for_status.assert_called_once()


# ==============================================================================
# KMAMarineCrawler Tests
# ==============================================================================


@pytest.mark.unit
class TestKMAMarineCrawler:
    """Tests for KMA marine weather crawler."""

    def test_crawl_returns_correct_count(self):
        """crawl() returns exactly the requested number of records."""
        crawler = KMAMarineCrawler(delay=0)
        records = crawler.crawl(limit=5)
        assert len(records) == 5

    def test_crawl_returns_correct_count_large(self):
        """crawl() handles larger limits correctly."""
        crawler = KMAMarineCrawler(delay=0)
        records = crawler.crawl(limit=50)
        assert len(records) == 50

    def test_crawl_record_structure(self):
        """crawl() returns records with required fields."""
        crawler = KMAMarineCrawler(delay=0)
        records = crawler.crawl(limit=1)
        rec = records[0]
        assert "weatherId" in rec
        assert "windSpeed" in rec
        assert "waveHeight" in rec
        assert "temperature" in rec
        assert "riskLevel" in rec
        assert rec["source"] == "kma_sample"

    def test_crawl_record_has_all_fields(self):
        """crawl() returns records with all expected fields."""
        crawler = KMAMarineCrawler(delay=0)
        records = crawler.crawl(limit=1)
        rec = records[0]
        expected_fields = [
            "weatherId",
            "areaName",
            "areaNameEn",
            "lat",
            "lon",
            "timestamp",
            "windSpeed",
            "windDirection",
            "waveHeight",
            "wavePeriod",
            "visibility",
            "seaState",
            "temperature",
            "humidity",
            "pressure",
            "precipitation",
            "riskLevel",
            "forecast",
            "source",
        ]
        for field in expected_fields:
            assert field in rec

    def test_crawl_risk_levels_valid(self):
        """crawl() returns only valid risk levels."""
        crawler = KMAMarineCrawler(delay=0)
        records = crawler.crawl(limit=20)
        valid_levels = {"LOW", "MODERATE", "HIGH"}
        for rec in records:
            assert rec["riskLevel"] in valid_levels

    def test_crawl_sea_state_range(self):
        """crawl() returns sea state values in valid range [0-6]."""
        crawler = KMAMarineCrawler(delay=0)
        records = crawler.crawl(limit=20)
        for rec in records:
            assert 0 <= rec["seaState"] <= 6

    def test_crawl_coordinates_valid(self):
        """crawl() returns valid lat/lon coordinates."""
        crawler = KMAMarineCrawler(delay=0)
        records = crawler.crawl(limit=20)
        for rec in records:
            assert 32.0 <= rec["lat"] <= 40.0  # Korean sea areas
            assert 124.0 <= rec["lon"] <= 132.0

    def test_crawl_wind_direction_valid(self):
        """crawl() returns wind direction in valid range [0-360]."""
        crawler = KMAMarineCrawler(delay=0)
        records = crawler.crawl(limit=20)
        for rec in records:
            assert 0 <= rec["windDirection"] <= 360

    def test_crawl_forecast_is_false(self):
        """crawl() returns records with forecast=False (observations)."""
        crawler = KMAMarineCrawler(delay=0)
        records = crawler.crawl(limit=10)
        for rec in records:
            assert rec["forecast"] is False


# ==============================================================================
# MaritimeAccidentsCrawler Tests
# ==============================================================================


@pytest.mark.unit
class TestMaritimeAccidentsCrawler:
    """Tests for maritime accidents crawler."""

    def test_crawl_returns_correct_count(self):
        """crawl() returns exactly the requested number of records."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=5)
        assert len(records) == 5

    def test_crawl_returns_correct_count_large(self):
        """crawl() handles larger limits correctly."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=30)
        assert len(records) == 30

    def test_crawl_record_structure(self):
        """crawl() returns records with required fields."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=1)
        rec = records[0]
        assert "incidentId" in rec
        assert "incidentType" in rec
        assert "severity" in rec
        assert "involvedVessels" in rec
        assert rec["source"] == "kmst_sample"

    def test_crawl_record_has_all_fields(self):
        """crawl() returns records with all expected fields."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=1)
        rec = records[0]
        expected_fields = [
            "incidentId",
            "incidentType",
            "date",
            "lat",
            "lon",
            "areaName",
            "severity",
            "description",
            "casualties",
            "pollutionAmount",
            "resolved",
            "resolvedDate",
            "involvedVessels",
            "investigatingOrg",
            "source",
        ]
        for field in expected_fields:
            assert field in rec

    def test_crawl_severity_valid(self):
        """crawl() returns only valid severity levels."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=20)
        valid = {"MINOR", "MODERATE", "MAJOR", "CRITICAL"}
        for rec in records:
            assert rec["severity"] in valid

    def test_crawl_sorted_by_date(self):
        """crawl() returns records sorted by date descending."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=10)
        dates = [rec["date"] for rec in records]
        assert dates == sorted(dates, reverse=True)

    def test_crawl_coordinates_valid(self):
        """crawl() returns valid lat/lon coordinates."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=20)
        for rec in records:
            assert 32.0 <= rec["lat"] <= 40.0  # Korean waters
            assert 124.0 <= rec["lon"] <= 132.0

    def test_crawl_involved_vessels_list(self):
        """crawl() returns involvedVessels as list."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=20)
        for rec in records:
            assert isinstance(rec["involvedVessels"], list)
            assert len(rec["involvedVessels"]) >= 1

    def test_crawl_collision_has_two_vessels(self):
        """crawl() returns two vessels for collision incidents."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=50)
        collision_records = [r for r in records if r["incidentType"] == "Collision"]
        for rec in collision_records:
            assert len(rec["involvedVessels"]) == 2

    def test_crawl_casualties_non_negative(self):
        """crawl() returns non-negative casualty counts."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=20)
        for rec in records:
            assert rec["casualties"] >= 0

    def test_crawl_pollution_amount_non_negative(self):
        """crawl() returns non-negative pollution amounts."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=20)
        for rec in records:
            assert rec["pollutionAmount"] >= 0.0

    def test_weighted_choice_returns_valid(self):
        """_weighted_choice() returns key from weights dict."""
        weights = {"A": 0.5, "B": 0.3, "C": 0.2}
        result = MaritimeAccidentsCrawler._weighted_choice(weights)
        assert result in weights

    def test_weighted_choice_distribution(self):
        """_weighted_choice() respects probability distribution roughly."""
        weights = {"A": 0.8, "B": 0.2}
        results = [MaritimeAccidentsCrawler._weighted_choice(weights) for _ in range(100)]
        a_count = results.count("A")
        # With 100 samples, expect roughly 80 A's (allow wide margin for randomness)
        assert 60 <= a_count <= 95

    def test_crawl_incident_id_format(self):
        """crawl() returns incident IDs in expected format."""
        crawler = MaritimeAccidentsCrawler(delay=0)
        records = crawler.crawl(limit=10)
        for rec in records:
            assert rec["incidentId"].startswith("INC-")
            assert len(rec["incidentId"]) >= 12  # INC-YYYYMMDD-NNN


# ==============================================================================
# KRISOPapersCrawler Tests
# ==============================================================================


@pytest.mark.unit
class TestKRISOPapersCrawlerMeta:
    """Tests for _meta static method."""

    def test_meta_returns_content_from_citation_title(self):
        """_meta returns content from citation_title meta tag."""
        from bs4 import BeautifulSoup

        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = '<html><head><meta name="citation_title" content="Test Title"/></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        result = KRISOPapersCrawler._meta(soup, "citation_title")
        assert result == "Test Title"

    def test_meta_returns_content_from_dc_title_fallback(self):
        """_meta returns content from DC.title fallback."""
        from bs4 import BeautifulSoup

        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = '<html><head><meta name="DC.title" content="DC Title"/></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        result = KRISOPapersCrawler._meta(soup, "citation_title", "DC.title")
        assert result == "DC Title"

    def test_meta_returns_none_when_no_match(self):
        """_meta returns None when no matching meta tag found."""
        from bs4 import BeautifulSoup

        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = "<html><head></head></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = KRISOPapersCrawler._meta(soup, "nonexistent")
        assert result is None

    def test_meta_list_returns_multiple_authors(self):
        """_meta_list returns multiple author values."""
        from bs4 import BeautifulSoup

        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = """<html><head>
            <meta name="citation_author" content="Author One"/>
            <meta name="citation_author" content="Author Two"/>
        </head></html>"""
        soup = BeautifulSoup(html, "html.parser")
        result = KRISOPapersCrawler._meta_list(soup, "citation_author")
        assert len(result) == 2
        assert "Author One" in result
        assert "Author Two" in result

    def test_meta_list_deduplicates_values(self):
        """_meta_list deduplicates repeated values."""
        from bs4 import BeautifulSoup

        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = """<html><head>
            <meta name="citation_author" content="Same Author"/>
            <meta name="citation_author" content="Same Author"/>
        </head></html>"""
        soup = BeautifulSoup(html, "html.parser")
        result = KRISOPapersCrawler._meta_list(soup, "citation_author")
        assert len(result) == 1
        assert result[0] == "Same Author"


@pytest.mark.unit
class TestKRISOPapersCrawlerParse:
    """Tests for parse_paper method."""

    def test_parse_paper_with_full_html_returns_correct_fields(self):
        """parse_paper with full HTML returns correct record fields."""
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = """<html><head>
            <meta name="citation_title" content="Test Paper"/>
            <meta name="citation_author" content="John Doe"/>
            <meta name="DC.description" content="This is abstract"/>
            <meta name="citation_date" content="2024-01-15"/>
            <meta name="citation_keywords" content="maritime"/>
            <meta name="citation_keywords" content="simulation"/>
        </head></html>"""

        crawler = KRISOPapersCrawler(delay=0)
        result = crawler.parse_paper(html, "http://example.com/12345")

        assert result is not None
        assert result["title"] == "Test Paper"
        assert "John Doe" in result["authors"]
        assert result["abstract"] == "This is abstract"
        assert result["issueDate"] == "2024-01-15"
        assert "maritime" in result["keywords"]

    def test_parse_paper_with_missing_title_falls_back_to_h2(self):
        """parse_paper with missing meta title falls back to h2 text."""
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = """<html>
            <body><h2>H2 Title</h2></body>
        </html>"""

        crawler = KRISOPapersCrawler(delay=0)
        result = crawler.parse_paper(html, "http://example.com/12345")

        assert result is not None
        assert result["title"] == "H2 Title"

    def test_parse_paper_with_no_title_returns_none(self):
        """parse_paper with no title returns None."""
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = "<html><head></head><body></body></html>"

        crawler = KRISOPapersCrawler(delay=0)
        result = crawler.parse_paper(html, "http://example.com/12345")

        assert result is None

    def test_parse_paper_record_has_all_expected_fields(self):
        """parse_paper record contains all expected fields."""
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = """<html><head>
            <meta name="citation_title" content="Test Paper"/>
            <meta name="citation_author" content="Author One"/>
        </head></html>"""

        crawler = KRISOPapersCrawler(delay=0)
        result = crawler.parse_paper(html, "http://example.com/12345")

        expected_fields = [
            "docId",
            "title",
            "authors",
            "abstract",
            "issueDate",
            "keywords",
            "sourceUrl",
        ]
        for field in expected_fields:
            assert field in result

    def test_parse_paper_doc_id_format(self):
        """parse_paper docId format is SW-KRISO-{id}."""
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        html = '<html><head><meta name="citation_title" content="Test"/></head></html>'

        crawler = KRISOPapersCrawler(delay=0)
        result = crawler.parse_paper(html, "http://example.com/handle/12345")

        assert result["docId"].startswith("SW-KRISO-")
        assert "12345" in result["docId"]


@pytest.mark.unit
class TestKRISOPapersCrawlerCrawl:
    """Tests for crawl method."""

    def test_crawl_respects_limit(self):
        """crawl respects limit parameter."""
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        crawler = KRISOPapersCrawler(delay=0)

        # Mock fetch to return valid HTML
        html = '<html><head><meta name="citation_title" content="Test"/></head></html>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch.object(crawler, "fetch", return_value=mock_response):
            records = crawler.crawl(start_id=1, end_id=100, limit=5)
            assert len(records) == 5

    def test_crawl_skips_404_responses(self):
        """crawl skips 404 responses (fetch returning None)."""
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        crawler = KRISOPapersCrawler(delay=0)

        # Mock fetch to return None (404) for some IDs
        html = '<html><head><meta name="citation_title" content="Test"/></head></html>'
        mock_response = MagicMock()
        mock_response.text = html

        call_count = 0

        def mock_fetch(url):
            nonlocal call_count
            call_count += 1
            # Return None for every other call (simulating 404)
            if call_count % 2 == 0:
                return None
            return mock_response

        with patch.object(crawler, "fetch", side_effect=mock_fetch):
            records = crawler.crawl(start_id=1, end_id=5, limit=10)
            # Should get 3 records (IDs 1, 3, 5 succeed; 2, 4 fail)
            assert len(records) == 3

    def test_crawl_skips_pages_without_title(self):
        """crawl skips pages without title."""
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        crawler = KRISOPapersCrawler(delay=0)

        # Mock fetch to return HTML without title
        mock_response = MagicMock()
        mock_response.text = "<html><head></head></html>"

        with patch.object(crawler, "fetch", return_value=mock_response):
            records = crawler.crawl(start_id=1, end_id=10, limit=10)
            assert len(records) == 0

    def test_crawl_returns_list_of_dicts(self):
        """crawl returns list of dicts."""
        from maritime.crawlers.kriso_papers import KRISOPapersCrawler

        crawler = KRISOPapersCrawler(delay=0)

        html = '<html><head><meta name="citation_title" content="Test"/></head></html>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch.object(crawler, "fetch", return_value=mock_response):
            records = crawler.crawl(start_id=1, end_id=5, limit=3)
            assert isinstance(records, list)
            assert all(isinstance(rec, dict) for rec in records)


# ==============================================================================
# KRISOFacilitiesCrawler Tests
# ==============================================================================


@pytest.mark.unit
class TestKRISOFacilitiesCrawlerParse:
    """Tests for parse_facility static method."""

    def test_parse_facility_extracts_title_from_h3_sub_title(self):
        """parse_facility extracts title from h3.sub_title."""
        from maritime.crawlers.kriso_facilities import KRISOFacilitiesCrawler

        html = '<html><body><h3 class="sub_title">Ocean Basin</h3></body></html>'

        result = KRISOFacilitiesCrawler.parse_facility(html, "oeb", "http://example.com")

        assert result is not None
        assert result["title"] == "Ocean Basin"

    def test_parse_facility_extracts_title_from_og_title_fallback(self):
        """parse_facility extracts title from og:title fallback."""
        from maritime.crawlers.kriso_facilities import KRISOFacilitiesCrawler

        html = '<html><head><meta property="og:title" content="Ice Tank"/></head></html>'

        result = KRISOFacilitiesCrawler.parse_facility(html, "ice", "http://example.com")

        assert result is not None
        assert result["title"] == "Ice Tank"

    def test_parse_facility_extracts_description_from_cont_area(self):
        """parse_facility extracts description from .cont_area paragraphs."""
        from maritime.crawlers.kriso_facilities import KRISOFacilitiesCrawler

        html = """<html><body>
            <h3 class="sub_title">Test Facility</h3>
            <div class="cont_area">
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
            </div>
        </body></html>"""

        result = KRISOFacilitiesCrawler.parse_facility(html, "test", "http://example.com")

        assert result is not None
        assert "First paragraph" in result["description"]
        assert "Second paragraph" in result["description"]

    def test_parse_facility_extracts_table_specs(self):
        """parse_facility extracts table specs."""
        from maritime.crawlers.kriso_facilities import KRISOFacilitiesCrawler

        html = """<html><body>
            <h3 class="sub_title">Test Facility</h3>
            <table>
                <tr><th>Length</th><td>100m</td></tr>
                <tr><th>Width</th><td>50m</td></tr>
            </table>
        </body></html>"""

        result = KRISOFacilitiesCrawler.parse_facility(html, "test", "http://example.com")

        assert result is not None
        assert "specs" in result
        assert isinstance(result["specs"], dict)
        assert result["specs"]["Length"] == "100m"
        assert result["specs"]["Width"] == "50m"

    def test_parse_facility_returns_correct_facility_id(self):
        """parse_facility returns correct facilityId."""
        from maritime.crawlers.kriso_facilities import KRISOFacilitiesCrawler

        html = '<html><body><h3 class="sub_title">Test</h3></body></html>'

        result = KRISOFacilitiesCrawler.parse_facility(html, "custom_id", "http://example.com")

        assert result["facilityId"] == "custom_id"

    def test_parse_facility_with_empty_page_returns_none_description(self):
        """parse_facility with empty page returns None description."""
        from maritime.crawlers.kriso_facilities import KRISOFacilitiesCrawler

        html = '<html><body><h3 class="sub_title">Test</h3></body></html>'

        result = KRISOFacilitiesCrawler.parse_facility(html, "test", "http://example.com")

        assert result["description"] is None or result["description"] == ""


@pytest.mark.unit
class TestKRISOFacilitiesCrawlerCrawl:
    """Tests for crawl method."""

    def test_crawl_fetches_all_facility_urls(self):
        """crawl fetches all FACILITY_URLS."""
        from maritime.crawlers.kriso_facilities import FACILITY_URLS, KRISOFacilitiesCrawler

        crawler = KRISOFacilitiesCrawler(delay=0)

        html = '<html><body><h3 class="sub_title">Test Facility</h3></body></html>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch.object(crawler, "fetch", return_value=mock_response) as mock_fetch:
            crawler.crawl()
            # Should call fetch for each facility URL
            assert mock_fetch.call_count == len(FACILITY_URLS)

    def test_crawl_skips_failed_fetches(self):
        """crawl skips failed fetches."""
        from maritime.crawlers.kriso_facilities import FACILITY_URLS, KRISOFacilitiesCrawler

        crawler = KRISOFacilitiesCrawler(delay=0)

        def mock_fetch(url):
            # Return None for first URL (Large Towing Tank)
            if "a20203010000" in url:
                return None
            mock_response = MagicMock()
            mock_response.text = '<html><body><h3 class="sub_title">Test</h3></body></html>'
            return mock_response

        with patch.object(crawler, "fetch", side_effect=mock_fetch):
            records = crawler.crawl()
            # Should get fewer records than total facilities (one failed)
            assert len(records) == len(FACILITY_URLS) - 1

    def test_crawl_returns_list_of_dicts(self):
        """crawl returns list of dicts with correct keys."""
        from maritime.crawlers.kriso_facilities import KRISOFacilitiesCrawler

        crawler = KRISOFacilitiesCrawler(delay=0)

        html = '<html><body><h3 class="sub_title">Test Facility</h3></body></html>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch.object(crawler, "fetch", return_value=mock_response):
            records = crawler.crawl()
            assert isinstance(records, list)
            assert all(isinstance(rec, dict) for rec in records)

    def test_crawl_record_has_required_keys(self):
        """crawl record has facilityId, title, description, specs, sourceUrl."""
        from maritime.crawlers.kriso_facilities import KRISOFacilitiesCrawler

        crawler = KRISOFacilitiesCrawler(delay=0)

        html = '<html><body><h3 class="sub_title">Test Facility</h3></body></html>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch.object(crawler, "fetch", return_value=mock_response):
            records = crawler.crawl()
            if records:
                rec = records[0]
                assert "facilityId" in rec
                assert "title" in rec
                assert "description" in rec
                assert "specs" in rec
                assert "sourceUrl" in rec


# ==============================================================================
# RelationExtractor Tests
# ==============================================================================


@pytest.mark.unit
class TestExtractedRelation:
    """Tests for ExtractedRelation dataclass."""

    def test_dataclass_fields(self):
        """ExtractedRelation has correct fields."""
        from maritime.crawlers.relation_extractor import ExtractedRelation

        rel = ExtractedRelation(
            source_id="DOC-001",
            target_type="VesselType",
            target_name="ContainerShip",
            relation_type="ABOUT_VESSEL_TYPE",
            confidence=0.8,
            context="sample context",
        )

        assert rel.source_id == "DOC-001"
        assert rel.target_type == "VesselType"
        assert rel.target_name == "ContainerShip"
        assert rel.relation_type == "ABOUT_VESSEL_TYPE"
        assert rel.confidence == 0.8
        assert rel.context == "sample context"

    def test_dataclass_creation(self):
        """ExtractedRelation can be created successfully."""
        from maritime.crawlers.relation_extractor import ExtractedRelation

        rel = ExtractedRelation("DOC-001", "Port", "KRPUS", "MENTIONS_PORT", 0.9, "context")

        assert isinstance(rel, ExtractedRelation)
        assert rel.target_name == "KRPUS"


@pytest.mark.unit
class TestRelationExtractorVessels:
    """Tests for extract_vessel_types method."""

    def test_extract_vessel_types_finds_korean_keyword(self):
        """extract_vessel_types finds Korean keyword 컨테이너선."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "이 논문은 컨테이너선의 안정성을 연구합니다."

        results = extractor.extract_vessel_types("DOC-001", text)

        assert len(results) > 0
        assert any(r.target_name == "ContainerShip" for r in results)

    def test_extract_vessel_types_finds_english_keyword(self):
        """extract_vessel_types finds English keyword 'tanker'."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "This paper studies tanker ship design."

        results = extractor.extract_vessel_types("DOC-001", text)

        assert len(results) > 0
        assert any(r.target_name == "Tanker" for r in results)

    def test_extract_vessel_types_case_insensitive(self):
        """extract_vessel_types is case insensitive."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "TANKER ship operations"

        results = extractor.extract_vessel_types("DOC-001", text)

        assert len(results) > 0
        assert any(r.target_name == "Tanker" for r in results)

    def test_extract_vessel_types_returns_empty_for_unrelated_text(self):
        """extract_vessel_types returns empty for unrelated text."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "This is about weather and birds."

        results = extractor.extract_vessel_types("DOC-001", text)

        assert len(results) == 0

    def test_extract_vessel_types_confidence_is_0_7(self):
        """extract_vessel_types confidence is 0.7."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "컨테이너선 연구"

        results = extractor.extract_vessel_types("DOC-001", text)

        assert len(results) > 0
        assert all(r.confidence == 0.7 for r in results)


@pytest.mark.unit
class TestRelationExtractorPorts:
    """Tests for extract_ports method."""

    def test_extract_ports_finds_busan_port(self):
        """extract_ports finds 부산항."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "부산항에서 출발한 선박"

        results = extractor.extract_ports("DOC-001", text)

        assert len(results) > 0
        assert any(r.target_name == "KRPUS" for r in results)

    def test_extract_ports_returns_correct_port_code(self):
        """extract_ports returns correct port code KRPUS."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "부산항 분석"

        results = extractor.extract_ports("DOC-001", text)

        port_result = next((r for r in results if r.target_name == "KRPUS"), None)
        assert port_result is not None
        assert port_result.relation_type == "MENTIONS_PORT"

    def test_extract_ports_confidence_is_0_8(self):
        """extract_ports confidence is 0.8."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "부산항"

        results = extractor.extract_ports("DOC-001", text)

        assert len(results) > 0
        assert all(r.confidence == 0.8 for r in results)


@pytest.mark.unit
class TestRelationExtractorSeaAreas:
    """Tests for extract_sea_areas method."""

    def test_extract_sea_areas_finds_korean_east_sea(self):
        """extract_sea_areas finds 동해."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "동해 해역의 해양 환경"

        results = extractor.extract_sea_areas("DOC-001", text)

        assert len(results) > 0
        assert any(r.target_name == "동해" for r in results)

    def test_extract_sea_areas_finds_english_east_sea(self):
        """extract_sea_areas finds English 'East Sea'."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "Research in the East Sea region"

        results = extractor.extract_sea_areas("DOC-001", text)

        assert len(results) > 0
        assert any(r.target_name == "동해" for r in results)


@pytest.mark.unit
class TestRelationExtractorTopics:
    """Tests for extract_topics method."""

    def test_extract_topics_finds_fluid_dynamics(self):
        """extract_topics finds 유체역학."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "유체역학 시뮬레이션 연구"

        results = extractor.extract_topics("DOC-001", text)

        assert len(results) > 0
        assert any("유체역학" in r.context for r in results)

    def test_extract_topics_uses_keywords_parameter(self):
        """extract_topics uses keywords parameter."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "research on simulation"
        keywords = ["시뮬레이션"]  # Known topic keyword

        results = extractor.extract_topics("DOC-001", text, keywords=keywords)

        assert len(results) > 0

    def test_extract_topics_confidence_is_0_65(self):
        """extract_topics confidence is 0.65."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "유체역학"

        results = extractor.extract_topics("DOC-001", text)

        assert len(results) > 0
        assert all(r.confidence == 0.65 for r in results)


@pytest.mark.unit
class TestRelationExtractorRegulations:
    """Tests for extract_regulations method."""

    def test_extract_regulations_finds_solas(self):
        """extract_regulations finds SOLAS."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "This research complies with SOLAS regulations."

        results = extractor.extract_regulations("DOC-001", text)

        assert len(results) > 0
        assert any(r.target_name == "SOLAS" for r in results)

    def test_extract_regulations_confidence_is_0_85(self):
        """extract_regulations confidence is 0.85."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "SOLAS 규정"

        results = extractor.extract_regulations("DOC-001", text)

        assert len(results) > 0
        assert all(r.confidence == 0.85 for r in results)


@pytest.mark.unit
class TestRelationExtractorFacilities:
    """Tests for extract_facilities method."""

    def test_extract_facilities_finds_towing_tank(self):
        """extract_facilities finds 예인수조."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "예인수조 실험 결과"

        results = extractor.extract_facilities("DOC-001", text)

        assert len(results) > 0
        assert any("예인수조" in r.context for r in results)

    def test_extract_facilities_case_insensitive(self):
        """extract_facilities is case insensitive."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "towing tank experiments"

        results = extractor.extract_facilities("DOC-001", text)

        assert len(results) > 0
        assert any("towing tank" in r.context.lower() for r in results)


@pytest.mark.unit
class TestRelationExtractorAll:
    """Tests for extract_all method."""

    def test_extract_all_returns_combined_results(self):
        """extract_all returns combined results from all extractors."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "부산항에서 컨테이너선이 출발했다. 동해 해역에서 SOLAS 규정을 준수한다."

        results = extractor.extract_all("DOC-001", text)

        # Should have results from multiple categories
        target_types = {r.target_type for r in results}
        assert len(target_types) > 1

    def test_extract_all_deduplicates(self):
        """extract_all deduplicates identical relations."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "부산항 부산항 부산항"

        results = extractor.extract_all("DOC-001", text)

        # Should only have one result for 부산항 despite multiple mentions
        port_results = [r for r in results if r.target_type == "Port"]
        assert len(port_results) == 1

    def test_extract_all_with_empty_text_returns_empty(self):
        """extract_all with empty text returns empty list."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = ""

        results = extractor.extract_all("DOC-001", text)

        assert len(results) == 0

    def test_extract_all_with_keywords(self):
        """extract_all accepts and uses keywords parameter."""
        from maritime.crawlers.relation_extractor import RelationExtractor

        extractor = RelationExtractor()
        text = "research topic"
        keywords = ["시뮬레이션"]  # Known topic keyword

        results = extractor.extract_all("DOC-001", text, keywords=keywords)

        # Should find the keyword from topics
        assert len(results) > 0


# ==============================================================================
# Crawler-ETL Integration Tests (BaseCrawler.run_through_etl)
# ==============================================================================


def _make_concrete_crawler() -> KMAMarineCrawler:
    """Create a concrete BaseCrawler subclass instance for testing."""
    return KMAMarineCrawler(delay=0)


@pytest.mark.unit
class TestCrawlerETLIntegration:
    """Tests for BaseCrawler.run_through_etl() ETL pipeline integration."""

    def test_run_through_etl_wraps_records(self):
        """Records are wrapped in RecordEnvelope with crawler source."""
        from kg.etl.models import PipelineConfig
        from kg.etl.pipeline import ETLPipeline

        crawler = _make_concrete_crawler()
        pipeline = ETLPipeline(PipelineConfig(name="test"))

        records = [{"id": "doc-1", "title": "Test"}]
        result = crawler.run_through_etl(records, pipeline)

        assert result.records_processed == 1
        assert result.total_input == 1

    def test_run_through_etl_uses_crawler_source(self):
        """RecordEnvelope.source is set to the crawler's info name."""
        from kg.etl.models import PipelineConfig
        from kg.etl.pipeline import ETLPipeline

        crawler = _make_concrete_crawler()
        pipeline = ETLPipeline(PipelineConfig(name="test"))

        # Capture envelopes by monkey-patching pipeline.run
        captured: list = []
        original_run = pipeline.run

        def capturing_run(records, session=None):
            captured.extend(records)
            return original_run(records, session)

        pipeline.run = capturing_run  # type: ignore[method-assign]

        records = [{"id": "doc-1", "title": "Test"}]
        crawler.run_through_etl(records, pipeline)

        assert len(captured) == 1
        # The source should match the crawler info name
        info = crawler.info()
        assert captured[0].source == info.name

    def test_run_through_etl_generates_record_ids(self):
        """Records without 'id' get auto-generated record IDs."""
        from kg.etl.models import PipelineConfig
        from kg.etl.pipeline import ETLPipeline

        crawler = _make_concrete_crawler()
        pipeline = ETLPipeline(PipelineConfig(name="test"))

        captured: list = []
        original_run = pipeline.run

        def capturing_run(records, session=None):
            captured.extend(records)
            return original_run(records, session)

        pipeline.run = capturing_run  # type: ignore[method-assign]

        records = [{"title": "No ID record"}]
        crawler.run_through_etl(records, pipeline)

        assert len(captured) == 1
        info = crawler.info()
        assert captured[0].record_id == f"{info.name}-0"

    def test_run_through_etl_uses_document_id_fallback(self):
        """Records with 'documentId' but no 'id' use documentId as record_id."""
        from kg.etl.models import PipelineConfig
        from kg.etl.pipeline import ETLPipeline

        crawler = _make_concrete_crawler()
        pipeline = ETLPipeline(PipelineConfig(name="test"))

        captured: list = []
        original_run = pipeline.run

        def capturing_run(records, session=None):
            captured.extend(records)
            return original_run(records, session)

        pipeline.run = capturing_run  # type: ignore[method-assign]

        records = [{"documentId": "DOC-42", "title": "Has documentId"}]
        crawler.run_through_etl(records, pipeline)

        assert len(captured) == 1
        assert captured[0].record_id == "DOC-42"

    def test_run_through_etl_empty_records(self):
        """Empty record list returns zero-count result."""
        from kg.etl.models import PipelineConfig
        from kg.etl.pipeline import ETLPipeline

        crawler = _make_concrete_crawler()
        pipeline = ETLPipeline(PipelineConfig(name="test"))

        result = crawler.run_through_etl([], pipeline)
        assert result.records_processed == 0
        assert result.total_input == 0

    def test_run_through_etl_multiple_records(self):
        """Multiple records are all wrapped and processed."""
        from kg.etl.models import PipelineConfig
        from kg.etl.pipeline import ETLPipeline

        crawler = _make_concrete_crawler()
        pipeline = ETLPipeline(PipelineConfig(name="test"))

        records = [
            {"id": "doc-1", "title": "First"},
            {"id": "doc-2", "title": "Second"},
            {"id": "doc-3", "title": "Third"},
        ]
        result = crawler.run_through_etl(records, pipeline)

        assert result.records_processed == 3
        assert result.total_input == 3

    def test_run_through_etl_with_validation_failure(self):
        """Records failing validation are routed to DLQ."""
        from kg.etl.models import PipelineConfig
        from kg.etl.pipeline import ETLPipeline
        from kg.etl.validator import RecordValidator, RequiredFieldsRule

        crawler = _make_concrete_crawler()
        pipeline = ETLPipeline(PipelineConfig(name="test", validate=True))
        pipeline.set_validator(
            RecordValidator([RequiredFieldsRule(["requiredField"])])
        )

        records = [{"id": "doc-1", "title": "Missing required"}]
        result = crawler.run_through_etl(records, pipeline)

        assert result.records_skipped == 1
        assert result.records_processed == 0

    def test_run_through_etl_passes_session_to_pipeline(self):
        """The session parameter is forwarded to the pipeline's run method."""
        from kg.etl.models import PipelineConfig
        from kg.etl.pipeline import ETLPipeline

        crawler = _make_concrete_crawler()
        pipeline = ETLPipeline(PipelineConfig(name="test"))

        received_sessions: list = []
        original_run = pipeline.run

        def capturing_run(records, session=None):
            received_sessions.append(session)
            return original_run(records, session)

        pipeline.run = capturing_run  # type: ignore[method-assign]

        mock_session = MagicMock()
        crawler.run_through_etl(
            [{"id": "doc-1"}], pipeline, session=mock_session
        )

        assert len(received_sessions) == 1
        assert received_sessions[0] is mock_session
