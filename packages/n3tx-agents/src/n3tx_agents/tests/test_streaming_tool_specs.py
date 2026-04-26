import pytest
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route
from n3tx_agents.tools import _method_tool_specs


pytestmark = pytest.mark.unit


def test_method_tool_specs_include_streaming_methods_with_stream_flag():
    class Analyzer(ActorModel):
        __tablename__ = 'analyzers'
        __storable__ = False

        @expose_route('/analyze', methods=['POST'], stream=True)
        async def analyze(self, query: str):
            yield {'name': 'text', 'data': {'text': 'partial'}}

        @expose_route('/inspect', methods=['POST'])
        async def inspect(self, query: str) -> str:
            return 'ok'

    schema = Analyzer.schema()
    specs = _method_tool_specs('analyzers', 'analyzers', 'Analyzer', schema)
    by_name = {spec.tool_name: spec for spec in specs}

    assert 'analyzers_analyze' in by_name
    assert by_name['analyzers_analyze'].stream is True
    assert 'analyzers_inspect' in by_name
    assert by_name['analyzers_inspect'].stream is False
