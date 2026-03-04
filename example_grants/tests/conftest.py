"""
Shared fixtures for Grant-Watching example integration tests.

Provides:
- Isolated test database per session
- FastAPI TestClient
- JWT tokens for test users
- Seed data
"""
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
from n3tx.core import authorize
authorize.configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=config.JWT_EXPIRY_HOURS)

os.environ["GENERATE_DOCS"] = "false"
from main import app  # noqa: triggers model registration

from n3tx.core.storage.sqlite_storage import SQLiteStorage
from n3tx.core.utils.registrar import registered_models
from models import User, Grant, Source, WebTools
from n3tx.core.agents.actor import AgentActor
from n3tx.core.agents.tool_model import AgentTool
from n3tx.core.authorize import create_token


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
        {"name": "Alice Martin", "email": "alice@example.com", "password": "alice123"},
        {"name": "Bob Johnson", "email": "bob@example.com", "password": "bob123"},
    ]
    created = {}
    for u in users_data:
        pw = u.pop("password")
        user = User(**u)
        user._plain_password = pw
        result = User.create(user)
        created[result.name.split()[0].lower()] = result

    admin = User(name="Admin User", email="admin@example.com", role="admin")
    admin._plain_password = "admin123"
    created['admin'] = User.create(admin)
    return created


def _seed_sources():
    sources_data = [
        {"name": "NSF", "url": "https://www.nsf.gov/funding/", "category": "government"},
        {"name": "NIH", "url": "https://grants.nih.gov/funding/", "category": "government"},
    ]
    created = []
    for s in sources_data:
        result = Source.create(Source(**s))
        created.append(result)
    return created


def _seed_grants(users):
    grants_data = [
        {
            "title": "CISE Research Grant",
            "agency": "NSF",
            "deadline": "2026-06-15",
            "amount_min": 100000,
            "amount_max": 500000,
            "url": "https://nsf.gov/example-cise",
            "description": "Computer science research funding.",
            "status": "discovered",
            "user_owner": users["alice"].id,
        },
    ]
    created = []
    for g in grants_data:
        result = Grant.create(Grant(**g))
        created.append(result)
    return created


def _seed_agent():
    # Look up the join model for AgentActor -> AgentTool
    join_cls = None
    for model_cls in registered_models.values():
        if (getattr(model_cls, '__owner__', None) is AgentActor
                and issubclass(model_cls, AgentTool)):
            join_cls = model_cls
            break

    agent = AgentActor(
        name="Grant Scanner",
        prompt="You are a grant discovery agent. List sources, scrape them, create grants.",
        llm="test",
    )
    created_agent = AgentActor.create(agent)

    # Create tool records via the join table
    if join_cls:
        tool_data = [
            {"target": "grants", "description": "Grant CRUD"},
            {"target": "sources", "description": "Source listing"},
            {"target": "web_tools", "description": "Web scraping"},
        ]
        for t in tool_data:
            record = join_cls(**t, agentactor_id=created_agent.id)
            join_cls.create(record)

    return created_agent


@pytest.fixture(scope="session")
def test_db():
    db_fd, db_path = tempfile.mkstemp(suffix='_test_grants.db')
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


@pytest.fixture(scope="session")
def seed_data(test_db):
    users = _seed_users()
    sources = _seed_sources()
    grants = _seed_grants(users)
    agent = _seed_agent()
    return {
        "users": users,
        "sources": sources,
        "grants": grants,
        "agent": agent,
    }


@pytest.fixture(scope="session")
def client(test_db, seed_data):
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def alice_token(seed_data):
    alice = seed_data["users"]["alice"]
    return create_token(alice.id, alice.email, alice.role)


@pytest.fixture(scope="session")
def bob_token(seed_data):
    bob = seed_data["users"]["bob"]
    return create_token(bob.id, bob.email, bob.role)


@pytest.fixture(scope="session")
def admin_token(seed_data):
    admin = seed_data["users"]["admin"]
    return create_token(admin.id, admin.email, admin.role)
