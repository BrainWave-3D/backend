from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.db.models import (
    CHAT_CONVERSATIONS_COLLECTION,
    CHAT_MESSAGES_COLLECTION,
    TOKEN_BLACKLIST_COLLECTION,
    USERS_COLLECTION,
)

_client: Optional[AsyncIOMotorClient] = None


async def connect_to_db() -> None:
    global _client
    if _client is not None:
        return

    client = AsyncIOMotorClient(settings.mongo_uri, uuidRepresentation="standard")
    await client.admin.command("ping")

    db = client[settings.mongo_db_name]
    await db[USERS_COLLECTION].create_index("email", unique=True)
    await db[USERS_COLLECTION].create_index(
        "personal_info.full_name",
        unique=True,
        partialFilterExpression={"personal_info.full_name": {"$type": "string"}},
    )
    await db[TOKEN_BLACKLIST_COLLECTION].create_index("jti", unique=True)
    await db[TOKEN_BLACKLIST_COLLECTION].create_index("expires_at", expireAfterSeconds=0)
    await db[CHAT_CONVERSATIONS_COLLECTION].create_index([("user_id", 1), ("updated_at", -1)])
    await db[CHAT_MESSAGES_COLLECTION].create_index([("conversation_id", 1), ("created_at", 1)])
    await db[CHAT_MESSAGES_COLLECTION].create_index([("user_id", 1), ("created_at", -1)])

    _client = client


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def get_database() -> AsyncIterator[AsyncIOMotorDatabase]:
    if _client is None:
        await connect_to_db()
    if _client is None:
        raise RuntimeError("MongoDB client is not initialized")
    yield _client[settings.mongo_db_name]
