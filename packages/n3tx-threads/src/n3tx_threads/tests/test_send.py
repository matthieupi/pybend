"""Protect TTX causal delivery at four native Actor/Matrix boundaries.

Disposable canonical storage and real one-way recipients cover detached sends,
class replies, middleware delegation and fail-closed context validation. These
trusted Python tests do not install application middleware or capture history.
Typed storage and exhaustive Actor behavior belong to their existing suites."""

import asyncio
from copy import deepcopy
from dataclasses import asdict
import inspect
from queue import Empty

import pytest

from n3tx_actors import Actor, Matrix, TX
from n3tx_core.models import proto_dump
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.registrar import register_model, registered_models
from n3tx_threads import TTX


@pytest.fixture
def send_context(tmp_path):
    """Isolate native routing, caches and runner-owned SQLite connections."""
    # 0. Preserve exact bindings, including absent own class attributes.
    missing = object()
    original_root = Actor.root()
    attributes = {
        name: TTX.__dict__.get(name, missing)
        for name in (
            "storage", "__matrix__", "__children__", "__interceptors__",
            "_subscribers",
        )
    }
    registries = (
        registered_models, ProtoModel._schema_cache,
        proto_dump._schema_url_cache, proto_dump._instance_url_cache,
    )
    snapshots = [dict(registry) for registry in registries]
    root = Matrix(addr="synthetic-root")
    deliveries = []

    class Recipient(Actor, auto_register=False):
        """Consume synthetic one-way events without generating replies."""

        __addr__ = "send-recipient"

        @classmethod
        def LIFECYCLE(cls, data, tx):
            """Retain the delivered envelope for boundary assertions."""
            deliveries.append(tx)

    storage = SQLiteStorage(
        database=str(tmp_path / "send.sqlite3"), pool_size=1,
    )
    try:
        # 1. Register only canonical storage and native routing participants.
        Actor.root(root)
        TTX.__matrix__ = root
        TTX.__children__, TTX.__interceptors__ = {}, {}
        TTX._subscribers = []
        register_model(TTX, storage=storage)
        root.register(TTX)
        root.register(Recipient)
        yield root, deliveries
    finally:
        # 2. Close owned handles and restore all shared bindings and caches.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()
        root.children.clear()
        root._interceptors.clear()
        Actor.__matrix__ = original_root
        for name, value in attributes.items():
            if value is missing:
                delattr(TTX, name)
            else:
                setattr(TTX, name, value)
        for registry, snapshot in zip(registries, snapshots):
            registry.clear()
            registry.update(snapshot)


def _event():
    """Build a synthetic TX with nested JSON and caller metadata."""
    return TX(
        "LIFECYCLE", "ttx/999", "send-recipient",
        data={"opaque": {"items": [1, None, "123"]}},
        meta={"user": {"user_id": 17}, "trace": {"items": ["synthetic"]}},
        uuid="synthetic-send", timestamp=456.125,
    )


@pytest.mark.asyncio
async def test_causal_delivery_detaches_concurrent_contexts(send_context):
    """Expose saved sources without mutating shared caller input."""
    # 0. Force overlapping sends of one TX through ordinary Matrix middleware.
    root, deliveries = send_context
    senders = [TTX.create(TTX.from_tx(_event())) for _ in range(2)]
    parents = [sender.parent for sender in senders]
    rows = [sender.model_dump(mode="json") for sender in senders]
    senders[0]._addr = "irrelevant-display-address"
    tx = _event()
    before, data, meta = asdict(tx), tx.data, tx.meta
    middleware = []
    release = asyncio.Event()

    async def observe(tx):
        """Hold delivery until both independent sends reach Matrix inbox."""
        middleware.append(asdict(tx))
        assert all(s.parent is p for s, p in zip(senders, parents))
        if len(middleware) == 2:
            release.set()
        await asyncio.wait_for(release.wait(), timeout=1.0)
        return tx

    root.use(observe, on="inbox")
    # 1. Both envelopes preserve all transport fields except causal source.
    assert await asyncio.gather(*(s.send(tx) for s in senders)) == [None, None]
    expected = [{**before, "source": f"ttx/{s.id}"} for s in senders]
    assert sorted(middleware, key=lambda t: t["source"]) == expected
    assert len(deliveries) == 2
    assert sorted(
        [asdict(item) for item in deliveries], key=lambda t: t["source"],
    ) == expected
    # 2. Downstream edits cannot affect another send, the input or saved rows.
    assert deliveries[0] is not deliveries[1] and deliveries[0] is not tx
    deliveries[0].data["opaque"]["items"].append("recipient-only")
    deliveries[0].meta["user"]["user_id"] = 99
    assert deliveries[1].data == before["data"]
    assert deliveries[1].meta == before["meta"]
    assert asdict(tx) == before and tx.data is data and tx.meta is meta
    assert [s.model_dump(mode="json") for s in senders] == rows
    assert [TTX.get(s.id).model_dump(mode="json") for s in senders] == rows
    assert all(s.parent is p for s, p in zip(senders, parents))
    assert len(TTX.list(archived=True)) == 2


@pytest.mark.asyncio
async def test_class_send_preserves_native_api_and_replies(
    send_context, monkeypatch,
):
    """Keep native class signatures and Matrix reply correlation."""
    # 0. Keep the native fullmethod API on both class and instance bindings.
    root, deliveries = send_context
    saved = TTX.create(TTX.from_tx(_event()))
    descriptor = inspect.getattr_static(TTX, "send")
    native = inspect.signature(Actor.send, eval_str=True)
    assert isinstance(descriptor, fullmethod)
    assert inspect.iscoroutinefunction(descriptor.fn)
    assert inspect.signature(TTX.send, eval_str=True) == native
    assert inspect.signature(saved.send, eval_str=True) == native
    # 1. ActorModel replies through the class to a root-owned pending request.
    request = TX("get", root.addr, "ttx", {"id": saved.id}, {"user": None})
    reply = await root.request(request, timeout=0.25)
    assert not reply.is_error, reply.data
    assert reply.meta["req"] == request.uuid
    assert reply.data["id"] == saved.id
    assert root._pending == {} and deliveries == []
    # 2. Sending on the class itself needs neither a saved ID nor SQL storage.
    monkeypatch.setattr(TTX, "storage", None)
    tx = _event()
    assert await TTX.send(tx) is None
    assert len(deliveries) == 1
    assert deliveries[0].source == "ttx/ttx/999"


@pytest.mark.asyncio
async def test_native_middleware_can_replace_and_reject(send_context):
    """Native send replacement reaches Matrix policy without bypassing it."""
    # 0. A native class interceptor replaces the transport on each class hop.
    root, deliveries = send_context
    sender = TTX.create(TTX.from_tx(_event()))
    seen = []

    def replace(tx):
        """Return a detached replacement carrying native traversal evidence."""
        replacement = deepcopy(tx)
        replacement.meta.setdefault("passes", []).append("class")
        return replacement

    def instance_hook(tx):
        """Retain the instance hop between native class-chain invocations."""
        tx.meta["passes"].append("instance")
        return tx

    def policy(tx):
        """Observe canonical causality and reject the second event."""
        seen.append(asdict(tx))
        return tx.error("Synthetic rejection", 403) if tx.data["deny"] else tx

    TTX.use(replace, on="send")
    sender.use(instance_hook, on="send")
    root.use(policy, on="inbox")
    tx = _event()
    tx.data["deny"] = False
    before = asdict(tx)
    # 1. Replacement survives native bubbling and ordinary Matrix middleware.
    assert await sender.send(tx) is None
    assert len(deliveries) == 1
    assert seen == [asdict(deliveries[0])]
    assert seen[0]["source"] == f"ttx/{sender.id}"
    assert seen[0]["meta"]["passes"] == ["class", "instance", "class"]
    assert asdict(tx) == before
    # 2. Returning a native error at Matrix blocks the next recipient call.
    tx.data["deny"] = True
    assert await sender.send(tx) is None
    assert len(seen) == 2 and len(deliveries) == 1
    assert seen[1]["source"] == f"ttx/{sender.id}"


@pytest.mark.asyncio
async def test_invalid_context_fails_before_routing(send_context):
    """Reject missing rows and unsupported trees before send hooks."""
    # 0. Observe both send interception and routing without replacing either.
    root, deliveries = send_context
    seen = []
    TTX.use(lambda tx: seen.append(tx) or tx, on="send")
    root.use(lambda tx: seen.append(tx) or tx, on="inbox")
    tx = _event()
    before = asdict(tx)
    # 1. An unsaved envelope cannot manufacture a canonical causal identity.
    sender = TTX.from_tx(tx)
    with pytest.raises(ValueError):
        await sender.send(tx)
    # 2. A live row still cannot bypass its canonical model-class routing hop.
    sender = TTX.create(sender)
    sender._parent = root
    with pytest.raises(RuntimeError):
        await sender.send(tx)
    assert seen == deliveries == []
    assert asdict(tx) == before


# Changelog (Python has no native block-comment syntax).
# - 2026-11-11: Protect canonical saved-context sources at native Matrix inbox
#   and destination, detached concurrent sends, native chains and class replies.
#   Reject noncanonical instance trees before send hooks; keep custom addresses
#   irrelevant to saved identity and preserve native class binding semantics.
#   Shorten overlong prose and require ValueError for missing saved contexts.
#   Consolidate into four boundary tests; retain native state and pool cleanup.
#   Retain class/instance/class interceptor order in the existing boundary case.
