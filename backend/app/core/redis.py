"""Upstash Redis REST integration for presence, typing, events, and rate limiting."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from upstash_redis import Redis

from app.core.config import settings

PRESENCE_KEY = "presence:{user_id}"
TYPING_KEY = "typing:{conversation_id}:{user_id}"
RATE_LIMIT_KEY = "ratelimit:msg:{user_id}"
EVENT_CHANNEL = settings.upstash_event_channel
PRESENCE_TTL_SECONDS = 30
TYPING_TTL_SECONDS = 5


class AsyncUpstashRedis:
    """Async facade around Upstash's connectionless HTTP Python client."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        operation: Callable[..., Any] = getattr(self._client, method)
        return await asyncio.to_thread(operation, *args, **kwargs)

    async def close(self) -> None:
        await self._call("close")

    async def get(self, key: str) -> str | None:
        val = await self._call("get", key)
        return str(val) if val is not None else None

    async def set(self, key: str, value: str, ex: int | None = None) -> Any:
        return await self._call("set", key, value, ex=ex)

    async def delete(self, key: str) -> Any:
        return await self._call("delete", key)

    async def exists(self, key: str) -> int:
        return int(await self._call("exists", key))

    async def publish(self, channel: str, message: str) -> int:
        return int(await self._call("publish", channel, message))

    async def execute(self, command: list[Any]) -> Any:
        return await self._call("execute", command)

    async def exists_many(self, keys: list[str]) -> list[int]:
        if not keys:
            return []
        def pipeline_exists() -> list[Any]:
            pipeline = self._client.pipeline()
            for key in keys:
                pipeline.exists(key)
            return pipeline.exec()

        res = await asyncio.to_thread(pipeline_exists)
        return [int(value) for value in res]


_redis: AsyncUpstashRedis | None = None


async def get_redis() -> AsyncUpstashRedis:
    global _redis
    if _redis is None:
        client = Redis(
            url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token,
            rest_retries=settings.upstash_redis_retries,
            rest_retry_interval=settings.upstash_redis_retry_interval,
            allow_telemetry=False,
        )
        _redis = AsyncUpstashRedis(client)
    return _redis


async def close_redis() -> None:
    """Reset the connectionless Upstash client facade during shutdown."""
    global _redis
    if _redis is not None:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None


async def set_user_online(user_id: str) -> None:
    await (await get_redis()).set(PRESENCE_KEY.format(user_id=user_id), "online", ex=PRESENCE_TTL_SECONDS)


async def set_user_offline(user_id: str) -> None:
    await (await get_redis()).delete(PRESENCE_KEY.format(user_id=user_id))


async def is_user_online(user_id: str) -> bool:
    return bool(await (await get_redis()).exists(PRESENCE_KEY.format(user_id=user_id)))


async def get_online_users(user_ids: list[str]) -> dict[str, bool]:
    if not user_ids:
        return {}
    redis = await get_redis()
    results = await redis.exists_many([PRESENCE_KEY.format(user_id=user_id) for user_id in user_ids])
    return {user_id: bool(result) for user_id, result in zip(user_ids, results)}


async def set_typing(conversation_id: str, user_id: str) -> None:
    await (await get_redis()).set(TYPING_KEY.format(conversation_id=conversation_id, user_id=user_id), "1", ex=TYPING_TTL_SECONDS)


async def clear_typing(conversation_id: str, user_id: str) -> None:
    await (await get_redis()).delete(TYPING_KEY.format(conversation_id=conversation_id, user_id=user_id))


async def check_rate_limit(user_id: str) -> bool:
    """Atomically increment and expire a fixed message-send window via Lua."""
    script = "local c=redis.call('INCR',KEYS[1]);if c==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end;return c"
    current = await (await get_redis()).execute([
        "EVAL", script, 1, RATE_LIMIT_KEY.format(user_id=user_id), settings.rate_limit_window_seconds,
    ])
    return int(current) <= settings.rate_limit_messages_per_window
