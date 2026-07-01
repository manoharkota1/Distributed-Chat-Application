"""
Integration tests for conversation and message REST endpoints.
"""

import pytest

from tests.conftest import create_test_user, make_auth_header


@pytest.mark.asyncio
class TestConversations:
    """Tests for conversation CRUD endpoints."""

    async def test_create_direct_conversation(self, client, db_session):
        """Should create a direct conversation between two users."""
        user1 = await create_test_user(db_session, email="user1@test.com", display_name="User 1")
        user2 = await create_test_user(db_session, email="user2@test.com", display_name="User 2")
        await db_session.commit()

        response = await client.post(
            "/conversations",
            json={
                "type": "direct",
                "member_ids": [str(user2.id)],
            },
            headers=make_auth_header(str(user1.id)),
        )
        data = response.json()
        assert data["error"] is None
        assert data["data"]["type"] == "direct"

    async def test_create_group_conversation(self, client, db_session):
        """Should create a group conversation with multiple members."""
        user1 = await create_test_user(db_session, email="g1@test.com", display_name="User 1")
        user2 = await create_test_user(db_session, email="g2@test.com", display_name="User 2")
        user3 = await create_test_user(db_session, email="g3@test.com", display_name="User 3")
        await db_session.commit()

        response = await client.post(
            "/conversations",
            json={
                "type": "group",
                "name": "Test Group",
                "member_ids": [str(user2.id), str(user3.id)],
            },
            headers=make_auth_header(str(user1.id)),
        )
        data = response.json()
        assert data["error"] is None
        assert data["data"]["type"] == "group"
        assert data["data"]["name"] == "Test Group"

    async def test_create_group_without_name_fails(self, client, db_session):
        """Group conversations must have a name."""
        user1 = await create_test_user(db_session, email="gn1@test.com", display_name="User 1")
        user2 = await create_test_user(db_session, email="gn2@test.com", display_name="User 2")
        await db_session.commit()

        response = await client.post(
            "/conversations",
            json={
                "type": "group",
                "member_ids": [str(user2.id)],
            },
            headers=make_auth_header(str(user1.id)),
        )
        data = response.json()
        assert data["error"] is not None
        assert data["error"]["code"] == "NAME_REQUIRED"

    async def test_list_conversations(self, client, db_session):
        """Should return the user's conversations."""
        user1 = await create_test_user(db_session, email="list1@test.com", display_name="User 1")
        user2 = await create_test_user(db_session, email="list2@test.com", display_name="User 2")
        await db_session.commit()

        # Create a conversation first
        await client.post(
            "/conversations",
            json={"type": "direct", "member_ids": [str(user2.id)]},
            headers=make_auth_header(str(user1.id)),
        )

        response = await client.get(
            "/conversations",
            headers=make_auth_header(str(user1.id)),
        )
        data = response.json()
        assert data["error"] is None
        assert data["data"]["total"] >= 1

    async def test_unauthorized_access(self, client):
        """Should reject requests without auth token."""
        response = await client.get("/conversations")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestMessages:
    """Tests for message send and retrieval endpoints."""

    async def test_send_message(self, client, db_session):
        """Should send a message to a conversation."""
        user1 = await create_test_user(db_session, email="msg1@test.com", display_name="User 1")
        user2 = await create_test_user(db_session, email="msg2@test.com", display_name="User 2")
        await db_session.commit()

        # Create conversation
        convo_resp = await client.post(
            "/conversations",
            json={"type": "direct", "member_ids": [str(user2.id)]},
            headers=make_auth_header(str(user1.id)),
        )
        convo_id = convo_resp.json()["data"]["id"]

        # Send message
        response = await client.post(
            f"/conversations/{convo_id}/messages",
            json={"content": "Hello, World!"},
            headers=make_auth_header(str(user1.id)),
        )
        data = response.json()
        assert data["error"] is None
        assert data["data"]["content"] == "Hello, World!"
        assert data["data"]["sender_id"] == str(user1.id)

    async def test_get_messages_with_pagination(self, client, db_session):
        """Should retrieve messages with cursor pagination."""
        user1 = await create_test_user(db_session, email="pag1@test.com", display_name="User 1")
        user2 = await create_test_user(db_session, email="pag2@test.com", display_name="User 2")
        await db_session.commit()

        # Create conversation
        convo_resp = await client.post(
            "/conversations",
            json={"type": "direct", "member_ids": [str(user2.id)]},
            headers=make_auth_header(str(user1.id)),
        )
        convo_id = convo_resp.json()["data"]["id"]
        headers = make_auth_header(str(user1.id))

        # Send multiple messages
        for i in range(5):
            await client.post(
                f"/conversations/{convo_id}/messages",
                json={"content": f"Message {i}"},
                headers=headers,
            )

        # Get messages
        response = await client.get(
            f"/conversations/{convo_id}/messages?limit=3",
            headers=headers,
        )
        data = response.json()
        assert data["error"] is None
        assert len(data["data"]["messages"]) == 3
        assert data["data"]["has_more"] is True
        assert data["data"]["next_cursor"] is not None

    async def test_non_member_cannot_send(self, client, db_session):
        """Non-members should not be able to send messages."""
        user1 = await create_test_user(db_session, email="nm1@test.com", display_name="User 1")
        user2 = await create_test_user(db_session, email="nm2@test.com", display_name="User 2")
        user3 = await create_test_user(db_session, email="nm3@test.com", display_name="User 3")
        await db_session.commit()

        # Create conversation between user1 and user2
        convo_resp = await client.post(
            "/conversations",
            json={"type": "direct", "member_ids": [str(user2.id)]},
            headers=make_auth_header(str(user1.id)),
        )
        convo_id = convo_resp.json()["data"]["id"]

        # user3 tries to send a message
        response = await client.post(
            f"/conversations/{convo_id}/messages",
            json={"content": "Unauthorized message"},
            headers=make_auth_header(str(user3.id)),
        )
        data = response.json()
        assert data["error"] is not None
        assert data["error"]["code"] == "NOT_A_MEMBER"
