from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.db.models import USERS_COLLECTION, now_utc, serialize_user
from app.schemas.user import UserUpdate


class UserService:
    async def get_by_id(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        *,
        include_password: bool = False,
    ) -> dict[str, Any] | None:
        if not ObjectId.is_valid(user_id):
            return None
        document = await db[USERS_COLLECTION].find_one({"_id": ObjectId(user_id)})
        if document is None:
            return None
        return serialize_user(document, include_password=include_password)

    async def get_by_email(
        self,
        db: AsyncIOMotorDatabase,
        email: str,
        *,
        include_password: bool = False,
    ) -> dict[str, Any] | None:
        document = await db[USERS_COLLECTION].find_one({"email": email})
        if document is None:
            return None
        return serialize_user(document, include_password=include_password)

    async def create_user(
        self,
        db: AsyncIOMotorDatabase,
        signup_data: dict[str, Any],
        password_hash: str,
    ) -> dict[str, Any]:
        timestamp = now_utc()
        document: dict[str, Any] = {
            "_id": ObjectId(),
            "email": signup_data["email"],
            "password_hash": password_hash,
            "name": signup_data.get("name"),
            "age": signup_data.get("age"),
            "bio": signup_data.get("bio"),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        await db[USERS_COLLECTION].insert_one(document)
        return serialize_user(document)

    async def update_user(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        user_update: UserUpdate,
    ) -> dict[str, Any] | None:
        if not ObjectId.is_valid(user_id):
            return None
        updates = user_update.model_dump(exclude_unset=True)
        if updates:
            updates["updated_at"] = now_utc()
            document = await db[USERS_COLLECTION].find_one_and_update(
                {"_id": ObjectId(user_id)},
                {"$set": updates},
                return_document=ReturnDocument.AFTER,
            )
        else:
            document = await db[USERS_COLLECTION].find_one({"_id": ObjectId(user_id)})
        if document is None:
            return None
        return serialize_user(document)

    async def delete_user(self, db: AsyncIOMotorDatabase, user_id: str) -> bool:
        if not ObjectId.is_valid(user_id):
            return False
        result = await db[USERS_COLLECTION].delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count == 1

    @staticmethod
    def sanitize_user(user: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(user)
        sanitized.pop("password_hash", None)
        return sanitized
