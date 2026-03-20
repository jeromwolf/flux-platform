"""Exception hierarchy for the Maritime KG platform.

All exceptions inherit from KGError. Each exception carries
optional keyword-only context fields for structured error reporting.
"""

from __future__ import annotations


class KGError(Exception):
    """Base exception for all knowledge-graph errors."""


# Backward compatibility alias
MaritimeKGError = KGError


class ConnectionError(KGError):
    """Failed to connect to Neo4j or other external service."""

    def __init__(
        self,
        message: str = "",
        *,
        uri: str = "",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.uri = uri
        self.cause = cause


class SchemaError(KGError):
    """Schema initialization or validation error."""

    def __init__(
        self,
        message: str = "",
        *,
        entity: str = "",
        constraint: str = "",
    ) -> None:
        super().__init__(message)
        self.entity = entity
        self.constraint = constraint


class CrawlerError(KGError):
    """Error during data crawling or ingestion."""

    def __init__(
        self,
        message: str = "",
        *,
        url: str = "",
        crawler: str = "",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.crawler = crawler
        self.status_code = status_code


class AccessDeniedError(KGError):
    """RBAC access control denied."""

    def __init__(
        self,
        message: str = "",
        *,
        user_id: str = "",
        data_class_id: str = "",
        required_level: int = 0,
    ) -> None:
        super().__init__(message)
        self.user_id = user_id
        self.data_class_id = data_class_id
        self.required_level = required_level


class QueryError(KGError):
    """Error generating or executing a query."""

    def __init__(
        self,
        message: str = "",
        *,
        query: str = "",
        parameters: dict[str, object] | None = None,
        language: str = "",
    ) -> None:
        super().__init__(message)
        self.query = query
        self.parameters = parameters or {}
        self.language = language
