import base64
import json

import pytest

from app.domain.strategies.base import AuthStrategy
from app.domain.strategies.webauthn_strategy import WebAuthnProvider, _b64url_decode


def test_auth_strategy_is_abstract():
    assert issubclass(AuthStrategy, ABC := AuthStrategy.__mro__[1])
    with pytest.raises(TypeError):
        AuthStrategy()  # type: ignore[abstract]


def test_webauthn_provider_init_normalizes_origin():
    provider = WebAuthnProvider(
        rp_id="localhost",
        rp_name="CampusConnect",
        origin="http://localhost:8080/",
    )
    assert provider.rp_id == "localhost"
    assert provider.rp_name == "CampusConnect"
    assert provider.origin == "http://localhost:8080"


@pytest.mark.parametrize(
    "rp_id,rp_name,origin",
    [
        ("", "CampusConnect", "http://localhost:8080"),
        ("localhost", "", "http://localhost:8080"),
        ("localhost", "CampusConnect", ""),
    ],
)
def test_webauthn_provider_init_missing_config_raises_value_error(
    rp_id: str, rp_name: str, origin: str
):
    with pytest.raises(ValueError, match="WebAuthn"):
        WebAuthnProvider(rp_id=rp_id, rp_name=rp_name, origin=origin)


def test_b64url_decode_without_padding():
    raw_bytes = b"challenge-webauthn-sans-padding-123456"
    encoded_no_pad = base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")

    assert _b64url_decode(encoded_no_pad) == raw_bytes


@pytest.mark.parametrize("invalid_value", ["", None])
def test_b64url_decode_empty_or_none_raises_value_error(invalid_value):
    with pytest.raises(ValueError, match="base64url"):
        _b64url_decode(invalid_value)  # type: ignore[arg-type]


def test_create_registration_options_and_extract_challenge():
    provider = WebAuthnProvider(
        rp_id="localhost",
        rp_name="CampusConnect",
        origin="http://localhost:8080",
    )
    user_id_bytes = b"user-id-bytes-001"

    options_json = provider.create_registration_options(
        user_id_bytes=user_id_bytes,
        user_email="etudiant@univ.cm",
        user_display_name="Étudiant Test",
    )
    parsed = json.loads(options_json)

    assert parsed["rp"]["id"] == "localhost"
    assert parsed["rp"]["name"] == "CampusConnect"
    assert parsed["user"]["name"] == "etudiant@univ.cm"
    assert "challenge" in parsed

    challenge_bytes = provider.challenge_from_options(options_json)
    assert isinstance(challenge_bytes, bytes)
    assert len(challenge_bytes) > 0


def test_create_authentication_options_with_and_without_credentials():
    provider = WebAuthnProvider(
        rp_id="localhost",
        rp_name="CampusConnect",
        origin="http://localhost:8080",
    )

    opts_without = json.loads(provider.create_authentication_options())
    assert opts_without["rpId"] == "localhost"
    assert "challenge" in opts_without

    cred_id = b"credential-id-abc-123"
    opts_with = json.loads(
        provider.create_authentication_options(allowed_credential_ids=[cred_id])
    )
    assert opts_with["rpId"] == "localhost"
    assert len(opts_with["allowCredentials"]) == 1