from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.db.models import USERS_COLLECTION, now_utc, serialize_user
from app.schemas.user import UserUpdate

_PERSONAL_INFO_FIELDS = ("full_name", "date_of_birth", "gender")
_CLINICAL_INFO_FIELDS = (
    "current_occupation",
    "highest_education_level",
    "primary_concerns",
    "symptom_onset_age",
)
_MEDICAL_INFO_FIELDS = ("relevant_history", "current_medications", "family_history", "sleep_patterns")


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

    async def get_by_full_name(
        self,
        db: AsyncIOMotorDatabase,
        full_name: str,
        *,
        include_password: bool = False,
    ) -> dict[str, Any] | None:
        normalized_name = full_name.strip()
        if not normalized_name:
            return None
        document = await db[USERS_COLLECTION].find_one({"personal_info.full_name": normalized_name})
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
        personal_info = self._normalize_section(signup_data.get("personal_info"), _PERSONAL_INFO_FIELDS)
        if personal_info.get("full_name") is None and signup_data.get("full_name") is not None:
            personal_info["full_name"] = signup_data["full_name"]
        clinical_info = self._normalize_section(signup_data.get("clinical_info"), _CLINICAL_INFO_FIELDS)
        medical_info = self._normalize_section(signup_data.get("medical_info"), _MEDICAL_INFO_FIELDS)
        personal_info = {key: self._prepare_for_storage(value) for key, value in personal_info.items()}
        clinical_info = {key: self._prepare_for_storage(value) for key, value in clinical_info.items()}
        medical_info = {key: self._prepare_for_storage(value) for key, value in medical_info.items()}
        document: dict[str, Any] = {
            "_id": ObjectId(),
            "email": signup_data["email"],
            "password_hash": password_hash,
            "personal_info": personal_info,
            "clinical_info": clinical_info,
            "medical_info": medical_info,
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
            flattened_updates = self._flatten_updates(updates)
            flattened_updates["updated_at"] = now_utc()
            document = await db[USERS_COLLECTION].find_one_and_update(
                {"_id": ObjectId(user_id)},
                {"$set": flattened_updates},
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

    @staticmethod
    def _normalize_section(section: dict[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any]:
        normalized = {key: None for key in keys}
        if section:
            for key in keys:
                if key in section:
                    normalized[key] = section[key]
        return normalized

    @classmethod
    def _flatten_updates(cls, updates: dict[str, Any]) -> dict[str, Any]:
        flattened: dict[str, Any] = {}
        for key, value in updates.items():
            if isinstance(value, dict):
                nested = cls._flatten_updates(value)
                for nested_key, nested_value in nested.items():
                    flattened[f"{key}.{nested_key}"] = cls._prepare_for_storage(nested_value)
            else:
                flattened[key] = cls._prepare_for_storage(value)
        return flattened

    @staticmethod
    def _prepare_for_storage(value: Any) -> Any:
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, time.min, tzinfo=timezone.utc)
        return value
