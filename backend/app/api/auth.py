"""
Authentication REST endpoints.

Handles registration, login, token refresh, and logout.
Refresh tokens are delivered as httpOnly, Secure, SameSite=Strict cookies.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user_id, get_refresh_token_from_cookie
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.common import APIResponse
from app.services.auth_service import AuthService, AuthServiceError

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie configuration for refresh tokens
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_MAX_AGE = settings.refresh_token_expire_days * 24 * 60 * 60


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Set the refresh token as an httpOnly, Secure, SameSite cookie."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/auth",  # Scoped to auth endpoints only
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/auth",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


@router.post("/register")
async def register(
    body: RegisterRequest,
    response: Response,
    user_agent: str | None = Header(None),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """
    Create a new account and issue access + refresh tokens.

    The refresh token is set as an httpOnly cookie.
    """
    auth_service = AuthService(db)
    try:
        user, access_token, raw_refresh = await auth_service.register(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            device_info=user_agent,
        )
    except AuthServiceError as e:
        return APIResponse.fail(e.code, e.message)

    _set_refresh_cookie(response, raw_refresh)

    return APIResponse.success(
        TokenResponse(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
        ).model_dump()
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    user_agent: str | None = Header(None),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """
    Authenticate with email + password and issue tokens.

    The refresh token is set as an httpOnly cookie.
    """
    auth_service = AuthService(db)
    try:
        user, access_token, raw_refresh = await auth_service.login(
            email=body.email,
            password=body.password,
            device_info=user_agent,
        )
    except AuthServiceError as e:
        return APIResponse.fail(e.code, e.message)

    _set_refresh_cookie(response, raw_refresh)

    return APIResponse.success(
        TokenResponse(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
        ).model_dump()
    )


@router.post("/refresh")
async def refresh(
    response: Response,
    raw_refresh: str = Depends(get_refresh_token_from_cookie),
    user_agent: str | None = Header(None),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """
    Rotate the refresh token and issue a new access token.

    Detects reuse of a stolen token and revokes the entire session chain.
    """
    auth_service = AuthService(db)
    try:
        access_token, new_raw_refresh = await auth_service.refresh_tokens(
            raw_refresh_token=raw_refresh,
            device_info=user_agent,
        )
    except AuthServiceError as e:
        _clear_refresh_cookie(response)
        return APIResponse.fail(e.code, e.message)

    _set_refresh_cookie(response, new_raw_refresh)

    return APIResponse.success(
        TokenResponse(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
        ).model_dump()
    )


@router.post("/logout")
async def logout(
    response: Response,
    raw_refresh: str = Depends(get_refresh_token_from_cookie),
    user_id: str = Depends(get_current_user_id),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """Revoke the current refresh token and clear the cookie."""
    auth_service = AuthService(db)
    try:
        await auth_service.logout(raw_refresh)
    except AuthServiceError as e:
        return APIResponse.fail(e.code, e.message)

    _clear_refresh_cookie(response)
    return APIResponse.success({"message": "Logged out successfully"})
