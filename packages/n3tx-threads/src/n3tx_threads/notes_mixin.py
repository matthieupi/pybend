"""Thin NOTE/NOTES actions over parent-authorized TTX storage.

Import the package before declaring __notes__ models. There is no persisted
notes field or separate container. Direct calls create a server envelope;
actor calls retain their incoming source, UUID and timestamp. Named HTTP
injection and actor metadata supply the caller, never action body fields."""

from dataclasses import replace
from typing import ClassVar

from n3tx_actors.tx import TX
from n3tx_core.authorize import DefaultResolver
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.erroring import MethodError

from .mixin import ThreadedMixin
from .ttx import TTX


def _message(value: str) -> str:
    """Validate bounded text before TTX interprets JSON or references."""
    # 0. Preserve whitespace in valid input without accepting empty notes.
    if not isinstance(value, str) or not value.strip():
        raise MethodError("Note message must be nonempty text", 400)
    if len(value) > 16000:
        raise MethodError("Note message exceeds 16000 characters", 413)
    return value


class NotesMixin(ThreadedMixin):
    """Expose raw note entries with the parent's read and update permissions.

    __notes__ injection prepends this mixin before ActorModel. No per-author
    grant or separate Notes policy is added. Raw text uses TTX normalization:
    '123' becomes a number and 'null' becomes None. Native reference URLs
    remain live pointers."""

    __notes__: ClassVar[bool] = True

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs) -> None:
        """Bind generated action policies to the host's native CRUD policies."""
        # 0. Preserve native hooks and unrelated permissions on each host.
        super().__pydantic_init_subclass__(**kwargs)
        resolver = DefaultResolver()
        cls.__access__ = {
            **(getattr(cls, "__access__", None) or {}),
            "NOTE": resolver.resolve_rule(cls, "update"),
            "NOTES": resolver.resolve_rule(cls, "read"),
        }

    @expose_route("/NOTE", methods=["POST"])
    def NOTE(self, message: str, user: dict = None) -> TTX:
        """Append raw note text using a server-created envelope and caller."""
        # 0. Source is a server-derived address, never an authorization grant.
        ident = (user or {}).get("user_id")
        source = f"users/{ident}" if ident is not None else "anonymous"
        return self._append_entry(
            TX("NOTE", source, self.addr, data=_message(message)), user=user,
        )

    @expose_route("/NOTES", methods=["POST"])
    def NOTES(self, user: dict = None) -> list[TTX]:
        """Return all parent-readable NOTE records in timestamp order."""
        # 0. The shared reader owns authorization, filtering and ordering.
        return self._entries(name="NOTE", user=user)

    @fullmethod
    async def handler(target, tx: TX) -> None:
        """Preserve NOTE envelopes and trusted callers on actor routes."""
        # 0. Other actions retain their native behavior without note capture.
        if tx.name not in {"NOTE", "NOTES"}:
            await super(NotesMixin, target).handler(tx)
            return
        try:
            # 1. Resolve the real host without accepting identity overrides.
            allowed = {"id", "message"} if tx.name == "NOTE" else {"id"}
            if type(tx.data) is not dict or not set(tx.data) <= allowed:
                raise ValueError("Unsupported notes action arguments")
            ident = tx.data.get("id")
            if isinstance(target, type):
                if type(ident) is not int or ident <= 0:
                    raise ValueError("Class-addressed notes require an id")
                owner = target.get(ident)
                if owner is None:
                    raise MethodError("Entry owner is unavailable", 404)
            else:
                owner = target
                if "id" in tx.data and (
                    type(ident) is not int or ident != owner.id
                ):
                    raise ValueError("Notes id conflicts with its target")
            # 2. Only NOTE uses the original TX; both actions use its caller.
            user = tx.meta.get("user")
            if tx.name == "NOTE":
                snapshot = replace(tx, data=_message(tx.data["message"]))
                result = owner._append_entry(snapshot, user=user).model_dump()
            else:
                result = [row.model_dump() for row in owner.NOTES(user=user)]
            response = tx.reply(data=result)
        except Exception as error:
            response = tx.exception(error)
        # 3. A send failure must not trigger a second correlated response.
        await target.send(response)


# Changelog (Python has no native block-comment syntax).
# - 2026-11-04: Replace Thread-backed notes with NOTE/NOTES TTX wrappers;
#   retain raw text, trusted callers and parent read/update permissions only.
#   Return native HTTP 400 errors for invalid or blank note messages.
#   Import the shared capability from mixin.py.
# - 2026-11-02: Move native notes into the standalone threads package.
# - 2026-10-31: Read NOTE content from the native payload container.
# - 2026-10-31: Add owner-bound immutable notes and trusted NOTE dispatch.
#   - Honor native decorator policy precedence and sanitize access denials.
#   - Permit omitted tool caller arguments only through verified TX bindings.
#   - Delegate Thread access to native source policy without notes ACL grants.
#   - Use native actor callers and Thread owner/admin access without bindings.
