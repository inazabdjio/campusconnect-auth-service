import base64
import json

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)


def _b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("Valeur base64url absente.")
    padded = value + ("=" * ((4 - len(value) % 4) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


class WebAuthnProvider:
    def __init__(self, rp_id: str, rp_name: str, origin: str):
        if not rp_id or not rp_name or not origin:
            raise ValueError("RP ID, RP name et origin WebAuthn doivent être configurés.")
        self.rp_id = rp_id
        self.rp_name = rp_name
        self.origin = origin.rstrip("/")

    def create_registration_options(self, user_id_bytes: bytes,
                                    user_email: str, user_display_name: str) -> str:
        options = generate_registration_options(
            rp_id=self.rp_id, rp_name=self.rp_name, user_id=user_id_bytes,
            user_name=user_email, user_display_name=user_display_name,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        return options_to_json(options)

    @staticmethod
    def challenge_from_options(options_json: str) -> bytes:
        data = json.loads(options_json)
        return _b64url_decode(data["challenge"])

    def verify_registration(self, credential_json: dict, expected_challenge: bytes):
        return verify_registration_response(
            credential=credential_json,
            expected_challenge=expected_challenge,
            expected_origin=self.origin,
            expected_rp_id=self.rp_id,
            require_user_verification=True,
        )

    def create_authentication_options(self,
                                      allowed_credential_ids: list[bytes] | None = None) -> str:
        kwargs = {
            "rp_id": self.rp_id,
            "user_verification": UserVerificationRequirement.REQUIRED,
        }
        if allowed_credential_ids:
            kwargs["allow_credentials"] = [
                PublicKeyCredentialDescriptor(id=cid) for cid in allowed_credential_ids
            ]
        return options_to_json(generate_authentication_options(**kwargs))

    def verify_authentication(self, credential_json: dict, expected_challenge: bytes,
                              credential_public_key: bytes,
                              credential_current_sign_count: int):
        return verify_authentication_response(
            credential=credential_json,
            expected_challenge=expected_challenge,
            expected_origin=self.origin,
            expected_rp_id=self.rp_id,
            credential_public_key=credential_public_key,
            credential_current_sign_count=credential_current_sign_count,
            require_user_verification=True,
        )