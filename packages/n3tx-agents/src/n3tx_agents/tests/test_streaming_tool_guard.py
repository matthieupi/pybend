"""Native streaming-tool routing with authorized saved conversation scope."""

import logging

import pytest
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.registrar import register_model
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_agents.tools import discover_tools


pytestmark = pytest.mark.unit


class TestStreamingToolGuard:
    """Keep streaming tool discovery and routing on native actor paths."""

    def test_discover_tools_includes_streaming_methods(
        self, fresh_matrix, tmp_path,
    ):
        """Discover exposed streaming methods as native tool specifications."""
        # 0. Register a synthetic streaming provider without inference.
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Analyzer(ActorModel):
            """Non-storable native streaming tool provider."""

            __tablename__ = 'analyzers'
            __storable__ = False

            @expose_route('/analyze', methods=['POST'], stream=True)
            async def analyze(self, query: str):
                """Yield synthetic text without any external calls."""
                yield {'name': 'text', 'data': {'text': 'partial'}}

        register_model(Analyzer, storage=storage)

        specs = discover_tools(
            ['analyzers'], fresh_matrix, caller_addr='scanner/1',
        )
        names = [spec.tool_name for spec in specs]
        assert 'analyzers_analyze' in names

    @pytest.mark.asyncio
    async def test_streaming_tool_avoids_matrix_self_route(
        self, fresh_matrix, tmp_path, caplog, agent_context,
    ):
        """Native streaming tools do not misroute replies back into Matrix."""
        from pydantic_ai.models.test import TestModel
        # 0. Register real native providers and explicitly scoped execution.
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Analyzer(ActorModel):
            """Synthetic streaming provider with terminal completion."""

            __tablename__ = 'analyzers'
            __storable__ = False

            @expose_route('/analyze', methods=['POST'], stream=True)
            async def analyze(self, query: str):
                """Yield the native text and completion event vocabulary."""
                yield {'name': 'text', 'data': {'text': 'partial'}}
                yield {'name': 'done', 'data': {'answer': 'done'}}

        class Scanner(ActorModel):
            """Non-storable execution target with explicit parent scope."""

            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True
            prompt: str = Field(default='Use the analyzer tool.')

        register_model(Analyzer, storage=storage)
        register_model(Scanner, storage=storage)

        scanner = Scanner(addr='scanners/1')

        with caplog.at_level(logging.ERROR):
            chunks = []
            async for chunk in scanner.run_stream(
                task='Analyze this text',
                prompt='Analyze this text',
                tools=['analyzers'],
                llm=TestModel(call_tools=['analyzers_analyze']),
                **agent_context,
            ):
                chunks.append(chunk)

        assert "Cannot route to self at matrix" not in caplog.text
        assert chunks


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Supply authorized saved scope to streaming-tool execution.
