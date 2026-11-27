from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.security import (
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.domain.enums import AuthMethodEnum, RoleEnum
from app.domain.models import AuthResult, UserEntity


def test_hash_and_verify_password_success():
    plain = "MonMotDePasseSecurise123!"
    hashed = hash_password(plain)

    assert isinstance(hashed, str)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("MauvaisMotDePasse", hashed) is False


@pytest.mark.parametrize("invalid_password", ["", None, 12345])
def test_hash_password_invalid_value_raises_value_error(invalid_password):
    with pytest.raises(ValueError, match="mot de passe"):
        hash_password(invalid_password)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "plain_input,hashed_input",
    [
        ("secret", "hash-invalide-non-bcrypt"),
        ("secret", ""),
        (None, "$2b$12$abcdefghijklmnopqrstuvwxyzABCDEFG"),  # type: ignore[arg-type]
    ],
)
def test_verify_password_invalid_inputs_return_false(plain_input, hashed_input):
    assert verify_password(plain_input, hashed_input) is False


def test_create_refresh_token_and_hash_token():
    refresh_token = create_refresh_token()
    assert isinstance(refresh_token, str)
    assert len(refresh_token) > 20

    hashed_1 = hash_token(refresh_token)
    hashed_2 = hash_token(refresh_token)

    assert len(hashed_1) == 64  # SHA-256 hex digest
    assert hashed_1 == hashed_2
    assert hashed_1 != refresh_token


@pytest.mark.parametrize("invalid_token", ["", None])
def test_hash_token_empty_or_none_raises_value_error(invalid_token):
    with pytest.raises(ValueError, match="token"):
        hash_token(invalid_token)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "role,expected_value",
    [
        (RoleEnum.STUDENT, "STUDENT"),
        (RoleEnum.LECTURER, "LECTURER"),
        (RoleEnum.ADMIN, "ADMIN"),
    ],
)
def test_role_enum_values_and_user_entity(role: RoleEnum, expected_value: str):
    assert role.value == expected_value
    assert RoleEnum(expected_value) is role

    user = UserEntity(
        id=uuid4(),
        email="etudiant@univ.cm",
        password_hash=hash_password("Pass1234!"),
        role=role,
        first_name="Ina",
        last_name="Test",
        created_at=datetime.now(timezone.utc),
    )
    assert user.role == role

    result = AuthResult(user=user, method=AuthMethodEnum.PASSWORD)
    assert result.user.role == role
    assert result.method == AuthMethodEnum.PASSWORD


def test_invalid_role_value_raises_value_error():
    with pytest.raises(ValueError):
        RoleEnum("UNKNOWN_ROLE")