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
    UserVerificationRequirement,
)


class WebAuthnProvider:
    def __init__(self, rp_id: str, rp_name: str, origin: str):
        self.rp_id = rp_id
        self.rp_name = rp_name
        self.origin = origin

    def create_registration_options(self, user_id_bytes: bytes, user_email: str, user_display_name: str) -> str:
        options = generate_registration_options(
            rp_id=self.rp_id,
            rp_name=self.rp_name,
            user_id=user_id_bytes,
            user_name=user_email,
            user_display_name=user_display_name,
            authenticator_selection=AuthenticatorSelectionCriteria(
                # REQUIRED force la vérification locale sur le téléphone (empreinte, visage appareil ou code/mot de passe téléphone)
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        return options_to_json(options)

    def verify_registration(self, credential_json: dict, expected_challenge: bytes):
        return verify_registration_response(
            credential=credential_json,
            expected_challenge=expected_challenge,
            expected_origin=self.origin,
            expected_rp_id=self.rp_id,
            require_user_verification=True,
        )

    def create_authentication_options(self, allowed_credential_ids: list[bytes] | None = None) -> str:
        allow_credentials = [
            PublicKeyCredentialDescriptor(id=cid) for cid in (allowed_credential_ids or [])
        ]
        options = generate_authentication_options(
            rp_id=self.rp_id,
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        return options_to_json(options)

    def verify_authentication(
        self,
        credential_json: dict,
        expected_challenge: bytes,
        credential_public_key: bytes,
        credential_current_sign_count: int,
    ):
        return verify_authentication_response(
            credential=credential_json,
            expected_challenge=expected_challenge,
            expected_origin=self.origin,
            expected_rp_id=self.rp_id,
            credential_public_key=credential_public_key,
            credential_current_sign_count=credential_current_sign_count,
            require_user_verification=True,
        )