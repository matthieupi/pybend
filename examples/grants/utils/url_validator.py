"""
URL validation with SSRF protection.

Prevents requests to private IP addresses, loopback, and link-local addresses
to mitigate Server-Side Request Forgery (SSRF) attacks.
"""

import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional


# Private IP ranges (RFC 1918)
PRIVATE_IP_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),  # Loopback
    ipaddress.ip_network('169.254.0.0/16'),  # Link-local
    ipaddress.ip_network('::1/128'),  # IPv6 loopback
    ipaddress.ip_network('fe80::/10'),  # IPv6 link-local
]


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is private, loopback, or link-local."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in PRIVATE_IP_RANGES)
    except ValueError:
        return False


def resolve_hostname(hostname: str) -> Optional[str]:
    """Resolve a hostname to an IP address. Returns None if resolution fails."""
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


def is_safe_url(url: str) -> bool:
    """
    Check if a URL is safe (not pointing to private/internal addresses).

    Returns True if the URL is safe, False otherwise.
    """
    try:
        parsed = urlparse(url)

        # Must have http or https scheme
        if parsed.scheme not in ('http', 'https'):
            return False

        # Extract hostname
        hostname = parsed.hostname
        if not hostname:
            return False

        # Check if hostname is an IP address
        try:
            ip = ipaddress.ip_address(hostname)
            if is_private_ip(str(ip)):
                return False
        except ValueError:
            # Not an IP address — it's a hostname
            # Resolve to IP and check
            resolved_ip = resolve_hostname(hostname)
            if resolved_ip and is_private_ip(resolved_ip):
                return False

        return True

    except Exception:
        return False


def validate_url(url: str) -> str:
    """
    Validate a URL for SSRF protection.

    Raises ValueError if the URL points to private/internal addresses.
    Returns the original URL if safe.
    """
    if not is_safe_url(url):
        raise ValueError(
            "URL points to a private, loopback, or link-local address. "
            "This is not allowed for security reasons."
        )
    return url
