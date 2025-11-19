from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    age: int | None = Field(default=None, ge=0)
    bio: str | None = Field(default=None, max_length=2000)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class UserUpdate(UserBase):
    pass
