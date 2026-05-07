"""Comprehensive SSRF validation tests for core.workflow.nodes.url_validator."""
from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from core.workflow.nodes.url_validator import SSRFError, validate_url


# ---------------------------------------------------------------------------
# 1. Valid URLs pass through
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_valid_http_url():
    result = validate_url("http://example.com")
    assert result == "http://example.com"


@pytest.mark.unit
def test_valid_https_url():
    result = validate_url("https://google.com")
    assert result == "https://google.com"


@pytest.mark.unit
def test_valid_https_with_path():
    url = "https://api.example.com/v1/data?foo=bar"
    assert validate_url(url) == url


@pytest.mark.unit
def test_valid_https_with_port():
    url = "https://example.com:8443/path"
    assert validate_url(url) == url


@pytest.mark.unit
def test_valid_http_with_port():
    url = "http://example.com:8080"
    assert validate_url(url) == url


# ---------------------------------------------------------------------------
# 2. Private IP ranges blocked (RFC 1918)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_private_ip_10_block():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://10.0.0.1")


@pytest.mark.unit
def test_private_ip_10_any_host():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://10.255.255.255")


@pytest.mark.unit
def test_private_ip_172_16():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://172.16.0.1")


@pytest.mark.unit
def test_private_ip_172_16_upper_bound():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://172.31.255.255")


@pytest.mark.unit
def test_private_ip_192_168():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://192.168.1.1")


@pytest.mark.unit
def test_private_ip_192_168_any():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("https://192.168.100.200")


# ---------------------------------------------------------------------------
# 3. Loopback blocked
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_loopback_127_0_0_1():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://127.0.0.1")


@pytest.mark.unit
def test_loopback_127_any():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://127.0.0.2")


@pytest.mark.unit
def test_loopback_localhost_hostname():
    with pytest.raises(SSRFError, match="Blocked hostname"):
        validate_url("http://localhost")


@pytest.mark.unit
def test_loopback_localhost_with_port():
    with pytest.raises(SSRFError, match="Blocked hostname"):
        validate_url("http://localhost:8080/api")


@pytest.mark.unit
def test_loopback_ipv6_short():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://[::1]")


@pytest.mark.unit
def test_loopback_ipv6_full():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://[0000:0000:0000:0000:0000:0000:0000:0001]")


# ---------------------------------------------------------------------------
# 4. Link-local blocked (169.254.0.0/16)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_link_local_169_254():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://169.254.1.1")


@pytest.mark.unit
def test_link_local_upper_range():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://169.254.255.255")


@pytest.mark.unit
def test_link_local_ipv6_fe80():
    # IPv6 link-local — parsed as hostname, ipaddress.ip_address handles bracket-stripped form
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://[fe80::1]")


# ---------------------------------------------------------------------------
# 5. Cloud metadata endpoints blocked
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_aws_metadata_ip():
    with pytest.raises(SSRFError, match="Blocked"):
        validate_url("http://169.254.169.254/latest/meta-data")


@pytest.mark.unit
def test_aws_metadata_path():
    with pytest.raises(SSRFError, match="Blocked"):
        validate_url("https://169.254.169.254/latest/meta-data/iam/security-credentials/")


@pytest.mark.unit
def test_cloud_metadata_hostname_string():
    # 169.254.169.254 appears in _BLOCKED_HOSTNAMES as string — direct hostname check
    with pytest.raises(SSRFError):
        validate_url("http://169.254.169.254")


# ---------------------------------------------------------------------------
# 6. Internal hostnames blocked (.internal, .local, .svc.cluster.local)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_internal_suffix():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("http://service.internal")


@pytest.mark.unit
def test_internal_suffix_subdomain():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("http://api.corp.internal")


@pytest.mark.unit
def test_local_suffix():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("http://myservice.local")


@pytest.mark.unit
def test_local_suffix_nested():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("http://db.infra.local/query")


@pytest.mark.unit
def test_svc_cluster_local_suffix():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("http://kubernetes.default.svc.cluster.local")


@pytest.mark.unit
def test_svc_cluster_local_with_namespace():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("http://my-service.default.svc.cluster.local:8080")


@pytest.mark.unit
def test_pod_cluster_local_suffix():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("http://10-0-0-5.default.pod.cluster.local")


# ---------------------------------------------------------------------------
# 7. Specific blocked hosts
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_metadata_google_internal_hostname():
    with pytest.raises(SSRFError, match="Blocked hostname|Blocked internal hostname"):
        validate_url("http://metadata.google.internal")


@pytest.mark.unit
def test_metadata_google_internal_with_path():
    with pytest.raises(SSRFError, match="Blocked hostname|Blocked internal hostname"):
        validate_url("http://metadata.google.internal/computeMetadata/v1/")


@pytest.mark.unit
def test_kubernetes_default_svc():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("http://kubernetes.default.svc.cluster.local")


@pytest.mark.unit
def test_kube_apiserver_typical():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("https://kubernetes.default.svc.cluster.local:443")


# ---------------------------------------------------------------------------
# 8. Scheme restriction — ftp, file, gopher blocked
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_ftp_scheme_blocked():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("ftp://example.com/file.txt")


@pytest.mark.unit
def test_file_scheme_blocked():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("file:///etc/passwd")


@pytest.mark.unit
def test_gopher_scheme_blocked():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("gopher://example.com:70/")


@pytest.mark.unit
def test_dict_scheme_blocked():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("dict://example.com:11111/")


@pytest.mark.unit
def test_ldap_scheme_blocked():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("ldap://example.com/dc=example,dc=com")


@pytest.mark.unit
def test_sftp_scheme_blocked():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("sftp://example.com/path")


@pytest.mark.unit
def test_data_scheme_blocked():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("data:text/plain;base64,SGVsbG8=")


# ---------------------------------------------------------------------------
# 9. Missing scheme raises error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_scheme_raises():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("example.com/path")


@pytest.mark.unit
def test_no_scheme_double_slash_only():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("//example.com/path")


@pytest.mark.unit
def test_no_scheme_bare_ip():
    with pytest.raises(SSRFError, match="Blocked URL scheme"):
        validate_url("192.168.1.1")


@pytest.mark.unit
def test_no_scheme_localhost():
    with pytest.raises((SSRFError, ValueError)):
        validate_url("localhost:8080")


# ---------------------------------------------------------------------------
# 10. Empty URL raises error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_empty_string_raises():
    with pytest.raises(ValueError, match="Empty URL"):
        validate_url("")


@pytest.mark.unit
def test_none_like_empty():
    # Empty string is the boundary; falsy value
    with pytest.raises(ValueError):
        validate_url("")


# ---------------------------------------------------------------------------
# Edge cases / additional hardening
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_url_returned_unchanged():
    url = "https://example.com/path?q=1#fragment"
    assert validate_url(url) == url


@pytest.mark.unit
def test_private_ip_as_hex_octet_not_bypassed():
    # 0x0a = 10, standard string representation — Python's ipaddress handles canonical form
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://10.1.2.3")


@pytest.mark.unit
def test_ipv6_private_fc00():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://[fc00::1]")


@pytest.mark.unit
def test_ipv6_private_fd00():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://[fd00::1]")


@pytest.mark.unit
def test_zero_network_blocked():
    with pytest.raises(SSRFError, match="Blocked internal IP"):
        validate_url("http://0.0.0.1")


@pytest.mark.unit
def test_hostname_dns_resolves_to_private_ip_is_blocked():
    """When a public-looking hostname resolves to a private IP it must be blocked."""
    fake_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0))
    ]
    with patch("core.workflow.nodes.url_validator.socket.getaddrinfo", return_value=fake_addrinfo):
        with pytest.raises(SSRFError, match="Blocked internal IP"):
            validate_url("http://evil.example.com")


@pytest.mark.unit
def test_hostname_dns_resolves_to_loopback_is_blocked():
    fake_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))
    ]
    with patch("core.workflow.nodes.url_validator.socket.getaddrinfo", return_value=fake_addrinfo):
        with pytest.raises(SSRFError, match="Blocked internal IP"):
            validate_url("http://suspicious.example.com")


@pytest.mark.unit
def test_dns_resolution_failure_does_not_raise():
    """If DNS resolution fails, validate_url should not raise (httpx handles it)."""
    with patch(
        "core.workflow.nodes.url_validator.socket.getaddrinfo",
        side_effect=socket.gaierror("Name or service not known"),
    ):
        # Should pass through (DNS failure → let caller handle)
        result = validate_url("http://nonexistent.example.com")
        assert result == "http://nonexistent.example.com"


@pytest.mark.unit
def test_uppercase_localhost_blocked():
    """Hostname check is case-insensitive."""
    with pytest.raises(SSRFError, match="Blocked hostname"):
        validate_url("http://LOCALHOST/admin")


@pytest.mark.unit
def test_mixed_case_internal_suffix():
    with pytest.raises(SSRFError, match="Blocked internal hostname"):
        validate_url("http://Service.INTERNAL/api")


@pytest.mark.unit
def test_link_local_metadata_full_path():
    with pytest.raises(SSRFError, match="Blocked internal IP|Blocked hostname"):
        validate_url("http://169.254.169.254/latest/meta-data/hostname")


@pytest.mark.unit
def test_ssrf_error_is_value_error_subclass():
    """SSRFError must be a subclass of ValueError for catch-all compatibility."""
    assert issubclass(SSRFError, ValueError)


@pytest.mark.unit
def test_ssrf_error_can_be_caught_as_value_error():
    with pytest.raises(ValueError):
        validate_url("http://127.0.0.1")
