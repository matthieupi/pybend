# tests/conftest.py

import pytest
from app import app as flask_app
from server.storage.sqlite_storage import SQLiteStorage
from server.utils.registrar import registered_models
import tempfile
import os


@pytest.fixture
def app():
    # Override the database for testing
    db_fd, db_path = tempfile.mkstemp()
    flask_app.config['TESTING'] = True
    storage_backend = SQLiteStorage(database=db_path)

    # Re-register models with the test storage backend
    for model in registered_models.values():
        if hasattr(model, 'set_storage'):
            model.set_storage(storage_backend)
            model.create_table()

    yield flask_app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()
