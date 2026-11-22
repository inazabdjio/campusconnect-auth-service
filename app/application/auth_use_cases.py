import base64
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
import numpy as np

from app.application.dtos import TokenPairResponse, UserResponse
from app.core.config import Settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decrypt_embedding,
    encrypt_embedding,
    hash_password,
    hash_token,
)
from app.domain.enums import RoleEnum
from app.domain.events import build_user_deleted_event, build_user_registered_event
from app.domain.interfaces import (
    AuthEventPublisher,
    FaceTemplateRepository,
    RefreshTokenRepository,
    UserRepository,
    WebAuthnCredentialRepository,
)
from app.domain.strategies.face_strategy import FaceBiometricEngine, FaceProcessingError
from app.domain.strategies.password_strategy import PasswordAuthStrategy
from app.domain.strategies.webauthn_strategy import WebAuthnProvider


class ConflictError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


class BadRequestError(Exception):
    pass


class AuthUseCases:
    def __init__(
        self,
        settings: Settings,
        user_repo: UserRepository,
        face_repo: FaceTemplateRepository,
        webauthn_repo: WebAuthnCredentialRepository,
        token_repo: RefreshTokenRepository,
        event_publisher: AuthEventPublisher,
        face_engine: FaceBiometricEngine,
        webauthn_provider: WebAuthnProvider,
    ):
        self.settings = settings
        self.user_repo = user_repo
        self.face_repo = face_repo
        self.webauthn_repo = webauthn_repo
        self.token_repo = token_repo
        self.event_publisher = event_publisher
        self.face_engine = face_engine
        self.webauthn_provider = webauthn_provider
        self.password_strategy = PasswordAuthStrategy(user_repo)
        # Stockage temporaire des challenges WebAuthn en mémoire (à passer sur Redis en multi-instance)
        self._challenges: dict[str, bytes] = {}

    def _issue_tokens(self, user_id: UUID, role: RoleEnum) -> TokenPairResponse:
        access_token = create_access_token(
            user_id=str(user_id),
            role=role.value,
            secret_key=self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
            expires_minutes=self.settings.access_token_expire_minutes,
        )
        raw_refresh = create_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.settings.refresh_token_expire_days)
        self.token_repo.save_token(user_id=user_id, token_hash=hash_token(raw_refresh), expires_at=expires_at)
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )

    def register(
        self,
        email: str,
        password: str,
        role: RoleEnum,
        first_name: str,
        last_name: str,
    ) -> UserResponse:
        existing = self.user_repo.get_by_email(email)
        if existing:
            raise ConflictError("Un compte existe déjà avec cette adresse e-mail.")

        user = self.user_repo.create(
            email=email,
            password_hash=hash_password(password),
            role=role,
            first_name=first_name,
            last_name=last_name,
        )
        event = build_user_registered_event(
            user_id=user.id,
            email=user.email,
            role=user.role.value,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        self.event_publisher.publish_user_registered(event)
        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            first_name=user.first_name,
            last_name=user.last_name,
            created_at=user.created_at,
        )

    def login_password(self, email: str, password: str) -> TokenPairResponse:
        result = self.password_strategy.authenticate(email=email, password=password)
        if not result:
            raise UnauthorizedError("Identifiants invalides.")
        return self._issue_tokens(result.user.id, result.user.role)

    def refresh_tokens(self, refresh_token: str) -> TokenPairResponse:
        record = self.token_repo.get_valid_token(hash_token(refresh_token))
        if not record:
            raise UnauthorizedError("Refresh token invalide ou révoqué.")
        if record["expires_at"] <= datetime.now(timezone.utc):
            raise UnauthorizedError("Refresh token expiré.")

        user = self.user_repo.get_by_id(record["user_id"])
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")

        self.token_repo.revoke_token(hash_token(refresh_token))
        return self._issue_tokens(user.id, user.role)

    def get_me(self, user_id: UUID) -> UserResponse:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")
        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            first_name=user.first_name,
            last_name=user.last_name,
            created_at=user.created_at,
        )

    def delete_user(self, user_id: UUID) -> None:
        deleted = self.user_repo.delete(user_id)
        if not deleted:
            raise BadRequestError("Utilisateur introuvable.")
        self.event_publisher.publish_user_deleted(build_user_deleted_event(user_id))

    def enroll_face(
        self,
        user_id: UUID,
        image_base64: str,
        frame_2_base64: str | None = None,
        consent_given: bool = True,
    ) -> dict:
        if not consent_given:
            raise BadRequestError("Le consentement explicite est requis pour l'enrôlement facial.")
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")

        self.face_engine.verify_simple_liveness(image_base64, frame_2_base64)
        embedding = self.face_engine.extract_embedding(image_base64)
        encrypted = encrypt_embedding(embedding.tobytes(), self.settings.face_encryption_key)
        self.face_repo.save_template(user_id=user.id, encrypted_embedding=encrypted)
        return {"status": "ENROLLED", "userId": str(user.id)}

    def login_face(
        self,
        email: str,
        image_base64: str,
        frame_2_base64: str | None = None,
    ) -> TokenPairResponse:
        user = self.user_repo.get_by_email(email)
        if not user:
            raise UnauthorizedError("Échec de l'authentification faciale.")

        encrypted_templates = self.face_repo.get_templates_by_user(user.id)
        if not encrypted_templates:
            raise UnauthorizedError("Aucun modèle facial enregistré pour cet utilisateur.")

        self.face_engine.verify_simple_liveness(image_base64, frame_2_base64)
        probe_vec = self.face_engine.extract_embedding(image_base64)

        matched = False
        for enc in encrypted_templates:
            try:
                raw_bytes = decrypt_embedding(enc, self.settings.face_encryption_key)
                stored_vec = np.frombuffer(raw_bytes, dtype=np.float32)
                ok, _ = self.face_engine.is_match(probe_vec, stored_vec)
                if ok:
                    matched = True
                    break
            except FaceProcessingError:
                continue

        if not matched:
            raise UnauthorizedError("Visage non reconnu.")
        return self._issue_tokens(user.id, user.role)

    def webauthn_register_options(self, user_id: UUID) -> dict:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")
        options_json = self.webauthn_provider.create_registration_options(
            user_id_bytes=user.id.bytes,
            user_email=user.email,
            user_display_name=f"{user.first_name} {user.last_name}",
        )
        challenge_key = secrets.token_urlsafe(16)
        self._challenges[challenge_key] = base64.urlsafe_b64encode(user.id.bytes)
        return {"challengeKey": challenge_key, "optionsJson": options_json}

    def webauthn_register_verify(self, user_id: UUID, credential: dict) -> dict:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")
        cred_id = credential.get("id") or credential.get("rawId")
        pub_key = credential.get("publicKey") or credential.get("response", {}).get("attestationObject", "")
        if not cred_id or not pub_key:
            raise BadRequestError("Données d'identifiant WebAuthn incomplètes.")
        self.webauthn_repo.save_credential(
            user_id=user.id,
            credential_id=str(cred_id),
            public_key=str(pub_key),
            sign_count=0,
        )
        return {"status": "REGISTERED", "credentialId": str(cred_id)}

    def webauthn_login_options(self, email: str | None = None) -> dict:
        options_json = self.webauthn_provider.create_authentication_options()
        challenge_key = secrets.token_urlsafe(16)
        self._challenges[challenge_key] = b"auth-challenge"
        return {"challengeKey": challenge_key, "optionsJson": options_json, "email": email}

    def webauthn_login_verify(self, credential: dict, email: str | None = None) -> TokenPairResponse:
        cred_id = credential.get("id") or credential.get("rawId")
        if not cred_id:
            raise UnauthorizedError("Identifiant WebAuthn manquant.")
        stored = self.webauthn_repo.get_by_credential_id(str(cred_id))
        if not stored:
            raise UnauthorizedError("Identifiant biométrique / téléphone non reconnu.")
        user = self.user_repo.get_by_id(stored["user_id"])
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")
        if email and user.email.lower() != email.strip().lower():
            raise UnauthorizedError("L'identifiant ne correspond pas au compte.")
        self.webauthn_repo.update_sign_count(str(cred_id), stored["sign_count"] + 1)
        return self._issue_tokens(user.id, user.role)