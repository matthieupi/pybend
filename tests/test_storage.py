# tests/test_storage.py
import sqlite3

import pytest
import os
from server.storage.sqlite_storage import SQLiteStorage
from server.models.user_model import User

@pytest.fixture
def sqlite_storage(tmp_path):
    db_path = tmp_path / "test_database.db"
    storage = SQLiteStorage(database=str(db_path))
    return storage

def test_sqlite_storage_create_table(sqlite_storage):
    sqlite_storage.create_table(User)
    # Verify the table was created
    conn = sqlite3.connect(sqlite_storage.database)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    table = cursor.fetchone()
    conn.close()
    assert table is not None

def test_sqlite_storage_crud_operations(sqlite_storage):
    sqlite_storage.create_table(User)
    # Create
    user_data = {"name": "Bob", "email": "bob@example.com", "age": 25}
    user = User(**user_data)
    created_user = sqlite_storage.create(User, user.model_dump())
    assert created_user.id is not None

    # Read
    fetched_user = sqlite_storage.get(User, created_user.id)
    assert fetched_user.email == "bob@example.com"

    # Update
    updated_data = {"name": "Bobby"}
    sqlite_storage.update(User, created_user.id, updated_data)
    updated_user = sqlite_storage.get(User, created_user.id)
    assert updated_user.name == "Bobby"

    # Delete
    sqlite_storage.delete(User, created_user.id)
    deleted_user = sqlite_storage.get(User, created_user.id)
    assert deleted_user is None
