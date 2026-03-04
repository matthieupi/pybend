"""
Test plan for authorize/auth.py edge cases
===========================================

JWT EDGE CASES — Token validation boundaries
  - test_token_with_wrong_algorithm_rejected
  - test_token_with_missing_user_id_claim
  - test_token_with_missing_email_claim
  - test_token_decode_with_wrong_secret_fails
  - test_token_expiration_boundary_just_expired
  - test_token_expiration_boundary_just_valid

PASSWORD HASHING
  - test_password_hash_roundtrip
  - test_empty_password_hash_and_verify
  - test_unicode_password_handling
  - test_password_case_sensitive_verification
  - test_wrong_password_fails_verification
  - test_hash_produces_different_salts

EDGE CASES
  - test_create_token_user_id_zero
  - test_decode_token_empty_string
  - test_verify_password_empty_vs_nonempty
"""

import pytest
import time
import jwt as pyjwt

from pybend.core.authorize.auth import (
    configure, hash_password, verify_password,
    create_token, decode_token,
)
from pybend.core import config as _config

pytestmark = pytest.mark.unit

# Restore to pybend config secret after tests
_RESTORE_SECRET = _config.JWT_SECRET
_RESTORE_EXPIRY = _config.JWT_EXPIRY_HOURS


# ===================================================================
# JWT EDGE CASES
# ===================================================================

class TestJWTEdgeCases:
    """JWT token validation edge cases."""

    def setup_method(self):
        configure(jwt_secret='test-edge-cases', jwt_expiry_hours=1)

    def teardown_method(self):
        configure(jwt_secret=_RESTORE_SECRET, jwt_expiry_hours=_RESTORE_EXPIRY)

    def test_token_with_wrong_algorithm_rejected(self):
        """Tokens signed with wrong algorithm should be rejected."""
        payload = {
            'user_id': 1,
            'email': 'test@example.com',
            'role': 'user',
            'exp': int(time.time()) + 3600,
            'iat': int(time.time()),
        }
        # Sign with HS512 instead of HS256
        token = pyjwt.encode(payload, 'test-edge-cases', algorithm='HS512')

        with pytest.raises(Exception):  # InvalidAlgorithmError or DecodeError
            decode_token(token)

    def test_token_with_missing_user_id_claim(self):
        """Tokens without user_id claim should decode but have None user_id."""
        payload = {
            'email': 'test@example.com',
            'role': 'user',
            'exp': int(time.time()) + 3600,
            'iat': int(time.time()),
        }
        token = pyjwt.encode(payload, 'test-edge-cases', algorithm='HS256')

        decoded = decode_token(token)
        assert 'user_id' not in decoded
        assert decoded['email'] == 'test@example.com'

    def test_token_with_missing_email_claim(self):
        """Tokens without email claim should decode but have None email."""
        payload = {
            'user_id': 1,
            'role': 'user',
            'exp': int(time.time()) + 3600,
            'iat': int(time.time()),
        }
        token = pyjwt.encode(payload, 'test-edge-cases', algorithm='HS256')

        decoded = decode_token(token)
        assert decoded['user_id'] == 1
        assert 'email' not in decoded

    def test_token_decode_with_wrong_secret_fails(self):
        """Tokens signed with different secret should be rejected."""
        configure(jwt_secret='secret-a')
        token = create_token(user_id=1, email='test@example.com')

        configure(jwt_secret='secret-b')
        with pytest.raises(Exception):  # InvalidSignatureError
            decode_token(token)

    def test_token_expiration_boundary_just_expired(self):
        """Token that just expired should be rejected."""
        # Create a token that expires in the past
        payload = {
            'user_id': 1,
            'email': 'test@example.com',
            'role': 'user',
            'exp': int(time.time()) - 1,  # 1 second ago
            'iat': int(time.time()) - 3600,
        }
        token = pyjwt.encode(payload, 'test-edge-cases', algorithm='HS256')

        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token)

    def test_token_expiration_boundary_just_valid(self):
        """Token that expires in 1 second should still be valid."""
        payload = {
            'user_id': 1,
            'email': 'test@example.com',
            'role': 'user',
            'exp': int(time.time()) + 1,  # 1 second from now
            'iat': int(time.time()),
        }
        token = pyjwt.encode(payload, 'test-edge-cases', algorithm='HS256')

        decoded = decode_token(token)
        assert decoded['user_id'] == 1


# ===================================================================
# PASSWORD HASHING
# ===================================================================

class TestPasswordHashing:
    """Password hashing and verification edge cases."""

    def test_password_hash_roundtrip(self):
        """Hash then verify should succeed."""
        password = 'my-secure-password'
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_empty_password_hash_and_verify(self):
        """Empty password should hash and verify correctly."""
        hashed = hash_password('')
        assert verify_password('', hashed) is True

    def test_unicode_password_handling(self):
        """Unicode characters in passwords should work."""
        password = 'pässwörd-日本語-🔐'
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_password_case_sensitive_verification(self):
        """Password verification is case-sensitive."""
        hashed = hash_password('Secret')
        assert verify_password('secret', hashed) is False
        assert verify_password('SECRET', hashed) is False
        assert verify_password('Secret', hashed) is True

    def test_wrong_password_fails_verification(self):
        """Wrong password should fail verification."""
        hashed = hash_password('correct-password')
        assert verify_password('wrong-password', hashed) is False

    def test_hash_produces_different_salts(self):
        """Same password should produce different hashes due to random salt."""
        hash1 = hash_password('password')
        hash2 = hash_password('password')
        assert hash1 != hash2

    def test_verify_password_empty_vs_nonempty(self):
        """Empty password should not verify against non-empty hash."""
        hashed = hash_password('nonempty')
        assert verify_password('', hashed) is False

    def test_long_password_within_bcrypt_limit(self):
        """Passwords within bcrypt's 72-byte limit should work."""
        # bcrypt truncates at 72 bytes
        password = 'a' * 72
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


# ===================================================================
# EDGE CASES
# ===================================================================

class TestTokenEdgeCases:
    """Edge cases in token creation and decoding."""

    def setup_method(self):
        configure(jwt_secret='test-token-edge', jwt_expiry_hours=1)

    def teardown_method(self):
        configure(jwt_secret=_RESTORE_SECRET, jwt_expiry_hours=_RESTORE_EXPIRY)

    def test_create_token_user_id_zero(self):
        """user_id=0 should be allowed (edge case for system users)."""
        token = create_token(user_id=0, email='system@example.com')
        decoded = decode_token(token)
        assert decoded['user_id'] == 0

    def test_decode_token_empty_string(self):
        """Empty token string should raise exception."""
        with pytest.raises(Exception):
            decode_token('')

    def test_decode_token_malformed_no_dots(self):
        """Malformed token without dots should raise exception."""
        with pytest.raises(Exception):
            decode_token('not-a-jwt-token')

    def test_decode_token_tampered_signature(self):
        """Tampered signature should be rejected."""
        token = create_token(user_id=1, email='test@example.com')
        # Tamper with the signature part
        parts = token.split('.')
        tampered = '.'.join(parts[:2] + ['INVALID_SIGNATURE'])

        with pytest.raises(Exception):  # InvalidSignatureError
            decode_token(tampered)

    def test_create_token_with_special_characters_in_email(self):
        """Email with special characters should encode correctly."""
        email = 'user+tag@example.com'
        token = create_token(user_id=1, email=email)
        decoded = decode_token(token)
        assert decoded['email'] == email
