
from fastapi import APIRouter, HTTPException, status

from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["Authentication"])
auth_service = AuthService()


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(credentials: LoginRequest):
    result = auth_service.login(
        email=credentials.email,
        password=credentials.password,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return result