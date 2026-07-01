"""
Authentication service — registration, login, token rotation, revocation.

Implements the security design from the README:
- Short-lived JWT access tokens (15 min)
- Opaque 256-bit refresh tokens stored as SHA-256 hashes
- Token rotation with stolen-token reuse detection
- Session listing and remote revocation
"""
from __future__ import annotations


import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User


class AuthServiceError(Exception):
    """Base exception for auth service errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class AuthService:
    """Handles registration, login, token lifecycle, and sessions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Registration ─────────────────────────────────────────────

    async def register(
        self,
        email: str,
        password: str,
        display_name: str,
        device_info: str | None = None,
    ) -> tuple[User, str, str]:
        """
        Create a new user account and issue tokens.

        Returns:
            Tuple of (user, access_token, raw_refresh_token).

        Raises:
            AuthServiceError: If email is already registered.
        """
        # Check for existing email
        existing = await self.db.execute(
            select(User).where(User.email == email)
        )
        if existing.scalar_one_or_none() is not None:
            raise AuthServiceError("EMAIL_EXISTS", "Email is already registered")

        # Create user
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
        )
        self.db.add(user)
        await self.db.flush()  # Assign user.id

        # Issue tokens
        access_token = create_access_token(str(user.id))
        raw_refresh_token = await self._create_refresh_token(
            user.id, device_info
        )

        return user, access_token, raw_refresh_token

    # ── Login ────────────────────────────────────────────────────

    async def login(
        self,
        email: str,
        password: str,
        device_info: str | None = None,
    ) -> tuple[User, str, str]:
        """
        Authenticate with email + password and issue tokens.

        Returns:
            Tuple of (user, access_token, raw_refresh_token).

        Raises:
            AuthServiceError: If credentials are invalid.
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user is None or not verify_password(password, user.password_hash):
            raise AuthServiceError("INVALID_CREDENTIALS", "Invalid email or password")

        access_token = create_access_token(str(user.id))
        raw_refresh_token = await self._create_refresh_token(
            user.id, device_info
        )

        return user, access_token, raw_refresh_token

    # ── Token Refresh (Rotation) ─────────────────────────────────

    async def refresh_tokens(
        self,
        raw_refresh_token: str,
        device_info: str | None = None,
    ) -> tuple[str, str]:
        """
        Rotate the refresh token and issue a new access token.

        Implements the rotation-with-reuse-detection pattern:
        1. Look up the token hash.
        2. If the token is already revoked → reuse detected → revoke entire chain.
        3. Otherwise, revoke the old token and issue a new pair.

        Returns:
            Tuple of (new_access_token, new_raw_refresh_token).

        Raises:
            AuthServiceError: If the token is invalid, expired, or reuse is detected.
        """
        token_hash = hash_refresh_token(raw_refresh_token)

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token_row = result.scalar_one_or_none()

        if token_row is None:
            raise AuthServiceError("INVALID_TOKEN", "Refresh token not found")

        # ── Reuse Detection ──────────────────────────────────────
        if token_row.revoked_at is not None:
            # This token was already used — potential theft!
            # Revoke the entire rotation chain for this user.
            await self._revoke_all_user_tokens(token_row.user_id)
            raise AuthServiceError(
                "TOKEN_REUSE_DETECTED",
                "Refresh token reuse detected — all sessions revoked"
            )

        # ── Expiry Check ─────────────────────────────────────────
        if token_row.expires_at < datetime.now(timezone.utc):
            raise AuthServiceError("TOKEN_EXPIRED", "Refresh token has expired")

        # ── Issue New Tokens ─────────────────────────────────────
        new_raw_token = await self._create_refresh_token(
            token_row.user_id, device_info
        )

        # Get the ID of the new token we just created
        new_hash = hash_refresh_token(new_raw_token)
        new_result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == new_hash)
        )
        new_token_row = new_result.scalar_one()

        # Revoke old token and link to replacement
        token_row.revoked_at = datetime.now(timezone.utc)
        token_row.replaced_by = new_token_row.id
        await self.db.flush()

        access_token = create_access_token(str(token_row.user_id))
        return access_token, new_raw_token

    # ── Logout (Revoke) ──────────────────────────────────────────

    async def logout(self, raw_refresh_token: str) -> None:
        """
        Revoke the current refresh token on logout.

        Raises:
            AuthServiceError: If the token is not found.
        """
        token_hash = hash_refresh_token(raw_refresh_token)

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token_row = result.scalar_one_or_none()

        if token_row is None:
            raise AuthServiceError("INVALID_TOKEN", "Refresh token not found")

        token_row.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ── Sessions ─────────────────────────────────────────────────

    async def get_active_sessions(self, user_id: str) -> list[RefreshToken]:
        """List all active (non-revoked, non-expired) refresh tokens for a user."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == uuid.UUID(user_id),
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_session(self, user_id: str, session_id: str) -> None:
        """
        Revoke a specific session (remote logout).

        Raises:
            AuthServiceError: If the session is not found or doesn't belong to the user.
        """
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.id == uuid.UUID(session_id),
                RefreshToken.user_id == uuid.UUID(user_id),
            )
        )
        token_row = result.scalar_one_or_none()

        if token_row is None:
            raise AuthServiceError("SESSION_NOT_FOUND", "Session not found")

        token_row.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ── Private Helpers ──────────────────────────────────────────

    async def _create_refresh_token(
        self,
        user_id: uuid.UUID,
        device_info: str | None,
    ) -> str:
        """Generate, hash, store, and return a new raw refresh token."""
        raw_token = generate_refresh_token()
        token_hash = hash_refresh_token(raw_token)

        token_row = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            device_info=device_info,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_expire_days),
        )
        self.db.add(token_row)
        await self.db.flush()

        return raw_token

    async def _revoke_all_user_tokens(self, user_id: uuid.UUID) -> None:
        """Revoke every active refresh token for a user (theft response)."""
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self.db.flush()
