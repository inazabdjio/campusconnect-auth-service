from sqlalchemy import select

from app.domain.enums import RoleEnum
from app.infrastructure.db.orm_models import UserORM


def test_register_login_me_and_delete_flow(client, db_session):
    register_payload = {
        "email": "Ina.Etudiante@Univ.Cm",
        "password": "MotDePasseFort123!",
        "role": RoleEnum.STUDENT.value,
        "first_name": "Ina",
        "last_name": "Tsopdjio",
    }

    # 1. Inscription (201) + vérification en base PostgreSQL
    res_reg = client.post("/auth/register", json=register_payload)
    assert res_reg.status_code == 201
    created_user = res_reg.json()
    assert created_user["email"] == "ina.etudiante@univ.cm"
    assert created_user["role"] == "STUDENT"
    assert created_user["first_name"] == "Ina"
    assert created_user["last_name"] == "Tsopdjio"
    assert "id" in created_user
    assert "created_at" in created_user

    db_user = db_session.scalar(
        select(UserORM).where(UserORM.email == "ina.etudiante@univ.cm")
    )
    assert db_user is not None
    assert db_user.password_hash != register_payload["password"]

    # 2. Connexion par mot de passe (200)
    res_login = client.post(
        "/auth/login",
        json={
            "email": "ina.etudiante@univ.cm",
            "password": "MotDePasseFort123!",
        },
    )
    assert res_login.status_code == 200
    tokens = res_login.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] > 0

    # 3. Récupération du profil courant via Bearer token (200)
    res_me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["id"] == created_user["id"]
    assert me_data["email"] == "ina.etudiante@univ.cm"

    # 4. Suppression de l'utilisateur (204) + disparition en base
    res_del = client.delete(f"/auth/users/{created_user['id']}")
    assert res_del.status_code == 204

    db_session.expire_all()
    assert db_session.scalar(select(UserORM).where(UserORM.id == db_user.id)) is None


def test_register_duplicate_email_returns_409(client):
    payload = {
        "email": "doublon@univ.cm",
        "password": "Password123!",
        "role": RoleEnum.LECTURER.value,
        "first_name": "Paul",
        "last_name": "Biya",
    }

    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/auth/register", json=payload)
    assert second.status_code == 409


def test_login_wrong_password_or_unknown_user_returns_401(client):
    client.post(
        "/auth/register",
        json={
            "email": "admin@univ.cm",
            "password": "BonnePassword123!",
            "role": RoleEnum.ADMIN.value,
            "first_name": "Chef",
            "last_name": "Admin",
        },
    )

    bad_pass = client.post(
        "/auth/login",
        json={"email": "admin@univ.cm", "password": "MauvaisPassword!"},
    )
    assert bad_pass.status_code == 401

    unknown_user = client.post(
        "/auth/login",
        json={"email": "inconnu@univ.cm", "password": "BonnePassword123!"},
    )
    assert unknown_user.status_code == 401


def test_me_without_credentials_or_invalid_token_returns_401(client):
    no_auth = client.get("/auth/me")
    assert no_auth.status_code == 401

    bad_token = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer token.invalide.ici"},
    )
    assert bad_token.status_code == 401