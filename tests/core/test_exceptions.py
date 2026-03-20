"""Unit tests for project exception hierarchy."""

from __future__ import annotations

import pytest

from kg.exceptions import (
    AccessDeniedError,
    CrawlerError,
    MaritimeKGError,
    QueryError,
    SchemaError,
)
from kg.exceptions import (
    ConnectionError as KGConnectionError,
)


@pytest.mark.unit
class TestExceptionHierarchy:
    """Test exception hierarchy and inheritance."""

    def test_all_exceptions_are_subclass_of_maritimekgerror(self):
        """All custom exceptions should inherit from MaritimeKGError."""
        assert issubclass(KGConnectionError, MaritimeKGError)
        assert issubclass(SchemaError, MaritimeKGError)
        assert issubclass(CrawlerError, MaritimeKGError)
        assert issubclass(AccessDeniedError, MaritimeKGError)
        assert issubclass(QueryError, MaritimeKGError)

    def test_all_exceptions_are_subclass_of_exception(self):
        """All exceptions should inherit from built-in Exception."""
        assert issubclass(MaritimeKGError, Exception)
        assert issubclass(KGConnectionError, Exception)
        assert issubclass(SchemaError, Exception)
        assert issubclass(CrawlerError, Exception)
        assert issubclass(AccessDeniedError, Exception)
        assert issubclass(QueryError, Exception)

    def test_maritimekgerror_can_be_raised_and_caught(self):
        """MaritimeKGError can be raised with a message and caught."""
        with pytest.raises(MaritimeKGError) as exc_info:
            raise MaritimeKGError("Base error occurred")
        assert str(exc_info.value) == "Base error occurred"

    def test_connectionerror_can_be_raised_with_message(self):
        """ConnectionError can be raised with a message."""
        with pytest.raises(KGConnectionError) as exc_info:
            raise KGConnectionError("Failed to connect to Neo4j")
        assert "Failed to connect to Neo4j" in str(exc_info.value)

    def test_schemaerror_can_be_raised_with_message(self):
        """SchemaError can be raised with a message."""
        with pytest.raises(SchemaError) as exc_info:
            raise SchemaError("Schema validation failed")
        assert "Schema validation failed" in str(exc_info.value)

    def test_crawlererror_can_be_raised_with_message(self):
        """CrawlerError can be raised with a message."""
        with pytest.raises(CrawlerError) as exc_info:
            raise CrawlerError("Data ingestion failed")
        assert "Data ingestion failed" in str(exc_info.value)

    def test_accessdeniederror_can_be_raised_with_message(self):
        """AccessDeniedError can be raised with a message."""
        with pytest.raises(AccessDeniedError) as exc_info:
            raise AccessDeniedError("User lacks permission")
        assert "User lacks permission" in str(exc_info.value)

    def test_queryerror_can_be_raised_with_message(self):
        """QueryError can be raised with a message."""
        with pytest.raises(QueryError) as exc_info:
            raise QueryError("Query generation failed")
        assert "Query generation failed" in str(exc_info.value)

    def test_catching_maritimekgerror_catches_all_subtypes(self):
        """Catching MaritimeKGError should catch all custom exceptions."""
        with pytest.raises(MaritimeKGError):
            raise KGConnectionError("Connection error")

        with pytest.raises(MaritimeKGError):
            raise SchemaError("Schema error")

        with pytest.raises(MaritimeKGError):
            raise CrawlerError("Crawler error")

        with pytest.raises(MaritimeKGError):
            raise AccessDeniedError("Access denied")

        with pytest.raises(MaritimeKGError):
            raise QueryError("Query error")

    def test_each_exception_has_correct_name(self):
        """Each exception class should have the correct __name__."""
        assert MaritimeKGError.__name__ == "KGError"
        assert KGConnectionError.__name__ == "ConnectionError"
        assert SchemaError.__name__ == "SchemaError"
        assert CrawlerError.__name__ == "CrawlerError"
        assert AccessDeniedError.__name__ == "AccessDeniedError"
        assert QueryError.__name__ == "QueryError"

    def test_exception_str_representation_works(self):
        """Exception string representation should contain the message."""
        error = MaritimeKGError("Test message")
        assert str(error) == "Test message"

        error = KGConnectionError("Connection failed")
        assert str(error) == "Connection failed"

    def test_exceptions_are_distinct_types(self):
        """Each exception should be a distinct type."""
        assert KGConnectionError is not SchemaError
        assert SchemaError is not CrawlerError
        assert CrawlerError is not AccessDeniedError
        assert AccessDeniedError is not QueryError
        assert QueryError is not MaritimeKGError


@pytest.mark.unit
class TestExceptionContext:
    """Test context fields on enriched exceptions."""

    def test_query_error_with_context(self):
        err = QueryError(
            "bad query", query="MATCH (n) RETURN n", parameters={"x": 1}, language="cypher"
        )
        assert str(err) == "bad query"
        assert err.query == "MATCH (n) RETURN n"
        assert err.parameters == {"x": 1}
        assert err.language == "cypher"

    def test_query_error_bare_still_works(self):
        err = QueryError("simple error")
        assert str(err) == "simple error"
        assert err.query == ""
        assert err.parameters == {}
        assert err.language == ""

    def test_crawler_error_with_context(self):
        err = CrawlerError(
            "fetch failed", url="https://example.com", crawler="kriso-papers", status_code=404
        )
        assert err.url == "https://example.com"
        assert err.crawler == "kriso-papers"
        assert err.status_code == 404

    def test_crawler_error_bare(self):
        err = CrawlerError("oops")
        assert err.url == ""
        assert err.status_code is None

    def test_connection_error_with_cause(self):
        original = OSError("connection refused")
        err = KGConnectionError("cannot connect", uri="bolt://localhost:7687", cause=original)
        assert err.uri == "bolt://localhost:7687"
        assert err.cause is original

    def test_access_denied_with_context(self):
        err = AccessDeniedError(
            "forbidden", user_id="USR-001", data_class_id="DC-SECRET", required_level=4
        )
        assert err.user_id == "USR-001"
        assert err.data_class_id == "DC-SECRET"
        assert err.required_level == 4

    def test_schema_error_with_context(self):
        err = SchemaError("constraint violation", entity="Vessel", constraint="vessel_mmsi")
        assert err.entity == "Vessel"
        assert err.constraint == "vessel_mmsi"

    def test_all_exceptions_still_subclass_base(self):
        for exc_cls in [
            KGConnectionError,
            SchemaError,
            CrawlerError,
            AccessDeniedError,
            QueryError,
        ]:
            err = exc_cls("test")
            assert isinstance(err, MaritimeKGError)
