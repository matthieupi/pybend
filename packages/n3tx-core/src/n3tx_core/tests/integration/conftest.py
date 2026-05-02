# tests/conftest.py
"""
Shared fixtures for N3TX backend integration tests.

Provides:
- Isolated test database per test module (test_n3tx.db)
- FastAPI TestClient
- JWT tokens for alice, bob, charlie, and an admin user
- Seed data population
- Helper functions for auth headers
"""

import os
import sys
import tempfile
import pytest

# Ensure the core directory and examples/core are on the Python path so imports resolve
_core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_workspace = os.path.dirname(os.path.dirname(os.path.dirname(_core_dir)))
_example_core = os.path.join(_workspace, 'examples', 'core')
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)
if _example_core not in sys.path:
    sys.path.insert(0, _example_core)
if os.path.join(_workspace, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(_workspace, 'src'))

from n3tx_core import config
from n3tx_core import authorize
TEST_JWT_SECRET = 'test-core-integration-secret-32-bytes'
authorize.configure(jwt_secret=TEST_JWT_SECRET, jwt_expiry_hours=config.JWT_EXPIRY_HOURS)

# Import main to trigger model registration and route setup (uses production DB initially)
os.environ["GENERATE_DOCS"] = "false"  # Skip doc generation during tests
from main import app  # noqa: triggers model registration

from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import registered_models, join_models
from models import Product, Comment, Like, User
from n3tx_core.authorize import create_token


def _setup_test_db(db_path):
    """Register all models with a fresh storage backend pointing at db_path."""
    storage = SQLiteStorage(database=db_path)

    # Re-register all models with the test storage
    for model_cls in registered_models.values():
        if hasattr(model_cls, 'set_storage'):
            model_cls.set_storage(storage)
            model_cls.create_table()
            if hasattr(storage, 'migrate_table'):
                storage.migrate_table(model_cls)

    return storage


def _seed_users():
    """Create seed users and return a dict of user objects keyed by name."""
    users_data = [
        {"name": "Alice Martin", "email": "alice@example.com", "password": "alice123", "age": 28,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Alice"},
        {"name": "Bob Johnson", "email": "bob@example.com", "password": "bob123", "age": 34,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Bob"},
        {"name": "Charlie Lee", "email": "charlie@example.com", "password": "charlie123", "age": 22,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Charlie"},
    ]

    created = {}
    for u in users_data:
        pw = u.pop("password")
        user = User(**u)
        user._plain_password = pw
        result = User.create(user)
        created[result.name.split()[0].lower()] = result

    # Create an admin user
    admin = User(name="Admin User", email="admin@example.com", role="admin",
                 image="https://api.dicebear.com/9.x/avataaars/svg?seed=Admin")
    admin._plain_password = "admin123"
    created['admin'] = User.create(admin)

    return created


def _seed_products():
    """Create seed products and return a list."""
    products_data = [
        {"name": "Wireless Headphones", "price": 79.99,
         "description": "Noise-cancelling over-ear headphones with 30h battery life.",
         "image": "https://picsum.photos/seed/headphones/400/300"},
        {"name": "Mechanical Keyboard", "price": 129.50,
         "description": "Cherry MX Brown switches, RGB backlight, TKL layout.",
         "image": "https://picsum.photos/seed/keyboard/400/300"},
        {"name": "USB-C Hub", "price": 45.00,
         "description": "7-in-1 hub: HDMI, USB-A x3, SD, microSD, PD charging.",
         "image": "https://picsum.photos/seed/usbhub/400/300"},
        {"name": "Standing Desk Mat", "price": 39.99,
         "description": "Anti-fatigue ergonomic mat, 20x34 inches.",
         "image": "https://picsum.photos/seed/deskmat/400/300"},
        {"name": "Monitor Light Bar", "price": 54.95,
         "description": "Asymmetric LED light bar, adjustable color temperature.",
         "image": "https://picsum.photos/seed/lightbar/400/300"},
    ]

    created = []
    for p in products_data:
        product = Product(**p)
        result = Product.create(product)
        created.append(result)
    return created


def _seed_comments(users, products):
    """Create seed comments on products and return a list."""
    comments_data = [
        {"product_idx": 0, "user_key": "bob", "name": "Great sound",
         "description": "Best headphones I've owned. ANC is incredible."},
        {"product_idx": 0, "user_key": "charlie", "name": "Comfortable",
         "description": "Wore them for 8 hours straight, no issues."},
        {"product_idx": 1, "user_key": "alice", "name": "Perfect for coding",
         "description": "The tactile feedback is just right. Love the layout."},
        {"product_idx": 1, "user_key": "charlie", "name": "A bit loud",
         "description": "Switches are louder than expected in a quiet office."},
        {"product_idx": 2, "user_key": "alice", "name": "Works perfectly",
         "description": "All ports recognized immediately on macOS and Linux."},
        {"product_idx": 3, "user_key": "bob", "name": "Feet love it",
         "description": "Standing all day is much easier with this mat."},
        {"product_idx": 4, "user_key": "alice", "name": "No more eye strain",
         "description": "Huge difference for late-night work sessions."},
        {"product_idx": 4, "user_key": "bob", "name": "Easy to install",
         "description": "Clips right onto the monitor, no tools needed."},
    ]

    created = []
    for c in comments_data:
        product = products[c["product_idx"]]
        user = users[c["user_key"]]
        comment = Comment(name=c["name"], description=c["description"], user_owner=user.id)
        comment.__owner__ = product
        result = comment.save()
        created.append(result)
    return created


def _seed_replies(users, products, comments):
    """Create nested replies with parent_id."""
    replies_data = [
        {"parent_idx": 0, "product_idx": 0, "user_key": "alice", "name": "Agreed!",
         "description": "The ANC on these is next level."},
        {"parent_idx": 0, "product_idx": 0, "user_key": "charlie", "name": "Which model?",
         "description": "Are you talking about the v2 or v3?"},
        {"parent_idx": 2, "product_idx": 1, "user_key": "bob", "name": "Same here",
         "description": "Cherry Browns are the sweet spot for me too."},
    ]

    created = []
    for r in replies_data:
        parent = comments[r["parent_idx"]]
        product = products[r["product_idx"]]
        user = users[r["user_key"]]
        reply = Comment(
            name=r["name"],
            description=r["description"],
            user_owner=user.id,
            parent_id=parent.id,
        )
        reply.__owner__ = product
        result = reply.save()
        created.append(result)
    return created


def _seed_likes(users, comments):
    """Create likes on comments."""
    from datetime import datetime

    likes_data = [
        {"comment_idx": 0, "user_key": "alice"},
        {"comment_idx": 0, "user_key": "charlie"},
        {"comment_idx": 2, "user_key": "bob"},
        {"comment_idx": 4, "user_key": "bob"},
        {"comment_idx": 6, "user_key": "charlie"},
    ]

    created = []
    for ld in likes_data:
        comment = comments[ld["comment_idx"]]
        user = users[ld["user_key"]]
        like = Like(user=user.id, created_at=datetime.now().isoformat())
        like.__owner__ = comment
        result = like.save()
        created.append(result)
    return created


def _seed_favorites(users, products):
    """Create favorites (ProductLike) on products."""
    from datetime import datetime

    fav_data = [
        {"product_idx": 0, "user_key": "alice"},
        {"product_idx": 1, "user_key": "alice"},
        {"product_idx": 0, "user_key": "bob"},
        {"product_idx": 2, "user_key": "charlie"},
        {"product_idx": 4, "user_key": "bob"},
    ]

    created = []
    for fd in fav_data:
        product = products[fd["product_idx"]]
        user = users[fd["user_key"]]
        fav = Like(user=user.id, created_at=datetime.now().isoformat())
        fav.__owner__ = product
        result = fav.save()
        created.append(result)
    return created


# ---------------------------------------------------------------------------
# Fixture factories (SD-3)
# ---------------------------------------------------------------------------

def _make_product(client, token, name="Factory Product", price=19.99, **overrides):
    """Create a product via the API and return the response data dict."""
    from n3tx_core.tests.helpers import auth_header
    payload = {"name": name, "price": price, **overrides}
    resp = client.post("/Product", json=payload, headers=auth_header(token))
    assert resp.status_code == 201, f"Failed to create product: {resp.text}"
    return resp.json()


def _make_comment(client, token, product_id, name="Factory Comment",
                  description="Factory description", **overrides):
    """Create a comment on a product via the API and return the response data dict."""
    from n3tx_core.tests.helpers import auth_header
    payload = {"name": name, "description": description, **overrides}
    resp = client.post(f"/Product/{product_id}/Comment", json=payload,
                       headers=auth_header(token))
    assert resp.status_code == 201, f"Failed to create comment: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_db():
    """Create a temporary database file for the test session.
    All models are re-registered with this DB. Cleaned up after the session."""
    db_fd, db_path = tempfile.mkstemp(suffix='_test_n3tx.db')

    # Point config at the test DB
    original_db = config.SQLITE_DB_FILE
    config.SQLITE_DB_FILE = db_path

    _setup_test_db(db_path)

    yield db_path

    # Restore original config and clean up
    config.SQLITE_DB_FILE = original_db
    try:
        os.close(db_fd)
    except OSError:
        pass
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture(scope="session")
def seed_data(test_db):
    """Seed the test database with users, products, comments, replies, likes, favorites.
    Returns a dict with all created entities."""
    users = _seed_users()
    products = _seed_products()
    comments = _seed_comments(users, products)
    replies = _seed_replies(users, products, comments)
    likes = _seed_likes(users, comments)
    favorites = _seed_favorites(users, products)

    return {
        "users": users,
        "products": products,
        "comments": comments,
        "replies": replies,
        "likes": likes,
        "favorites": favorites,
    }


@pytest.fixture(scope="session")
def client(test_db, seed_data):
    """FastAPI TestClient wrapping the application."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def alice_token(seed_data):
    """JWT token for alice (regular user)."""
    alice = seed_data["users"]["alice"]
    return create_token(alice.id, alice.email, alice.role)


@pytest.fixture(scope="session")
def bob_token(seed_data):
    """JWT token for bob (regular user)."""
    bob = seed_data["users"]["bob"]
    return create_token(bob.id, bob.email, bob.role)


@pytest.fixture(scope="session")
def charlie_token(seed_data):
    """JWT token for charlie (regular user)."""
    charlie = seed_data["users"]["charlie"]
    return create_token(charlie.id, charlie.email, charlie.role)


@pytest.fixture(scope="session")
def admin_token(seed_data):
    """JWT token for admin user."""
    admin = seed_data["users"]["admin"]
    return create_token(admin.id, admin.email, admin.role)


@pytest.fixture(scope="session")
def make_product(client, alice_token):
    """Fixture factory for creating products via the API (SD-3)."""
    def _factory(name="Factory Product", price=19.99, token=None, **overrides):
        return _make_product(client, token or alice_token, name=name,
                             price=price, **overrides)
    return _factory


@pytest.fixture(scope="session")
def make_comment(client, alice_token):
    """Fixture factory for creating comments via the API (SD-3)."""
    def _factory(product_id, name="Factory Comment",
                 description="Factory description", token=None, **overrides):
        return _make_comment(client, token or alice_token, product_id,
                             name=name, description=description, **overrides)
    return _factory
