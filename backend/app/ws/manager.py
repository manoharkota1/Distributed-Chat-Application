"""
WebSocket connection manager.

Maintains an in-memory map of user_id → set of WebSocket connections.
This is per-instance state — Redis Pub/Sub handles cross-instance delivery.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages local WebSocket connections for this FastAPI instance.

    Each user can have multiple connections (multiple tabs/devices
    connected to this particular instance).
    """

    def __init__(self) -> None:
        # user_id → set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Register a new WebSocket connection for a user."""
        async with self._lock:
            self._connections[user_id].add(websocket)
        logger.info("User %s connected (total: %d)", user_id, len(self._connections[user_id]))

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection for a user."""
        async with self._lock:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info("User %s disconnected", user_id)

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to all local connections of a user."""
        connections = self._connections.get(user_id, set()).copy()
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                # Connection may have died; it will be cleaned up on disconnect
                logger.warning("Failed to send to user %s, connection may be stale", user_id)

    async def broadcast_to_users(self, user_ids: list[str], message: dict) -> None:
        """Send a message to all local connections of multiple users."""
        tasks = [
            self.send_to_user(uid, message)
            for uid in user_ids
            if uid in self._connections
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_connected_user_ids(self) -> list[str]:
        """Return a list of all locally connected user IDs."""
        return list(self._connections.keys())

    def is_user_connected(self, user_id: str) -> bool:
        """Check if a user has any local connections."""
        return user_id in self._connections and len(self._connections[user_id]) > 0


# Singleton instance used across the application
manager = ConnectionManager()
