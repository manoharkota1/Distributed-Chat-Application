"""User profile, search, and session management endpoints."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pymongo import ASCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user_id
from app.core.security import hash_password, verify_password
from app.schemas.common import APIResponse
from app.schemas.user import (
    ChangePasswordRequest,
    SessionResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.auth_service import AuthService, AuthServiceError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_current_user(user_id: str = Depends(get_current_user_id), db: AsyncDatabase = Depends(get_db)) -> APIResponse:
    user = await db.users.find_one({"id": user_id})
    if user is None:
        return APIResponse.fail("USER_NOT_FOUND", "User not found")
    return APIResponse.success(UserResponse(id=user["id"], email=user["email"], display_name=user["display_name"], created_at=user["created_at"]).model_dump())


@router.patch("/me")
async def update_profile(
    body: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """Update the current user's profile (display name)."""
    updates: dict = {}
    if body.display_name is not None:
        updates["display_name"] = body.display_name

    if not updates:
        return APIResponse.fail("NO_CHANGES", "No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc)
    await db.users.update_one({"id": user_id}, {"$set": updates})

    user = await db.users.find_one({"id": user_id})
    if user is None:
        return APIResponse.fail("USER_NOT_FOUND", "User not found")

    return APIResponse.success(
        UserResponse(
            id=user["id"],
            email=user["email"],
            display_name=user["display_name"],
            created_at=user["created_at"],
        ).model_dump()
    )


@router.post("/me/password")
async def change_password(
    body: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """Change the current user's password after verifying the current one."""
    user = await db.users.find_one({"id": user_id})
    if user is None:
        return APIResponse.fail("USER_NOT_FOUND", "User not found")

    if not verify_password(body.current_password, user["password_hash"]):
        return APIResponse.fail("INVALID_PASSWORD", "Current password is incorrect")

    if body.current_password == body.new_password:
        return APIResponse.fail("SAME_PASSWORD", "New password must be different from the current password")

    new_hash = hash_password(body.new_password)
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.now(timezone.utc)}},
    )

    return APIResponse.success({"message": "Password changed successfully"})


@router.get("/me/sessions")
async def list_sessions(user_id: str = Depends(get_current_user_id), db: AsyncDatabase = Depends(get_db)) -> APIResponse:
    sessions = await AuthService(db).get_active_sessions(user_id)
    return APIResponse.success([SessionResponse(id=session["id"], device_info=session.get("device_info"), created_at=session["created_at"], expires_at=session["expires_at"]).model_dump() for session in sessions])


@router.delete("/me/sessions/{session_id}")
async def revoke_session(session_id: str, user_id: str = Depends(get_current_user_id), db: AsyncDatabase = Depends(get_db)) -> APIResponse:
    try:
        await AuthService(db).revoke_session(user_id, session_id)
    except AuthServiceError as exc:
        return APIResponse.fail(exc.code, exc.message)
    return APIResponse.success({"message": "Session revoked"})


@router.get("/search")
async def search_users(q: str, user_id: str = Depends(get_current_user_id), db: AsyncDatabase = Depends(get_db)) -> APIResponse:
    pattern = re.escape(q.strip())
    cursor = db.users.find({"$or": [{"email": {"$regex": pattern, "$options": "i"}}, {"display_name": {"$regex": pattern, "$options": "i"}}]}, {"id": 1, "email": 1, "display_name": 1, "created_at": 1}).sort("email", ASCENDING).limit(20)
    users = [user async for user in cursor]
    return APIResponse.success([UserResponse(id=user["id"], email=user["email"], display_name=user["display_name"], created_at=user["created_at"]).model_dump() for user in users])

