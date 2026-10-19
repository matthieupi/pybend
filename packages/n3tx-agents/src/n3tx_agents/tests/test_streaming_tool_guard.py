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
    def test_discover_tools_includes_streaming_methods(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Analyzer(ActorModel):
            __tablename__ = 'analyzers'
            __storable__ = False

            @expose_route('/analyze', methods=['POST'], stream=True)
            async def analyze(self, query: str):
                yield {'name': 'text', 'data': {'text': 'partial'}}

        register_model(Analyzer, storage=storage)

        specs = discover_tools(['analyzers'], fresh_matrix, caller_addr='scanner/1')
        names = [spec.tool_name for spec in specs]
        assert 'analyzers_analyze' in names

    @pytest.mark.asyncio
    async def test_run_stream_does_not_log_matrix_self_route_for_streaming_tool(self, fresh_matrix, tmp_path, caplog):
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Analyzer(ActorModel):
            __tablename__ = 'analyzers'
            __storable__ = False

            @expose_route('/analyze', methods=['POST'], stream=True)
            async def analyze(self, query: str):
                yield {'name': 'text', 'data': {'text': 'partial'}}
                yield {'name': 'done', 'data': {'answer': 'done'}}

        class Scanner(ActorModel):
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
            ):
                chunks.append(chunk)

        assert "Cannot route to self at matrix" not in caplog.text
        assert chunks
