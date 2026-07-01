"""
Presence service — online/offline tracking via Redis TTL keys.

Presence is ephemeral and stored only in Redis. A user is considered
online if their ``presence:{user_id}`` key exists; key absence means offline.
The TTL is refreshed on every WebSocket heartbeat (30s).
"""
from __future__ import annotations


from app.core.redis import (
    get_online_users,
    is_user_online,
    set_user_offline,
    set_user_online,
)


class PresenceService:
    """Manages user online/offline presence via Redis."""

    @staticmethod
    async def set_online(user_id: str) -> None:
        """Mark a user as online (set/refresh TTL key)."""
        await set_user_online(user_id)

    @staticmethod
    async def set_offline(user_id: str) -> None:
        """Mark a user as offline (delete key)."""
        await set_user_offline(user_id)

    @staticmethod
    async def check_online(user_id: str) -> bool:
        """Check if a single user is online."""
        return await is_user_online(user_id)

    @staticmethod
    async def batch_check(user_ids: list[str]) -> dict[str, bool]:
        """Batch-check online status for multiple users."""
        return await get_online_users(user_ids)
