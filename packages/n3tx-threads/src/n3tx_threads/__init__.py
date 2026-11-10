"""Canonical TTX storage and explicit typed transaction capabilities.

Exports: TTX owns storage; Note, Message and Thread are typed views; NoteMixin
supplies NOTE/NOTES; ThreadedMixin declares receiver/list action stubs.
Import registers only the default schema
pipeline's ttx stage. Applications register storage and compose hosts directly.
no mixin flags, actors, tables or HTTP aliases are registered here."""

from .ttx import TTX
from .note import Note, NoteMixin
from .thread import Thread
from .message import Message
from .mixin import ThreadedMixin

# 0. Register the schema stage without installing runtime capabilities.
from . import schema_ext as _schema_ext  # noqa: F401

__all__ = ["TTX", "Note", "Message", "Thread", "NoteMixin", "ThreadedMixin"]


# Changelog (Python has no block-comment syntax).
# - 2026-11-10: Export Message and contract-only ThreadedMixin explicitly.
# - 2026-11-10: Import relocated types before registering the schema stage.
# - 2026-11-09: Export explicit typed capabilities and register only the schema
#   extension; remove obsolete module imports and global notes injection.
# - 2026-11-04: Export only TTX; remove legacy mixin imports and registration.
#   Export the replacement entry helpers and register lean NOTE/NOTES actions.
#   Import the shared capability from the canonical mixin module.
#   Export the semantic Thread subclass without separate registration.
# - 2026-11-03: Export TTX instead of the removed TXRecord model.
# - 2026-11-02: Export neutral thread capabilities and register notes once.
