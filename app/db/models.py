from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from bson import ObjectId

USERS_COLLECTION = "users"
TOKEN_BLACKLIST_COLLECTION = "token_blacklist"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize_user(document: Mapping[str, Any], *, include_password: bool = False) -> dict[str, Any]:
    user: dict[str, Any] = {
        "id": str(document["_id"]),
        "email": document["email"],
        "name": document.get("name"),
        "age": document.get("age"),
        "bio": document.get("bio"),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }
    if include_password and "password_hash" in document:
        user["password_hash"] = document["password_hash"]
    return user


def to_object_id(value: str) -> ObjectId:
    return ObjectId(value)
