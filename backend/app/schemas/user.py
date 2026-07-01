"""User and session schemas."""

from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    """Public user profile."""

    id: str
    email: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """Active session (refresh token) info."""

    id: str
    device_info: str | None
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}
