from __future__ import annotations

from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.session import get_database
from app.schemas.auth import (
    AuthResponse,
    AuthTokens,
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    SignupRequest,
)
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
_auth_service = AuthService()


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AuthResponse:
    user, access_meta, refresh_meta = await _auth_service.register_user(db, payload)
    tokens = AuthTokens(access_token=access_meta.token, refresh_token=refresh_meta.token)
    return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AuthResponse:
    user, access_meta, refresh_meta = await _auth_service.authenticate_user(db, payload)
    tokens = AuthTokens(access_token=access_meta.token, refresh_token=refresh_meta.token)
    return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    payload: RefreshTokenRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> LogoutResponse:
    await _auth_service.blacklist_refresh_token(db, payload.refresh_token)
    return LogoutResponse(detail="Logged out successfully")
