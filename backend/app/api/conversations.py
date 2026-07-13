"""
Conversation REST endpoints.

Handles conversation CRUD, message history, and read position updates.
All endpoints verify membership before returning data.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user_id
from app.schemas.common import APIResponse
from app.schemas.conversation import ConversationCreate, ReadUpdateRequest
from app.schemas.message import MessageCreate
from app.services.conversation_service import ConversationService, ConversationServiceError
from app.services.message_service import MessageService, MessageServiceError

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """Get paginated list of the user's conversations."""
    service = ConversationService(db)
    conversations, total = await service.get_user_conversations(
        user_id, offset, limit
    )

    return APIResponse.success({
        "conversations": conversations,
        "total": total,
        "has_more": offset + limit < total,
    })


@router.post("")
async def create_conversation(
    body: ConversationCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """Create a new direct or group conversation."""
    service = ConversationService(db)
    try:
        convo = await service.create_conversation(
            creator_id=user_id,
            conversation_type=body.type,
            name=body.name,
            member_ids=body.member_ids,
        )
    except ConversationServiceError as e:
        return APIResponse.fail(e.code, e.message)

    return APIResponse.success({
        "id": convo["id"],
        "type": convo["type"],
        "name": convo.get("name"),
        "created_at": convo["created_at"].isoformat(),
    })


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """Get cursor-paginated message history for a conversation."""
    service = MessageService(db)
    try:
        messages, next_cursor, has_more = await service.get_messages(
            conversation_id=conversation_id,
            user_id=user_id,
            cursor=cursor,
            limit=limit,
        )
    except MessageServiceError as e:
        return APIResponse.fail(e.code, e.message)

    return APIResponse.success({
        "messages": messages,
        "next_cursor": next_cursor,
        "has_more": has_more,
    })


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: MessageCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """Send a message via REST (fallback path — WebSocket is preferred)."""
    service = MessageService(db)
    try:
        message = await service.send_message(
            conversation_id=conversation_id,
            sender_id=user_id,
            content=body.content,
        )
    except MessageServiceError as e:
        return APIResponse.fail(e.code, e.message)

    return APIResponse.success({
        "id": message["id"],
        "conversation_id": message["conversation_id"],
        "sender_id": message["sender_id"],
        "content": message["content"],
        "created_at": message["created_at"].isoformat(),
    })


@router.patch("/{conversation_id}/read")
async def update_read_position(
    conversation_id: str,
    body: ReadUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncDatabase = Depends(get_db),
) -> APIResponse:
    """Update the caller's last-read message in a conversation."""
    service = ConversationService(db)
    try:
        await service.update_read_position(
            conversation_id=conversation_id,
            user_id=user_id,
            message_id=body.message_id,
        )
    except ConversationServiceError as e:
        return APIResponse.fail(e.code, e.message)

    return APIResponse.success({"message": "Read position updated"})
