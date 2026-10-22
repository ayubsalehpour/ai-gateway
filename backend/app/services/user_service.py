from app.core.security import hash_password
from app.repositories.user_repository import UserRepository
from app.services.wallet_service import WalletService


class UserService:
    def __init__(self):
        self.repository = UserRepository()
        self.wallet_service = WalletService()

    def create_user(self, user_data: dict):
        user_data["role"] = "user"
        user_data["password"] = hash_password(user_data["password"])

        user = self.repository.create(user_data)

        user_id = str(user["_id"])
        self.wallet_service.create_wallet(user_id)

        user["_id"] = user_id
        return user

    def get_users(self):
        users = self.repository.get_all()

        for user in users:
            user["_id"] = str(user["_id"])

        return users