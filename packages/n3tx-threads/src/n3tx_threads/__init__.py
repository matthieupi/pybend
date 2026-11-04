"""TTX storage, its semantic Thread name and optional model notes.

Import before declaring __notes__ models to inject their NOTE/NOTES actions.
Applications register TTX storage explicitly. No separate Thread container or
automatic execution interception is installed."""

from n3tx_core.models.proto_model import register_mixin

from .mixin import ThreadedMixin
from .notes_mixin import NotesMixin
from .thread import Thread
from .ttx import TTX
# 0. Register the optional action capability before host model declarations.
register_mixin("__notes__", NotesMixin)

__all__ = ["TTX", "Thread", "NotesMixin", "ThreadedMixin"]


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Export only TTX; remove legacy mixin imports and registration.
#   Export the replacement entry helpers and register lean NOTE/NOTES actions.
#   Import the shared capability from the canonical mixin module.
#   Export the semantic Thread subclass without separate registration.
# - 2026-11-03: Export TTX instead of the removed TXRecord model.
# - 2026-11-02: Export neutral thread capabilities and register notes once.
