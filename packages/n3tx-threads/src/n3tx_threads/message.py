"""Message — validated textual content over canonical TTX storage.

API: Message inherits conversion and exact-kind storage from TTX; desc is
strict, nonblank text. Register only TTX, never a separate Message table.
Sending and receiving are explicit actions, not constructor side effects."""

from __future__ import annotations

from pydantic import Field, field_validator

from .ttx import TTX


class Message(TTX, auto_register=False):
    """MESSAGE envelope with a strict textual desc content field.

    API: inherited tx()/ttx()/value and typed persistence; desc validates text.
    Boundary: TTX owns storage, callers own authority and delivery. Valid
    whitespace is retained; no JSON-text parsing or automatic dispatch occurs.
    Usage: Message(source="users/1", target="users/2", desc="Hello")."""

    name: str = "MESSAGE"
    desc: str = Field(strict=True)

    @field_validator("desc")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        """Reject blank descriptions without trimming valid content."""
        if not value.strip():
            raise ValueError("Message description must not be blank")
        return value


# Changelog (Python has no block-comment syntax).
# - 2026-11-10: Declare Message content without delivery side effects.
