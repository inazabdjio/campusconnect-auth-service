import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Le mot de passe ne peut pas être vide.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError, AttributeError):
        return False


def hash_token(token: str) -> str:
    if not isinstance(token, str) or not token:
        raise ValueError("Le token ne peut pas être vide.")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, role: str, secret_key: str,
                        algorithm: str = "HS256", expires_minutes: int = 30) -> str:
    if not secret_key:
        raise ValueError("JWT_SECRET_KEY n'est pas configurée.")
    if expires_minutes <= 0:
        raise ValueError("La durée de vie du token doit être positive.")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id), "userId": str(user_id), "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def decode_access_token(token: str, secret_key: str, algorithm: str = "HS256") -> dict:
    if not secret_key:
        raise ValueError("JWT_SECRET_KEY n'est pas configurée.")
    return jwt.decode(token, secret_key, algorithms=[algorithm])


def _build_fernet(encryption_key: str) -> Fernet:
    if not encryption_key or not encryption_key.strip():
        raise ValueError("FACE_ENCRYPTION_KEY est absente. Configure une clé secrète.")
    raw = encryption_key.encode("utf-8")
    try:
        return Fernet(raw)
    except (ValueError, TypeError):
        # Compatibilité avec l'ancienne version qui dérivait les clés non-Fernet.
        digest = hashlib.sha256(raw).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_embedding(embedding_bytes: bytes, encryption_key: str) -> bytes:
    if not embedding_bytes:
        raise ValueError("Le modèle facial à chiffrer est vide.")
    return _build_fernet(encryption_key).encrypt(embedding_bytes)


def decrypt_embedding(encrypted_bytes: bytes, encryption_key: str) -> bytes:
    return _build_fernet(encryption_key).decrypt(encrypted_bytes)