"""Conversation schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    """Payload to create a new conversation."""

    type: str = Field(..., pattern="^(direct|group)$")
    name: str | None = None
    member_ids: list[str] = Field(..., min_length=1)


class MemberInfo(BaseModel):
    """Brief member info within a conversation response."""

    user_id: str
    display_name: str
    is_online: bool = False


class ConversationResponse(BaseModel):
    """Single conversation detail."""

    id: str
    type: str
    name: str | None
    created_at: datetime
    members: list[MemberInfo] = []
    last_message: dict | None = None
    unread_count: int = 0

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    """Paginated list of conversations."""

    conversations: list[ConversationResponse]
    total: int
    has_more: bool


class ReadUpdateRequest(BaseModel):
    """Payload to update read position."""

    message_id: str
