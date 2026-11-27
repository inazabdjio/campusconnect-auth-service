import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.infrastructure.db.orm_models import Base
from app.infrastructure.db.session import get_db
from app.main import app


def _load_test_env_file() -> None:
    """Charge les variables de .env.test sans écraser l'environnement existant."""
    env_path = Path(__file__).resolve().parents[2] / ".env.test"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


_load_test_env_file()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL est manquant. Définis-le dans .env.test ou dans l'environnement."
    )

integration_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
IntegrationSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=integration_engine
)


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    """Crée le schéma en base au début de la session d'intégration."""
    Base.metadata.create_all(bind=integration_engine)
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    """Nettoie les tables avant et après chaque test pour garantir l'isolation."""
    truncate_sql = text(
        "TRUNCATE TABLE refresh_tokens, face_templates, webauthn_credentials, users RESTART IDENTITY CASCADE;"
    )
    with integration_engine.begin() as conn:
        conn.execute(truncate_sql)
    yield
    with integration_engine.begin() as conn:
        conn.execute(truncate_sql)


@pytest.fixture
def db_session():
    session = IntegrationSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """Client HTTP FastAPI branché sur la session de test PostgreSQL."""
    os.environ.setdefault(
        "FACE_ENCRYPTION_KEY",
        "dGVzdC1mZXJuZXQta2V5LWZvci1pbnRlZ3JhdGlvbi10ZXN0cy0xMjM0NQ==",
    )
    get_settings.cache_clear()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()