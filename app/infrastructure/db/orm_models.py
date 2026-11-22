import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

from app.domain.enums import RoleEnum

Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserORM(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum, name="user_role_enum"), nullable=False, default=RoleEnum.STUDENT)
    first_name = Column(String(120), nullable=False)
    last_name = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    face_templates = relationship("FaceTemplateORM", back_populates="user", cascade="all, delete-orphan")
    webauthn_credentials = relationship("WebAuthnCredentialORM", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshTokenORM", back_populates="user", cascade="all, delete-orphan")


class FaceTemplateORM(Base):
    __tablename__ = "face_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = Column(LargeBinary, nullable=False)  # Vecteur chiffré au repos (aucune image brute stockée)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("UserORM", back_populates="face_templates")


class WebAuthnCredentialORM(Base):
    __tablename__ = "webauthn_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_id = Column(Text, unique=True, nullable=False)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("UserORM", back_populates="webauthn_credentials")


class RefreshTokenORM(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)

    user = relationship("UserORM", back_populates="refresh_tokens")