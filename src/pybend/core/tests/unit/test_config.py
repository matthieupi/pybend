"""
Tests for config.py — Configuration values.
"""

import config


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

    def test_sqlite_db_file(self):
        assert isinstance(config.SQLITE_DB_FILE, str)
        assert config.SQLITE_DB_FILE == 'pybend.db'

    def test_jwt_secret_is_string(self):
        assert isinstance(config.JWT_SECRET, str)

    def test_jwt_expiry_hours_is_int(self):
        assert isinstance(config.JWT_EXPIRY_HOURS, int)
        assert config.JWT_EXPIRY_HOURS > 0

    def test_jwt_secret_has_default(self):
        assert len(config.JWT_SECRET) > 0

    def test_api_url_contains_port(self):
        assert str(config.PORT) in config.API_URL
