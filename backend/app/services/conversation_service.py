"""
Conversation service — create, list, membership management.
"""
from __future__ import annotations


import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis import get_online_users
from app.models.conversation import Conversation, ConversationType
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.message_read import MessageRead
from app.models.user import User


class ConversationServiceError(Exception):
    """Base exception for conversation service errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class ConversationService:
    """Handles conversation creation, listing, and membership."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create Conversation ──────────────────────────────────────

    async def create_conversation(
        self,
        creator_id: str,
        conversation_type: str,
        name: str | None,
        member_ids: list[str],
    ) -> Conversation:
        """
        Create a new direct or group conversation.

        For direct conversations:
        - Checks if a DM already exists between the two users.
        - Exactly one other member is required.

        For group conversations:
        - A name is required.
        - At least one other member is required.

        Returns:
            The created Conversation.

        Raises:
            ConversationServiceError: On validation failure.
        """
        creator_uuid = uuid.UUID(creator_id)

        # Ensure the creator is included in the members list
        all_member_uuids = {uuid.UUID(mid) for mid in member_ids}
        all_member_uuids.add(creator_uuid)

        if conversation_type == "direct":
            if len(all_member_uuids) != 2:
                raise ConversationServiceError(
                    "INVALID_MEMBERS",
                    "Direct conversations must have exactly 2 members"
                )

            # Check for existing DM between these users
            other_id = (all_member_uuids - {creator_uuid}).pop()
            existing = await self._find_existing_dm(creator_uuid, other_id)
            if existing:
                return existing

        elif conversation_type == "group":
            if not name:
                raise ConversationServiceError(
                    "NAME_REQUIRED",
                    "Group conversations must have a name"
                )
            if len(all_member_uuids) < 2:
                raise ConversationServiceError(
                    "INVALID_MEMBERS",
                    "Group conversations must have at least 2 members"
                )
        else:
            raise ConversationServiceError(
                "INVALID_TYPE",
                "Conversation type must be 'direct' or 'group'"
            )

        # Verify all member IDs correspond to real users
        result = await self.db.execute(
            select(User.id).where(User.id.in_(all_member_uuids))
        )
        existing_user_ids = {row[0] for row in result.all()}
        missing = all_member_uuids - existing_user_ids
        if missing:
            raise ConversationServiceError(
                "USERS_NOT_FOUND",
                f"Users not found: {[str(m) for m in missing]}"
            )

        # Create conversation
        convo = Conversation(
            type=ConversationType(conversation_type),
            name=name,
        )
        self.db.add(convo)
        await self.db.flush()

        # Add members
        for uid in all_member_uuids:
            member = ConversationMember(
                conversation_id=convo.id,
                user_id=uid,
            )
            self.db.add(member)
        await self.db.flush()

        return convo

    # ── List Conversations ───────────────────────────────────────

    async def get_user_conversations(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        """
        Get all conversations a user belongs to, with last message preview.

        Returns:
            Tuple of (conversations_list, total_count).
        """
        user_uuid = uuid.UUID(user_id)

        # Get conversation IDs the user belongs to
        member_query = select(ConversationMember.conversation_id).where(
            ConversationMember.user_id == user_uuid
        )

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(member_query.subquery())
        )
        total = count_result.scalar() or 0

        # Get conversations with members
        convos_result = await self.db.execute(
            select(Conversation)
            .where(Conversation.id.in_(member_query))
            .options(selectinload(Conversation.members))
            .order_by(Conversation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        conversations = convos_result.scalars().all()

        # Build response
        result_list = []
        for convo in conversations:
            # Get member info
            member_user_ids = [str(m.user_id) for m in convo.members]
            online_status = await get_online_users(member_user_ids)

            # Get member display names
            member_users_result = await self.db.execute(
                select(User).where(
                    User.id.in_([m.user_id for m in convo.members])
                )
            )
            member_users = {
                str(u.id): u for u in member_users_result.scalars().all()
            }

            members_info = []
            for m in convo.members:
                uid_str = str(m.user_id)
                user = member_users.get(uid_str)
                members_info.append({
                    "user_id": uid_str,
                    "display_name": user.display_name if user else "Unknown",
                    "is_online": online_status.get(uid_str, False),
                })

            # Get last message
            last_msg_result = await self.db.execute(
                select(Message)
                .where(Message.conversation_id == convo.id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            last_msg = last_msg_result.scalar_one_or_none()

            # Get unread count
            user_membership = next(
                (m for m in convo.members if m.user_id == user_uuid), None
            )
            unread_count = 0
            if user_membership and user_membership.last_read_message_id:
                # Get the created_at of the last read message
                last_read_result = await self.db.execute(
                    select(Message.created_at).where(
                        Message.id == user_membership.last_read_message_id
                    )
                )
                last_read_at = last_read_result.scalar_one_or_none()
                if last_read_at:
                    unread_result = await self.db.execute(
                        select(func.count()).where(
                            Message.conversation_id == convo.id,
                            Message.created_at > last_read_at,
                        )
                    )
                    unread_count = unread_result.scalar() or 0
            elif user_membership:
                # No read position — all messages are unread
                unread_result = await self.db.execute(
                    select(func.count()).where(
                        Message.conversation_id == convo.id
                    )
                )
                unread_count = unread_result.scalar() or 0

            result_list.append({
                "id": str(convo.id),
                "type": convo.type.value,
                "name": convo.name,
                "created_at": convo.created_at.isoformat(),
                "members": members_info,
                "last_message": {
                    "id": str(last_msg.id),
                    "content": last_msg.content,
                    "sender_id": str(last_msg.sender_id),
                    "created_at": last_msg.created_at.isoformat(),
                } if last_msg else None,
                "unread_count": unread_count,
            })

        return result_list, total

    # ── Update Read Position ─────────────────────────────────────

    async def update_read_position(
        self,
        conversation_id: str,
        user_id: str,
        message_id: str,
    ) -> None:
        """Update the user's last-read message in a conversation."""
        convo_uuid = uuid.UUID(conversation_id)
        user_uuid = uuid.UUID(user_id)
        msg_uuid = uuid.UUID(message_id)

        result = await self.db.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == convo_uuid,
                ConversationMember.user_id == user_uuid,
            )
        )
        membership = result.scalar_one_or_none()

        if membership is None:
            raise ConversationServiceError(
                "NOT_A_MEMBER",
                "You are not a member of this conversation"
            )

        membership.last_read_message_id = msg_uuid
        await self.db.flush()

    # ── Membership Check ─────────────────────────────────────────

    async def verify_membership(
        self, conversation_id: str, user_id: str
    ) -> bool:
        """Check if a user is a member of a conversation."""
        result = await self.db.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == uuid.UUID(conversation_id),
                ConversationMember.user_id == uuid.UUID(user_id),
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_conversation_member_ids(
        self, conversation_id: str
    ) -> list[str]:
        """Get all member user IDs for a conversation."""
        result = await self.db.execute(
            select(ConversationMember.user_id).where(
                ConversationMember.conversation_id == uuid.UUID(conversation_id)
            )
        )
        return [str(row[0]) for row in result.all()]

    # ── Private Helpers ──────────────────────────────────────────

    async def _find_existing_dm(
        self, user_a: uuid.UUID, user_b: uuid.UUID
    ) -> Conversation | None:
        """Find an existing direct conversation between two users."""
        # Subquery: conversations where user_a is a member
        a_convos = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_a)
            .subquery()
        )

        # Subquery: conversations where user_b is a member
        b_convos = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_b)
            .subquery()
        )

        result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.type == ConversationType.DIRECT,
                Conversation.id.in_(select(a_convos)),
                Conversation.id.in_(select(b_convos)),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
