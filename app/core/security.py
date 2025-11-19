from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from passlib.context import CryptContext

from app.core.config import settings
from app.db.models import TOKEN_BLACKLIST_COLLECTION
from app.db.session import get_database
from app.services.user_service import UserService

try:
    import bcrypt as _bcrypt  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional legacy dependency
    _bcrypt = None

# Use pbkdf2_sha256 to avoid bcrypt's 72-byte limit and backend issues on Windows
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__default_rounds=310000,
)
_http_bearer = HTTPBearer(auto_error=False)
user_service = UserService()


@dataclass
class TokenMeta:
    token: str
    jti: str
    expires_at: datetime


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    # Prefer the configured context, but fall back to bcrypt hashes that may exist already
    identified = pwd_context.identify(password_hash)
    if identified:
        return pwd_context.verify(password, password_hash)
    if password_hash.startswith("$2") and _bcrypt is not None:
        try:
            return _bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False
    return False


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> TokenMeta:
    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return TokenMeta(token=token, jti=payload["jti"], expires_at=expires_at)


def create_access_token(subject: str, extra_claims: Optional[Dict[str, Any]] = None) -> TokenMeta:
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    return _create_token(subject=subject, token_type="access", expires_delta=expires_delta, extra_claims=extra_claims)


def create_refresh_token(subject: str, extra_claims: Optional[Dict[str, Any]] = None) -> TokenMeta:
    expires_delta = timedelta(minutes=settings.refresh_token_expire_minutes)
    return _create_token(subject=subject, token_type="refresh", expires_delta=expires_delta, extra_claims=extra_claims)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials") from exc


async def _ensure_token_not_blacklisted(db: AsyncIOMotorDatabase, jti: str) -> None:
    token_entry = await db[TOKEN_BLACKLIST_COLLECTION].find_one({"jti": jti})
    if token_entry is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing or invalid")

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access" or "sub" not in payload or "jti" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    await _ensure_token_not_blacklisted(db, payload["jti"])

    user = await user_service.get_by_id(db, payload["sub"], include_password=False)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")

    return user
