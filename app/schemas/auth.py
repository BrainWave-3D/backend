from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.user import UserRead


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    user: UserRead
    tokens: AuthTokens


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class LogoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    detail: str
