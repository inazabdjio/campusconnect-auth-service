from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
import jwt
from sqlalchemy.orm import Session

from app.application.auth_use_cases import (
    AuthUseCases,
    BadRequestError,
    ConflictError,
    UnauthorizedError,
)
from app.application.dtos import (
    FaceEnrollRequest,
    FaceLoginRequest,
    PasswordLoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairResponse,
    UserResponse,
    WebAuthnVerifyRequest,
)
from app.core.config import get_settings
from app.core.security import decode_access_token
from app.domain.strategies.face_strategy import FaceBiometricEngine, FaceProcessingError, LivenessCheckError
from app.domain.strategies.webauthn_strategy import WebAuthnProvider
from app.infrastructure.db.session import get_db
from app.infrastructure.messaging.kafka_producer import KafkaEventPublisher
from app.infrastructure.repositories.face_repo import SqlAlchemyFaceTemplateRepository
from app.infrastructure.repositories.token_repo import SqlAlchemyRefreshTokenRepository
from app.infrastructure.repositories.user_repo import SqlAlchemyUserRepository
from app.infrastructure.repositories.webauthn_repo import SqlAlchemyWebAuthnRepository

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_use_cases(db: Session = Depends(get_db)) -> AuthUseCases:
    settings = get_settings()
    publisher = KafkaEventPublisher(
        enabled=settings.kafka_enabled,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        user_registered_topic=settings.kafka_topic_user_registered,
        user_deleted_topic=settings.kafka_topic_user_deleted,
    )
    face_engine = FaceBiometricEngine()
    webauthn_provider = WebAuthnProvider(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        origin=settings.webauthn_origin,
    )
    return AuthUseCases(
        settings=settings,
        user_repo=SqlAlchemyUserRepository(db),
        face_repo=SqlAlchemyFaceTemplateRepository(db),
        webauthn_repo=SqlAlchemyWebAuthnRepository(db),
        token_repo=SqlAlchemyRefreshTokenRepository(db),
        event_publisher=publisher,
        face_engine=face_engine,
        webauthn_provider=webauthn_provider,
    )


def get_current_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> UUID:
    settings = get_settings()
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        try:
            payload = decode_access_token(token, settings.jwt_secret_key, settings.jwt_algorithm)
            uid = payload.get("userId") or payload.get("sub")
            return UUID(str(uid))
        except (jwt.PyJWTError, ValueError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton invalide ou expiré.")
    if x_user_id:
        try:
            return UUID(x_user_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="En-tête X-User-Id invalide.")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise.")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, use_cases: AuthUseCases = Depends(get_auth_use_cases)):
    try:
        return use_cases.register(
            email=payload.email,
            password=payload.password,
            role=payload.role,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/login", response_model=TokenPairResponse)
def login(payload: PasswordLoginRequest, use_cases: AuthUseCases = Depends(get_auth_use_cases)):
    try:
        return use_cases.login_password(email=payload.email, password=payload.password)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(payload: RefreshTokenRequest, use_cases: AuthUseCases = Depends(get_auth_use_cases)):
    try:
        return use_cases.refresh_tokens(refresh_token=payload.refresh_token)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.get("/me", response_model=UserResponse)
def me(user_id: UUID = Depends(get_current_user_id), use_cases: AuthUseCases = Depends(get_auth_use_cases)):
    try:
        return use_cases.get_me(user_id=user_id)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/face/enroll")
def face_enroll(
    payload: FaceEnrollRequest,
    user_id: UUID = Depends(get_current_user_id),
    use_cases: AuthUseCases = Depends(get_auth_use_cases),
):
    try:
        return use_cases.enroll_face(
            user_id=user_id,
            image_base64=payload.image_base64,
            frame_2_base64=payload.frame_2_base64,
            consent_given=payload.consent_given,
        )
    except (LivenessCheckError, FaceProcessingError, BadRequestError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/face/login", response_model=TokenPairResponse)
def face_login(payload: FaceLoginRequest, use_cases: AuthUseCases = Depends(get_auth_use_cases)):
    try:
        return use_cases.login_face(
            email=payload.email,
            image_base64=payload.image_base64,
            frame_2_base64=payload.frame_2_base64,
        )
    except (LivenessCheckError, FaceProcessingError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/webauthn/register/options")
def webauthn_register_options(
    user_id: UUID = Depends(get_current_user_id),
    use_cases: AuthUseCases = Depends(get_auth_use_cases),
):
    try:
        return use_cases.webauthn_register_options(user_id=user_id)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/webauthn/register/verify")
def webauthn_register_verify(
    payload: WebAuthnVerifyRequest,
    user_id: UUID = Depends(get_current_user_id),
    use_cases: AuthUseCases = Depends(get_auth_use_cases),
):
    try:
        return use_cases.webauthn_register_verify(user_id=user_id, credential=payload.credential)
    except (BadRequestError, UnauthorizedError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/webauthn/login/options")
def webauthn_login_options(
    email: str | None = None,
    use_cases: AuthUseCases = Depends(get_auth_use_cases),
):
    return use_cases.webauthn_login_options(email=email)


@router.post("/webauthn/login/verify", response_model=TokenPairResponse)
def webauthn_login_verify(
    payload: WebAuthnVerifyRequest,
    use_cases: AuthUseCases = Depends(get_auth_use_cases),
):
    try:
        return use_cases.webauthn_login_verify(credential=payload.credential, email=payload.email)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, use_cases: AuthUseCases = Depends(get_auth_use_cases)):
    try:
        use_cases.delete_user(user_id=user_id)
    except BadRequestError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))