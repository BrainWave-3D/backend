from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import get_current_user
from app.db.session import get_database
from app.schemas.auth import LogoutResponse
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/profile", tags=["profile"])
_user_service = UserService()


@router.get("/me", response_model=ProfileResponse)
async def read_profile(current_user: dict = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse.model_validate(current_user)


@router.put("/me", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> ProfileResponse:
    user = await _user_service.update_user(db, current_user["id"], payload)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return ProfileResponse.model_validate(user)


@router.delete("/me", response_model=LogoutResponse)
async def delete_profile(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> LogoutResponse:
    deleted = await _user_service.delete_user(db, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return LogoutResponse(detail="Account deleted")
