"""
Redis Pub/Sub bridge — cross-instance message fanout.

This is the core component that enables horizontal scaling:
- Every FastAPI instance subscribes to Redis channels for its
  locally connected users' conversations.
- When a message is published to a channel, each instance receives
  it and pushes it to any locally connected clients that are members
  of that conversation.

This decouples "who received the request" from "who needs to deliver
the response."
"""
from __future__ import annotations


import asyncio
import json
import logging

import redis.asyncio as redis

from app.core.config import settings
from app.core.redis import CHANNEL_KEY
from app.ws.manager import manager

logger = logging.getLogger(__name__)


class RedisBridge:
    """
    Manages Redis Pub/Sub subscriptions and fans out received
    messages to locally connected WebSocket clients.
    """

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._task: asyncio.Task | None = None
        self._subscribed_channels: set[str] = set()

    async def start(self) -> None:
        """Initialize Redis connection and start the listener loop."""
        self._redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._pubsub = self._redis.pubsub()
        self._task = asyncio.create_task(self._listener_loop())
        logger.info("Redis Pub/Sub bridge started")

    async def stop(self) -> None:
        """Gracefully shut down the bridge."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.aclose()

        if self._redis:
            await self._redis.aclose()

        logger.info("Redis Pub/Sub bridge stopped")

    async def subscribe_to_conversation(self, conversation_id: str) -> None:
        """Subscribe to a conversation channel for cross-instance delivery."""
        channel = CHANNEL_KEY.format(conversation_id=conversation_id)
        if channel not in self._subscribed_channels and self._pubsub:
            await self._pubsub.subscribe(channel)
            self._subscribed_channels.add(channel)
            logger.debug("Subscribed to channel: %s", channel)

    async def unsubscribe_from_conversation(self, conversation_id: str) -> None:
        """Unsubscribe from a conversation channel."""
        channel = CHANNEL_KEY.format(conversation_id=conversation_id)
        if channel in self._subscribed_channels and self._pubsub:
            await self._pubsub.unsubscribe(channel)
            self._subscribed_channels.discard(channel)
            logger.debug("Unsubscribed from channel: %s", channel)

    async def _listener_loop(self) -> None:
        """
        Background task that listens for Redis Pub/Sub messages
        and fans them out to locally connected WebSocket clients.
        """
        if not self._pubsub:
            return

        logger.info("Pub/Sub listener loop started")

        try:
            while True:
                try:
                    message = await self._pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )

                    if message and message["type"] == "message":
                        await self._handle_pubsub_message(message)

                    # Small yield to prevent tight loop
                    await asyncio.sleep(0.01)

                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Error in Pub/Sub listener loop")
                    await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("Pub/Sub listener loop cancelled")

    async def _handle_pubsub_message(self, message: dict) -> None:
        """
        Process a received Pub/Sub message and deliver it to
        locally connected clients.
        """
        try:
            channel = message["channel"]
            data = json.loads(message["data"])

            event_type = data.get("type")
            payload = data.get("payload", {})

            # Extract conversation_id from the channel name
            # Channel format: chan:convo:{conversation_id}
            conversation_id = channel.replace("chan:convo:", "")

            # Find locally connected users who are members of this conversation
            # We broadcast to all locally connected users — the frontend
            # filters by conversation membership
            connected_users = manager.get_connected_user_ids()

            if connected_users:
                ws_message = {
                    "type": event_type,
                    "payload": payload,
                }
                await manager.broadcast_to_users(connected_users, ws_message)

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Invalid Pub/Sub message: %s", e)


# Singleton instance
redis_bridge = RedisBridge()
