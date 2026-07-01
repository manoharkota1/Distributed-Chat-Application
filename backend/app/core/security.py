"""
JWT creation/verification, password hashing, and refresh-token helpers.

Security design follows the README specification:
- Access tokens: short-lived (15 min) JWTs verified by signature only.
- Refresh tokens: 256-bit random strings, stored as SHA-256 hashes.
- Token rotation with stolen-token reuse detection.
"""
from __future__ import annotations


import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Password Hashing ────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Access Tokens ────────────────────────────────────────────

def create_access_token(
    user_id: str,
    extra_claims: dict | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        user_id: Subject claim (the user's UUID as a string).
        extra_claims: Optional additional JWT claims.
        expires_delta: Custom expiration; defaults to settings value.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is malformed or signature invalid.
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token type is not 'access'")
    return payload


# ── Refresh Tokens ───────────────────────────────────────────────

def generate_refresh_token() -> str:
    """Generate a cryptographically secure 256-bit random refresh token."""
    return secrets.token_urlsafe(32)  # 256 bits of entropy


def hash_refresh_token(token: str) -> str:
    """
    SHA-256 hash of the raw refresh token for storage.

    The raw token is NEVER stored — only this hash.
    """
    return hashlib.sha256(token.encode()).hexdigest()
