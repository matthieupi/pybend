# tests/helpers.py
"""Shared test helper functions (importable without triggering conftest import chain).

SD-4: Provides parse_href_id() to replace fragile string parsing everywhere.
"""

from urllib.parse import urlparse


def auth_header(token):
    """Return a dict with the x-access-token header for authenticated requests."""
    return {"x-access-token": token}


def parse_href_id(href):
    """Extract the trailing integer ID from an href URL.

    Examples:
        parse_href_id("http://localhost:5000/Product/1/Comment/3") -> 3
        parse_href_id("http://localhost:5000/users/5") -> 5
    """
    if isinstance(href, int):
        return href
    path = urlparse(str(href)).path.rstrip("/")
    return int(path.rsplit("/", 1)[-1])


def href_ends_with(href, suffix):
    """Check if href path ends with the given suffix (e.g. '/comments/3').

    More robust than `str(id) in str(href)` which is a substring match.
    """
    path = urlparse(str(href)).path.rstrip("/")
    return path.endswith(suffix)


def extract_items(response_data):
    """Extract the list of items from a response that may be a plain list
    or a paginated dict with 'data' key."""
    if isinstance(response_data, list):
        return response_data
    return response_data.get("data", [])
