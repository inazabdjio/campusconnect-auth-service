from uuid import UUID
from sqlalchemy.orm import Session

from app.domain.interfaces import RefreshTokenRepository
from app.infrastructure.db.orm_models import RefreshTokenORM


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, db: Session):
        self.db = db

    def save_token(self, user_id: UUID, token_hash: str, expires_at) -> None:
        orm = RefreshTokenORM(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
        self.db.add(orm)
        self.db.commit()

    def get_valid_token(self, token_hash: str) -> dict | None:
        orm = (
            self.db.query(RefreshTokenORM)
            .filter(
                RefreshTokenORM.token_hash == token_hash,
                RefreshTokenORM.revoked.is_(False),
            )
            .first()
        )
        if not orm:
            return None
        return {
            "id": orm.id,
            "user_id": orm.user_id,
            "token_hash": orm.token_hash,
            "expires_at": orm.expires_at,
            "revoked": orm.revoked,
        }

    def revoke_token(self, token_hash: str) -> None:
        orm = (
            self.db.query(RefreshTokenORM)
            .filter(RefreshTokenORM.token_hash == token_hash)
            .first()
        )
        if orm:
            orm.revoked = True
            self.db.commit()