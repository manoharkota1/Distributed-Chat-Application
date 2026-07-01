"""
Message model — indexed for cursor-based pagination.

The composite index on (conversation_id, created_at DESC, id DESC) is the
single most important index in the system, enabling efficient cursor-based
pagination at any scroll depth.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Message(Base):
    """A message within a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")
    reads = relationship("MessageRead", back_populates="message", lazy="noload")

    # Critical composite index for cursor-based pagination
    __table_args__ = (
        Index(
            "ix_messages_cursor_pagination",
            conversation_id,
            created_at.desc(),
            id.desc(),
        ),
    )

    def __repr__(self) -> str:
        return f"<Message {self.id} in {self.conversation_id}>"
