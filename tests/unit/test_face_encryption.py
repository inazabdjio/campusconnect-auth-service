import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.security import decrypt_embedding, encrypt_embedding

VALID_FERNET_KEY = Fernet.generate_key().decode("utf-8")
OTHER_FERNET_KEY = Fernet.generate_key().decode("utf-8")


def test_encrypt_and_decrypt_embedding_success():
    raw_embedding = b"\x00\x01\x02\x03face-embedding-vector-bytes-test"

    encrypted = encrypt_embedding(raw_embedding, VALID_FERNET_KEY)
    assert isinstance(encrypted, bytes)
    assert encrypted != raw_embedding

    decrypted = decrypt_embedding(encrypted, VALID_FERNET_KEY)
    assert decrypted == raw_embedding


def test_encrypt_and_decrypt_with_non_fernet_string_key():
    custom_key = "ma-cle-personnalisee-non-fernet-pour-test"
    raw_embedding = b"embedding-avec-cle-derivee-sha256"

    encrypted = encrypt_embedding(raw_embedding, custom_key)
    decrypted = decrypt_embedding(encrypted, custom_key)

    assert decrypted == raw_embedding


@pytest.mark.parametrize("empty_key", ["", "   "])
def test_encrypt_embedding_missing_key_raises_value_error(empty_key: str):
    with pytest.raises(ValueError, match="FACE_ENCRYPTION_KEY"):
        encrypt_embedding(b"sample-bytes", empty_key)


@pytest.mark.parametrize("empty_key", ["", "   "])
def test_decrypt_embedding_missing_key_raises_value_error(empty_key: str):
    encrypted = encrypt_embedding(b"sample-bytes", VALID_FERNET_KEY)

    with pytest.raises(ValueError, match="FACE_ENCRYPTION_KEY"):
        decrypt_embedding(encrypted, empty_key)


def test_encrypt_empty_embedding_raises_value_error():
    with pytest.raises(ValueError, match="vide"):
        encrypt_embedding(b"", VALID_FERNET_KEY)


def test_decrypt_with_wrong_key_raises_invalid_token():
    encrypted = encrypt_embedding(b"secret-face-data", VALID_FERNET_KEY)

    with pytest.raises(InvalidToken):
        decrypt_embedding(encrypted, OTHER_FERNET_KEY)


def test_decrypt_tampered_data_raises_invalid_token():
    encrypted = bytearray(encrypt_embedding(b"secret-face-data", VALID_FERNET_KEY))
    encrypted[-1] ^= 0xFF

    with pytest.raises(InvalidToken):
        decrypt_embedding(bytes(encrypted), VALID_FERNET_KEY)