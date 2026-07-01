"""Authentication request/response schemas."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Account registration payload."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Access token returned on login/register/refresh."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiry
