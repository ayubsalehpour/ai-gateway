from app.core.security import hash_password
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self):
        self.repository = UserRepository()
        

    def create_user(self, user_data: dict):
        user_data["role"] = "user"
        
        user_data["password"] = hash_password(
            user_data["password"]
        )

        user = self.repository.create(user_data)
        user["_id"] = str(user["_id"])

        return user

    def get_users(self):
        users = self.repository.get_all()

        for user in users:
            user["_id"] = str(user["_id"])

        return users