"""Tests for authorize/auth.py — JWT tokens and password hashing."""

import pytest
import time
import jwt as pyjwt

from authorize.auth import (
    configure, hash_password, verify_password,
    create_token, decode_token,
    _jwt_secret, _jwt_expiry_hours,
)


class TestConfigure:

    def test_sets_jwt_secret(self):
        configure(jwt_secret='test-secret-123')
        token = create_token(user_id=1, email='a@b.com')
        decoded = decode_token(token)
        assert decoded['user_id'] == 1
        # Restore
        configure(jwt_secret='authorize-dev-secret-change-in-production')

    def test_sets_expiry_hours(self):
        configure(jwt_expiry_hours=2)
        token = create_token(user_id=1, email='a@b.com')
        decoded = decode_token(token)
        assert decoded['user_id'] == 1
        configure(jwt_expiry_hours=24)

    def test_none_does_not_change(self):
        old_secret = 'known-test-secret'
        configure(jwt_secret=old_secret)
        configure(jwt_secret=None)  # Should not change
        token = create_token(user_id=1, email='a@b.com')
        decoded = pyjwt.decode(token, old_secret, algorithms=['HS256'])
        assert decoded['user_id'] == 1
        configure(jwt_secret='authorize-dev-secret-change-in-production')

    def test_multiple_calls(self):
        configure(jwt_secret='first')
        configure(jwt_secret='second')
        token = create_token(user_id=1, email='a@b.com')
        decoded = pyjwt.decode(token, 'second', algorithms=['HS256'])
        assert decoded['user_id'] == 1
        configure(jwt_secret='authorize-dev-secret-change-in-production')


class TestHashPassword:

    def test_returns_string(self):
        h = hash_password('hello')
        assert isinstance(h, str)

    def test_different_from_plain(self):
        h = hash_password('hello')
        assert h != 'hello'

    def test_different_salts(self):
        h1 = hash_password('hello')
        h2 = hash_password('hello')
        assert h1 != h2  # bcrypt uses random salt

    def test_empty_string(self):
        h = hash_password('')
        assert isinstance(h, str)
        assert len(h) > 0

    def test_unicode_chars(self):
        h = hash_password('pässwörd')
        assert isinstance(h, str)

    def test_long_password(self):
        # bcrypt truncates at 72 bytes; verify it still works within that limit
        h = hash_password('a' * 72)
        assert isinstance(h, str)


class TestVerifyPassword:

    def test_correct_password(self):
        h = hash_password('secret')
        assert verify_password('secret', h) is True

    def test_wrong_password(self):
        h = hash_password('secret')
        assert verify_password('wrong', h) is False

    def test_empty_password(self):
        h = hash_password('')
        assert verify_password('', h) is True

    def test_empty_vs_nonempty(self):
        h = hash_password('secret')
        assert verify_password('', h) is False

    def test_case_sensitive(self):
        h = hash_password('Secret')
        assert verify_password('secret', h) is False


class TestCreateToken:

    def setup_method(self):
        configure(jwt_secret='test-create-token', jwt_expiry_hours=1)

    def teardown_method(self):
        configure(jwt_secret='authorize-dev-secret-change-in-production', jwt_expiry_hours=24)

    def test_returns_string(self):
        token = create_token(user_id=1, email='a@b.com')
        assert isinstance(token, str)

    def test_contains_user_id(self):
        token = create_token(user_id=42, email='a@b.com')
        decoded = decode_token(token)
        assert decoded['user_id'] == 42

    def test_contains_email(self):
        token = create_token(user_id=1, email='test@example.com')
        decoded = decode_token(token)
        assert decoded['email'] == 'test@example.com'

    def test_default_role(self):
        token = create_token(user_id=1, email='a@b.com')
        decoded = decode_token(token)
        assert decoded['role'] == 'user'

    def test_custom_role(self):
        token = create_token(user_id=1, email='a@b.com', role='admin')
        decoded = decode_token(token)
        assert decoded['role'] == 'admin'

    def test_has_exp(self):
        token = create_token(user_id=1, email='a@b.com')
        decoded = decode_token(token)
        assert 'exp' in decoded

    def test_has_iat(self):
        token = create_token(user_id=1, email='a@b.com')
        decoded = decode_token(token)
        assert 'iat' in decoded

    def test_user_id_zero(self):
        token = create_token(user_id=0, email='a@b.com')
        decoded = decode_token(token)
        assert decoded['user_id'] == 0


class TestDecodeToken:

    def setup_method(self):
        configure(jwt_secret='test-decode-token', jwt_expiry_hours=1)

    def teardown_method(self):
        configure(jwt_secret='authorize-dev-secret-change-in-production', jwt_expiry_hours=24)

    def test_valid_token(self):
        token = create_token(user_id=1, email='a@b.com')
        decoded = decode_token(token)
        assert decoded['user_id'] == 1
        assert decoded['email'] == 'a@b.com'

    def test_expired_token(self):
        configure(jwt_expiry_hours=0)
        # Create a token that expires immediately
        payload = {
            'user_id': 1, 'email': 'a@b.com', 'role': 'user',
            'exp': 0, 'iat': 0,
        }
        token = pyjwt.encode(payload, 'test-decode-token', algorithm='HS256')
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token)

    def test_tampered_token(self):
        token = create_token(user_id=1, email='a@b.com')
        # Tamper with the token
        tampered = token[:-5] + 'XXXXX'
        with pytest.raises(Exception):  # InvalidSignatureError or DecodeError
            decode_token(tampered)

    def test_malformed_token(self):
        with pytest.raises(Exception):
            decode_token('not.a.valid.token.at.all')

    def test_wrong_secret(self):
        configure(jwt_secret='secret-a')
        token = create_token(user_id=1, email='a@b.com')
        configure(jwt_secret='secret-b')
        with pytest.raises(Exception):
            decode_token(token)
