"""Message schemas with cursor-based pagination support."""

from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    """Payload to send a new message."""

    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    """Single message in a conversation."""

    id: str
    conversation_id: str
    sender_id: str
    sender_display_name: str = ""
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CursorPaginationParams(BaseModel):
    """
    Cursor-based pagination parameters.

    The cursor encodes (created_at, id) of the last row seen.
    """

    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class MessageListResponse(BaseModel):
    """Cursor-paginated message history."""

    messages: list[MessageResponse]
    next_cursor: str | None = None
    has_more: bool = False
