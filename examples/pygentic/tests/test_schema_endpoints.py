"""Schema endpoint tests."""
import pytest

pytestmark = pytest.mark.integration


class TestSchemaEndpoints:
    def test_task_schema_has_agent(self, client):
        resp = client.get('/Task')
        assert resp.status_code == 200
        schema = resp.json()
        assert 'agent' in schema
        assert schema['agent']['enabled'] is True

    def test_task_schema_has_analyze_method(self, client):
        resp = client.get('/Task')
        schema = resp.json()
        methods = schema.get('methods', {})
        assert 'analyze' in methods
        assert methods['analyze'].get('stream') is True

    def test_agent_schema_has_agentic_stream(self, client):
        resp = client.get('/AgentActor')
        schema = resp.json()
        methods = schema.get('methods', {})
        assert 'agentic_stream' in methods
        assert methods['agentic_stream'].get('stream') is True

    def test_memory_schema(self, client):
        resp = client.get('/Memory')
        assert resp.status_code == 200
        schema = resp.json()
        assert 'content' in schema.get('properties', {})
