from uuid import UUID
from sqlalchemy.orm import Session

from app.domain.interfaces import FaceTemplateRepository
from app.infrastructure.db.orm_models import FaceTemplateORM


class SqlAlchemyFaceTemplateRepository(FaceTemplateRepository):
    def __init__(self, db: Session):
        self.db = db

    def save_template(self, user_id: UUID, encrypted_embedding: bytes) -> None:
        orm = FaceTemplateORM(user_id=user_id, embedding=encrypted_embedding)
        self.db.add(orm)
        self.db.commit()

    def get_templates_by_user(self, user_id: UUID) -> list[bytes]:
        rows = (
            self.db.query(FaceTemplateORM)
            .filter(FaceTemplateORM.user_id == user_id)
            .order_by(FaceTemplateORM.created_at.desc())
            .all()
        )
        return [r.embedding for r in rows]