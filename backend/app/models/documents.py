"""Typed MongoDB document shapes used by the persistence services."""
from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class Collections:
    USERS = "users"
    REFRESH_TOKENS = "refresh_tokens"
    CONVERSATIONS = "conversations"
    MESSAGES = "messages"


class UserDocument(TypedDict):
    id: str
    email: str
    password_hash: str
    display_name: str
    created_at: datetime


class RefreshTokenDocument(TypedDict):
    id: str
    user_id: str
    token_hash: str
    device_info: str | None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    replaced_by: str | None


class ConversationMemberDocument(TypedDict):
    user_id: str
    last_read_message_id: str | None
    joined_at: datetime


class ConversationDocument(TypedDict):
    id: str
    type: str
    name: str | None
    member_ids: list[str]
    direct_key: str | None
    created_at: datetime
    members: list[ConversationMemberDocument]


class MessageDocument(TypedDict):
    id: str
    conversation_id: str
    sender_id: str
    content: str
    created_at: datetime
