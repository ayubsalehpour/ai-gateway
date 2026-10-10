
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.users import router as users_router
from app.core.config import settings
from app.repositories.user_repository import UserRepository
from app.api.auth import router as auth_router
from app.api.private import router as private_router
from app.api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = UserRepository()
    repository.create_email_index()

    yield


app = FastAPI(
    title=settings.app_name,
    description="Unified API Gateway for AI providers",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(private_router)
app.include_router(admin_router)