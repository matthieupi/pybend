"""Keep native streaming tools discoverable and free of Matrix self-routing."""

import logging

import pytest
from pydantic_ai.models.test import TestModel as SDKTestModel

from n3tx_actors.models.actor_model import ActorModel
from n3tx_agents.threaded_mixin import current_execution
from n3tx_agents.tools import discover_tools
from n3tx_core.utils.decorators import expose_route


@pytest.mark.asyncio
async def test_stream_tool_discovery_and_native_causal_route(
    fresh_matrix, caplog,
):
    """Execute a discovered stream tool without Matrix self-routing."""
    # 0. A real class action emits native text and explicit completion.
    class Analyzer(ActorModel):
        """Supply a harmless streaming tool for native discovery."""

        __tablename__ = "stream_guard_analyzers"
        __storable__ = False

        @classmethod
        @expose_route("/analyze", methods=["POST"], stream=True)
        async def analyze(cls, query: str):
            """Emit synthetic text and a terminal application result."""
            yield {"name": "text", "data": {"text": "partial"}}
            yield {"name": "done", "data": {"answer": "done"}}

    class Scanner(ActorModel, auto_register=False):
        """Use the trusted streaming engine with a saved canonical owner."""

        __tablename__ = "stream_guard_scanners"
        __storable__ = False
        __agent__ = True

    specs = discover_tools([Analyzer.addr], fresh_matrix)
    assert [spec.tool_name for spec in specs] == [
        "stream_guard_analyzers_analyze",
    ]
    assert specs[0].stream is True
    # 1. Retain actual Matrix/SDK dispatch and require successful completion.
    with caplog.at_level(logging.ERROR):
        chunks = [chunk async for chunk in Scanner.run_stream(
            task="Analyze synthetic text", prompt="Use the analyzer",
            tools=[Analyzer.addr],
            llm=SDKTestModel(call_tools=[specs[0].tool_name]),
            ttx=current_execution.get(),
        )]
    assert "Cannot route to self" not in caplog.text
    assert chunks[-1]["name"] == "done"
    assert not any(chunk["name"] == "error" for chunk in chunks)


# Changelog (Python has no native block-comment syntax).
# - 2026-11-12: Combine native stream discovery/routing regression coverage and
#   require canonical execution instead of implicit legacy history allocation.
