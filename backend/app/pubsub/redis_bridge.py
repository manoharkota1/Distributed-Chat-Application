"""Upstash REST Server-Sent Events bridge for cross-instance WebSocket fanout."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.database import get_database
from app.core.redis import EVENT_CHANNEL
from app.ws.manager import manager

logger = logging.getLogger(__name__)


class RedisBridge:
    """Consumes Upstash's REST Pub/Sub SSE endpoint and fans events to local members."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stopping = False

    async def start(self) -> None:
        if self._task is None:
            self._stopping = False
            self._task = asyncio.create_task(self._listen_forever(), name="upstash-event-listener")
            logger.info("upstash_event_bridge_started", extra={"channel": EVENT_CHANNEL})

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    async def _listen_forever(self) -> None:
        delay = 1.0
        headers = {"Authorization": f"Bearer {settings.upstash_redis_rest_token}", "Accept": "text/event-stream"}
        url = f"{settings.upstash_redis_rest_url}/subscribe/{quote(EVENT_CHANNEL, safe='')}"
        while not self._stopping:
            try:
                timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client, client.stream("POST", url, headers=headers) as response:
                    response.raise_for_status()
                    delay = 1.0
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            await self._handle_sse_event(line[6:])
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("upstash_event_listener_failed", extra={"retry_in_seconds": delay})
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def _handle_sse_event(self, event: str) -> None:
        try:
            event_type, _channel, raw_message = event.split(",", 2)
            if event_type != "message":
                return
            data = json.loads(raw_message)
            payload = data.get("payload", {})
            conversation_id = payload.get("conversation_id")
            connected_users = manager.get_connected_user_ids()
            if not conversation_id or not connected_users:
                return
            conversation = await get_database().conversations.find_one(
                {"id": conversation_id, "member_ids": {"$in": connected_users}},
                {"member_ids": 1},
            )
            if conversation is None:
                return
            member_ids = [user_id for user_id in connected_users if user_id in conversation["member_ids"]]
            await manager.broadcast_to_users(member_ids, {"type": data.get("type"), "payload": payload})
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("upstash_event_invalid")


redis_bridge = RedisBridge()
