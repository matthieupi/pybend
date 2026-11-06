"""Opt-in recording of native execution TXs using ordinary Thread storage.

Only declared root actions create manifests. Nested participating actors share
the current manifest; unthreaded actors are not observed. Caller metadata is an
execution input, never a persisted credential or a grant from Thread identity.
Persistence is not atomic with business effects and does not provide replay."""

from contextvars import ContextVar
from dataclasses import replace
from typing import ClassVar

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.tx import TX
from n3tx_core.models.ref import local_ref_id, public_id_url
from n3tx_core.utils.descriptors import fullmethod

from .thread import Thread


current_execution: ContextVar[TX | None] = ContextVar(
    "threaded_execution", default=None,
)
_RECORD_META = frozenset({
    "thread", "req", "seq", "stream", "stream_end", "error",
})
_EXCLUDED = frozenset({"schema", "login", "register", "register_user"})


async def invoke_threaded(model, method, arguments, *, user) -> TX:
    """Dispatch an authorized HTTP action as one server execution TX.

    The generated HTTP route owns authentication, action authorization and
    argument parsing. This bridge never accepts client TX metadata or caller
    claims from the action body. It does not preserve a browser TX envelope."""
    # 0. Keep caller metadata separate from recordable domain arguments.
    cls = model if isinstance(model, type) else type(model)
    data = {key: value for key, value in arguments.items() if key != "user"}
    if not isinstance(model, type):
        data["id"] = model.id
    root = Actor.root()
    # 1. Use native correlation without retries or a separate dispatch layer.
    return await root.request(TX(
        name=method, source=root.addr, target=cls.addr,
        data=data, meta={"user": user},
    ))


class ThreadedMixin:
    """Capture incoming TXs for explicitly participating actors.

    Compose before Actor/ActorModel. Root names are case-sensitive, like native
    exposed actions. Do not enable this on credential-bearing actors. Thread
    and TXRecord infrastructure is excluded even if composed accidentally."""

    __thread_roots__: ClassVar[frozenset[str]] = frozenset()

    @fullmethod
    def _thread_for(target, tx: TX) -> Thread | None:
        """Resolve the inherited local manifest or create a declared root."""
        # 0. Exclude infrastructure, schema and authentication traffic.
        from .tx_record import TXRecord
        cls = target if isinstance(target, type) else type(target)
        if issubclass(cls, (Matrix, Thread, TXRecord)):
            return None
        if tx.name.lower() in _EXCLUDED:
            return None
        # 1. Resolve only local Thread identities, never remote hydration.
        active = current_execution.get()
        reference = tx.meta.get("thread")
        if reference is None and active is not None:
            reference = active.meta.get("thread")
        if reference is not None:
            ident = local_ref_id(reference, target_cls=Thread)
            thread = Thread.get(ident) if ident is not None else None
            if thread is None:
                raise ValueError("Execution Thread is unavailable")
            return thread
        # 2. Only selected entrypoints create new manifests.
        if tx.name not in target.__thread_roots__:
            return None
        user = tx.meta.get("user")
        ident = tx.data.get("id") if isinstance(tx.data, dict) else None
        if not isinstance(target, type):
            ident = getattr(target, "id", None)
        scope = (
            public_id_url(ident, target_cls=cls) if ident is not None else None
        )
        return Thread.create(Thread(
            user_owner=user.get("user_id") if user is not None else None,
            scope=scope,
        ))

    @fullmethod
    def _record(target, tx: TX, thread: Thread) -> None:
        """Persist payload and identity with noncredential metadata."""
        # 0. Preserve the envelope without persisting caller/runtime objects.
        snapshot = replace(tx, meta={
            key: value for key, value in tx.meta.items() if key in _RECORD_META
        })
        thread.append(snapshot, user=tx.meta.get("user"))

    @fullmethod
    async def inbox(target, tx: TX) -> None:
        """Record destination arrivals before native interceptors/dispatch."""
        # 0. Routing intermediaries do not own the destination's snapshot.
        if tx.target != target.addr:
            await super(ThreadedMixin, target).inbox(tx)
            return
        # 1. Resolve the manifest for this receiving destination only.
        thread = target._thread_for(tx)
        if thread is None:
            await super(ThreadedMixin, target).inbox(tx)
            return
        # 2. A failed incoming snapshot prevents dispatch, without retry.
        tx.meta["thread"] = public_id_url(thread.id, target_cls=Thread)
        target._record(tx, thread)
        token = current_execution.set(tx)
        try:
            await super(ThreadedMixin, target).inbox(tx)
        finally:
            current_execution.reset(token)


# Changelog (Python has no block-comment syntax).
# - 2026-10-31: Bridge selected authenticated actions into native TX dispatch.
# - 2026-10-31: Record arrivals only at the envelope's exact destination.
# - 2026-10-31: Record only inbox arrivals; remove send capture and its guard.
# - 2026-10-31: Add opt-in native TX capture without global Matrix observation.
