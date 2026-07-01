"""
RefreshToken model — stores hashed refresh tokens with rotation chain.

Security design:
- Only the SHA-256 hash of the token is stored; the raw token is never persisted.
- ``replaced_by`` forms a rotation chain for theft/reuse detection.
- ``revoked_at`` is set when a token is rotated out or explicitly revoked.
"""
from __future__ import annotations


import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RefreshToken(Base):
    """Hashed refresh token with rotation chain for reuse detection."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),  # SHA-256 hex digest
        unique=True,
        nullable=False,
        index=True,
    )
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refresh_tokens.id"),
        nullable=True,
    )

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    @property
    def is_active(self) -> bool:
        """Check if this refresh token is still valid."""
        now = datetime.now(timezone.utc)
        return self.revoked_at is None and self.expires_at > now

    def __repr__(self) -> str:
        return f"<RefreshToken user_id={self.user_id} active={self.is_active}>"
