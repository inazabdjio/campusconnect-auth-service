from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.interfaces import RefreshTokenRepository
from app.infrastructure.db.orm_models import RefreshTokenORM


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, db: Session):
        self.db = db

    def save_token(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None:
        try:
            self.db.add(RefreshTokenORM(
                user_id=user_id, token_hash=token_hash,
                expires_at=expires_at, revoked=False,
            ))
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def get_valid_token(self, token_hash: str) -> dict | None:
        orm = self.db.query(RefreshTokenORM).filter(
            RefreshTokenORM.token_hash == token_hash,
            RefreshTokenORM.revoked.is_(False),
        ).first()
        if not orm:
            return None
        expires_at = _utc(orm.expires_at)
        if expires_at <= datetime.now(timezone.utc):
            return None
        return {
            "id": orm.id, "user_id": orm.user_id,
            "token_hash": orm.token_hash, "expires_at": expires_at,
            "revoked": orm.revoked,
        }

    def consume_token(self, token_hash: str) -> dict | None:
        """Consomme un token une seule fois; FOR UPDATE protège les accès concurrents sur PostgreSQL."""
        try:
            orm = self.db.query(RefreshTokenORM).filter(
                RefreshTokenORM.token_hash == token_hash,
                RefreshTokenORM.revoked.is_(False),
            ).with_for_update().first()
            if not orm:
                return None
            expires_at = _utc(orm.expires_at)
            if expires_at <= datetime.now(timezone.utc):
                return None
            record = {
                "id": orm.id, "user_id": orm.user_id,
                "token_hash": orm.token_hash, "expires_at": expires_at,
                "revoked": orm.revoked,
            }
            orm.revoked = True
            self.db.commit()
            return record
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def revoke_token(self, token_hash: str) -> None:
        try:
            orm = self.db.query(RefreshTokenORM).filter(
                RefreshTokenORM.token_hash == token_hash
            ).first()
            if orm and not orm.revoked:
                orm.revoked = True
                self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def revoke_all_for_user(self, user_id: UUID) -> None:
        try:
            self.db.execute(
                update(RefreshTokenORM)
                .where(RefreshTokenORM.user_id == user_id,
                       RefreshTokenORM.revoked.is_(False))
                .values(revoked=True)
            )
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise