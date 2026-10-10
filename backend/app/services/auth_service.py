
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self):
        self.repository = UserRepository()

    def login(self, email: str, password: str):
        user = self.repository.get_by_email(email)

        if not user:
            return None

        if not verify_password(
            password,
            user["password"],
        ):
            return None

        access_token = create_access_token(
            str(user["_id"])
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }