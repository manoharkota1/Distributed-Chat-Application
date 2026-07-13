"""MongoDB Atlas integration-test fixtures using an isolated test database."""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.database import ensure_indexes, get_db
from app.core.security import create_access_token, hash_password
from app.main import app


@pytest_asyncio.fixture(scope="session")
async def mongo_client() -> AsyncGenerator[AsyncMongoClient, None]:
    uri = os.getenv("MONGODB_URI")
    if not uri:
        pytest.skip("MONGODB_URI is required for MongoDB integration tests")
    client = AsyncMongoClient(uri, serverSelectionTimeoutMS=5000)
    await client.admin.command("ping")
    yield client
    await client.close()


@pytest_asyncio.fixture
async def db_session(mongo_client: AsyncMongoClient) -> AsyncGenerator[AsyncDatabase, None]:
    db = mongo_client.get_database(f"{os.getenv('MONGODB_DATABASE', 'chat_db')}_test")
    for collection in ["users", "refresh_tokens", "conversations", "messages"]:
        await db.drop_collection(collection)
    await ensure_indexes(db)
    yield db
    for collection in ["users", "refresh_tokens", "conversations", "messages"]:
        await db.drop_collection(collection)


@pytest_asyncio.fixture
async def client(db_session: AsyncDatabase) -> AsyncGenerator[AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncDatabase, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with patch("app.core.redis.check_rate_limit", return_value=True), patch("app.core.redis.get_redis", new_callable=AsyncMock):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    app.dependency_overrides.clear()


def make_auth_header(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def create_test_user(db: AsyncDatabase, email: str = "test@example.com", password: str = "testpassword123", display_name: str = "Test User") -> SimpleNamespace:
    user = {"id": str(uuid.uuid4()), "email": email, "password_hash": hash_password(password), "display_name": display_name, "created_at": datetime.now(timezone.utc)}
    await db.users.insert_one(user)
    return SimpleNamespace(**user)
