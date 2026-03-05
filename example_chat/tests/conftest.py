"""
Shared fixtures for Chat example integration tests.

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
from models import User, Conversation, Message
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


def _seed_conversations(users):
    convs = []
    conv = Conversation(
        name="Test Chat",
        prompt="You are a helpful test assistant.",
        user_owner=users["alice"].id,
    )
    convs.append(Conversation.create(conv))

    conv2 = Conversation(
        name="Bob's Chat",
        prompt="You are Bob's assistant.",
        user_owner=users["bob"].id,
    )
    convs.append(Conversation.create(conv2))
    return convs


@pytest.fixture(scope="session")
def test_db():
    db_fd, db_path = tempfile.mkstemp(suffix='_test_chat.db')
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
    convs = _seed_conversations(users)
    return {
        "users": users,
        "conversations": convs,
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
