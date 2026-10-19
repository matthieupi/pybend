"""
Test plan for SSRF protection
==============================

SSRF VALIDATION
  - test_public_url_allowed
  - test_private_ip_10_x_blocked
  - test_private_ip_172_16_31_blocked
  - test_private_ip_192_168_blocked
  - test_loopback_127_0_0_1_blocked
  - test_loopback_localhost_blocked
  - test_ipv6_loopback_blocked
  - test_link_local_169_254_blocked
  - test_hostname_resolving_to_private_ip_blocked
  - test_valid_external_urls_pass_through

URL VALIDATION
  - test_invalid_scheme_rejected
  - test_missing_hostname_rejected
"""

import pytest
from utils.url_validator import validate_url, is_safe_url, is_private_ip


class TestSSRFProtection:
    """SSRF protection blocks requests to private/internal addresses."""

    def test_public_url_allowed(self):
        url = "https://www.example.com/grants"
        assert is_safe_url(url) is True
        assert validate_url(url) == url

    def test_private_ip_10_x_blocked(self):
        url = "http://10.0.0.1/admin"
        assert is_safe_url(url) is False
        with pytest.raises(ValueError, match="private"):
            validate_url(url)

    def test_private_ip_172_16_31_blocked(self):
        url = "http://172.16.0.1/internal"
        assert is_safe_url(url) is False
        with pytest.raises(ValueError):
            validate_url(url)

    def test_private_ip_192_168_blocked(self):
        url = "http://192.168.1.1/router"
        assert is_safe_url(url) is False
        with pytest.raises(ValueError):
            validate_url(url)

    def test_loopback_127_0_0_1_blocked(self):
        url = "http://127.0.0.1:8000/admin"
        assert is_safe_url(url) is False
        with pytest.raises(ValueError):
            validate_url(url)

    def test_loopback_localhost_blocked(self):
        url = "http://localhost:5000/admin"
        assert is_safe_url(url) is False
        with pytest.raises(ValueError):
            validate_url(url)

    def test_ipv6_loopback_blocked(self):
        url = "http://[::1]/admin"
        assert is_safe_url(url) is False
        with pytest.raises(ValueError):
            validate_url(url)

    def test_link_local_169_254_blocked(self):
        url = "http://169.254.169.254/metadata"
        assert is_safe_url(url) is False
        with pytest.raises(ValueError):
            validate_url(url)

    def test_hostname_resolving_to_private_ip_blocked(self):
        # This test depends on DNS resolution
        # localhost resolves to 127.0.0.1, which is private
        url = "http://localhost/admin"
        assert is_safe_url(url) is False

    def test_valid_external_urls_pass_through(self):
        valid_urls = [
            "https://www.nsf.gov/funding",
            "https://grants.nih.gov/",
            "https://www.energy.gov/grants",
            "https://www.google.com",
        ]
        for url in valid_urls:
            assert is_safe_url(url) is True
            assert validate_url(url) == url


class TestIPValidation:
    """IP address validation helper."""

    def test_private_ip_ranges_detected(self):
        private_ips = [
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.0.1",
            "192.168.255.255",
            "127.0.0.1",
            "127.255.255.255",
            "169.254.0.1",
        ]
        for ip in private_ips:
            assert is_private_ip(ip) is True, f"{ip} should be detected as private"

    def test_public_ip_not_flagged(self):
        public_ips = [
            "8.8.8.8",
            "1.1.1.1",
            "93.184.216.34",  # example.com
        ]
        for ip in public_ips:
            assert is_private_ip(ip) is False, f"{ip} should not be flagged as private"


class TestURLValidation:
    """URL format validation."""

    def test_invalid_scheme_rejected(self):
        url = "ftp://example.com/file"
        assert is_safe_url(url) is False

    def test_missing_hostname_rejected(self):
        url = "http://"
        assert is_safe_url(url) is False

    def test_url_with_port_to_internal_service(self):
        url = "http://127.0.0.1:8080/admin"
        assert is_safe_url(url) is False

    def test_url_without_scheme_rejected(self):
        url = "www.example.com/grants"
        assert is_safe_url(url) is False

    def test_file_scheme_rejected(self):
        url = "file:///etc/passwd"
        assert is_safe_url(url) is False
