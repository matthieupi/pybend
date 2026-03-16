"""Test helpers for the grant-watching example."""


def auth_header(token: str) -> dict:
    return {"x-access-token": token}
