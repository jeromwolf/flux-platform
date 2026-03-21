"""IMSP API error code registry.

Central registry mapping error codes to their HTTP status, title, and severity.
Only Y1-relevant codes are included initially.
"""
from __future__ import annotations

from kg.api.errors import ErrorCodeInfo

# Error code registry organized by namespace
ERROR_CODES: dict[str, ErrorCodeInfo] = {
    # AUTH — Authentication & Authorization
    "AUTH-1001": ErrorCodeInfo("AUTH-1001", 401, "Token Expired", "INFO"),
    "AUTH-1002": ErrorCodeInfo("AUTH-1002", 401, "Invalid Token", "INFO"),
    "AUTH-1003": ErrorCodeInfo("AUTH-1003", 403, "Access Denied", "WARN"),
    "AUTH-1004": ErrorCodeInfo("AUTH-1004", 401, "Missing Credentials", "INFO"),
    "AUTH-1005": ErrorCodeInfo("AUTH-1005", 401, "API Key Missing", "INFO"),
    "AUTH-1006": ErrorCodeInfo("AUTH-1006", 401, "Invalid API Key", "INFO"),
    "AUTH-1007": ErrorCodeInfo("AUTH-1007", 403, "Insufficient Role", "WARN"),
    # KG — Knowledge Graph
    "KG-2001": ErrorCodeInfo("KG-2001", 400, "Cypher Syntax Error", "WARN"),
    "KG-2002": ErrorCodeInfo("KG-2002", 400, "Forbidden Cypher Clause", "WARN"),
    "KG-2003": ErrorCodeInfo("KG-2003", 404, "Node Not Found", "INFO"),
    "KG-2004": ErrorCodeInfo("KG-2004", 400, "Schema Validation Error", "WARN"),
    "KG-2005": ErrorCodeInfo("KG-2005", 400, "Invalid Label", "WARN"),
    "KG-2006": ErrorCodeInfo("KG-2006", 400, "Constraint Violation", "WARN"),
    "KG-2007": ErrorCodeInfo("KG-2007", 503, "Database Unavailable", "FATAL"),
    # ETL — Data Pipeline
    "ETL-3001": ErrorCodeInfo("ETL-3001", 404, "Pipeline Not Found", "INFO"),
    "ETL-3002": ErrorCodeInfo("ETL-3002", 400, "Invalid Pipeline Config", "WARN"),
    "ETL-3003": ErrorCodeInfo("ETL-3003", 500, "Crawler Execution Error", "ERROR"),
    "ETL-3004": ErrorCodeInfo("ETL-3004", 400, "Transform Error", "WARN"),
    "ETL-3005": ErrorCodeInfo("ETL-3005", 500, "Load Error", "ERROR"),
    # NLP — Natural Language Processing
    "NLP-4001": ErrorCodeInfo("NLP-4001", 400, "Parse Error", "WARN"),
    "NLP-4002": ErrorCodeInfo("NLP-4002", 400, "Entity Resolution Failed", "WARN"),
    "NLP-4003": ErrorCodeInfo("NLP-4003", 400, "Unsupported Language", "INFO"),
    # API — General API Errors
    "API-5001": ErrorCodeInfo("API-5001", 422, "Validation Error", "INFO"),
    "API-5002": ErrorCodeInfo("API-5002", 429, "Rate Limit Exceeded", "WARN"),
    "API-5003": ErrorCodeInfo("API-5003", 404, "Endpoint Not Found", "INFO"),
    "API-5004": ErrorCodeInfo("API-5004", 405, "Method Not Allowed", "INFO"),
    "API-5005": ErrorCodeInfo("API-5005", 415, "Unsupported Media Type", "INFO"),
    # SYS — System
    "SYS-9001": ErrorCodeInfo("SYS-9001", 503, "Service Unavailable", "FATAL"),
    "SYS-9002": ErrorCodeInfo("SYS-9002", 500, "Configuration Error", "FATAL"),
    "SYS-9999": ErrorCodeInfo("SYS-9999", 500, "Internal Server Error", "FATAL"),
}


def get_error_info(code: str) -> ErrorCodeInfo | None:
    """Look up error metadata by code.

    Args:
        code: Error code string (e.g. "AUTH-1001").

    Returns:
        ErrorCodeInfo if found, None otherwise.
    """
    return ERROR_CODES.get(code)
