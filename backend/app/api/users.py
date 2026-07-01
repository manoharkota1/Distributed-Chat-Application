"""
User REST endpoints — profile and session management.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user_id
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.user import SessionResponse, UserResponse
from app.services.auth_service import AuthService, AuthServiceError

from sqlalchemy import select

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> APIResponse:
    """Get the current authenticated user's profile."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return APIResponse.fail("USER_NOT_FOUND", "User not found")

    return APIResponse.success(
        UserResponse(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            created_at=user.created_at,
        ).model_dump()
    )


@router.get("/me/sessions")
async def list_sessions(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> APIResponse:
    """List all active sessions (non-revoked, non-expired refresh tokens)."""
    auth_service = AuthService(db)
    sessions = await auth_service.get_active_sessions(user_id)

    return APIResponse.success([
        SessionResponse(
            id=str(s.id),
            device_info=s.device_info,
            created_at=s.created_at,
            expires_at=s.expires_at,
        ).model_dump()
        for s in sessions
    ])


@router.delete("/me/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> APIResponse:
    """Revoke a specific session (remote logout for a device)."""
    auth_service = AuthService(db)
    try:
        await auth_service.revoke_session(user_id, session_id)
    except AuthServiceError as e:
        return APIResponse.fail(e.code, e.message)

    return APIResponse.success({"message": "Session revoked"})


@router.get("/search")
async def search_users(
    q: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> APIResponse:
    """Search users by email or display name (for adding to conversations)."""
    result = await db.execute(
        select(User)
        .where(
            (User.email.ilike(f"%{q}%")) | (User.display_name.ilike(f"%{q}%"))
        )
        .limit(20)
    )
    users = result.scalars().all()

    return APIResponse.success([
        UserResponse(
            id=str(u.id),
            email=u.email,
            display_name=u.display_name,
            created_at=u.created_at,
        ).model_dump()
        for u in users
    ])
