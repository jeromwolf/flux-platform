"""Unit tests for the RFC 7807 error handling framework."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from kg.api.errors import ErrorDetail, IMSPHTTPException, ProblemDetail, ErrorCodeInfo
from kg.api.error_codes import ERROR_CODES, get_error_info


@pytest.mark.unit
class TestProblemDetail:
    """Tests for ProblemDetail Pydantic model."""

    def test_default_values(self):
        pd = ProblemDetail()
        assert pd.type == "about:blank"
        assert pd.status == 500
        assert pd.errors == []

    def test_full_construction(self):
        pd = ProblemDetail(
            type="https://imsp.kriso.re.kr/errors/KG-2001",
            title="Cypher Syntax Error",
            status=400,
            detail="Missing RETURN clause",
            instance="/api/v1/query",
            traceId="abc-123",
        )
        assert pd.status == 400
        assert pd.title == "Cypher Syntax Error"

    def test_with_errors_list(self):
        pd = ProblemDetail(
            status=422,
            errors=[
                ErrorDetail(field="name", code="API-5001", message="required"),
                ErrorDetail(field="type", code="API-5001", message="invalid"),
            ],
        )
        assert len(pd.errors) == 2
        assert pd.errors[0].field == "name"

    def test_serialization(self):
        pd = ProblemDetail(type="test", title="Test", status=400, detail="bad")
        data = pd.model_dump()
        assert data["type"] == "test"
        assert data["status"] == 400
        assert isinstance(data["errors"], list)


@pytest.mark.unit
class TestErrorDetail:
    def test_creation(self):
        ed = ErrorDetail(field="name", code="API-5001", message="required")
        assert ed.field == "name"
        assert ed.code == "API-5001"

    def test_optional_field(self):
        ed = ErrorDetail(code="KG-2001", message="error")
        assert ed.field is None


@pytest.mark.unit
class TestErrorCodeInfo:
    def test_frozen(self):
        info = ErrorCodeInfo(code="AUTH-1001", http_status=401, title="Expired", severity="INFO")
        with pytest.raises(AttributeError):
            info.code = "other"  # type: ignore[misc]

    def test_fields(self):
        info = ErrorCodeInfo(code="KG-2001", http_status=400, title="Syntax Error", severity="WARN")
        assert info.http_status == 400
        assert info.severity == "WARN"


@pytest.mark.unit
class TestIMSPHTTPException:
    def test_creation(self):
        exc = IMSPHTTPException("KG-2001", status=400, detail="bad query")
        assert exc.error_code == "KG-2001"
        assert exc.status == 400
        assert exc.detail == "bad query"
        assert exc.context == {}

    def test_with_context(self):
        exc = IMSPHTTPException("ETL-3003", status=500, detail="fail", context={"crawler": "kma"})
        assert exc.context["crawler"] == "kma"

    def test_default_status_500(self):
        exc = IMSPHTTPException("SYS-9999")
        assert exc.status == 500

    def test_is_exception(self):
        exc = IMSPHTTPException("KG-2001", detail="test")
        assert isinstance(exc, Exception)


@pytest.mark.unit
class TestErrorCodeRegistry:
    def test_auth_codes_exist(self):
        assert "AUTH-1001" in ERROR_CODES
        assert "AUTH-1002" in ERROR_CODES

    def test_kg_codes_exist(self):
        assert "KG-2001" in ERROR_CODES
        assert "KG-2004" in ERROR_CODES

    def test_sys_codes_exist(self):
        assert "SYS-9999" in ERROR_CODES

    def test_get_error_info_found(self):
        info = get_error_info("AUTH-1001")
        assert info is not None
        assert info.http_status == 401
        assert info.title == "Token Expired"

    def test_get_error_info_not_found(self):
        info = get_error_info("NONEXISTENT-0000")
        assert info is None

    def test_all_codes_have_valid_status(self):
        for code, info in ERROR_CODES.items():
            assert 400 <= info.http_status <= 599, f"{code} has invalid status {info.http_status}"

    def test_all_codes_have_severity(self):
        valid_severities = {"FATAL", "ERROR", "WARN", "INFO"}
        for code, info in ERROR_CODES.items():
            assert info.severity in valid_severities, f"{code} has invalid severity {info.severity}"


@pytest.mark.unit
class TestKGErrorWithErrorCode:
    """Test that KGError now supports error_code attribute."""

    def test_kgerror_default_error_code(self):
        from kg.exceptions import KGError
        exc = KGError("test error")
        assert exc.error_code == ""

    def test_kgerror_with_error_code(self):
        from kg.exceptions import KGError
        exc = KGError("test", error_code="KG-2001")
        assert exc.error_code == "KG-2001"

    def test_subclass_preserves_error_code_default(self):
        from kg.exceptions import QueryError
        exc = QueryError("bad query", query="MATCH (n) RETRN n")
        assert exc.error_code == ""  # default from base

    def test_connection_error_still_works(self):
        from kg.exceptions import ConnectionError
        exc = ConnectionError("failed", uri="bolt://localhost:7687")
        assert exc.uri == "bolt://localhost:7687"
        assert str(exc) == "failed"
