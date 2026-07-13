"""
WebSocket event schemas.

All WS messages share a common envelope: {"type", "payload", "request_id"}.
"""
from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel


class WSEventType(str, enum.Enum):
    """All supported WebSocket event types."""

    # Client → Server
    MESSAGE_SEND = "message.send"
    TYPING_START = "typing.start"
    TYPING_STOP = "typing.stop"
    READ_UPDATE = "read.update"

    # Server → Client
    MESSAGE_NEW = "message.new"
    MESSAGE_ACK = "message.ack"
    TYPING_UPDATE = "typing.update"
    PRESENCE_UPDATE = "presence.update"
    READ_RECEIPT = "read.receipt"

    # System
    ERROR = "error"
    PONG = "pong"


class WSMessage(BaseModel):
    """
    Common envelope for all WebSocket messages.

    Both client-to-server and server-to-client messages use this format.
    """

    type: str
    payload: dict[str, Any] = {}
    request_id: str | None = None
