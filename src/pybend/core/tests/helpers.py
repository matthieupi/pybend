# tests/helpers.py
"""Shared test helper functions (importable without triggering conftest import chain)."""


def auth_header(token):
    """Return a dict with the x-access-token header for authenticated requests."""
    return {"x-access-token": token}
