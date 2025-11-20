from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from bson import ObjectId

USERS_COLLECTION = "users"
TOKEN_BLACKLIST_COLLECTION = "token_blacklist"

_PERSONAL_INFO_KEYS = ("full_name", "date_of_birth", "gender")
_CLINICAL_INFO_KEYS = (
    "current_occupation",
    "highest_education_level",
    "primary_concerns",
    "symptom_onset_age",
)
_MEDICAL_INFO_KEYS = ("relevant_history", "current_medications", "family_history", "sleep_patterns")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize_user(document: Mapping[str, Any], *, include_password: bool = False) -> dict[str, Any]:
    personal_info = _normalize_section(document.get("personal_info"), _PERSONAL_INFO_KEYS)
    clinical_info = _normalize_section(document.get("clinical_info"), _CLINICAL_INFO_KEYS)
    medical_info = _normalize_section(document.get("medical_info"), _MEDICAL_INFO_KEYS)
    user: dict[str, Any] = {
        "id": str(document["_id"]),
        "email": document["email"],
        "personal_info": personal_info,
        "clinical_info": clinical_info,
        "medical_info": medical_info,
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }
    if include_password and "password_hash" in document:
        user["password_hash"] = document["password_hash"]
    return user


def to_object_id(value: str) -> ObjectId:
    return ObjectId(value)


def _normalize_section(section: Mapping[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any]:
    normalized = {key: None for key in keys}
    if section:
        for key in keys:
            if key in section:
                normalized[key] = section[key]
    return normalized
