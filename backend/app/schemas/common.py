"""
Standard API response envelope.

All responses follow: {"data": ..., "error": null} on success,
and {"data": null, "error": {"code": ..., "message": ...}} on failure.
"""
from __future__ import annotations


from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIError(BaseModel):
    """Error detail in the standard response envelope."""

    code: str
    message: str


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper.

    All REST endpoints return this envelope for consistency.
    """

    data: T | None = None
    error: APIError | None = None

    @classmethod
    def success(cls, data: Any) -> "APIResponse":
        """Create a success response."""
        return cls(data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str) -> "APIResponse":
        """Create an error response."""
        return cls(data=None, error=APIError(code=code, message=message))
