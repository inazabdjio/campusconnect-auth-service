from functools import lru_cache
from typing import Any
import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import re

_PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z0-9_]+):([^}]*)\}")


def _resolve_placeholders(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return _PLACEHOLDER_RE.sub(
        lambda m: os.environ.get(m.group(1), m.group(2)),
        value,
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "auth-service"
    service_port: int = 8001
    spring_profiles_active: str = "dev"
    config_server_url: str = "http://localhost:8888"

    database_url: str = "postgresql://postgres:postgres@localhost:5433/auth_db"

    jwt_secret_key: str = "dev-secret-key-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    face_encryption_key: str = ""

    eureka_enabled: bool = False
    eureka_server_url: str = "http://localhost:8761/eureka"

    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_user_registered: str = "user.registered"
    kafka_topic_user_deleted: str = "user.deleted"

    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "CampusConnect"
    webauthn_origin: str = "http://localhost:8080"


def fetch_spring_config(service_name: str, profile: str, config_server_url: str) -> dict[str, Any]:
    """Récupère et fusionne les propertySources depuis Spring Cloud Config Server."""
    url = f"{config_server_url.rstrip('/')}/{service_name}/{profile}"
    merged: dict[str, Any] = {}
    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
            # Les propertySources sont généralement ordonnées de la plus prioritaire à la moins prioritaire
            for source in reversed(payload.get("propertySources", [])):
                props = source.get("source", {})
                if isinstance(props, dict):
                    for key, val in props.items():
                        merged[key] = _resolve_placeholders(val)
    except Exception:
        # En mode isolé ou si Config Server n'est pas encore démarré, on garde les valeurs env/défaut
        pass
    return merged


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    remote_props = fetch_spring_config(
        settings.service_name,
        settings.spring_profiles_active,
        settings.config_server_url,
    )
    if remote_props:
        mapped: dict[str, Any] = {}
        if "server.port" in remote_props:
            mapped["service_port"] = int(remote_props["server.port"])
        if "spring.datasource.url" in remote_props:
            raw_url = str(remote_props["spring.datasource.url"])
            # Convertit jdbc:postgresql://... en postgresql://... si présent
            if raw_url.startswith("jdbc:"):
                raw_url = raw_url.replace("jdbc:", "", 1)
            user = remote_props.get("spring.datasource.username", "postgres")
            password = remote_props.get("spring.datasource.password", "postgres")
            if "://" in raw_url and "@" not in raw_url:
                scheme, rest = raw_url.split("://", 1)
                raw_url = f"{scheme}://{user}:{password}@{rest}"
            mapped["database_url"] = raw_url
        if "spring.kafka.bootstrap-servers" in remote_props:
            mapped["kafka_bootstrap_servers"] = str(remote_props["spring.kafka.bootstrap-servers"])
        if "eureka.client.service-url.defaultZone" in remote_props:
            mapped["eureka_server_url"] = str(remote_props["eureka.client.service-url.defaultZone"])

        settings = settings.model_copy(update=mapped)
    return settings
