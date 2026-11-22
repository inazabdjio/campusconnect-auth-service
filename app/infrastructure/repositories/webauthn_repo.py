from uuid import UUID
from sqlalchemy.orm import Session

from app.domain.interfaces import WebAuthnCredentialRepository
from app.infrastructure.db.orm_models import WebAuthnCredentialORM


class SqlAlchemyWebAuthnRepository(WebAuthnCredentialRepository):
    def __init__(self, db: Session):
        self.db = db

    def save_credential(
        self,
        user_id: UUID,
        credential_id: str,
        public_key: str,
        sign_count: int,
    ) -> None:
        existing = (
            self.db.query(WebAuthnCredentialORM)
            .filter(WebAuthnCredentialORM.credential_id == credential_id)
            .first()
        )
        if existing:
            existing.public_key = public_key
            existing.sign_count = sign_count
            self.db.commit()
            return

        orm = WebAuthnCredentialORM(
            user_id=user_id,
            credential_id=credential_id,
            public_key=public_key,
            sign_count=sign_count,
        )
        self.db.add(orm)
        self.db.commit()

    def get_by_credential_id(self, credential_id: str) -> dict | None:
        orm = (
            self.db.query(WebAuthnCredentialORM)
            .filter(WebAuthnCredentialORM.credential_id == credential_id)
            .first()
        )
        if not orm:
            return None
        return {
            "id": orm.id,
            "user_id": orm.user_id,
            "credential_id": orm.credential_id,
            "public_key": orm.public_key,
            "sign_count": orm.sign_count,
        }

    def update_sign_count(self, credential_id: str, new_sign_count: int) -> None:
        orm = (
            self.db.query(WebAuthnCredentialORM)
            .filter(WebAuthnCredentialORM.credential_id == credential_id)
            .first()
        )
        if orm:
            orm.sign_count = new_sign_count
            self.db.commit()