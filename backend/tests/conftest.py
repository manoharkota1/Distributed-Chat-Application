"""
Test fixtures and configuration.

Provides:
- Async test database (SQLite in-memory for speed)
- Test HTTP client
- Test Redis mock
- Factory fixtures for creating test users, conversations, etc.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base, get_db_session
from app.core.security import create_access_token, hash_password
from app.main import app


# ── Test Database Engine (SQLite async) ──────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create and tear down all tables for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async test HTTP client with mocked dependencies."""

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db

    # Mock Redis operations to avoid needing a real Redis
    with patch("app.core.redis.get_redis", new_callable=AsyncMock) as mock_redis, \
         patch("app.core.redis.check_rate_limit", return_value=True), \
         patch("app.services.conversation_service.get_online_users", return_value={}), \
         patch("app.pubsub.redis_bridge.redis_bridge"):
        mock_redis_instance = AsyncMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.set = AsyncMock()
        mock_redis_instance.get = AsyncMock(return_value=None)
        mock_redis_instance.delete = AsyncMock()
        mock_redis_instance.exists = AsyncMock(return_value=0)
        mock_redis_instance.incr = AsyncMock(return_value=1)
        mock_redis_instance.expire = AsyncMock()
        mock_redis_instance.publish = AsyncMock()
        mock_redis_instance.pipeline = AsyncMock(return_value=mock_redis_instance)
        mock_redis_instance.execute = AsyncMock(return_value=[])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


# ── Helper Functions ─────────────────────────────────────────────

def make_auth_header(user_id: str) -> dict[str, str]:
    """Create an Authorization header with a valid JWT for the given user."""
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


async def create_test_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "testpassword123",
    display_name: str = "Test User",
) -> "User":
    """Create and persist a test user."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    await db.flush()
    return user
