"""User and session schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


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


class UpdateProfileRequest(BaseModel):
    """Profile update payload (partial)."""

    display_name: str | None = Field(None, min_length=1, max_length=100)


class ChangePasswordRequest(BaseModel):
    """Password change payload."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

