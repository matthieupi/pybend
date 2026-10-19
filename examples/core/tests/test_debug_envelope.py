"""
Test plan for debug envelope feature — integration tests via HTTP
=================================================================

These tests hit the FastAPI application using TestClient and verify that the
debug envelope wrapping produced by @expose_route behaves correctly at the
HTTP boundary.

NOTE: Code bug found during test writing.
  Methods annotated with a non-dict return type (e.g. `-> str`) that are
  registered with `response_model=str` will produce a 500 when DEBUG=True,
  because the route layer's `response_model` validation rejects the dict
  envelope. Only methods annotated `-> dict` (or with no response_model) pass
  through correctly.
  Affected: Product.comment (-> str), Product.favorite (-> str)
  Working: BaseUser.login (-> dict), BaseUser.register_user (-> dict)

DEBUG=True envelope via classmethod (login -> dict)
  - test_login_with_debug_true_returns_envelope
  - test_login_envelope_contains_result_and_debug_keys
  - test_login_envelope_top_level_has_exactly_two_keys
  - test_login_envelope_result_contains_token_and_user
  - test_login_envelope_debug_method_name_is_login
  - test_login_envelope_debug_model_name_is_user_class
  - test_login_envelope_debug_instance_id_is_none
  - test_login_envelope_debug_duration_ms_is_nonnegative
  - test_login_envelope_debug_section_has_exactly_four_keys

DEBUG=False — login returns raw result
  - test_login_with_debug_false_returns_raw_result
  - test_login_debug_false_no_envelope_keys
  - test_login_debug_false_no_result_key

Classmethod register (-> dict)
  - test_register_debug_true_returns_envelope
  - test_register_debug_true_method_name_is_register_user
  - test_register_debug_true_instance_id_is_none

str-returning instance method regression (code bug)
  - test_str_returning_method_debug_true_returns_500_due_to_response_model_mismatch

DEBUG toggle — opposite behaviors
  - test_debug_false_gives_raw_dict_debug_true_gives_envelope
"""

import json
import pytest

from helpers import auth_header
from n3tx_core import config as n3tx_config

pytestmark = pytest.mark.integration


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def _restore_debug():
    """Ensure config.DEBUG is always restored to False after each test.

    The integration conftest sets DEBUG=False after app import.
    Individual tests in this file opt-in to DEBUG=True explicitly.
    """
    original = n3tx_config.DEBUG
    yield
    n3tx_config.DEBUG = original


@pytest.fixture
def debug_on():
    """Enable DEBUG mode for the duration of a single test."""
    n3tx_config.DEBUG = True
    yield
    n3tx_config.DEBUG = False


# ===================================================================
# Classmethod (login -> dict) — DEBUG=True returns envelope
# ===================================================================

class TestLoginDebugEnvelope:
    """POST /users/login with DEBUG=True returns a debug envelope.

    login() is annotated -> dict. The route layer registers it with
    response_model=dict, which is compatible with the envelope dict.
    """

    def test_login_with_debug_true_returns_envelope(self, client, seed_data, debug_on):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert 'data' in data
        assert '_debug' in data

    def test_login_envelope_contains_result_and_debug_keys(
        self, client, seed_data, debug_on
    ):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data = resp.json()
        assert set(data.keys()) == {'data', '_debug'}

    def test_login_envelope_top_level_has_exactly_two_keys(
        self, client, seed_data, debug_on
    ):
        resp = client.post("/users/login", json={
            "email": "bob@example.com",
            "password": "bob123",
        })
        data = resp.json()
        assert len(data) == 2

    def test_login_envelope_result_contains_token_and_user(
        self, client, seed_data, debug_on
    ):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data = resp.json()
        result = data['data']
        assert 'token' in result
        assert 'user' in result

    def test_login_envelope_debug_method_name_is_login(
        self, client, seed_data, debug_on
    ):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data = resp.json()
        assert data['_debug']['method'] == 'login'

    def test_login_envelope_debug_model_name_is_user_class(
        self, client, seed_data, debug_on
    ):
        """For a classmethod, model is the class name (User), not an instance type."""
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data = resp.json()
        assert data['_debug']['model'] == 'User'

    def test_login_envelope_debug_instance_id_is_none(
        self, client, seed_data, debug_on
    ):
        """Classmethods have no self.id, so instance_id must be None."""
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data = resp.json()
        assert data['_debug']['instance_id'] is None

    def test_login_envelope_debug_duration_ms_is_nonnegative(
        self, client, seed_data, debug_on
    ):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data = resp.json()
        assert isinstance(data['_debug']['duration_ms'], (int, float))
        assert data['_debug']['duration_ms'] >= 0

    def test_login_envelope_debug_section_has_exactly_four_keys(
        self, client, seed_data, debug_on
    ):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data = resp.json()
        assert set(data['_debug'].keys()) == {'method', 'model', 'instance_id', 'duration_ms'}


# ===================================================================
# Classmethod (login -> dict) — DEBUG=False returns raw result
# ===================================================================

class TestLoginDebugFalse:
    """POST /users/login returns the original dict when DEBUG=False."""

    def test_login_with_debug_false_returns_raw_result(self, client, seed_data):
        n3tx_config.DEBUG = False
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'token' in data
        assert 'user' in data

    def test_login_debug_false_no_envelope_keys(self, client, seed_data):
        n3tx_config.DEBUG = False
        resp = client.post("/users/login", json={
            "email": "bob@example.com",
            "password": "bob123",
        })
        data = resp.json()
        assert '_debug' not in data

    def test_login_debug_false_no_envelope_key(self, client, seed_data):
        n3tx_config.DEBUG = False
        resp = client.post("/users/login", json={
            "email": "charlie@example.com",
            "password": "charlie123",
        })
        data = resp.json()
        # Raw login response has 'token' and 'user', not envelope keys
        assert '_debug' not in data


# ===================================================================
# Classmethod register_user (-> dict) — DEBUG=True returns envelope
# ===================================================================

class TestRegisterDebugEnvelope:
    """POST /users/register with DEBUG=True returns a debug envelope."""

    def test_register_debug_true_returns_envelope(self, client, debug_on):
        resp = client.post("/users/register", json={
            "name": "debugregtest",
            "email": "debugregtest@example.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'data' in data
        assert '_debug' in data

    def test_register_debug_true_method_name_is_register_user(self, client, debug_on):
        resp = client.post("/users/register", json={
            "name": "methodtest",
            "email": "methodtest@example.com",
            "password": "pass123",
        })
        data = resp.json()
        assert data['_debug']['method'] == 'register_user'

    def test_register_debug_true_instance_id_is_none(self, client, debug_on):
        """register_user is a classmethod, so instance_id must be None."""
        resp = client.post("/users/register", json={
            "name": "instancetest",
            "email": "instancetest@example.com",
            "password": "pass123",
        })
        data = resp.json()
        assert data['_debug']['instance_id'] is None

    def test_register_debug_true_result_has_token_and_user(self, client, debug_on):
        resp = client.post("/users/register", json={
            "name": "resulttest",
            "email": "resulttest@example.com",
            "password": "pass123",
        })
        data = resp.json()
        result = data['data']
        assert 'token' in result
        assert 'user' in result


# ===================================================================
# Code bug regression: str-returning instance methods with DEBUG=True
# ===================================================================

class TestStrReturningMethod:
    """Test that str-annotated @expose_route methods work with debug envelope.

    register_routes() uses response_model=None when DEBUG=True so the dict
    envelope passes through FastAPI's response validation without error.
    """

    def test_str_returning_method_debug_true_returns_envelope(
        self, client, alice_token, seed_data, debug_on
    ):
        """Product.comment() is annotated -> str. With DEBUG=True the envelope
        passes through because response_model is disabled in debug mode.
        """
        product = seed_data["products"][0]
        resp = client.post(
            f"/Product/{product.id}/comment",
            json={"comment": {"name": "Debug test", "description": "Works now"}},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert '_debug' in data
        assert 'data' in data

    def test_str_returning_method_debug_false_returns_200(
        self, client, alice_token, seed_data
    ):
        """With DEBUG=False, Product.comment() works correctly (no envelope)."""
        n3tx_config.DEBUG = False
        product = seed_data["products"][0]
        resp = client.post(
            f"/Product/{product.id}/comment",
            json={"comment": {"name": "No debug", "description": "Should work"}},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200


# ===================================================================
# DEBUG toggle — switching changes behavior
# ===================================================================

class TestDebugToggle:
    """Turning DEBUG on/off between requests produces different response shapes."""

    def test_debug_false_gives_raw_dict_debug_true_gives_envelope(
        self, client, seed_data
    ):
        """Same endpoint, same credentials — different DEBUG flag → different shape."""
        n3tx_config.DEBUG = False
        resp_off = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data_off = resp_off.json()

        n3tx_config.DEBUG = True
        resp_on = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data_on = resp_on.json()

        # DEBUG=False: raw dict with token and user
        assert 'token' in data_off
        assert '_debug' not in data_off

        # DEBUG=True: envelope with data and _debug
        assert 'data' in data_on
        assert '_debug' in data_on

    def test_invalid_credentials_debug_true_still_returns_401(
        self, client, seed_data, debug_on
    ):
        """Exceptions (HTTPException) raised inside the method propagate correctly
        even with DEBUG=True. The debug envelope only wraps successful returns."""
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
