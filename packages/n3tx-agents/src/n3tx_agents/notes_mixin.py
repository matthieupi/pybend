"""Native model notes over Thread records.

Import and register this mixin before declaring ``__notes__`` models. Routed
calls use native trusted actor caller metadata; HTTP uses named user injection.
Notes enforces parent and action permissions, then native Thread owner/admin
policy controls record access. Scope is metadata, not an access grant.
First-note creation is not concurrency-safe or multi-write atomic."""

from typing import ClassVar

from n3tx_actors.tx import TX
from n3tx_core.authorize import AccessContext, DefaultResolver
from n3tx_core.authorize.errors import AccessDenied
from n3tx_core.models.ref import Ref, public_id_url
from n3tx_core.utils.decorators import expose_route, exposed_method_info
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.erroring import MethodError

from .thread import Thread


def _content(content: str) -> tuple[str, str]:
    """Validate bounded text or normalize a native HTTP(S) entity reference."""
    # 0. Do not stringify live entities, dictionaries, tokens or arbitrary data.
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Note content must be a nonempty string")
    if len(content) > 16000:
        raise MethodError("Note content exceeds 16000 characters", 413)
    # 1. Use native Ref validation for resource content.
    if content.lstrip().lower().startswith(("http:", "https:")):
        return Ref.url(content), "resource"
    return content, "text"


def _owner(owner, user: dict, action: str):
    """Reload the owner and enforce source and exposed-method permissions."""
    # 0. Read the owning record through ordinary native storage.
    cls = type(owner)
    saved = cls.get(owner.id)
    # 1. Evaluate the owning model's actual native read/update policy.
    if saved is None:
        raise MethodError("Notes owning record is unavailable", 404)
    resolver = DefaultResolver()
    method_name = "NOTE" if action == "update" else "read_notes"
    exposed = exposed_method_info(cls, method_name)
    method_rule = exposed.endpoint.get("access") if exposed else None
    try:
        resolver.authorize(AccessContext(
            user=user, action=action, model_class=cls, resource=saved,
        ))
        # 2. Native decorator access takes precedence over model action policy.
        ctx = AccessContext(
            user=user, action=method_name, model_class=cls, resource=saved,
        )
        if method_rule is None:
            resolver.authorize(ctx)
        elif not method_rule.evaluate(ctx):
            raise MethodError("Notes access denied", 403)
    except AccessDenied:
        raise MethodError("Notes access denied", 403) from None
    return saved


def _notes_thread(owner) -> Thread:
    """Load the saved notes reference through ordinary native storage."""
    # 0. The typed notes field supplies the Thread identity.
    thread = Thread.get(Ref.id(owner.notes))
    if thread is None:
        raise MethodError("Notes Thread is unavailable", 404)
    return thread


class NotesMixin:
    """Add lazy native note storage and explicit NOTE/read_notes actions.

    ProtoModel's registered-mixin injection prepends this plain mixin before
    Pydantic collects inherited type hints. Validate model_fields/schema/storage
    on the installed revision before enabling application opt-ins."""

    notes: Ref[Thread] | None = None
    __notes__: ClassVar[bool] = True

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs) -> None:
        """Preserve inherited protected fields and protect the notes pointer."""
        # 0. Keep native subclass hooks and union every existing protection.
        super().__pydantic_init_subclass__(**kwargs)
        protected = {"notes"}
        for base in cls.__mro__:
            protected.update(base.__dict__.get("__protected_fields__", ()))
        cls.__protected_fields__ = protected

    @fullmethod
    async def handler(target, tx: TX) -> None:
        """Handle Notes actions and delegate other TXs through native MRO."""
        # 0. Preserve class/instance fullmethod binding for native delegation.
        if tx.name not in {"NOTE", "read_notes"}:
            await super(NotesMixin, target).handler(tx)
            return
        # 1. Resolve the actual owner; do not let data redirect an instance.
        try:
            user = tx.meta.get("user") or {}
            fields = (
                {"id", "content"} if tx.name == "NOTE"
                else {"id", "cursor", "limit"}
            )
            if type(tx.data) is not dict or not set(tx.data) <= fields:
                raise ValueError("Unsupported notes action arguments")
            entity_id = tx.data.get("id")
            if isinstance(target, type):
                if type(entity_id) is not int or entity_id <= 0:
                    raise ValueError("Class-addressed notes require an id")
                owner = target.get(entity_id)
                if owner is None:
                    raise MethodError("Notes owning record is unavailable", 404)
            else:
                owner = target
                if "id" in tx.data and (
                    type(entity_id) is not int or entity_id != owner.id
                ):
                    raise ValueError("Notes id conflicts with its target")
            if tx.name == "NOTE":
                result = owner._append_note(tx, user)
            else:
                owner = _owner(owner, user, "read")
                result = owner.read_notes(
                    cursor=tx.data["cursor"], limit=tx.data["limit"], user=user,
                )
            response = tx.reply(data=result)
        except Exception as error:
            response = tx.exception(error)
        # 2. Send once; a failed response send must not emit another response.
        await target.send(response)

    @expose_route("/NOTE", methods=["POST"])
    def NOTE(self, content: str, user: dict = None) -> dict:
        """Append using the native named HTTP caller and a server envelope."""
        # 0. Direct HTTP has no incoming actor TX; never invent caller metadata.
        tx = TX(
            "NOTE", f"users/{(user or {}).get('user_id')}", self.addr,
            data={"content": content},
        )
        return self._append_note(tx, user)

    def _append_note(self, tx: TX, user: dict) -> dict:
        """Authorize owner update and record a sanitized original NOTE snapshot.

        Lazy Thread creation and owner linking are separate native writes. A
        failure may leave an empty/unlinked Thread; no automatic cleanup or
        first-note race prevention is performed."""
        # 0. Validate the envelope and current owning-record update permission.
        user = user or {}
        if (
            not isinstance(tx, TX) or tx.name != "NOTE"
            or type(tx.data) is not dict
            or not set(tx.data) <= {"id", "content"}
        ):
            raise ValueError("A native NOTE content envelope is required")
        if "id" in tx.data and (
            type(tx.data["id"]) is not int or tx.data["id"] != self.id
        ):
            raise ValueError("NOTE id conflicts with its owner")
        content, _kind = _content(tx.data.get("content"))
        saved = _owner(self, user, "update")
        # 1. Link one lazy owner-scoped Thread through the native owner update.
        if saved.notes is None:
            thread = Thread.create(Thread(
                user_owner=user.get("user_id"),
                scope=public_id_url(saved.id, target_cls=type(saved)),
            ))
            if thread is None:
                raise MethodError("Notes Thread creation failed", 409)
            saved = saved.update({
                "notes": public_id_url(thread.id, target_cls=Thread),
            })
            if saved is None:
                raise MethodError("Notes reference update failed", 409)
        # 2. Keep original identity/source/time; retain no untrusted metadata.
        snapshot = TX(
            name="NOTE", source=tx.source, target=tx.target,
            data={"content": content}, meta={},
            timestamp=tx.timestamp, uuid=tx.uuid,
        )
        # 3. Native Thread owner/admin policy controls record persistence.
        thread = _notes_thread(saved)
        try:
            record = thread.append(snapshot, user=user)
        except AccessDenied:
            raise MethodError("Notes access denied", 403) from None
        self.notes = saved.notes
        return {"id": record.id, "thread_id": thread.id}

    @expose_route("/read_notes", methods=["POST"])
    def read_notes(self, cursor: str, limit: int, user: dict = None) -> dict:
        """Read a safe notes page using native caller and owner/admin policy."""
        # 0. Authorize even empty notes and validate the native paging inputs.
        user = user or {}
        if not isinstance(cursor, str) or type(limit) is not int:
            raise ValueError("Notes require a string cursor and integer limit")
        if not 1 <= limit <= 50:
            raise ValueError("Notes limit must be between 1 and 50")
        saved = _owner(self, user, "read")
        if saved.notes is None:
            if cursor:
                raise ValueError("An empty notes Thread has no cursor")
            return {"data": [], "cursor": "", "has_more": False}
        # 1. Parent permission does not grant access to another owner's Thread.
        thread = _notes_thread(saved)
        try:
            page = thread.records(user=user, cursor=cursor, limit=limit)
        except AccessDenied:
            raise MethodError("Notes access denied", 403) from None
        # 2. Project only validated NOTE content and server provenance.
        data = []
        for record in page["data"]:
            if record.name != "NOTE":
                continue
            payload = record.data["payload"]
            if not isinstance(payload, dict) or set(payload) != {"content"}:
                continue
            try:
                content, kind = _content(payload["content"])
            except (TypeError, ValueError, MethodError):
                continue
            data.append({
                "id": record.id, "kind": kind, "content": content,
                "recorded_at": record.recorded_at.isoformat(),
                "recorded_by": record.recorded_by,
            })
        return {
            "data": data, "cursor": page["cursor"],
            "has_more": page["has_more"],
        }


# Changelog (Python has no native block-comment syntax).
# - 2026-10-31: Read NOTE content from the native payload container.
# - 2026-10-31: Add owner-bound immutable notes and trusted NOTE dispatch.
#   - Honor native decorator policy precedence and sanitize access denials.
#   - Permit omitted tool caller arguments only through verified TX bindings.
#   - Delegate Thread access to native source policy without notes ACL grants.
#   - Use native actor callers and Thread owner/admin access without bindings.
