
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.core.config import settings
from app.core.security import jwt
from app.repositories.user_repository import UserRepository


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise unauthorized

        ObjectId(user_id)

    except (InvalidTokenError, InvalidId, TypeError, ValueError):
        raise unauthorized

    user = UserRepository().get_by_id(user_id)

    if user is None:
        raise unauthorized

    user["_id"] = str(user["_id"])
    user.pop("password", None)

    return user

def require_admin(
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user