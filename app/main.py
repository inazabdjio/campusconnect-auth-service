from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import get_settings
from app.infrastructure.api.routes.auth_routes import router as auth_router
from app.infrastructure.api.routes.health_routes import router as health_router
from app.infrastructure.db.orm_models import Base
from app.infrastructure.db.session import engine
from app.infrastructure.discovery.eureka_client import EurekaClient

settings = get_settings()
eureka_client = EurekaClient(
    enabled=settings.eureka_enabled,
    eureka_url=settings.eureka_server_url,
    app_name=settings.service_name,
    port=settings.service_port,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    eureka_client.start()
    try:
        yield
    finally:
        eureka_client.stop()


app = FastAPI(title="CampusConnect Auth Service", version="1.0.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(auth_router)