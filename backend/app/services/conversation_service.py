"""MongoDB conversation documents, membership, read positions, and list views."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

import json
from app.core.redis import get_online_users, get_redis, EVENT_CHANNEL


class ConversationServiceError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class ConversationService:
    def __init__(self, db: AsyncDatabase):
        self.db = db

    async def create_conversation(self, creator_id: str, conversation_type: str, name: str | None, member_ids: list[str]) -> dict:
        all_member_ids = sorted(set(member_ids) | {creator_id})
        if conversation_type == "direct":
            if len(all_member_ids) != 2:
                raise ConversationServiceError("INVALID_MEMBERS", "Direct conversations must have exactly 2 members")
            direct_key = ":".join(all_member_ids)
            existing = await self.db.conversations.find_one({"type": "direct", "direct_key": direct_key})
            if existing:
                return existing
        elif conversation_type == "group":
            if not name:
                raise ConversationServiceError("NAME_REQUIRED", "Group conversations must have a name")
            if len(all_member_ids) < 2:
                raise ConversationServiceError("INVALID_MEMBERS", "Group conversations must have at least 2 members")
            direct_key = None
        else:
            raise ConversationServiceError("INVALID_TYPE", "Conversation type must be 'direct' or 'group'")

        found_user_ids = {user["id"] async for user in self.db.users.find({"id": {"$in": all_member_ids}}, {"id": 1})}
        missing = set(all_member_ids) - found_user_ids
        if missing:
            raise ConversationServiceError("USERS_NOT_FOUND", f"Users not found: {sorted(missing)}")

        now = datetime.now(timezone.utc)
        conversation = {
            "id": str(uuid.uuid4()), "type": conversation_type, "name": name,
            "member_ids": all_member_ids, "direct_key": direct_key, "created_at": now,
            "members": [{"user_id": member_id, "last_read_message_id": None, "joined_at": now} for member_id in all_member_ids],
        }
        await self.db.conversations.insert_one(conversation)

        r = await get_redis()
        await r.publish(EVENT_CHANNEL, json.dumps({
            "type": "conversation.update",
            "payload": {
                "conversation_id": conversation["id"],
                "action": "created",
            }
        }))

        return conversation

    async def get_user_conversations(self, user_id: str, offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        query = {"member_ids": user_id}
        total = await self.db.conversations.count_documents(query)
        conversations = [conversation async for conversation in self.db.conversations.find(query).sort("created_at", DESCENDING).skip(offset).limit(limit)]
        response: list[dict] = []
        for conversation in conversations:
            member_ids = conversation["member_ids"]
            users = {user["id"]: user async for user in self.db.users.find({"id": {"$in": member_ids}}, {"id": 1, "display_name": 1})}
            online = await get_online_users(member_ids)
            last_message = await self.db.messages.find_one({"conversation_id": conversation["id"]}, sort=[("created_at", DESCENDING), ("id", DESCENDING)])
            membership = next((member for member in conversation["members"] if member["user_id"] == user_id), None)
            unread_query: dict = {
                "conversation_id": conversation["id"],
                "sender_id": {"$ne": user_id},
            }
            if membership and membership.get("last_read_message_id"):
                read_message = await self.db.messages.find_one({"id": membership["last_read_message_id"]}, {"created_at": 1})
                if read_message:
                    unread_query["created_at"] = {"$gt": read_message["created_at"]}
            unread_count = await self.db.messages.count_documents(unread_query) if membership else 0
            response.append({
                "id": conversation["id"], "type": conversation["type"], "name": conversation.get("name"),
                "created_at": conversation["created_at"].isoformat(),
                "members": [{"user_id": member_id, "display_name": users.get(member_id, {}).get("display_name", "Unknown"), "is_online": online.get(member_id, False)} for member_id in member_ids],
                "last_message": self._message_preview(last_message), "unread_count": unread_count,
            })
        return response, total

    async def update_read_position(self, conversation_id: str, user_id: str, message_id: str) -> None:
        result = await self.db.conversations.update_one(
            {"id": conversation_id, "member_ids": user_id},
            {"$set": {"members.$[member].last_read_message_id": message_id}},
            array_filters=[{"member.user_id": user_id}],
        )
        if result.matched_count == 0:
            raise ConversationServiceError("NOT_A_MEMBER", "You are not a member of this conversation")

    async def verify_membership(self, conversation_id: str, user_id: str) -> bool:
        return bool(await self.db.conversations.find_one({"id": conversation_id, "member_ids": user_id}, {"_id": 1}))

    async def get_conversation_member_ids(self, conversation_id: str) -> list[str]:
        conversation = await self.db.conversations.find_one({"id": conversation_id}, {"member_ids": 1})
        return conversation.get("member_ids", []) if conversation else []

    async def add_member(self, conversation_id: str, operator_id: str, user_id_to_add: str) -> dict:
        if not await self.verify_membership(conversation_id, operator_id):
            raise ConversationServiceError("NOT_A_MEMBER", "You are not a member of this conversation")

        convo = await self.db.conversations.find_one({"id": conversation_id})
        if not convo:
            raise ConversationServiceError("CONVERSATION_NOT_FOUND", "Conversation not found")
        if convo["type"] != "group":
            raise ConversationServiceError("INVALID_TYPE", "Cannot add members to a direct conversation")

        if user_id_to_add in convo["member_ids"]:
            raise ConversationServiceError("ALREADY_MEMBER", "User is already a member of this conversation")

        user_exists = await self.db.users.find_one({"id": user_id_to_add}, {"_id": 1})
        if not user_exists:
            raise ConversationServiceError("USER_NOT_FOUND", f"User not found")

        now = datetime.now(timezone.utc)
        await self.db.conversations.update_one(
            {"id": conversation_id},
            {
                "$addToSet": {"member_ids": user_id_to_add},
                "$push": {"members": {"user_id": user_id_to_add, "last_read_message_id": None, "joined_at": now}}
            }
        )
        updated_convo = await self.db.conversations.find_one({"id": conversation_id})
        if updated_convo is None:
            raise ConversationServiceError("CONVERSATION_NOT_FOUND", "Conversation not found")
        
        r = await get_redis()
        await r.publish(EVENT_CHANNEL, json.dumps({
            "type": "conversation.update",
            "payload": {
                "conversation_id": conversation_id,
                "action": "member_added",
                "user_id": user_id_to_add,
            }
        }))
        return updated_convo

    async def remove_member(self, conversation_id: str, operator_id: str, user_id_to_remove: str) -> dict:
        if not await self.verify_membership(conversation_id, operator_id):
            raise ConversationServiceError("NOT_A_MEMBER", "You are not a member of this conversation")

        convo = await self.db.conversations.find_one({"id": conversation_id})
        if not convo:
            raise ConversationServiceError("CONVERSATION_NOT_FOUND", "Conversation not found")
        if convo["type"] != "group":
            raise ConversationServiceError("INVALID_TYPE", "Cannot remove members from a direct conversation")

        if user_id_to_remove not in convo["member_ids"]:
            raise ConversationServiceError("NOT_A_MEMBER", "User is not a member of this conversation")

        await self.db.conversations.update_one(
            {"id": conversation_id},
            {
                "$pull": {
                    "member_ids": user_id_to_remove,
                    "members": {"user_id": user_id_to_remove}
                }
            }
        )
        updated_convo = await self.db.conversations.find_one({"id": conversation_id})
        if updated_convo is None:
            raise ConversationServiceError("CONVERSATION_NOT_FOUND", "Conversation not found")

        r = await get_redis()
        await r.publish(EVENT_CHANNEL, json.dumps({
            "type": "conversation.update",
            "payload": {
                "conversation_id": conversation_id,
                "action": "member_removed",
                "user_id": user_id_to_remove,
            }
        }))
        return updated_convo

    @staticmethod
    def _message_preview(message: dict | None) -> dict | None:
        if message is None:
            return None
        return {"id": message["id"], "content": message["content"], "sender_id": message["sender_id"], "created_at": message["created_at"].isoformat()}
