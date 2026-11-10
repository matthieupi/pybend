"""Typed Note content and explicit NoteMixin host actions.

API: Note validates text; NoteMixin exposes NOTE/NOTES on composed hosts.
TTX owns canonical storage and kind registration; ingress owns authorization.
Import from n3tx_threads and compose NoteMixin before the host ActorModel.
The class example uses n3tx_actors.models.actor_model.ActorModel."""

from __future__ import annotations

from pydantic import Field, field_validator

from n3tx_core.utils.decorators import expose_route

from .ttx import TTX


class Note(TTX, auto_register=False):
    """Note — typed NOTE envelope with strictly textual desc content.

    API Surface:
        tx() / ttx() — Inherited transport/storage conversion
        create() / get() / save() — Canonical typed persistence
        list() / update() / delete() — Exact-kind native-shaped projections

    The split: desc is authoritative and becomes data["desc"]. Numeric-looking
    text stays text; nonblank validation preserves the supplied whitespace.

    Usage:
        note = Note(source="users/1", target="emails/42", desc="123")
        assert note.tx().data == {"desc": "123"}"""

    name: str = "NOTE"
    desc: str = Field(strict=True)

    @field_validator("desc")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        """Reject blank note content without trimming valid text."""
        if not value.strip():
            raise ValueError("Note description must not be blank")
        return value


class NoteMixin:
    """NoteMixin — explicit NOTE/NOTES capability for ActorModels.

    API Surface:
        NOTE(message, user) — Persist and return a Note targeting self.addr
        NOTES(user)         — Return all Notes targeting self.addr

    The split: host policy controls access; Note owns typed content; canonical
    TTX owns persistence. No host fields, pointer or container are introduced.
    Inherit this mixin before the host ActorModel base; register host and TTX.
    No global __notes__ flag or actor handler is installed. Direct HTTP and
    ActorModel dispatch inject named user from trusted transport context.

    Authorization belongs to the configured ingress: HTTP uses native action
    policies; raw ActorModel dispatch lacks the same default-policy fallback.
    The mixin adds no authorization checks.
    Direct Python calls are trusted; no extra CRUD guard, saved-host check or
    fresh host reload occurs here. Calls create a fresh envelope with users/<id>
    attribution, or anonymous without a caller ID; original incoming TX
    source/time and execution-context capture are not propagated. Reads are
    direct, unbounded and unordered. No graph permissions or atomicity follow.

    Usage:
        class Email(NoteMixin, ActorModel):
            __tablename__ = "emails"
            __storable__ = True
            subject: str

        # After registering host/TTX storage and supplying a trusted caller:
        note = email.NOTE("Hello", user=caller)
        notes = email.NOTES(user=caller)"""

    @expose_route("/NOTE", methods=["POST"])
    def NOTE(self, message: str, user: dict | None = None) -> Note:
        """Persist at self.addr; the calling boundary owns authorization."""
        # 0. Derive identity from trusted caller context, never action data.
        user_id = (user or {}).get("user_id")
        source = f"users/{user_id}" if user_id is not None else "anonymous"
        # 1. Typed validation and canonical storage own note persistence.
        return Note.create(Note(
            source=source, target=self.addr,
            desc=message, user_owner=user_id,
        ))

    @expose_route("/NOTES", methods=["POST"])
    def NOTES(self, user: dict | None = None) -> list[Note]:
        """List self.addr Notes; authorization belongs to the calling boundary.

        user remains available for native caller injection compatibility."""
        # 0. Filter host target and projected Note kind in native storage.
        return Note.list(sql_filter=("target = ?", [self.addr]))


# Changelog (Python has no block-comment syntax).
# - 2026-11-10: Move Note and NoteMixin from ttx without behavior changes.
