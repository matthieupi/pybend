"""Notes contract tests — native projection and HTTP/TX/tool integration.

Exercise NOTE and read_notes against disposable registered models. Parent
actions and Thread owner/admin policy stay independent; trusted transport
callers supply attribution, and pages expose original numeric TX time."""

import json
from copy import deepcopy
from queue import Empty
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import Agent as PydanticAgent, models
from pydantic_ai.messages import ModelRequest, ToolReturnPart
from pydantic_ai.models.test import TestModel

from n3tx_agents import (
    AgentDeps, NotesMixin, Thread, TXRecord, discover_tools, make_tool,
)
from n3tx_actors import Actor, Matrix, TX
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core import config
from n3tx_core.api.routes_fastapi import router
from n3tx_core.app import create_app
from n3tx_core.authorize import NEVER, ROLE, auth, create_token
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import Ref, public_id_url
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.erroring import MethodError


pytestmark = pytest.mark.unit
WRITER = {"user_id": 1, "role": "staff"}
OTHER = {"user_id": 2, "role": "staff"}
ADMIN = {"user_id": 3, "role": "admin"}


class Notebook(ActorModel):
    """Use flag-collected notes with ordinary native parent permissions."""

    __tablename__ = "notes_examples"
    __storable__ = True
    __notes__ = True
    __protected_fields__: ClassVar[set] = {"user_owner", "locked"}
    __access__: ClassVar[dict] = {
        "*": NEVER, "create": ROLE("staff", "admin"),
        "read": ROLE("staff", "admin"), "list": ROLE("staff", "admin"),
        "update": ROLE("staff", "admin"),
        "NOTE": ROLE("staff", "admin"),
        "read_notes": ROLE("staff", "admin"),
    }
    title: str = "Synthetic notebook"
    user_owner: int = 1
    locked: bool = False


class BlockedNotebook(Notebook):
    """Keep parent permissions but explicitly deny both notes actions."""

    __tablename__ = "blocked_notes_examples"

    @expose_route("/NOTE", methods=["POST"], access=NEVER)
    def NOTE(self, content: str, user: dict = None) -> dict:
        """Retain the native signature behind an explicit denial."""
        return super().NOTE(content, user)

    @expose_route("/read_notes", methods=["POST"], access=NEVER)
    def read_notes(self, cursor: str, limit: int, user: dict = None) -> dict:
        """Retain the native reader behind an explicit denial."""
        return super().read_notes(cursor, limit, user)


def _ref(record):
    """Return a saved synthetic resource's canonical URL."""
    return public_id_url(record.id, target_cls=type(record))


def _headers(user):
    """Issue native tokens containing only synthetic identity claims."""
    return {"x-access-token": create_token(
        user["user_id"], "notes@example.test", user["role"],
    )}


def _records(owner):
    """Inspect snapshots under their native Thread owner's permission."""
    reference = type(owner).get(owner.id).notes
    return Thread.get(int(Ref.id(reference))).records(user=WRITER)["data"]


@pytest.fixture
def notes_runtime(tmp_path, monkeypatch, request):
    """Register real notes-only models with disposable native storage."""
    # 0. Preserve process globals; do not replace model or Thread policies.
    saved_routes = list(router.routes)
    saved_cache = dict(ProtoModel._schema_cache)
    saved_auth = (auth._jwt_secret, auth._jwt_expiry_hours)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    monkeypatch.setattr(config, "DEBUG", False)
    for model in (Notebook, BlockedNotebook, Thread, TXRecord):
        monkeypatch.setattr(
            model, "storage", getattr(model, "storage", None), raising=False,
        )
        monkeypatch.setattr(model, "__interceptors__", {
            key: list(value) for key, value in model.__interceptors__.items()
        })
    owners = getattr(request, "param", (Notebook,))
    storage = SQLiteStorage(str(tmp_path / "notes.sqlite3"))
    try:
        application = create_app(
            models=list(owners), storage=storage, static_dir=None,
            debug=False, ssr="off", remotes={},
            jwt_secret="synthetic-notes-secret-not-for-production",
        )
        root = Matrix()
        Actor.root(root)
        for model in (*owners, Thread, TXRecord):
            root._children[model.__addr__] = model
        with TestClient(application) as client:
            yield root, client
    finally:
        # 1. Close only owned storage and restore factory globals.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()
        router.routes[:] = saved_routes
        ProtoModel._schema_cache.clear()
        ProtoModel._schema_cache.update(saved_cache)
        auth._jwt_secret, auth._jwt_expiry_hours = saved_auth


def test_flag_collects_lazy_ref_and_protected_union(notes_runtime):
    """Collect the field, actions and protected union through flag injection."""
    # 0. Native declarations and empty reads require no pre-created Thread.
    assert issubclass(Notebook, NotesMixin)
    assert Notebook.model_fields["notes"].default is None
    assert {"notes", "user_owner", "locked"} <= Notebook.__protected_fields__
    schema = Notebook.schema()
    assert "notes" in schema["properties"]
    for action in ("NOTE", "read_notes"):
        assert "user" not in schema["methods"][action]["parameters"]
    owner = Notebook.create(Notebook())
    assert owner.read_notes("", 10, WRITER)["data"] == []
    assert Thread.list() == []
    # 1. First write links a native Thread with the expected metadata.
    result = owner.NOTE("first note", WRITER)
    saved = Notebook.get(owner.id)
    assert saved.notes == public_id_url(result["thread_id"], target_cls=Thread)
    thread = Thread.get(result["thread_id"])
    assert thread.user_owner == 1 and thread.scope == _ref(owner)
    assert len(Thread.list()) == 1


@pytest.mark.asyncio
async def test_http_injection_protection_and_non_note_crud(notes_runtime):
    """HTTP identity injection and native CRUD remain authoritative."""
    # 0. A forged body user cannot replace the caller injected from the token.
    root, client = notes_runtime
    owner = Notebook.create(Notebook())
    response = client.post(
        f"/notes_examples/{owner.id}/NOTE", headers=_headers(WRITER),
        json={"content": "HTTP note", "user": OTHER},
    )
    assert response.status_code == 200, response.text
    saved = Notebook.get(owner.id)
    page = client.post(
        f"/Notebook/{owner.id}/read_notes", headers=_headers(WRITER),
        json={"cursor": "", "limit": 10, "user": OTHER},
    )
    assert page.status_code == 200, page.text
    row = page.json()["data"][0]
    assert set(row) == {"id", "kind", "content", "timestamp", "user_owner"}
    assert row["user_owner"] == 1
    assert row["timestamp"] == _records(owner)[0].timestamp
    denied = client.post(
        f"/Notebook/{owner.id}/read_notes", headers=_headers(OTHER),
        json={"cursor": "", "limit": 10, "user": WRITER},
    )
    assert denied.status_code == 403
    # 1. Native updates preserve notes and the parent's other protected fields.
    updated = client.put(
        f"/notes_examples/{owner.id}", headers=_headers(WRITER),
        json={"title": "updated", "notes": None, "locked": True,
              "user_owner": 999},
    )
    assert updated.status_code == 200, updated.text
    current = Notebook.get(owner.id)
    assert current.notes == saved.notes and current.user_owner == 1
    assert not current.locked and current.title == "updated"
    # 2. Other TX names delegate to ordinary CRUD without recording notes.
    for action, values in (
        ("get", {"id": owner.id}),
        ("update", {"id": owner.id, "title": "native CRUD"}),
    ):
        reply = await root.request(TX(
            action, root.addr, Notebook.__addr__, data=values,
            meta={"user": WRITER},
        ), timeout=2)
        assert not reply.is_error
    assert Notebook.get(owner.id).title == "native CRUD"
    assert len(_records(owner)) == 1


@pytest.mark.asyncio
async def test_discovered_testmodel_tools_note_and_admin_read(notes_runtime):
    """Use generated tools with native actor caller metadata and TestModel."""
    # 0. Discover real signatures without exposing the injected user argument.
    root, _ = notes_runtime
    owner = Notebook.create(Notebook())
    specs = {
        spec.method_name: spec
        for spec in discover_tools([Notebook.__addr__], root)
        if spec.method_name in {"NOTE", "read_notes"}
    }
    assert set(specs) == {"NOTE", "read_notes"}
    for spec in specs.values():
        assert "user" not in spec.parameters.get("properties", {})

    class FixedNotesModel(TestModel):
        """Supply valid synthetic IDs through the native TestModel loop."""

        def gen_tool_args(self, tool_def):
            """Generate only the discovered business arguments."""
            if tool_def.name == specs["NOTE"].tool_name:
                return {"id": owner.id, "content": "agent tool note"}
            assert tool_def.name == specs["read_notes"].tool_name
            return {"id": owner.id, "cursor": "", "limit": 10}

    returns = {}
    # 1. Commit the writer's note before a separate admin reader tool runs.
    for action, user in (("NOTE", WRITER), ("read_notes", ADMIN)):
        spec = specs[action]
        agent = PydanticAgent(
            FixedNotesModel(call_tools=[spec.tool_name]),
            tools=[make_tool(spec)], deps_type=AgentDeps, retries=0,
        )
        result = await agent.run(
            "Synthetic notes request",
            deps=AgentDeps(user=user, agent_addr="notes_test_agent"),
        )
        parts = [
            part for message in result.all_messages()
            if isinstance(message, ModelRequest)
            for part in message.parts if isinstance(part, ToolReturnPart)
        ]
        assert len(parts) == 1 and parts[0].tool_name == spec.tool_name
        returns[action] = json.loads(parts[0].content)
    assert returns["NOTE"]["thread_id"] == int(Ref.id(
        Notebook.get(owner.id).notes,
    ))
    assert returns["read_notes"]["data"][0]["content"] == "agent tool note"
    assert returns["read_notes"]["data"][0]["user_owner"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("instance_target", [False, True])
async def test_native_routed_snapshot_and_single_reply(
    notes_runtime, instance_target,
):
    """Preserve the native incoming envelope once while stripping metadata."""
    # 0. Internal Matrix uses explicit user metadata as the native caller.
    root, _ = notes_runtime
    owner = Notebook.create(Notebook())
    target = Notebook.__addr__
    data = {"id": owner.id, "content": "original routed note"}
    if instance_target:
        owner._addr = "pinned_notes_owner"
        root.register(owner)
        target = owner.addr
        data.pop("id")
    tx = TX(
        "NOTE", "original_sender", target, data=data,
        meta={"user": WRITER, "token": "synthetic-secret"},
        timestamp=1234.5, uuid="original-note-uuid",
    )
    original = deepcopy(tx)
    sent = []

    def observe(response):
        """Count only this native request's correlated outgoing response."""
        if response.meta.get("req") == tx.uuid:
            sent.append(response)
        return response

    Notebook.use(observe, on="send")
    reply = await root.request(tx, timeout=2)
    # 1. One saved snapshot and one response do not mutate the incoming TX.
    assert not reply.is_error and reply.meta["req"] == tx.uuid
    assert len(sent) == 1 and tx == original
    records = _records(owner)
    assert len(records) == 1
    record = records[0]
    assert (record.uuid, record.source, record.target, record.timestamp) == (
        original.uuid, original.source, original.target, original.timestamp,
    )
    assert record.meta == {} and record.data == {
        "payload": {"content": "original routed note"},
    }
    assert record.user_owner == 1
    assert owner.read_notes("", 10, WRITER)["data"] == [{
        "id": record.id, "kind": "text", "content": "original routed note",
        "timestamp": 1234.5, "user_owner": 1,
    }]


@pytest.mark.asyncio
@pytest.mark.parametrize("case,status", [
    ("missing_user", 403), ("extra_user", 400),
    ("missing_id", 400), ("conflicting_id", 400),
])
async def test_routed_notes_validate_parent_caller_and_arguments(
    notes_runtime, case, status,
):
    """Retain native parent permission and notes argument validation."""
    # 0. Native handler inputs cannot redirect an instance or inject data.user.
    root, _ = notes_runtime
    owner = Notebook.create(Notebook())
    target = Notebook.__addr__
    data = {"id": owner.id, "content": "invalid request"}
    if case == "extra_user":
        data["user"] = WRITER
    elif case == "missing_id":
        data.pop("id")
    elif case == "conflicting_id":
        owner._addr = "fixed_notes_owner"
        root.register(owner)
        target = owner.addr
        data["id"] = owner.id + 1
    reply = await root.request(TX(
        "NOTE", "sender", target, data=data,
        meta={} if case == "missing_user" else {"user": WRITER},
    ), timeout=2)
    # 1. Rejection occurs before lazy Thread allocation.
    assert reply.is_error and reply.data["code"] == status
    assert Notebook.get(owner.id).notes is None and Thread.list() == []


def test_parent_read_does_not_grant_thread_and_admin_can_access(notes_runtime):
    """Keep parent permission and Thread owner/admin checks independent."""
    # 0. Another staff caller can read the parent but not its notes Thread.
    owner = Notebook.create(Notebook())
    owner.NOTE("owner note", WRITER)
    for operation in (
        lambda: owner.read_notes("", 10, OTHER),
        lambda: owner.NOTE("other staff note", OTHER),
    ):
        with pytest.raises(MethodError) as caught:
            operation()
        assert caught.value.status_code == 403
    # 1. Native admin access works when the parent also permits that action.
    owner.NOTE("admin note", ADMIN)
    page = owner.read_notes("", 10, ADMIN)
    assert {row["user_owner"] for row in page["data"]} == {1, 3}
    denied_parent = {"user_id": 1, "role": "user"}
    with pytest.raises(MethodError) as caught:
        owner.read_notes("", 10, denied_parent)
    assert caught.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["NOTE", "read_notes"])
@pytest.mark.parametrize("notes_runtime", [(BlockedNotebook,)], indirect=True)
async def test_explicit_decorator_denial_http_and_routed(
    notes_runtime, action,
):
    """Explicit NEVER still defeats otherwise allowed native parent policy."""
    # 0. Native parent update remains available without granting notes actions.
    root, client = notes_runtime
    owner = BlockedNotebook.create(BlockedNotebook())
    allowed = client.put(
        f"/blocked_notes_examples/{owner.id}", headers=_headers(WRITER),
        json={"title": "still editable"},
    )
    assert allowed.status_code == 200, allowed.text
    values = (
        {"content": "denied"} if action == "NOTE"
        else {"cursor": "", "limit": 10}
    )
    # 1. Both enabled paths honor the actual method decorator.
    response = client.post(
        f"/BlockedNotebook/{owner.id}/{action}",
        headers=_headers(WRITER), json=values,
    )
    assert response.status_code == 403
    reply = await root.request(TX(
        action, root.addr, BlockedNotebook.__addr__,
        data={"id": owner.id, **values}, meta={"user": WRITER},
    ), timeout=2)
    assert reply.is_error and reply.data["code"] == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["NOTE", "read_notes"])
async def test_none_decorator_falls_back_to_named_action_policy(
    notes_runtime, monkeypatch, action,
):
    """A None decorator rule retains the named native model action policy."""
    # 0. Deny only the action, leaving native parent CRUD policy unchanged.
    root, client = notes_runtime
    owner = Notebook.create(Notebook())
    monkeypatch.setattr(Notebook, "__access__", {
        **Notebook.__access__, action: NEVER,
    })
    Notebook.invalidate_schema_cache()
    values = (
        {"content": "denied"} if action == "NOTE"
        else {"cursor": "", "limit": 10}
    )
    # 1. HTTP and internal Matrix dispatch both enforce the fallback rule.
    response = client.post(
        f"/Notebook/{owner.id}/{action}",
        headers=_headers(WRITER), json=values,
    )
    assert response.status_code == 403
    reply = await root.request(TX(
        action, root.addr, Notebook.__addr__, data={"id": owner.id, **values},
        meta={"user": WRITER},
    ), timeout=2)
    assert reply.is_error and reply.data["code"] == 403


def test_notes_numeric_paging_preserves_filtering_and_nullable_owner(
    notes_runtime,
):
    """Keep native page bounds while projecting TX time and nullable callers."""
    # 0. Save notes out of time order with one non-NOTE in the older page.
    owner = Notebook.create(Notebook())
    thread = Thread.create(Thread(user_owner=1, scope=_ref(owner)))
    owner.update({"notes": _ref(thread)})
    for timestamp, name, caller in (
        (2.25, "NOTE", WRITER), (-1.0, "NOTE", None),
        (0.0, "execution", WRITER), (0.125, "NOTE", ADMIN),
    ):
        thread.append(TX(
            name, "test", "sink", data={"content": str(timestamp)},
            timestamp=timestamp,
        ), user=caller)
    # 1. The projected envelope uses the unfiltered native continuation.
    page = owner.read_notes("", 2, WRITER)
    assert set(page) == {"data", "cursor", "has_more"}
    assert page["cursor"] == "0.125" and page["has_more"] is True
    assert [row["timestamp"] for row in page["data"]] == [2.25, 0.125]
    assert [row["user_owner"] for row in page["data"]] == [1, 3]
    older = owner.read_notes(page["cursor"], 2, WRITER)
    assert older["cursor"] == "" and older["has_more"] is False
    assert len(older["data"]) == 1
    assert older["data"][0] == {
        "id": thread.records(user=WRITER)["data"][-1].id,
        "kind": "text", "content": "-1.0", "timestamp": -1.0,
        "user_owner": None,
    }


def test_bounded_content_and_native_resource_projection(notes_runtime):
    """Retain bounded notes content and native resource reference projection."""
    # 0. Invalid content cannot allocate a notes Thread.
    owner = Notebook.create(Notebook())
    for content in ("", "   ", {"not": "text"}):
        with pytest.raises(ValueError):
            owner.NOTE(content, WRITER)
    with pytest.raises(MethodError) as caught:
        owner.NOTE("x" * 16001, WRITER)
    assert caught.value.status_code == 413 and Thread.list() == []
    # 1. Resource notes are pointers, not populated parent records.
    owner.NOTE(_ref(owner), WRITER)
    page = owner.read_notes("", 10, WRITER)
    assert page["data"][0]["content"] == _ref(owner)
    assert page["data"][0]["kind"] == "resource"
    assert "title" not in page["data"][0]


# Changelog (Python has no native block-comment syntax).
# - 2026-11-06: Assert timestamp/user_owner projections across HTTP, tools and
#   raw NOTE; restore wrapped payloads and cover filtered numeric-time pages.
# - 2026-10-31: Cover flag-based notes fields, HTTP/tool/raw caller boundaries,
#   native action policies, immutable snapshots and transaction-time revocation.
#   - Use notes-only native bootstrap without fixture policy replacements.
#   - Replace Thread grants with inherited scope policy; retain transport-only
#     Notes caller expiry and preflight notes-pointer integrity checks.
# - 2026-10-31: Align with approved native owner/admin Notes cleanup.
#   - Retire removed caller-capability expiry, UUID pinning, scope-inherited
#     access and transactional pointer/source checks; scope is metadata only.
#   - Retain named HTTP caller injection, native raw caller metadata, snapshot
#     conversion, protected notes fields and parent/action/Thread permissions.
