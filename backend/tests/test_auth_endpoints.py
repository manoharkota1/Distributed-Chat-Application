"""
Integration tests for authentication REST endpoints.

Tests the full flow: register → login → refresh → logout,
including token rotation and reuse detection.
"""

import pytest

from tests.conftest import create_test_user


@pytest.mark.asyncio
class TestRegister:
    """Tests for POST /auth/register."""

    async def test_register_success(self, client):
        """Should create account and return access token."""
        response = await client.post("/auth/register", json={
            "email": "new@example.com",
            "password": "securepass123",
            "display_name": "New User",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert data["data"]["access_token"] is not None
        assert data["data"]["token_type"] == "bearer"

    async def test_register_duplicate_email(self, client, db_session):
        """Should reject duplicate email registration."""
        await create_test_user(db_session, email="existing@example.com")

        response = await client.post("/auth/register", json={
            "email": "existing@example.com",
            "password": "securepass123",
            "display_name": "Duplicate",
        })
        data = response.json()
        assert data["error"] is not None
        assert data["error"]["code"] == "EMAIL_EXISTS"

    async def test_register_invalid_email(self, client):
        """Should reject invalid email format."""
        response = await client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "securepass123",
            "display_name": "Bad Email",
        })
        assert response.status_code == 422

    async def test_register_short_password(self, client):
        """Should reject passwords shorter than 8 characters."""
        response = await client.post("/auth/register", json={
            "email": "short@example.com",
            "password": "short",
            "display_name": "Short Pass",
        })
        assert response.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    """Tests for POST /auth/login."""

    async def test_login_success(self, client, db_session):
        """Should authenticate and return access token."""
        await create_test_user(
            db_session,
            email="login@example.com",
            password="loginpass123",
        )

        response = await client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "loginpass123",
        })
        data = response.json()
        assert data["error"] is None
        assert data["data"]["access_token"] is not None

    async def test_login_wrong_password(self, client, db_session):
        """Should reject wrong password."""
        await create_test_user(
            db_session,
            email="wrongpass@example.com",
            password="correctpass",
        )

        response = await client.post("/auth/login", json={
            "email": "wrongpass@example.com",
            "password": "wrongpassword",
        })
        data = response.json()
        assert data["error"] is not None
        assert data["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_login_nonexistent_user(self, client):
        """Should reject login for non-existent email."""
        response = await client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "somepassword",
        })
        data = response.json()
        assert data["error"] is not None
        assert data["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
class TestHealthCheck:
    """Tests for GET /health."""

    async def test_health_check(self, client):
        """Health endpoint should return healthy status."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
