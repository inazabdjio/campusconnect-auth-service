from app.core.security import verify_password
from app.domain.enums import AuthMethodEnum
from app.domain.interfaces import UserRepository
from app.domain.models import AuthResult
from app.domain.strategies.base import AuthStrategy


class PasswordAuthStrategy(AuthStrategy):
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def authenticate(self, email: str, password: str) -> AuthResult | None:
        user = self.user_repo.get_by_email(email.strip().lower())
        if not user or not verify_password(password, user.password_hash):
            return None
        return AuthResult(user=user, method=AuthMethodEnum.PASSWORD)