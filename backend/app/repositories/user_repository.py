from app.core.database import users_collection
from bson import ObjectId


class UserRepository:
    def create(self, user_data: dict):
        result = users_collection.insert_one(user_data)

        return users_collection.find_one(
            {"_id": result.inserted_id}
        )

    def get_all(self):
        return list(
            users_collection.find(
                {},
                {"password": 0},
            )
        )

    def get_by_email(self, email: str):
        return users_collection.find_one({"email": email})

    def create_email_index(self):
        users_collection.create_index(
            "email",
            unique=True,
        )

    def get_by_id(self, user_id: str):
        return users_collection.find_one(
        {"_id": ObjectId(user_id)}
    )