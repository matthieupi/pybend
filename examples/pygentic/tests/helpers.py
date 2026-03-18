"""Test helpers for the Pygentic example."""


def auth_header(token: str) -> dict:
    return {'x-access-token': token}
