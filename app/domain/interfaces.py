from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.enums import RoleEnum
from app.domain.models import AuthResult, UserEntity


class UserRepository(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> UserEntity | None:
        ...

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> UserEntity | None:
        ...

    @abstractmethod
    def create(
        self,
        email: str,
        password_hash: str,
        role: RoleEnum,
        first_name: str,
        last_name: str,
    ) -> UserEntity:
        ...

    @abstractmethod
    def delete(self, user_id: UUID) -> bool:
        ...


class FaceTemplateRepository(ABC):
    @abstractmethod
    def save_template(self, user_id: UUID, encrypted_embedding: bytes) -> None:
        ...

    @abstractmethod
    def get_templates_by_user(self, user_id: UUID) -> list[bytes]:
        ...


class WebAuthnCredentialRepository(ABC):
    @abstractmethod
    def save_credential(
        self,
        user_id: UUID,
        credential_id: str,
        public_key: str,
        sign_count: int,
    ) -> None:
        ...

    @abstractmethod
    def get_by_credential_id(self, credential_id: str) -> dict | None:
        ...

    @abstractmethod
    def update_sign_count(self, credential_id: str, new_sign_count: int) -> None:
        ...


class RefreshTokenRepository(ABC):
    @abstractmethod
    def save_token(self, user_id: UUID, token_hash: str, expires_at) -> None:
        ...

    @abstractmethod
    def get_valid_token(self, token_hash: str) -> dict | None:
        ...

    @abstractmethod
    def revoke_token(self, token_hash: str) -> None:
        ...


class AuthEventPublisher(ABC):
    @abstractmethod
    def publish_user_registered(self, payload: dict) -> None:
        ...

    @abstractmethod
    def publish_user_deleted(self, payload: dict) -> None:
        ...