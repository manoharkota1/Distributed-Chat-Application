"""MongoDB-backed authentication, refresh-token rotation, and sessions."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from pymongo import DESCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


class AuthServiceError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class AuthService:
    def __init__(self, db: AsyncDatabase):
        self.db = db

    async def register(self, email: str, password: str, display_name: str, device_info: str | None = None) -> tuple[dict, str, str]:
        now = datetime.now(timezone.utc)
        user = {
            "id": str(uuid.uuid4()), "email": email.lower(), "password_hash": hash_password(password),
            "display_name": display_name, "created_at": now,
        }
        raw_refresh = generate_refresh_token()
        refresh = self._refresh_document(user["id"], raw_refresh, device_info, now)
        try:
            await self.db.users.insert_one(user)
            await self.db.refresh_tokens.insert_one(refresh)
        except DuplicateKeyError as exc:
            raise AuthServiceError("EMAIL_EXISTS", "Email is already registered") from exc
        return user, create_access_token(user["id"]), raw_refresh

    async def login(self, email: str, password: str, device_info: str | None = None) -> tuple[dict, str, str]:
        user = await self.db.users.find_one({"email": email.lower()})
        if user is None or not verify_password(password, user["password_hash"]):
            raise AuthServiceError("INVALID_CREDENTIALS", "Invalid email or password")
        raw_refresh = generate_refresh_token()
        await self.db.refresh_tokens.insert_one(self._refresh_document(user["id"], raw_refresh, device_info))
        return user, create_access_token(user["id"]), raw_refresh

    async def refresh_tokens(self, raw_refresh_token: str, device_info: str | None = None) -> tuple[str, str]:
        now = datetime.now(timezone.utc)
        token_hash = hash_refresh_token(raw_refresh_token)
        token = await self.db.refresh_tokens.find_one({"token_hash": token_hash})
        if token is None:
            raise AuthServiceError("INVALID_TOKEN", "Refresh token not found")
        if token.get("revoked_at") is not None:
            await self._revoke_all_user_tokens(token["user_id"])
            raise AuthServiceError("TOKEN_REUSE_DETECTED", "Refresh token reuse detected — all sessions revoked")
        if token["expires_at"] < now:
            raise AuthServiceError("TOKEN_EXPIRED", "Refresh token has expired")

        raw_replacement = generate_refresh_token()
        replacement = self._refresh_document(token["user_id"], raw_replacement, device_info, now)
        claimed = await self.db.refresh_tokens.find_one_and_update(
            {"id": token["id"], "revoked_at": None},
            {"$set": {"revoked_at": now, "replaced_by": replacement["id"]}},
            return_document=ReturnDocument.AFTER,
        )
        if claimed is None:
            await self._revoke_all_user_tokens(token["user_id"])
            raise AuthServiceError("TOKEN_REUSE_DETECTED", "Refresh token reuse detected — all sessions revoked")
        await self.db.refresh_tokens.insert_one(replacement)
        return create_access_token(token["user_id"]), raw_replacement

    async def logout(self, raw_refresh_token: str) -> None:
        result = await self.db.refresh_tokens.update_one(
            {"token_hash": hash_refresh_token(raw_refresh_token)},
            {"$set": {"revoked_at": datetime.now(timezone.utc)}},
        )
        if result.matched_count == 0:
            raise AuthServiceError("INVALID_TOKEN", "Refresh token not found")

    async def get_active_sessions(self, user_id: str) -> list[dict]:
        cursor = self.db.refresh_tokens.find({"user_id": user_id, "revoked_at": None, "expires_at": {"$gt": datetime.now(timezone.utc)}}).sort("created_at", DESCENDING)
        return [token async for token in cursor]

    async def revoke_session(self, user_id: str, session_id: str) -> None:
        result = await self.db.refresh_tokens.update_one(
            {"id": session_id, "user_id": user_id},
            {"$set": {"revoked_at": datetime.now(timezone.utc)}},
        )
        if result.matched_count == 0:
            raise AuthServiceError("SESSION_NOT_FOUND", "Session not found")

    def _refresh_document(self, user_id: str, raw_token: str, device_info: str | None, now: datetime | None = None) -> dict:
        created_at = now or datetime.now(timezone.utc)
        return {
            "id": str(uuid.uuid4()), "user_id": user_id, "token_hash": hash_refresh_token(raw_token),
            "device_info": device_info, "created_at": created_at,
            "expires_at": created_at + timedelta(days=settings.refresh_token_expire_days),
            "revoked_at": None, "replaced_by": None,
        }

    async def _revoke_all_user_tokens(self, user_id: str, session=None) -> None:
        await self.db.refresh_tokens.update_many(
            {"user_id": user_id, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc)}},
            session=session,
        )
