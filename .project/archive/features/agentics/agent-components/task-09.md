# Create Pygentic test suite

**ID:** task-09 | **Wave:** 4 | **Depends on:** task-07, task-08

## Intent

The test suite validates the Pygentic app's CRUD operations, schema endpoints, agent execution, and streaming. It follows the standard test pattern from examples/grants/ with session-scoped fixtures for DB, seed data, and authenticated client.

## Context

Test suites for example apps live in examples/<app>/tests/. They use session-scoped fixtures (test_db, seed_data, client, tokens) to avoid re-creating the database between tests. The grants example conftest.py at examples/grants/tests/conftest.py is the reference pattern.

Key patterns:
- conftest.py sets up sys.path, namespace shims, auth config, test DB, seed data, FastAPI TestClient, JWT tokens
- helpers.py provides auth_header()
- Tests use pytest marks: pytest.mark.integration for HTTP tests
- Agent tests use pydantic-ai TestModel for mock LLM
- Streaming tests check for typed events in SSE response

## Instructions

Create the following test files under /workspace/examples/pygentic/tests/:

**1. /workspace/examples/pygentic/tests/__init__.py** — empty

**2. /workspace/examples/pygentic/tests/helpers.py**:
```python
"""Test helpers for the Pygentic example."""


def auth_header(token: str) -> dict:
    return {'x-access-token': token}
```

**3. /workspace/examples/pygentic/tests/conftest.py**:
```python
"""Shared fixtures for Pygentic example integration tests."""
import os
import sys
import types
import tempfile
import pytest

_tests = os.path.dirname(os.path.abspath(__file__))
_example = os.path.dirname(_tests)
_workspace = os.path.dirname(_example)
_src = os.path.join(_workspace, 'src')
_n3tx = os.path.join(_src, 'n3tx')
_core = os.path.join(_n3tx, 'core')

if _tests not in sys.path:
    sys.path.insert(0, _tests)
if _example not in sys.path:
    sys.path.insert(0, _example)
if _src not in sys.path:
    sys.path.insert(0, _src)

_namespace_shims = {
    'n3tx': _n3tx,
    'n3tx.core': _core,
}
for name, path in _namespace_shims.items():
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = [path]
        m.__package__ = name
        sys.modules[name] = m

import config
from n3tx_core import config as n3tx_config
from n3tx_core import authorize
authorize.configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=config.JWT_EXPIRY_HOURS)

os.environ['GENERATE_DOCS'] = 'false'
from main import app

n3tx_config.DEBUG = False

from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import registered_models
from models import User, Task, Memory
from n3tx_agents.actor import AgentActor
from n3tx_agents.tool_model import AgentTool
from n3tx_core.authorize import create_token


def _setup_test_db(db_path):
    storage = SQLiteStorage(database=db_path)
    for model_cls in registered_models.values():
        if hasattr(model_cls, 'set_storage'):
            model_cls.set_storage(storage)
            model_cls.create_table()
            if hasattr(storage, 'migrate_table'):
                storage.migrate_table(model_cls)
    return storage


def _seed_users():
    users_data = [
        {'name': 'Alice Martin', 'email': 'alice@example.com', 'password': 'alice123'},
        {'name': 'Bob Johnson', 'email': 'bob@example.com', 'password': 'bob123'},
    ]
    created = {}
    for u in users_data:
        pw = u.pop('password')
        user = User(**u)
        user._plain_password = pw
        result = User.create(user)
        created[result.name.split()[0].lower()] = result

    admin = User(name='Admin User', email='admin@example.com', role='admin')
    admin._plain_password = 'admin123'
    created['admin'] = User.create(admin)
    return created


def _seed_tasks(users):
    tasks_data = [
        {'title': 'Setup CI', 'status': 'open', 'priority': 'high',
         'description': 'Configure CI pipeline.', 'user_owner': users['alice'].id},
        {'title': 'Review auth', 'status': 'in_progress', 'priority': 'critical',
         'description': 'Audit JWT auth.', 'user_owner': users['bob'].id},
    ]
    created = []
    for t in tasks_data:
        result = Task.create(Task(**t))
        created.append(result)
    return created


def _seed_agent():
    join_cls = None
    for model_cls in registered_models.values():
        if (getattr(model_cls, '__owner__', None) is AgentActor
                and issubclass(model_cls, AgentTool)):
            join_cls = model_cls
            break

    agent = AgentActor(
        name='Test Agent',
        prompt='You are a helpful test agent.',
        llm='test',
    )
    created_agent = AgentActor.create(agent)

    if join_cls:
        tool_data = [
            {'target': 'tasks', 'description': 'Task CRUD'},
            {'target': 'memories', 'description': 'Memory store'},
        ]
        for t in tool_data:
            record = join_cls(**t, agentactor_id=created_agent.id)
            join_cls.create(record)

    return created_agent


@pytest.fixture(scope='session')
def test_db():
    db_fd, db_path = tempfile.mkstemp(suffix='_test_pygentic.db')
    original_db = config.SQLITE_DB_FILE
    config.SQLITE_DB_FILE = db_path
    _setup_test_db(db_path)
    yield db_path
    config.SQLITE_DB_FILE = original_db
    try:
        os.close(db_fd)
    except OSError:
        pass
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture(scope='session')
def seed_data(test_db):
    users = _seed_users()
    tasks = _seed_tasks(users)
    agent = _seed_agent()
    return {'users': users, 'tasks': tasks, 'agent': agent}


@pytest.fixture(scope='session')
def client(test_db, seed_data):
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope='session')
def alice_token(seed_data):
    alice = seed_data['users']['alice']
    return create_token(alice.id, alice.email, alice.role)


@pytest.fixture(scope='session')
def bob_token(seed_data):
    bob = seed_data['users']['bob']
    return create_token(bob.id, bob.email, bob.role)


@pytest.fixture(scope='session')
def admin_token(seed_data):
    admin = seed_data['users']['admin']
    return create_token(admin.id, admin.email, admin.role)
```

**4. /workspace/examples/pygentic/tests/test_boot.py**:
```python
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
```

**5. /workspace/examples/pygentic/tests/test_task_crud.py**:
```python
"""CRUD tests for the Task model."""
import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration


class TestTaskCRUD:
    def test_list_tasks_public(self, client, seed_data):
        resp = client.get('/tasks')
        assert resp.status_code == 200
        data = resp.json()
        assert 'data' in data
        assert len(data['data']) >= 2

    def test_create_task_requires_auth(self, client):
        resp = client.post('/tasks', json={'title': 'Test'})
        assert resp.status_code in (401, 403)

    def test_create_task(self, client, alice_token):
        resp = client.post(
            '/tasks',
            json={'title': 'New task', 'priority': 'high'},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['title'] == 'New task'

    def test_get_task(self, client, seed_data):
        task_id = seed_data['tasks'][0].id
        resp = client.get(f'/tasks/{task_id}')
        assert resp.status_code == 200
```

**6. /workspace/examples/pygentic/tests/test_schema_endpoints.py**:
```python
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
```

**7. /workspace/examples/pygentic/tests/test_agent_run.py**:
```python
"""Tests for agent execution in Pygentic."""
import json
import pytest
from helpers import auth_header
from n3tx_agents.actor import AgentActor

pytestmark = pytest.mark.integration


class TestAgentAgentic:
    def test_agentic_via_http(self, client, seed_data, alice_token):
        agent = seed_data['agent']
        resp = client.post(
            f'/agents/{agent.id}/agentic',
            json={'task': 'List tasks'},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, str):
            data = json.loads(data)
        if 'result' in data and '_debug' in data:
            data = data['result']
        assert 'answer' in data

    @pytest.mark.asyncio
    async def test_agentic_direct(self, test_db, seed_data):
        from pydantic_ai.models.test import TestModel
        agent = AgentActor.get(seed_data['agent'].id)
        result_str = await agent.agentic(
            task='List tasks',
            llm=TestModel(call_tools=['tasks_list']),
        )
        result = json.loads(result_str)
        assert 'answer' in result
```

## Conventions

Tests use session-scoped fixtures (test_db, seed_data, client, tokens). Mark: pytestmark = pytest.mark.integration. Helpers in helpers.py. conftest.py handles sys.path, namespace shims, auth config, DB setup. Agent tests use TestModel. HTTP tests use FastAPI TestClient.

## Files

**Read:** - /workspace/examples/grants/tests/conftest.py
- /workspace/examples/grants/tests/helpers.py
- /workspace/examples/grants/tests/test_agent_chat.py
- /workspace/examples/grants/tests/test_agent_run.py
- /workspace/examples/grants/tests/test_boot.py

**Modify:** none

**Create:** - /workspace/examples/pygentic/tests/__init__.py
- /workspace/examples/pygentic/tests/helpers.py
- /workspace/examples/pygentic/tests/conftest.py
- /workspace/examples/pygentic/tests/test_boot.py
- /workspace/examples/pygentic/tests/test_task_crud.py
- /workspace/examples/pygentic/tests/test_schema_endpoints.py
- /workspace/examples/pygentic/tests/test_agent_run.py

## Verification

**Commands:**
- `cd /workspace && python3 -m pytest examples/pygentic/tests/test_boot.py -v --tb=short -x`
- `cd /workspace && python3 -m pytest examples/pygentic/tests/ -v --tb=short`

**Checks:**
- All test files import without errors
- Boot tests pass (/_meta, schema endpoints)
- Task CRUD tests pass
- Schema tests verify agent section and streaming methods
- Agent run test passes with TestModel
