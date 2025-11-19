from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import (
    TokenMeta,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.models import TOKEN_BLACKLIST_COLLECTION, now_utc
from app.schemas.auth import LoginRequest, SignupRequest
from app.services.user_service import UserService


class AuthService:
    def __init__(self) -> None:
        self.user_service = UserService()

    async def register_user(
        self, db: AsyncIOMotorDatabase, signup: SignupRequest
    ) -> tuple[dict[str, Any], TokenMeta, TokenMeta]:
        existing_user = await self.user_service.get_by_email(db, signup.email)
        if existing_user is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        signup_payload = signup.model_dump(exclude_none=True)
        password = signup_payload.pop("password")
        password_hash = get_password_hash(password)
        user = await self.user_service.create_user(db, signup_payload, password_hash)
        return user, *self._issue_tokens(user)

    async def authenticate_user(
        self, db: AsyncIOMotorDatabase, login: LoginRequest
    ) -> tuple[dict[str, Any], TokenMeta, TokenMeta]:
        user = await self.user_service.get_by_email(db, login.email, include_password=True)
        if user is None or not verify_password(login.password, user.get("password_hash", "")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        sanitized_user = self.user_service.sanitize_user(user)
        return sanitized_user, *self._issue_tokens(sanitized_user)

    async def blacklist_refresh_token(self, db: AsyncIOMotorDatabase, token: str) -> None:
        payload = decode_token(token)
        if payload.get("type") != "refresh" or "jti" not in payload or "sub" not in payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token")

        jti = payload["jti"]
        existing = await db[TOKEN_BLACKLIST_COLLECTION].find_one({"jti": jti})
        if existing is not None:
            return

        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        entry = {
            "jti": jti,
            "token_type": "refresh",
            "user_id": payload["sub"],
            "expires_at": expires_at,
            "created_at": now_utc(),
        }
        await db[TOKEN_BLACKLIST_COLLECTION].insert_one(entry)

    def _issue_tokens(self, user: dict[str, Any]) -> tuple[TokenMeta, TokenMeta]:
        extra_claims = {"email": user.get("email")}
        access_meta = create_access_token(subject=str(user.get("id")), extra_claims=extra_claims)
        refresh_meta = create_refresh_token(subject=str(user.get("id")), extra_claims=extra_claims)
        return access_meta, refresh_meta
