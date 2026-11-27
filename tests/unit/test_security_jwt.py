import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.security import create_access_token, decode_access_token

SECRET_KEY = "unit-test-secret-key-with-at-least-32-bytes-for-hs256!"
OTHER_SECRET_KEY = "another-secret-key-with-at-least-32-bytes-for-hs256!"


def test_create_and_decode_access_token_success():
    token = create_access_token(
        user_id="user-123",
        role="STUDENT",
        secret_key=SECRET_KEY,
        algorithm="HS256",
        expires_minutes=15,
    )

    assert isinstance(token, str)
    assert len(token) > 0

    payload = decode_access_token(token, secret_key=SECRET_KEY, algorithm="HS256")
    assert payload["sub"] == "user-123"
    assert payload["userId"] == "user-123"
    assert payload["role"] == "STUDENT"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_create_access_token_empty_secret_raises_value_error():
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        create_access_token(user_id="user-123", role="ADMIN", secret_key="")


@pytest.mark.parametrize("invalid_minutes", [0, -1, -10])
def test_create_access_token_non_positive_expiry_raises_value_error(invalid_minutes: int):
    with pytest.raises(ValueError, match="durée de vie"):
        create_access_token(
            user_id="user-123",
            role="TEACHER",
            secret_key=SECRET_KEY,
            expires_minutes=invalid_minutes,
        )


def test_decode_access_token_empty_secret_raises_value_error():
    token = create_access_token(user_id="user-123", role="STUDENT", secret_key=SECRET_KEY)

    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        decode_access_token(token, secret_key="")


def test_decode_access_token_wrong_secret_raises_invalid_signature():
    token = create_access_token(user_id="user-123", role="STUDENT", secret_key=SECRET_KEY)

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token, secret_key=OTHER_SECRET_KEY)


def test_decode_access_token_malformed_token_raises_decode_error():
    with pytest.raises(jwt.DecodeError):
        decode_access_token("ceci.nest.pas.un.jwt", secret_key=SECRET_KEY)


def test_decode_access_token_expired_raises_expired_signature():
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    expired_payload = {
        "sub": "user-999",
        "userId": "user-999",
        "role": "STUDENT",
        "iat": int(past.timestamp()) - 60,
        "exp": int(past.timestamp()),
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm="HS256")
    time.sleep(0.05)

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token, secret_key=SECRET_KEY, algorithm="HS256")