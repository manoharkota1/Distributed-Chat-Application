"""
FastAPI dependencies for authentication and shared resources.
"""
from __future__ import annotations


from fastapi import Cookie, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

import jwt as pyjwt

from app.core.config import settings
from app.core.database import get_db_session
from app.core.security import decode_access_token


async def get_current_user_id(
    authorization: str | None = None,
    token: str | None = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db_session),
) -> str:
    """
    Extract and verify the current user ID from a JWT access token.

    Accepts the token from:
    1. ``Authorization: Bearer <token>`` header (REST endpoints)
    2. ``?token=<jwt>`` query parameter (WebSocket handshake)

    Raises:
        HTTPException 401: If the token is missing, expired, or invalid.
    """
    raw_token: str | None = None

    # Try Authorization header first
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]
    # Fall back to query parameter (WebSocket handshake)
    elif token:
        raw_token = token

    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(raw_token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return user_id
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_refresh_token_from_cookie(
    refresh_token: str | None = Cookie(None),
) -> str:
    """
    Extract the refresh token from the httpOnly cookie.

    Raises:
        HTTPException 401: If no refresh token cookie is present.
    """
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )
    return refresh_token
