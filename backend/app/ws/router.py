"""
WebSocket router — the single persistent connection endpoint.

Clients connect at ``wss://.../ws?token=<jwt>``. Authentication is
performed at handshake time before the connection is accepted.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session, async_session_factory
from app.core.security import decode_access_token
from app.services.presence_service import PresenceService
from app.ws.handlers import handle_ws_message
from app.ws.manager import manager

import jwt as pyjwt

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    """
    WebSocket endpoint with JWT authentication at handshake.

    The client must provide a valid JWT access token as a query parameter.
    If the token is invalid or expired, the connection is rejected.
    """
    # ── Authenticate Before Accepting ────────────────────────
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token payload")
            return
    except pyjwt.ExpiredSignatureError:
        await websocket.close(code=4001, reason="Token expired")
        return
    except pyjwt.InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # ── Accept Connection ────────────────────────────────────
    await websocket.accept()
    await manager.connect(user_id, websocket)

    # Set user online
    await PresenceService.set_online(user_id)

    logger.info("WebSocket connected: user %s", user_id)

    try:
        while True:
            # Receive message and handle it
            raw_data = await websocket.receive_text()

            # Use a fresh DB session for each message
            async with async_session_factory() as db:
                try:
                    await handle_ws_message(user_id, raw_data, db)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.exception(
                        "Error processing WS message from user %s", user_id
                    )

            # Refresh presence on every message (heartbeat)
            await PresenceService.set_online(user_id)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user %s", user_id)
    except Exception:
        logger.exception("WebSocket error for user %s", user_id)
    finally:
        await manager.disconnect(user_id, websocket)
        await PresenceService.set_offline(user_id)
