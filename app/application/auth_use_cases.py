import base64
import threading
import time
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


# AuthUseCases est recréé à chaque requête FastAPI dans la configuration actuelle.
# Ce cache de processus permet de retrouver le challenge entre /options et /verify.
# Pour plusieurs workers/serveurs, remplacer impérativement par Redis ou un stockage partagé.
_WEBAUTHN_CHALLENGES: dict[str, tuple[bytes, float]] = {}
_WEBAUTHN_CHALLENGES_LOCK = threading.Lock()
_WEBAUTHN_CHALLENGE_TTL = 300


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("Valeur base64url absente.")
    padded = value + ("=" * ((4 - len(value) % 4) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _store_challenge(key: str, challenge: bytes) -> None:
    now = time.time()
    with _WEBAUTHN_CHALLENGES_LOCK:
        for old_key, (_, expiry) in list(_WEBAUTHN_CHALLENGES.items()):
            if expiry <= now:
                _WEBAUTHN_CHALLENGES.pop(old_key, None)
        _WEBAUTHN_CHALLENGES[key] = (challenge, now + _WEBAUTHN_CHALLENGE_TTL)


def _consume_challenge(key: str) -> bytes | None:
    with _WEBAUTHN_CHALLENGES_LOCK:
        item = _WEBAUTHN_CHALLENGES.pop(key, None)
    if item is None:
        return None
    challenge, expiry = item
    return challenge if expiry > time.time() else None


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

    def _issue_tokens(self, user_id: UUID, role: RoleEnum) -> TokenPairResponse:
        access_token = create_access_token(
            user_id=str(user_id),
            role=role.value,
            secret_key=self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
            expires_minutes=self.settings.access_token_expire_minutes,
        )
        raw_refresh = create_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.settings.refresh_token_expire_days
        )
        self.token_repo.save_token(
            user_id=user_id,
            token_hash=hash_token(raw_refresh),
            expires_at=expires_at,
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )

    def register(self, email: str, password: str, role: RoleEnum,
                 first_name: str, last_name: str) -> UserResponse:
        normalized_email = email.strip().lower()
        if self.user_repo.get_by_email(normalized_email):
            raise ConflictError("Un compte existe déjà avec cette adresse e-mail.")
        user = self.user_repo.create(
            email=normalized_email,
            password_hash=hash_password(password),
            role=role,
            first_name=first_name,
            last_name=last_name,
        )
        event = build_user_registered_event(
            user_id=user.id, email=user.email, role=user.role.value,
            first_name=user.first_name, last_name=user.last_name,
        )
        self.event_publisher.publish_user_registered(event)
        return UserResponse(
            id=user.id, email=user.email, role=user.role,
            first_name=user.first_name, last_name=user.last_name,
            created_at=user.created_at,
        )

    def login_password(self, email: str, password: str) -> TokenPairResponse:
        result = self.password_strategy.authenticate(email=email, password=password)
        if not result:
            raise UnauthorizedError("Identifiants invalides.")
        return self._issue_tokens(result.user.id, result.user.role)

    def refresh_tokens(self, refresh_token: str) -> TokenPairResponse:
        digest = hash_token(refresh_token)
        consume = getattr(self.token_repo, "consume_token", None)
        if callable(consume):
            record = consume(digest)
        else:
            record = self.token_repo.get_valid_token(digest)
            if record:
                expires_at = record["expires_at"]
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= datetime.now(timezone.utc):
                    record = None
                else:
                    self.token_repo.revoke_token(digest)
        if not record:
            raise UnauthorizedError("Refresh token invalide, expiré ou déjà utilisé.")
        user = self.user_repo.get_by_id(record["user_id"])
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")
        return self._issue_tokens(user.id, user.role)

    def get_me(self, user_id: UUID) -> UserResponse:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")
        return UserResponse(
            id=user.id, email=user.email, role=user.role,
            first_name=user.first_name, last_name=user.last_name,
            created_at=user.created_at,
        )

    def delete_user(self, user_id: UUID) -> None:
        if not self.user_repo.get_by_id(user_id):
            raise BadRequestError("Utilisateur introuvable.")
        revoke_all = getattr(self.token_repo, "revoke_all_for_user", None)
        if callable(revoke_all):
            revoke_all(user_id)
        if not self.user_repo.delete(user_id):
            raise BadRequestError("Utilisateur introuvable.")
        self.event_publisher.publish_user_deleted(build_user_deleted_event(user_id))

    def enroll_face(self, user_id: UUID, image_base64: str,
                    frame_2_base64: str | None = None,
                    consent_given: bool = True) -> dict:
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

    def login_face(self, email: str, image_base64: str,
                   frame_2_base64: str | None = None) -> TokenPairResponse:
        user = self.user_repo.get_by_email(email.strip().lower())
        if not user:
            raise UnauthorizedError("Échec de l'authentification faciale.")
        templates = self.face_repo.get_templates_by_user(user.id)
        if not templates:
            raise UnauthorizedError("Aucun modèle facial enregistré pour cet utilisateur.")
        self.face_engine.verify_simple_liveness(image_base64, frame_2_base64)
        probe = self.face_engine.extract_embedding(image_base64)
        matched = False
        for encrypted in templates:
            try:
                raw = decrypt_embedding(encrypted, self.settings.face_encryption_key)
                stored = np.frombuffer(raw, dtype=np.float32)
                ok, _ = self.face_engine.is_match(probe, stored)
                if ok:
                    matched = True
                    break
            except Exception:
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
        challenge = self.webauthn_provider.challenge_from_options(options_json)
        _store_challenge(f"register:{user.id}", challenge)
        return {"challengeKey": str(user.id), "optionsJson": options_json}

    def webauthn_register_verify(self, user_id: UUID, credential: dict) -> dict:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")
        challenge = _consume_challenge(f"register:{user.id}")
        if challenge is None:
            raise UnauthorizedError("Challenge WebAuthn absent ou expiré. Recommence l'enregistrement.")
        try:
            result = self.webauthn_provider.verify_registration(credential, challenge)
        except Exception as exc:
            raise UnauthorizedError("Échec de la vérification cryptographique de l'enregistrement WebAuthn.") from exc
        credential_id = _b64url_encode(result.credential_id)
        submitted_id = credential.get("rawId") or credential.get("id")
        if submitted_id and submitted_id != credential_id:
            raise UnauthorizedError("L'identifiant du credential WebAuthn ne correspond pas.")
        self.webauthn_repo.save_credential(
            user_id=user.id,
            credential_id=credential_id,
            public_key=_b64url_encode(result.credential_public_key),
            sign_count=int(result.sign_count),
        )
        return {"status": "REGISTERED", "credentialId": credential_id}

    def webauthn_login_options(self, email: str | None = None) -> dict:
        normalized_email = email.strip().lower() if email else None
        options_json = self.webauthn_provider.create_authentication_options()
        challenge = self.webauthn_provider.challenge_from_options(options_json)
        scope = normalized_email or "*"
        _store_challenge(f"login:{scope}", challenge)
        return {"challengeKey": scope, "optionsJson": options_json, "email": normalized_email}

    def webauthn_login_verify(self, credential: dict,
                              email: str | None = None) -> TokenPairResponse:
        credential_id = credential.get("rawId") or credential.get("id")
        if not credential_id:
            raise UnauthorizedError("Identifiant WebAuthn manquant.")
        stored = self.webauthn_repo.get_by_credential_id(str(credential_id))
        if not stored:
            raise UnauthorizedError("Identifiant biométrique / téléphone non reconnu.")
        user = self.user_repo.get_by_id(stored["user_id"])
        if not user:
            raise UnauthorizedError("Utilisateur introuvable.")
        normalized_email = email.strip().lower() if email else None
        if normalized_email and user.email.lower() != normalized_email:
            raise UnauthorizedError("L'identifiant biométrique ne correspond pas à ce compte.")
        scope = normalized_email or "*"
        challenge = _consume_challenge(f"login:{scope}")
        if challenge is None:
            raise UnauthorizedError("Challenge WebAuthn absent ou expiré. Recommence la connexion.")
        try:
            result = self.webauthn_provider.verify_authentication(
                credential_json=credential,
                expected_challenge=challenge,
                credential_public_key=_b64url_decode(stored["public_key"]),
                credential_current_sign_count=int(stored["sign_count"]),
            )
        except Exception as exc:
            raise UnauthorizedError("Échec de la vérification cryptographique WebAuthn.") from exc
        self.webauthn_repo.update_sign_count(
            str(credential_id), int(result.new_sign_count)
        )
        return self._issue_tokens(user.id, user.role)