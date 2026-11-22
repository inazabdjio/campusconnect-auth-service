from uuid import UUID
from sqlalchemy.orm import Session

from app.domain.enums import RoleEnum
from app.domain.interfaces import UserRepository
from app.domain.models import UserEntity
from app.infrastructure.db.orm_models import UserORM


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_entity(orm: UserORM) -> UserEntity:
        return UserEntity(
            id=orm.id,
            email=orm.email,
            password_hash=orm.password_hash,
            role=orm.role,
            first_name=orm.first_name,
            last_name=orm.last_name,
            created_at=orm.created_at,
        )

    def get_by_email(self, email: str) -> UserEntity | None:
        orm = self.db.query(UserORM).filter(UserORM.email == email.strip().lower()).first()
        return self._to_entity(orm) if orm else None

    def get_by_id(self, user_id: UUID) -> UserEntity | None:
        orm = self.db.query(UserORM).filter(UserORM.id == user_id).first()
        return self._to_entity(orm) if orm else None

    def create(
        self,
        email: str,
        password_hash: str,
        role: RoleEnum,
        first_name: str,
        last_name: str,
    ) -> UserEntity:
        orm = UserORM(
            email=email.strip().lower(),
            password_hash=password_hash,
            role=role,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
        )
        self.db.add(orm)
        self.db.commit()
        self.db.refresh(orm)
        return self._to_entity(orm)

    def delete(self, user_id: UUID) -> bool:
        orm = self.db.query(UserORM).filter(UserORM.id == user_id).first()
        if not orm:
            return False
        self.db.delete(orm)
        self.db.commit()
        return True