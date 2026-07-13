"""MongoDB message persistence with membership checks and cursor pagination."""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone

from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.core.redis import check_rate_limit


class MessageServiceError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class MessageService:
    def __init__(self, db: AsyncDatabase):
        self.db = db

    async def send_message(self, conversation_id: str, sender_id: str, content: str) -> dict:
        if not await self.db.conversations.find_one({"id": conversation_id, "member_ids": sender_id}, {"_id": 1}):
            raise MessageServiceError("NOT_A_MEMBER", "You are not a member of this conversation")
        if not await check_rate_limit(sender_id):
            raise MessageServiceError("RATE_LIMITED", "Message rate limit exceeded. Please wait before sending more messages.")
        message = {"id": str(uuid.uuid4()), "conversation_id": conversation_id, "sender_id": sender_id, "content": content, "created_at": datetime.now(timezone.utc)}
        await self.db.messages.insert_one(message)
        return message

    async def get_messages(self, conversation_id: str, user_id: str, cursor: str | None = None, limit: int = 50) -> tuple[list[dict], str | None, bool]:
        if not await self.db.conversations.find_one({"id": conversation_id, "member_ids": user_id}, {"_id": 1}):
            raise MessageServiceError("NOT_A_MEMBER", "You are not a member of this conversation")
        query: dict = {"conversation_id": conversation_id}
        decoded = self._decode_cursor(cursor) if cursor else None
        if decoded:
            created_at, message_id = decoded
            query["$or"] = [{"created_at": {"$lt": created_at}}, {"created_at": created_at, "id": {"$lt": message_id}}]
        rows = [row async for row in self.db.messages.find(query).sort([("created_at", DESCENDING), ("id", DESCENDING)]).limit(limit + 1)]
        has_more = len(rows) > limit
        rows = rows[:limit]
        sender_ids = list({row["sender_id"] for row in rows})
        users = {user["id"]: user async for user in self.db.users.find({"id": {"$in": sender_ids}}, {"id": 1, "display_name": 1})}
        messages = [{"id": row["id"], "conversation_id": row["conversation_id"], "sender_id": row["sender_id"], "sender_display_name": users.get(row["sender_id"], {}).get("display_name", "Unknown"), "content": row["content"], "created_at": row["created_at"].isoformat()} for row in rows]
        next_cursor = self._encode_cursor(messages[-1]["created_at"], messages[-1]["id"]) if has_more and messages else None
        return messages, next_cursor, has_more

    @staticmethod
    def _encode_cursor(created_at_iso: str, message_id: str) -> str:
        return base64.urlsafe_b64encode(json.dumps({"c": created_at_iso, "i": message_id}).encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor))
            return datetime.fromisoformat(data["c"]), data["i"]
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
