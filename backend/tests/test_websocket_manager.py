"""
Unit tests for WebSocket connection manager.
"""

from unittest.mock import AsyncMock

import pytest

from app.ws.manager import ConnectionManager


@pytest.mark.asyncio
class TestConnectionManager:
    """Tests for the WebSocket connection manager."""

    async def test_connect_and_disconnect(self):
        """Should track connections and clean up on disconnect."""
        mgr = ConnectionManager()
        ws = AsyncMock()

        await mgr.connect("user-1", ws)
        assert mgr.is_user_connected("user-1")
        assert "user-1" in mgr.get_connected_user_ids()

        await mgr.disconnect("user-1", ws)
        assert not mgr.is_user_connected("user-1")

    async def test_multiple_connections_per_user(self):
        """A user can have multiple connections (multiple tabs)."""
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await mgr.connect("user-1", ws1)
        await mgr.connect("user-1", ws2)
        assert mgr.is_user_connected("user-1")

        # Disconnect one — still connected via the other
        await mgr.disconnect("user-1", ws1)
        assert mgr.is_user_connected("user-1")

        # Disconnect the last one
        await mgr.disconnect("user-1", ws2)
        assert not mgr.is_user_connected("user-1")

    async def test_send_to_user(self):
        """Should send to all connections of a user."""
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await mgr.connect("user-1", ws1)
        await mgr.connect("user-1", ws2)

        await mgr.send_to_user("user-1", {"type": "test"})
        ws1.send_json.assert_called_once_with({"type": "test"})
        ws2.send_json.assert_called_once_with({"type": "test"})

    async def test_send_to_nonexistent_user(self):
        """Should not raise when sending to a non-connected user."""
        mgr = ConnectionManager()
        await mgr.send_to_user("nonexistent", {"type": "test"})

    async def test_broadcast_to_users(self):
        """Should broadcast to multiple users."""
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await mgr.connect("user-1", ws1)
        await mgr.connect("user-2", ws2)

        await mgr.broadcast_to_users(
            ["user-1", "user-2", "user-3"],  # user-3 not connected
            {"type": "broadcast"},
        )

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()
