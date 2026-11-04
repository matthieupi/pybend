"""Semantic Thread name for TTX-backed conversations and interaction roots.

Register TTX only. This subclass shares its fields, storage and operations;
it does not create a container table, actor registration or transport API.
Persisted references remain canonical TTX references."""

from .ttx import TTX


class Thread(TTX, auto_register=False):
    """Name a TTX as a thread without adding fields or overriding behavior."""


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Add a semantic Thread subclass without actor auto-registration.
