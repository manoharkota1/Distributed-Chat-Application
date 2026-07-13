"""
FastAPI dependencies for authentication and shared resources.
"""
from __future__ import annotations

import jwt as pyjwt
from fastapi import Cookie, Header, HTTPException, Query, status

from app.core.security import decode_access_token


async def get_current_user_id(
    authorization: str | None = Header(None),
    token: str | None = Query(None, alias="token"),
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
    except pyjwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


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
