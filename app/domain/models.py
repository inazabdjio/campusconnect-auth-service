from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.enums import AuthMethodEnum, RoleEnum


@dataclass
class UserEntity:
    id: UUID
    email: str
    password_hash: str
    role: RoleEnum
    first_name: str
    last_name: str
    created_at: datetime


@dataclass
class AuthResult:
    user: UserEntity
    method: AuthMethodEnum