"""MongoDB Atlas connection lifecycle and collection indexes."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import certifi
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncMongoClient | None = None
_database: AsyncDatabase | None = None


async def connect_mongodb() -> None:
    """Create the shared Atlas client, verify connectivity, and create indexes."""
    global _client, _database
    if _database is not None:
        return

    _client = AsyncMongoClient(
        settings.mongodb_uri,
        appname=settings.app_name.replace(" ", "-"),
        maxPoolSize=settings.mongodb_max_pool_size,
        minPoolSize=settings.mongodb_min_pool_size,
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=10000,
        retryWrites=True,
        retryReads=True,
        tlsCAFile=certifi.where(),
    )
    _database = _client.get_database(settings.mongodb_database)

    # Retry ping to handle intermittent SSL handshake failures with Atlas
    import asyncio

    for attempt in range(5):
        try:
            await _database.command("ping")
            break
        except Exception as exc:
            if attempt < 4:
                logger.warning(
                    "mongodb_ping_retry attempt=%d error=%s", attempt + 1, exc
                )
                await asyncio.sleep(2)
            else:
                raise

    await ensure_indexes(_database)
    logger.info("mongodb_connected", extra={"database": settings.mongodb_database})


def get_database() -> AsyncDatabase:
    """Return the initialized application database."""
    if _database is None:
        raise RuntimeError("MongoDB has not been initialized")
    return _database


async def get_db() -> AsyncGenerator[AsyncDatabase, None]:
    """FastAPI dependency returning the shared async MongoDB database."""
    yield get_database()


async def close_mongodb() -> None:
    """Close MongoDB's pool during application shutdown."""
    global _client, _database
    if _client is not None:
        await _client.close()
        logger.info("mongodb_disconnected")
    _client = None
    _database = None


async def ensure_indexes(db: AsyncDatabase) -> None:
    """Create query-critical indexes idempotently on application startup."""
    await db.users.create_index("id", unique=True, name="users_id_unique")
    await db.users.create_index("email", unique=True, name="users_email_unique")
    await db.users.create_index(
        [("email", ASCENDING), ("display_name", ASCENDING)],
        name="users_search",
    )
    await db.refresh_tokens.create_index(
        "token_hash", unique=True, name="refresh_token_hash_unique"
    )
    await db.refresh_tokens.create_index(
        [("user_id", ASCENDING), ("revoked_at", ASCENDING), ("expires_at", DESCENDING)],
        name="refresh_tokens_active_sessions",
    )
    await db.conversations.create_index("id", unique=True, name="conversations_id_unique")
    await db.conversations.create_index(
        [("member_ids", ASCENDING), ("created_at", DESCENDING)],
        name="conversations_member_feed",
    )
    await db.conversations.create_index(
        [("type", ASCENDING), ("direct_key", ASCENDING)],
        unique=True,
        partialFilterExpression={"type": "direct"},
        name="direct_conversation_unique",
    )
    await db.messages.create_index("id", unique=True, name="messages_id_unique")
    await db.messages.create_index(
        [("conversation_id", ASCENDING), ("created_at", DESCENDING), ("id", DESCENDING)],
        name="messages_cursor_pagination",
    )
