"""
Unit tests for core security module.

Tests JWT creation/verification, password hashing, and refresh token hashing.
"""

import pytest
from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


class TestPasswordHashing:
    """Tests for bcrypt password hashing."""

    def test_hash_and_verify(self):
        """Hashed password should verify correctly."""
        password = "my_secure_password_123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        """Wrong password should not verify."""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt should produce different hashes (due to salting)."""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # Different salt each time
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWTAccessToken:
    """Tests for JWT access token creation and verification."""

    def test_create_and_decode(self):
        """Should create a valid token and decode it back."""
        user_id = "test-user-123"
        token = create_access_token(user_id)
        payload = decode_access_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    def test_expired_token(self):
        """Expired token should raise ExpiredSignatureError."""
        import jwt as pyjwt

        token = create_access_token(
            "test-user",
            expires_delta=timedelta(seconds=-1),  # Already expired
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_invalid_token(self):
        """Tampered token should raise InvalidTokenError."""
        import jwt as pyjwt

        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token("invalid.token.here")

    def test_extra_claims(self):
        """Extra claims should be included in the token."""
        token = create_access_token(
            "test-user",
            extra_claims={"role": "admin"},
        )
        payload = decode_access_token(token)
        assert payload["role"] == "admin"


class TestRefreshToken:
    """Tests for refresh token generation and hashing."""

    def test_generate_unique_tokens(self):
        """Each generated token should be unique."""
        tokens = {generate_refresh_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_hash_is_deterministic(self):
        """Same token should always produce the same hash."""
        token = "test-refresh-token"
        hash1 = hash_refresh_token(token)
        hash2 = hash_refresh_token(token)
        assert hash1 == hash2

    def test_hash_is_hex(self):
        """Hash should be a 64-char hex string (SHA-256)."""
        token = generate_refresh_token()
        hashed = hash_refresh_token(token)
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_different_tokens_different_hashes(self):
        """Different tokens should produce different hashes."""
        t1 = generate_refresh_token()
        t2 = generate_refresh_token()
        assert hash_refresh_token(t1) != hash_refresh_token(t2)
