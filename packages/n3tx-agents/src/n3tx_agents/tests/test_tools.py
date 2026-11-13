"""Protect schema-to-tool generation and native TTX routing boundaries.

Discovery is capability selection, not authorization. Tool caller policy is
covered separately; these tests keep CRUD/action discovery, generated signatures
and native error/stream result handling without a second dispatcher."""

import inspect
import json
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry
from pydantic_ai.tools import Tool

from n3tx_actors.models.actor_model import ActorModel
from n3tx_agents.agent import AgentDeps
from n3tx_agents.threaded_mixin import current_execution
from n3tx_agents.tools import (
    ToolSpec, create_tool_function, discover_tools, make_tool, _route_tool_call,
)
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.registrar import register_model


def test_discovery_preserves_native_crud_scope_and_required_parameters(
    fresh_matrix, memory_storage,
):
    """Discover native CRUD/actions without recursive self-selection."""
    # 0. Declare one storable model and one parameterized native action.
    class Grant(ActorModel):
        """Supply ordinary CRUD fields for native tool discovery."""

        __tablename__ = "tool_grants"
        __storable__ = True
        title: str = ""

    class Extractor(ActorModel):
        """Supply required/defaulted arguments and instance scope."""

        __tablename__ = "tool_extractors"
        __storable__ = False

        @expose_route("/extract", methods=["POST"])
        def extract(self, html: str, selector: str = "body") -> str:
            """Return a synthetic value without external work."""
            return selector

    register_model(Grant, storage=memory_storage)
    # 1. Requiredness and implicit instance identity survive schema discovery.
    specs = discover_tools([Grant.addr, Extractor.addr], fresh_matrix)
    crud = {spec.method_name for spec in specs if spec.actor_addr == Grant.addr}
    assert crud == {"list", "get", "create", "update", "delete"}
    extract = next(spec for spec in specs if spec.method_name == "extract")
    assert set(extract.parameters["required"]) == {"id", "html"}
    assert "selector" in extract.parameters["properties"]
    assert discover_tools(
        [Grant.addr], fresh_matrix, caller_addr=Grant.addr,
    ) == []
    assert discover_tools(["missing-tool"], fresh_matrix) == []


def test_generated_tool_signature_preserves_schema_and_safe_names():
    """Generate typed async SDK tools with valid names and optional defaults."""
    # 0. One representative signature covers required/optional JSON types.
    spec = ToolSpec(
        actor_addr="synthetic", method_name="create",
        tool_name="synthetic-tool.create", description='Quoted "tool" C:\\path',
        parameters={
            "type": "object", "required": ["name", "count"],
            "properties": {
                "name": {"type": "string"}, "count": {"type": "integer"},
                "price": {"type": "number"}, "active": {"type": "boolean"},
                "tags": {"type": "array"}, "meta": {"type": "object"},
                "123invalid": {"type": "string"},
            },
        },
    )
    fn = create_tool_function(spec)
    parameters = inspect.signature(fn).parameters
    # 1. SDK introspection receives native Python types, not a second schema.
    assert inspect.iscoroutinefunction(fn)
    assert fn.__name__ == "synthetic_tool_create"
    assert fn.__doc__ == spec.description
    assert list(parameters)[0] == "ctx" and "123invalid" not in parameters
    assert parameters["name"].default is inspect.Parameter.empty
    assert parameters["count"].default is inspect.Parameter.empty
    for name, expected in (
        ("name", str), ("count", int), ("price", float), ("active", bool),
        ("tags", list), ("meta", dict),
    ):
        assert fn.__annotations__[name] is expected
        if name not in {"name", "count"}:
            assert parameters[name].default is None
    spec.tool_name = fn.__name__
    tool = make_tool(spec)
    assert isinstance(tool, Tool) and tool.name == spec.tool_name
    assert tool.description == spec.description
    # 2. Parameterless schemas remain valid async context-only functions.
    empty = create_tool_function(ToolSpec(
        actor_addr="synthetic", method_name="list", tool_name="synthetic_list",
        description="List", parameters={"type": "object", "properties": {}},
    ))
    assert list(inspect.signature(empty).parameters) == ["ctx"]


@pytest.mark.asyncio
async def test_tool_routing_retains_errors_and_stream_result_selection(
    fresh_matrix, monkeypatch,
):
    """Native TTX tools propagate errors and select completion/text payloads."""
    # 0. All requests use the real Matrix and active canonical execution owner.
    class StreamActor(ActorModel):
        """Emit completion or text-only synthetic native streams."""

        __tablename__ = "stream_tool"
        __storable__ = False

        @classmethod
        @expose_route("/analyze", methods=["POST"], stream=True)
        async def analyze(cls, complete: bool):
            """Produce harmless native text and optional completion evidence."""
            yield {"name": "text", "data": {"text": "Hello "}}
            yield {"name": "text", "data": {"text": "world"}}
            if complete:
                yield {"name": "done", "data": {"answer": "Final"}}

        @classmethod
        def fail(cls, data, tx):
            """Return a native structured failure without raising locally."""
            return tx.error("Synthetic failure", code=500)

    ctx = SimpleNamespace(deps=AgentDeps(
        None, "synthetic-agent", current_execution.get(),
    ))
    # 1. Structured native errors become ModelRetry without hiding their cause.
    with pytest.raises(ModelRetry, match="Synthetic failure"):
        await _route_tool_call(ctx, StreamActor.addr, "fail", {})
    native_request = type(fresh_matrix).request

    async def bounded_request(target, tx, timeout=30.0):
        """Bound waiting without replacing native no-route dispatch."""
        return await native_request(target, tx, timeout=min(timeout, 0.05))

    monkeypatch.setattr(type(fresh_matrix), "request", bounded_request)
    with pytest.raises(ModelRetry, match="No route"):
        await _route_tool_call(ctx, "missing-tool", "get", {"id": 1})
    # 2. Explicit completion wins; text-only streams concatenate their chunks.
    complete = await _route_tool_call(
        ctx, StreamActor.addr, "analyze", {"complete": True}, stream=True,
    )
    text = await _route_tool_call(
        ctx, StreamActor.addr, "analyze", {"complete": False}, stream=True,
    )
    assert json.loads(complete) == {"answer": "Final"}
    assert json.loads(text) == {"answer": "Hello world"}
    # 3. Missing execution cannot fall back to a synthetic Matrix source.
    token = current_execution.set(None)
    try:
        with pytest.raises(RuntimeError, match="active TTX"):
            await _route_tool_call(ctx, StreamActor.addr, "fail", {})
    finally:
        current_execution.reset(token)


# Changelog (Python has no native block-comment syntax).
# - 2026-11-12: Consolidate discovery/signature/native routing coverage and
#   require canonical active TTX dependencies instead of legacy Matrix sources.
