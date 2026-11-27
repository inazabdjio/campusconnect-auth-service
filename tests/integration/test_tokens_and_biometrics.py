import base64

import cv2
import numpy as np
from sqlalchemy import select

from app.core.security import hash_token
from app.domain.enums import RoleEnum
from app.infrastructure.db.orm_models import FaceTemplateORM, RefreshTokenORM


def _make_textured_jpeg_b64(seed: int = 1) -> str:
    """Génère une image JPEG texturée en base64 avec suffisamment de détails pour le test de vivacité."""
    rng = np.random.default_rng(seed)
    grid = np.zeros((160, 160, 3), dtype=np.uint8)
    grid[20:140, 20:140] = (180, 180, 180)
    grid[40:120:16, 40:120:16] = (40, 40, 40)
    noise = rng.integers(0, 60, size=(160, 160, 3), dtype=np.uint8)
    img = cv2.add(grid, noise)

    ok, encoded = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    assert ok
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _register_and_login(
    client, email: str = "biometrie@univ.cm", password: str = "SecretPass123!"
):
    reg = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "role": RoleEnum.STUDENT.value,
            "first_name": "Ina",
            "last_name": "Biom",
        },
    )
    assert reg.status_code == 201
    user_data = reg.json()

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return user_data, login.json()


def test_refresh_token_rotation_and_replay_protection(client, db_session):
    _, initial_tokens = _register_and_login(client, email="refresh@univ.cm")
    old_refresh = initial_tokens["refresh_token"]
    old_hash = hash_token(old_refresh)

    # Le refresh token initial est bien présent et actif en base
    db_token = db_session.scalar(
        select(RefreshTokenORM).where(RefreshTokenORM.token_hash == old_hash)
    )
    assert db_token is not None
    assert db_token.revoked is False

    # 1. Premier rafraîchissement -> 200 et rotation du refresh token
    res_refresh = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert res_refresh.status_code == 200
    new_tokens = res_refresh.json()
    assert isinstance(new_tokens["access_token"], str) and new_tokens["access_token"]
    assert isinstance(new_tokens["refresh_token"], str) and new_tokens["refresh_token"]
    assert new_tokens["refresh_token"] != old_refresh

    # Le nouvel access token permet bien d'accéder à /auth/me
    me_res = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert me_res.status_code == 200

    # L'ancien refresh token est marqué révoqué en base
    db_session.expire_all()
    refreshed_db_token = db_session.scalar(
        select(RefreshTokenORM).where(RefreshTokenORM.token_hash == old_hash)
    )
    assert refreshed_db_token is not None
    assert refreshed_db_token.revoked is True

    # 2. Réutiliser l'ancien refresh token doit être refusé -> 401
    replay = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401

    # 3. Un refresh token inconnu doit être refusé -> 401
    unknown = client.post(
        "/auth/refresh", json={"refresh_token": "refresh-token-inexistant"}
    )
    assert unknown.status_code == 401


def test_face_enroll_and_login_flow_in_postgresql(client, db_session):
    user_data, tokens = _register_and_login(client, email="visage@univ.cm")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    img_b64 = _make_textured_jpeg_b64(seed=42)

    # 1. Consentement obligatoire
    no_consent = client.post(
        "/auth/face/enroll",
        headers=headers,
        json={"image_base64": img_b64, "consent_given": False},
    )
    assert no_consent.status_code == 400

    # 2. Enrôlement facial -> 200 et embedding chiffré stocké dans face_templates
    enroll = client.post(
        "/auth/face/enroll",
        headers=headers,
        json={"image_base64": img_b64, "consent_given": True},
    )
    assert enroll.status_code == 200
    assert enroll.json()["status"] == "ENROLLED"

    templates = db_session.scalars(
        select(FaceTemplateORM).where(FaceTemplateORM.user_id == user_data["id"])
    ).all()
    assert len(templates) == 1
    assert isinstance(templates[0].embedding, (bytes, bytearray))
    assert len(templates[0].embedding) > 0

    # 3. Connexion faciale avec la même capture -> 200 et tokens émis
    face_login = client.post(
        "/auth/face/login",
        json={"email": "visage@univ.cm", "image_base64": img_b64},
    )
    assert face_login.status_code == 200
    assert "access_token" in face_login.json()
    assert "refresh_token" in face_login.json()


def test_webauthn_options_and_invalid_verify_rejected(client):
    _, tokens = _register_and_login(client, email="webauthn@univ.cm")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Génération des options d'inscription WebAuthn
    reg_opts = client.post("/auth/webauthn/register/options", headers=headers)
    assert reg_opts.status_code == 200
    assert "optionsJson" in reg_opts.json()

    # Génération des options de connexion WebAuthn
    login_opts = client.post(
        "/auth/webauthn/login/options", params={"email": "webauthn@univ.cm"}
    )
    assert login_opts.status_code == 200
    assert "optionsJson" in login_opts.json()

    # Vérification avec un credential factice/invalide -> rejetée
    bad_verify = client.post(
        "/auth/webauthn/login/verify",
        json={
            "email": "webauthn@univ.cm",
            "credential": {"id": "fake-cred-id", "rawId": "fake-cred-id", "response": {}},
        },
    )
    assert bad_verify.status_code == 401