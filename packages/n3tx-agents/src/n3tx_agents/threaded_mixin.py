"""Native destination capture with one task-local canonical TTX context.

API: ThreadedMixin captures declared root actions and participating nested
destinations; invoke_threaded bridges authorized HTTP methods into Matrix.
current_execution contains only a saved TTX or None. _ttx_execution scopes an
already authorized owner without changing native dispatch.

Boundary: routing and correlation stay native. Authentication/schema traffic
is excluded; caller objects and runtime configuration are never persisted.
Agent commands reuse their authorized preallocated root; other operations save
fresh frames with the current TTX as source. No UUID deduplication, replay or
atomic coupling to business effects is supplied."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import ClassVar

from pydantic_core import to_jsonable_python

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.tx import TX
from n3tx_core.utils.descriptors import fullmethod
from n3tx_threads import TTX


current_execution: ContextVar[TTX | None] = ContextVar(
    "ttx_execution", default=None,
)
_RECORD_META = frozenset({
    "req", "seq", "stream", "stream_end", "error", "kind",
})
_EXCLUDED = frozenset({"schema", "login", "register", "register_user"})


@contextmanager
def _ttx_execution(ttx: TTX) -> Iterator[TTX]:
    """Bind one authorized saved owner and always restore the parent context."""
    if not isinstance(ttx, TTX) or ttx.id <= 0:
        raise ValueError("Execution requires a saved TTX")
    token = current_execution.set(ttx)
    try:
        yield ttx
    finally:
        current_execution.reset(token)


async def invoke_threaded(model, method, arguments, *, user) -> TX:
    """Bridge a caller-authorized HTTP action into native Matrix dispatch.

    The generated route owns authentication, parsing and action admission.
    Body identity is removed; trusted caller metadata never becomes evidence."""
    # 0. Preserve actual destination identity and noncredential arguments.
    cls = model if isinstance(model, type) else type(model)
    data = {key: value for key, value in arguments.items() if key != "user"}
    if not isinstance(model, type):
        data["id"] = model.id
    root = Actor.root()
    if root is None:
        raise RuntimeError("No Matrix root is available")
    active = current_execution.get()
    source = f"ttx/{active.id}" if active is not None else root.addr
    # 1. Retain native correlation without another dispatcher or retry loop.
    return await root.request(TX(
        method, source, cls.addr, data=data, meta={"user": user},
    ))


class ThreadedMixin:
    """Capture declared native root actions and participating child operations.

    API: inbox saves a destination frame, then delegates native interception;
    send records final non-agent RETURN evidence before normal routing.
    Compose before ActorModel. __thread_roots__ names root actions explicitly.
    Agent AGENTIC roots and their RETURN records are owned by agent adapters.
    Never compose this capability onto credential-bearing actors."""

    __thread_roots__: ClassVar[frozenset[str]] = frozenset()

    @fullmethod
    def _execution_frame(target, tx: TX) -> TTX | None:
        """Reuse an authorized agent root or save a fresh destination frame."""
        from .agent import Agent

        cls = target if isinstance(target, type) else type(target)
        # 0. Infrastructure and credential-bearing traffic cannot be captured.
        if issubclass(cls, (Matrix, TTX)) or tx.name.lower() in _EXCLUDED:
            return None
        if tx.is_error or tx.name.endswith("_RESPONSE"):
            return None
        if tx.name == "AGENTIC":
            return Agent.get_history(
                tx.data.get("ttx_ref"), user=tx.meta.get("user"),
                action="update",
            )
        active = current_execution.get()
        if active is None and tx.name not in target.__thread_roots__:
            return None
        # 1. Preserve actual instance routing without hydrating business data.
        data = {key: value for key, value in tx.data.items() if key != "user"}
        ident = data.get("id")
        if not isinstance(target, type):
            ident = getattr(target, "id", None)
        address = cls.addr
        if type(ident) is int and ident > 0:
            address = f"{address}/{ident}"
        user = tx.meta.get("user")
        user_id = user.get("user_id") if isinstance(user, dict) else None
        source = (
            f"ttx/{active.id}" if active is not None else
            f"users/{user_id}" if user_id is not None else tx.source
        )
        # 2. Detach full JSON content and retain safe transport metadata only.
        return TTX.create(TTX.from_tx(TX(
            tx.name, source, address, data=to_jsonable_python(data),
            meta={
                key: value for key, value in tx.meta.items()
                if key in _RECORD_META
            }, uuid=tx.uuid, timestamp=tx.timestamp,
        ), user_owner=user_id))

    @fullmethod
    async def inbox(target, tx: TX) -> None:
        """Capture destination arrivals and restore context after dispatch."""
        # 0. Matrix routes class actors with an optional instance suffix.
        if tx.target.split("/")[0] != target.addr.split("/")[0]:
            await super(ThreadedMixin, target).inbox(tx)
            return
        frame = target._execution_frame(tx)
        if frame is None:
            await super(ThreadedMixin, target).inbox(tx)
            return
        # 1. Persist before dispatch; failures never replay domain side effects.
        with _ttx_execution(frame):
            await super(ThreadedMixin, target).inbox(tx)

    @fullmethod
    async def send(target, tx: TX) -> None:
        """Record a final domain reply, then preserve native routing."""
        active = current_execution.get()
        # 0. Agent adapters own RETURN; stream chunks are not completions.
        if (
            active is not None and tx.meta.get("req")
            and active.meta.get("agent_history") is not True
            and active.target.split("/")[0] == target.addr.split("/")[0]
            and (not tx.meta.get("stream") or tx.meta.get("stream_end"))
        ):
            active.ATTACH(TTX.from_tx(TX(
                "RETURN", active.target, f"ttx/{active.id}",
                data=to_jsonable_python(tx.data),
                meta={
                    **{key: value for key, value in tx.meta.items()
                       if key in _RECORD_META},
                    "reply_name": tx.name,
                }, uuid=tx.uuid, timestamp=tx.timestamp,
            )))
        # 1. No Actor/Matrix routing semantics or source mutation are replaced.
        await super(ThreadedMixin, target).send(tx)


# Changelog (Python has no block-comment syntax).
# - 2026-11-11: Capture canonical root/child/RETURN frames with one TTX context;
#   reuse authorized agent owners and exclude credentials/runtime metadata.
# - 2026-11-11: Bind explicit TTX calls with scoped token restoration; skip
#   legacy manifests within that context and preserve legacy root capture.
# - 2026-10-31: Bridge selected authenticated actions into native TX dispatch.
# - 2026-10-31: Record arrivals only at the envelope's exact destination.
# - 2026-10-31: Record only inbox arrivals; remove send capture and its guard.
# - 2026-10-31: Add opt-in native TX capture without global Matrix observation.
