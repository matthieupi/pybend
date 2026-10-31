"""Discovery must advertise the configured public origin, not the listener."""

import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize('origin', [
    'https://neuralys.cloud',
    'http://localhost:5000',
])
@pytest.mark.parametrize('endpoint', ['/_meta', '/.well-known/agent.json'])
def test_builder_discovery_uses_canonical_origin(origin, endpoint):
    # Fresh processes isolate config, schema caches and native registries.
    script = """
import sys

from fastapi.testclient import TestClient
from n3tx_core.app import N3TXApp
from n3tx_core.authorize import ANYONE, NEVER
from n3tx_core.models.proto_model import ProtoModel

class DiscoveryEntry(ProtoModel):
    __tablename__ = 'discovery_entries'
    __access__ = {'*': NEVER, 'read': ANYONE, 'list': ANYONE}
    name: str = ''

origin, endpoint = sys.argv[1:]
app = N3TXApp(
    storage='sqlite:///:memory:', debug=False, ssr=False, remotes={},
    jwt_secret='synthetic-discovery-test-secret-32-bytes',
).model(DiscoveryEntry).build(name='Discovery test')
with TestClient(app, base_url='http://internal.test:4000') as client:
    response = client.get(endpoint)
    assert response.status_code == 200, response.text
    data = response.json()
    if endpoint == '/_meta':
        assert data['base_url'] == origin, data
        model = data['models']['discovery_entries']
        assert model['schema_url'] == origin + '/DiscoveryEntry'
        assert model['collection_url'] == origin + '/DiscoveryEntry/_'
        assert data['debug'] is False
    else:
        assert data['url'] == origin, data
        assert data['authentication']['credentials'] == origin + '/users/login'
"""
    env = {
        **os.environ,
        'PYTHONDONTWRITEBYTECODE': '1',
        'N3TX_API_URL': origin,
        'N3TX_HOST': '0.0.0.0',
        'N3TX_PORT': '4000',
        'N3TX_SQLITE_DB': ':memory:',
        'N3TX_DEBUG': 'false',
        'N3TX_REMOTES': '{}',
        'N3TX_AGENT_DEFAULTS': '{"llm": ""}',
        'COLLAGEN_AI_MODE': 'disabled',
        'COLLAGEN_AI_ALLOW_PROVIDER': 'false',
    }
    result = subprocess.run(
        [sys.executable, '-B', '-c', script, origin, endpoint],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
