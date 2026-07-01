"""
Redis connection pool and helper utilities.

Redis serves four roles in this application:
1. Pub/Sub — cross-instance message fanout
2. Presence — TTL keys tracking online status
3. Typing indicators — auto-expiring TTL keys
4. Rate limiting — sliding-window counters
"""
from __future__ import annotations


import redis.asyncio as redis

from app.core.config import settings

# ── Connection Pool ──────────────────────────────────────────────

_redis_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Return the shared async Redis connection (lazy-initialized)."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool during shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None


# ── Key Patterns ─────────────────────────────────────────────────

PRESENCE_KEY = "presence:{user_id}"
TYPING_KEY = "typing:{conversation_id}:{user_id}"
CHANNEL_KEY = "chan:convo:{conversation_id}"
RATE_LIMIT_KEY = "ratelimit:msg:{user_id}"

# ── TTL Constants ────────────────────────────────────────────────

PRESENCE_TTL_SECONDS = 30
TYPING_TTL_SECONDS = 5


# ── Presence Helpers ─────────────────────────────────────────────

async def set_user_online(user_id: str) -> None:
    """Mark a user as online by setting/refreshing a TTL key."""
    r = await get_redis()
    key = PRESENCE_KEY.format(user_id=user_id)
    await r.set(key, "online", ex=PRESENCE_TTL_SECONDS)


async def set_user_offline(user_id: str) -> None:
    """Explicitly remove a user's presence key."""
    r = await get_redis()
    key = PRESENCE_KEY.format(user_id=user_id)
    await r.delete(key)


async def is_user_online(user_id: str) -> bool:
    """Check whether a user's presence key exists."""
    r = await get_redis()
    key = PRESENCE_KEY.format(user_id=user_id)
    return await r.exists(key) == 1


async def get_online_users(user_ids: list[str]) -> dict[str, bool]:
    """Batch-check online status for a list of user IDs."""
    r = await get_redis()
    pipe = r.pipeline()
    for uid in user_ids:
        pipe.exists(PRESENCE_KEY.format(user_id=uid))
    results = await pipe.execute()
    return {uid: bool(res) for uid, res in zip(user_ids, results)}


# ── Typing Indicator Helpers ─────────────────────────────────────

async def set_typing(conversation_id: str, user_id: str) -> None:
    """Set typing indicator with auto-expiry (no explicit stop needed)."""
    r = await get_redis()
    key = TYPING_KEY.format(conversation_id=conversation_id, user_id=user_id)
    await r.set(key, "1", ex=TYPING_TTL_SECONDS)


async def clear_typing(conversation_id: str, user_id: str) -> None:
    """Explicitly clear a typing indicator."""
    r = await get_redis()
    key = TYPING_KEY.format(conversation_id=conversation_id, user_id=user_id)
    await r.delete(key)


# ── Rate Limiting ────────────────────────────────────────────────

async def check_rate_limit(user_id: str) -> bool:
    """
    Check if a user has exceeded the message send rate limit.

    Uses a simple sliding-window counter approach:
    - Increment the counter for the user's key.
    - Set TTL on first increment to create the window.
    - Return True if under the limit, False if exceeded.
    """
    r = await get_redis()
    key = RATE_LIMIT_KEY.format(user_id=user_id)

    current = await r.incr(key)
    if current == 1:
        # First message in this window — set expiry
        await r.expire(key, settings.rate_limit_window_seconds)

    return current <= settings.rate_limit_messages_per_window
