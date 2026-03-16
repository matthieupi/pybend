"""
Tests for config.py — Configuration values.

Note: The integration test suite overrides config.SQLITE_DB_FILE to point at
a temporary DB.  These tests therefore check the *type* and the *compile-time
defaults* that cannot be altered by the session fixture (BACKEND, VERSION, HOST,
PORT, API_URL, JWT_SECRET format).  SQLITE_DB_FILE is only checked for type,
not exact value, to avoid execution-order dependency (TI-1/UT-1).
"""

import pytest
from n3tx_core import config

pytestmark = pytest.mark.unit



class TestConfig:

    def test_backend_is_fastapi(self):
        assert config.BACKEND == 'fastapi'

    def test_version_is_string(self):
        assert isinstance(config.VERSION, str)

    def test_host(self):
        assert config.HOST == '0.0.0.0'

    def test_port(self):
        assert config.PORT == 5000

    def test_api_url_format(self):
        assert config.API_URL == f'http://localhost:{config.PORT}'

    def test_sqlite_db_file_is_string(self):
        """DB file may be overridden by test fixtures; only check type."""
        assert isinstance(config.SQLITE_DB_FILE, str)
        assert len(config.SQLITE_DB_FILE) > 0

    def test_sqlite_db_file_default_value(self):
        """The source-code default is 'n3tx.db'; integration fixtures may
        override it, so we test by re-reading the module attribute that is
        NOT affected by fixture-level mutation."""
        import importlib, types
        # Read the default from a fresh module load -- but only check
        # the original source default by inspecting the file, not the
        # runtime value, to stay isolated from integration fixtures.
        import inspect, ast, pathlib
        src = pathlib.Path(inspect.getfile(config)).read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'SQLITE_DB_FILE':
                        # The default in source should be the string 'n3tx.db'
                        assert isinstance(node.value, ast.Constant)
                        assert node.value.value == 'n3tx.db'
                        return
        raise AssertionError("SQLITE_DB_FILE not found in config source")

    def test_jwt_secret_is_string(self):
        assert isinstance(config.JWT_SECRET, str)

    def test_jwt_expiry_hours_is_int(self):
        assert isinstance(config.JWT_EXPIRY_HOURS, int)
        assert config.JWT_EXPIRY_HOURS > 0

    def test_jwt_secret_has_default(self):
        assert len(config.JWT_SECRET) > 0

    def test_api_url_contains_port(self):
        assert str(config.PORT) in config.API_URL
