"""Conversation model — container for both DMs and group chats."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ConversationType(str, enum.Enum):
    """Distinguishes between one-to-one and group conversations."""

    DIRECT = "direct"
    GROUP = "group"


class Conversation(Base):
    """A conversation (DM or group) containing messages."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    type: Mapped[ConversationType] = mapped_column(
        Enum(ConversationType, name="conversation_type"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    members = relationship(
        "ConversationMember",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "Message",
        back_populates="conversation",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.type.value} name={self.name}>"
