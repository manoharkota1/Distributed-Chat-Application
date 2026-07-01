"""
Message service — creation, cursor-based pagination, rate limiting.

Implements the cursor-based pagination design from the README using the
composite index on (conversation_id, created_at DESC, id DESC).
"""
from __future__ import annotations


import base64
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.redis import check_rate_limit
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.user import User


class MessageServiceError(Exception):
    """Base exception for message service errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class MessageService:
    """Handles message creation and retrieval with cursor pagination."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Send Message ─────────────────────────────────────────────

    async def send_message(
        self,
        conversation_id: str,
        sender_id: str,
        content: str,
    ) -> Message:
        """
        Create and persist a new message.

        Validates:
        1. Sender is a member of the conversation.
        2. Rate limit is not exceeded.

        Returns:
            The persisted Message with a generated id and timestamp.

        Raises:
            MessageServiceError: On membership or rate-limit violations.
        """
        convo_uuid = uuid.UUID(conversation_id)
        sender_uuid = uuid.UUID(sender_id)

        # ── Membership Check ─────────────────────────────────────
        membership = await self.db.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == convo_uuid,
                ConversationMember.user_id == sender_uuid,
            )
        )
        if membership.scalar_one_or_none() is None:
            raise MessageServiceError(
                "NOT_A_MEMBER",
                "You are not a member of this conversation"
            )

        # ── Rate Limit ───────────────────────────────────────────
        allowed = await check_rate_limit(sender_id)
        if not allowed:
            raise MessageServiceError(
                "RATE_LIMITED",
                "Message rate limit exceeded. Please wait before sending more messages."
            )

        # ── Persist ──────────────────────────────────────────────
        message = Message(
            conversation_id=convo_uuid,
            sender_id=sender_uuid,
            content=content,
        )
        self.db.add(message)
        await self.db.flush()

        return message

    # ── Cursor-Based Pagination ──────────────────────────────────

    async def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[dict], str | None, bool]:
        """
        Retrieve messages with cursor-based pagination.

        The cursor encodes (created_at_iso, id) of the last row seen.
        Uses the composite index for efficient seeks.

        Args:
            conversation_id: The conversation to fetch messages from.
            user_id: The requesting user (for membership verification).
            cursor: Opaque cursor string, or None for the first page.
            limit: Number of messages per page (1–100).

        Returns:
            Tuple of (messages_list, next_cursor, has_more).

        Raises:
            MessageServiceError: If the user is not a member.
        """
        convo_uuid = uuid.UUID(conversation_id)
        user_uuid = uuid.UUID(user_id)

        # ── Membership Check ─────────────────────────────────────
        membership = await self.db.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == convo_uuid,
                ConversationMember.user_id == user_uuid,
            )
        )
        if membership.scalar_one_or_none() is None:
            raise MessageServiceError(
                "NOT_A_MEMBER",
                "You are not a member of this conversation"
            )

        # ── Build Query ──────────────────────────────────────────
        query = (
            select(Message, User.display_name)
            .join(User, Message.sender_id == User.id)
            .where(Message.conversation_id == convo_uuid)
        )

        # Apply cursor filter
        if cursor:
            cursor_data = self._decode_cursor(cursor)
            if cursor_data:
                cursor_created_at, cursor_id = cursor_data
                query = query.where(
                    and_(
                        Message.created_at <= cursor_created_at,
                        ~and_(
                            Message.created_at == cursor_created_at,
                            Message.id >= uuid.UUID(cursor_id),
                        ),
                    )
                )

        query = (
            query
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit + 1)  # Fetch one extra to detect has_more
        )

        result = await self.db.execute(query)
        rows = result.all()

        # ── Build Response ───────────────────────────────────────
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        messages = []
        for msg, display_name in rows:
            messages.append({
                "id": str(msg.id),
                "conversation_id": str(msg.conversation_id),
                "sender_id": str(msg.sender_id),
                "sender_display_name": display_name,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            })

        next_cursor = None
        if has_more and messages:
            last = messages[-1]
            next_cursor = self._encode_cursor(
                last["created_at"], last["id"]
            )

        return messages, next_cursor, has_more

    # ── Cursor Encoding/Decoding ─────────────────────────────────

    @staticmethod
    def _encode_cursor(created_at_iso: str, message_id: str) -> str:
        """Encode pagination cursor as a base64 JSON string."""
        payload = json.dumps({"c": created_at_iso, "i": message_id})
        return base64.urlsafe_b64encode(payload.encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
        """Decode a cursor back into (created_at, id)."""
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor))
            created_at = datetime.fromisoformat(payload["c"])
            return created_at, payload["i"]
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
