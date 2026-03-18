"""Smoke tests — app boots and responds."""
import pytest

pytestmark = pytest.mark.integration


class TestBoot:
    def test_meta_endpoint(self, client):
        resp = client.get('/_meta')
        assert resp.status_code == 200
        data = resp.json()
        assert data['name'] == 'Pygentic'

    def test_schema_endpoints_exist(self, client):
        for model in ['Task', 'Memory', 'AgentActor']:
            resp = client.get(f'/{model}')
            assert resp.status_code == 200, f'{model} schema failed: {resp.status_code}'
