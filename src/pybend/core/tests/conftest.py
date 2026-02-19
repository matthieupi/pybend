# tests/conftest.py

import pytest
import tempfile
import os

import config
from storage.sqlite_storage import SQLiteStorage
from utils.registrar import registered_models


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    """Every test gets its own temporary database. The real DB is never touched."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    # Redirect config so nothing can accidentally use the real DB
    monkeypatch.setattr(config, 'SQLITE_DB_FILE', db_path)

    storage_backend = SQLiteStorage(database=db_path)

    # Re-register models with the test storage backend
    for model in registered_models.values():
        if hasattr(model, 'set_storage'):
            model.set_storage(storage_backend)
            model.create_table()

    yield db_path

    os.close(db_fd)
    os.unlink(db_path)
