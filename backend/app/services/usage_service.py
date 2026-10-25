
from bson import ObjectId

from app.repositories.usage_repository import UsageRepository


class UsageService:
    def __init__(self):
        self.repository = UsageRepository()

    def create_usage_record(
        self,
        user_id: str,
        request_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        status: str,
    ) -> dict:
        if not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID")

        if not request_id or not request_id.strip():
            raise ValueError("Request ID is required")

        if not provider or not provider.strip():
            raise ValueError("Provider is required")

        if not model or not model.strip():
            raise ValueError("Model is required")

        token_values = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

        for field, value in token_values.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{field} must be an integer")

            if value < 0:
                raise ValueError(f"{field} cannot be negative")

        if total_tokens != input_tokens + output_tokens:
            raise ValueError(
                "Total tokens must equal input tokens plus output tokens"
            )

        allowed_providers = {"openai", "anthropic", "gemini"}
        if provider not in allowed_providers:
            raise ValueError("Unsupported provider")

        if status not in {"success", "failed"}:
            raise ValueError("Invalid usage status")

        return self.repository.create_usage_record(
            {
                "user_id": user_id,
                "request_id": request_id.strip(),
                "provider": provider,
                "model": model.strip(),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "status": status,
            }
        )

    def get_usage_by_request_id(self, request_id: str) -> dict | None:
        if not request_id or not request_id.strip():
            raise ValueError("Request ID is required")

        return self.repository.get_by_request_id(request_id.strip())

    def get_user_usage(
        self,
        user_id: str,
        limit: int = 20,
        skip: int = 0,
    ) -> list[dict]:
        if not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID")

        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")

        if isinstance(skip, bool) or not isinstance(skip, int) or skip < 0:
            raise ValueError("Skip cannot be negative")

        return self.repository.get_user_usage(
            user_id=user_id,
            limit=limit,
            skip=skip,
        )
