import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from cryptography.fernet import Fernet


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: str,
    role: str,
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 30,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "userId": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def decode_access_token(token: str, secret_key: str, algorithm: str = "HS256") -> dict:
    return jwt.decode(token, secret_key, algorithms=[algorithm])


def _build_fernet(encryption_key: str) -> Fernet:
    if encryption_key:
        raw = encryption_key.encode("utf-8")
        # Accepte une clé Fernet valide ou dérive une clé 32 octets encodée base64url
        try:
            Fernet(raw)
            return Fernet(raw)
        except Exception:
            digest = hashlib.sha256(raw).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    digest = hashlib.sha256(b"campusconnect-dev-face-key").digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_embedding(embedding_bytes: bytes, encryption_key: str) -> bytes:
    return _build_fernet(encryption_key).encrypt(embedding_bytes)


def decrypt_embedding(encrypted_bytes: bytes, encryption_key: str) -> bytes:
    return _build_fernet(encryption_key).decrypt(encrypted_bytes)