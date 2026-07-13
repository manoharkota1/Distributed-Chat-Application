"""
WebSocket event handlers.

Routes incoming WebSocket events by type and dispatches to the
appropriate handler. Integrates with Redis Pub/Sub for cross-instance
message delivery.
"""
from __future__ import annotations

import json
import logging

from pymongo.asynchronous.database import AsyncDatabase

from app.core.redis import (
    EVENT_CHANNEL,
    clear_typing,
    get_redis,
    set_typing,
)
from app.schemas.websocket import WSEventType, WSMessage
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService, MessageServiceError
from app.ws.manager import manager

logger = logging.getLogger(__name__)


async def handle_ws_message(
    user_id: str,
    raw_data: str,
    db: AsyncDatabase,
) -> None:
    """
    Parse and route an incoming WebSocket message to its handler.

    Args:
        user_id: The authenticated user who sent the message.
        raw_data: Raw JSON string from the WebSocket.
        db: Database session for this request.
    """
    try:
        data = json.loads(raw_data)
        ws_msg = WSMessage(**data)
    except (json.JSONDecodeError, ValueError) as e:
        await manager.send_to_user(user_id, {
            "type": WSEventType.ERROR,
            "payload": {"message": f"Invalid message format: {e}"},
        })
        return

    event_type = ws_msg.type
    payload = ws_msg.payload
    request_id = ws_msg.request_id

    try:
        if event_type == WSEventType.MESSAGE_SEND:
            await _handle_message_send(user_id, payload, request_id, db)
        elif event_type == WSEventType.TYPING_START:
            await _handle_typing_start(user_id, payload)
        elif event_type == WSEventType.TYPING_STOP:
            await _handle_typing_stop(user_id, payload)
        elif event_type == WSEventType.READ_UPDATE:
            await _handle_read_update(user_id, payload, db)
        elif event_type == "ping":
            await manager.send_to_user(user_id, {
                "type": WSEventType.PONG,
                "payload": {},
            })
        else:
            await manager.send_to_user(user_id, {
                "type": WSEventType.ERROR,
                "payload": {"message": f"Unknown event type: {event_type}"},
                "request_id": request_id,
            })
    except Exception as e:
        logger.exception("Error handling WS event %s from user %s", event_type, user_id)
        await manager.send_to_user(user_id, {
            "type": WSEventType.ERROR,
            "payload": {"message": str(e)},
            "request_id": request_id,
        })


async def _handle_message_send(
    user_id: str,
    payload: dict,
    request_id: str | None,
    db: AsyncDatabase,
) -> None:
    """
    Handle message.send: persist → publish to Redis → send ack.

    Flow (from the README):
    1. Persist message to PostgreSQL, get generated id + timestamp.
    2. Publish to Redis channel scoped to the conversation.
    3. Send direct ack back to the sender for optimistic UI reconciliation.
    """
    conversation_id = payload.get("conversation_id")
    content = payload.get("content")
    client_temp_id = payload.get("client_temp_id")

    if not conversation_id or not content:
        await manager.send_to_user(user_id, {
            "type": WSEventType.ERROR,
            "payload": {"message": "conversation_id and content are required"},
            "request_id": request_id,
        })
        return

    service = MessageService(db)
    try:
        message = await service.send_message(
            conversation_id=conversation_id,
            sender_id=user_id,
            content=content,
        )
    except MessageServiceError as e:
        await manager.send_to_user(user_id, {
            "type": WSEventType.ERROR,
            "payload": {"code": e.code, "message": e.message},
            "request_id": request_id,
        })
        return

    # Build the message payload for broadcasting
    msg_payload = {
        "id": message["id"],
        "conversation_id": message["conversation_id"],
        "sender_id": message["sender_id"],
        "content": message["content"],
        "created_at": message["created_at"].isoformat(),
        "client_temp_id": client_temp_id,
    }

    # ── Publish to Redis for cross-instance fanout ────────────
    r = await get_redis()
    await r.publish(EVENT_CHANNEL, json.dumps({
        "type": WSEventType.MESSAGE_NEW,
        "payload": msg_payload,
    }))

    # ── Send ack directly to the sender ───────────────────────
    await manager.send_to_user(user_id, {
        "type": WSEventType.MESSAGE_ACK,
        "payload": {
            **msg_payload,
            "client_temp_id": client_temp_id,
        },
        "request_id": request_id,
    })


async def _handle_typing_start(user_id: str, payload: dict) -> None:
    """Handle typing.start: set Redis TTL key and publish update."""
    conversation_id = payload.get("conversation_id")
    if not conversation_id:
        return

    await set_typing(conversation_id, user_id)

    # Publish typing update via Redis for cross-instance delivery
    r = await get_redis()
    await r.publish(EVENT_CHANNEL, json.dumps({
        "type": WSEventType.TYPING_UPDATE,
        "payload": {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "is_typing": True,
        },
    }))


async def _handle_typing_stop(user_id: str, payload: dict) -> None:
    """Handle typing.stop: clear Redis key and publish update."""
    conversation_id = payload.get("conversation_id")
    if not conversation_id:
        return

    await clear_typing(conversation_id, user_id)

    r = await get_redis()
    await r.publish(EVENT_CHANNEL, json.dumps({
        "type": WSEventType.TYPING_UPDATE,
        "payload": {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "is_typing": False,
        },
    }))


async def _handle_read_update(
    user_id: str, payload: dict, db: AsyncDatabase
) -> None:
    """Handle read.update: update DB and publish receipt."""
    conversation_id = payload.get("conversation_id")
    message_id = payload.get("message_id")
    if not conversation_id or not message_id:
        return

    service = ConversationService(db)
    try:
        await service.update_read_position(conversation_id, user_id, message_id)
    except Exception:
        logger.exception("Failed to update read position")
        return

    # Publish read receipt for cross-instance delivery
    r = await get_redis()
    await r.publish(EVENT_CHANNEL, json.dumps({
        "type": WSEventType.READ_RECEIPT,
        "payload": {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "message_id": message_id,
        },
    }))
