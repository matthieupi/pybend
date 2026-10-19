"""Test helpers for the chat example."""


def auth_header(token: str) -> dict:
    return {"x-access-token": token}
