"""URL validation for SSRF protection.

Blocks requests to:
- Private IP ranges (RFC 1918): 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
- Loopback: 127.0.0.0/8, ::1
- Link-local: 169.254.0.0/16, fe80::/10
- Cloud metadata endpoints: 169.254.169.254
- Internal Docker/K8s DNS: *.internal, *.local, *.svc.cluster.local
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Blocked IP networks
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fd00::/8"),
]

# Blocked hostnames (substrings)
_BLOCKED_HOSTNAME_SUFFIXES = [
    ".internal",
    ".local",
    ".svc.cluster.local",
    ".pod.cluster.local",
    "metadata.google.internal",
]

_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "169.254.169.254",
}


class SSRFError(ValueError):
    """Raised when a URL targets a blocked internal resource."""
    pass


def validate_url(url: str) -> str:
    """Validate a URL against SSRF blocklist.

    Args:
        url: The URL to validate.

    Returns:
        The validated URL (unchanged).

    Raises:
        SSRFError: If the URL targets a blocked resource.
        ValueError: If the URL is malformed.
    """
    if not url:
        raise ValueError("Empty URL")

    parsed = urlparse(url)

    # Must have a scheme
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Blocked URL scheme: {parsed.scheme}. Only http/https allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"No hostname in URL: {url}")

    # Check blocked hostnames
    hostname_lower = hostname.lower()
    if hostname_lower in _BLOCKED_HOSTNAMES:
        raise SSRFError(f"Blocked hostname: {hostname}")

    for suffix in _BLOCKED_HOSTNAME_SUFFIXES:
        if hostname_lower.endswith(suffix):
            raise SSRFError(f"Blocked internal hostname: {hostname}")

    # Resolve hostname to IP and check against blocked networks
    try:
        # Try parsing as IP directly
        ip = ipaddress.ip_address(hostname)
        _check_ip(ip, hostname)
    except ValueError:
        # It's a hostname — resolve it
        try:
            resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for family, _, _, _, sockaddr in resolved_ips:
                ip = ipaddress.ip_address(sockaddr[0])
                _check_ip(ip, hostname)
        except socket.gaierror:
            # DNS resolution failed — let httpx handle it
            pass

    return url


def _check_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str) -> None:
    """Check if an IP is in a blocked network.

    Raises:
        SSRFError: If the IP is blocked.
    """
    for network in _BLOCKED_NETWORKS:
        if ip in network:
            raise SSRFError(
                f"Blocked internal IP: {ip} (hostname={hostname}, network={network})"
            )
