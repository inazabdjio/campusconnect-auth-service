from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

from app.domain.enums import RoleEnum


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: RoleEnum = RoleEnum.STUDENT
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class FaceEnrollRequest(BaseModel):
    image_base64: str
    frame_2_base64: str | None = None
    consent_given: bool = True


class FaceLoginRequest(BaseModel):
    email: EmailStr
    image_base64: str
    frame_2_base64: str | None = None


class WebAuthnVerifyRequest(BaseModel):
    email: EmailStr | None = None
    credential: dict[str, Any]


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: RoleEnum
    first_name: str
    last_name: str
    created_at: datetime