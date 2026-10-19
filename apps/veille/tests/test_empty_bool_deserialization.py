"""
Tests for SQLite empty-string boolean deserialization bug.

Bug: SQLite stores '' (empty string) for boolean fields added via migration.
Pydantic rejects '' as a boolean, causing Organization.list() to throw a
ValidationError. This cascades into:
  1. Scheduler loop crashes repeatedly
  2. Grant.analyze() silently swallows the error and reports "No organization found"
     even though an Organization exists in the DB.

These tests reproduce all three angles of the bug.
"""

import sys
import os
import sqlite3
import pytest
from typing import ClassVar, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydantic import Field, ValidationError

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model, registered_models


@pytest.fixture(autouse=True)
def reset_state():
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_models = dict(registered_models)

    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    registered_models.clear()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children
    registered_models.clear()
    registered_models.update(saved_models)


@pytest.fixture
def fresh_matrix():
    return Matrix()


# ── Test model mimicking Organization with a bool field ──────────────

class OrgModel(ActorModel):
    __tablename__: ClassVar[str] = 'organizations'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': ROLE('admin'),
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }

    name: str = Field(min_length=1, max_length=300)
    schedule_enabled: bool = Field(default=False)
    schedule_interval_hours: int = Field(default=168)


# ── Test 1: Unit — Pydantic model rejects '' for bool field ──────────

class TestEmptyStringBoolUnit:
    def test_deserialize_coerces_empty_string_bool(self):
        """_deserialize_json_fields coerces '' → False for bool fields."""
        from n3tx_core.storage.sqlite_storage import _deserialize_json_fields

        record = {'name': 'Test Org', 'schedule_enabled': '', 'schedule_interval_hours': 168}
        _deserialize_json_fields(OrgModel, record)
        assert record['schedule_enabled'] is False

    def test_deserialize_coerces_literal_quotes_bool(self):
        """Coerces "''" (literal two-quote string from repr-based DEFAULT)."""
        from n3tx_core.storage.sqlite_storage import _deserialize_json_fields

        record = {'name': 'Test Org', 'schedule_enabled': "''", 'schedule_interval_hours': 168}
        _deserialize_json_fields(OrgModel, record)
        assert record['schedule_enabled'] is False

    def test_deserialize_preserves_valid_bool_values(self):
        """Coercion only fires for non-parseable strings — valid values pass through."""
        from n3tx_core.storage.sqlite_storage import _deserialize_json_fields

        for val, expected in [(0, 0), (1, 1), (True, True), (False, False), (None, None),
                              ('true', 'true'), ('false', 'false'), ('0', '0'), ('1', '1')]:
            record = {'name': 'Test Org', 'schedule_enabled': val, 'schedule_interval_hours': 168}
            _deserialize_json_fields(OrgModel, record)
            assert record['schedule_enabled'] == expected, f"Changed {val!r} unexpectedly"

    def test_organization_accepts_valid_bool_values(self):
        """Sanity: True, False, 0, 1 should all work at model level."""
        for val, expected in [(True, True), (False, False), (0, False), (1, True),
                              ('true', True), ('false', False)]:
            org = OrgModel(name='Test Org', schedule_enabled=val)
            assert org.schedule_enabled is expected, f"Failed for {val!r}"


# ── Test 2: Integration — SQLite round-trip with empty string ────────

class TestSQLiteEmptyBoolRoundTrip:
    def test_list_org_with_empty_bool_in_db(self, fresh_matrix, tmp_path):
        """Organization.list() should succeed even when the DB has '' for
        schedule_enabled. This reproduces the exact production failure.

        The bug: SQLite migration adds a bool column with DEFAULT '',
        Pydantic can't parse '' as bool, list() throws ValidationError.
        """
        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(OrgModel, storage=storage)

        # Simulate what a migration does: insert a row with '' for the bool column
        conn = sqlite3.connect(str(tmp_path / 'test.db'))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                schedule_enabled TEXT DEFAULT '',
                schedule_interval_hours INTEGER DEFAULT 168
            )
        """)
        conn.execute(
            "INSERT INTO organizations (name, schedule_enabled, schedule_interval_hours) VALUES (?, ?, ?)",
            ('Test Org', "''", 168),
        )
        conn.commit()
        conn.close()

        # This should NOT throw — but currently does
        result = OrgModel.list(limit=1)
        data = result.get('data', result) if isinstance(result, dict) else result
        assert len(data) > 0, "Organization should be found"

    def test_get_org_with_empty_bool_in_db(self, fresh_matrix, tmp_path):
        """Organization.get(id) should succeed with '' bool in DB."""
        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(OrgModel, storage=storage)

        conn = sqlite3.connect(str(tmp_path / 'test.db'))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                schedule_enabled TEXT DEFAULT '',
                schedule_interval_hours INTEGER DEFAULT 168
            )
        """)
        conn.execute(
            "INSERT INTO organizations (name, schedule_enabled, schedule_interval_hours) VALUES (?, ?, ?)",
            ('Test Org', "''", 168),
        )
        conn.commit()
        conn.close()

        org = OrgModel.get(1)
        assert org is not None
        assert org.schedule_enabled is False


# ── Test 3: Cascade — analyze() fails because org load fails ─────────

class TestAnalyzeCascadeFailure:
    def test_analyze_finds_org_when_bool_field_is_empty_string(self, fresh_matrix, tmp_path):
        """Grant.analyze() should find the organization even when its
        schedule_enabled column contains '' in SQLite.

        The cascade: Organization.list() throws ValidationError →
        caught by bare except → data=[] → "No organization found" error.
        The org EXISTS but can't be deserialized.
        """
        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(OrgModel, storage=storage)

        # Insert org with empty-string bool (simulating migration state)
        conn = sqlite3.connect(str(tmp_path / 'test.db'))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                schedule_enabled TEXT DEFAULT '',
                schedule_interval_hours INTEGER DEFAULT 168
            )
        """)
        conn.execute(
            "INSERT INTO organizations (name, schedule_enabled, schedule_interval_hours) VALUES (?, ?, ?)",
            ('My Org', "''", 168),
        )
        conn.commit()
        conn.close()

        # This mimics what Grant.analyze() does
        try:
            orgs = OrgModel.list(limit=1)
            data = orgs.get('data', orgs) if isinstance(orgs, dict) else orgs
        except Exception:
            data = []

        assert len(data) > 0, (
            "Organization should be loadable — the bug silently swallows "
            "a ValidationError and reports 'No organization found'"
        )
