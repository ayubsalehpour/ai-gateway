
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING

from app.core.database import client, database


class PricingRepository:
    def __init__(self):
        self.collection = database["model_pricing"]

    def get_active_price(
        self,
        provider: str,
        model: str,
    ) -> dict[str, Any] | None:
        return self.collection.find_one(
            {
                "provider": provider,
                "model": model,
                "is_active": True,
            }
        )

    def create_indexes(self) -> None:
        # At most one active price for each provider/model.
        self.collection.create_index(
            [
                ("provider", ASCENDING),
                ("model", ASCENDING),
            ],
            unique=True,
            partialFilterExpression={"is_active": True},
            name="unique_active_model_price",
        )

        # Supports retrieving the latest historical version.
        self.collection.create_index(
            [
                ("provider", ASCENDING),
                ("model", ASCENDING),
                ("version", DESCENDING),
            ],
            unique=True,
            name="unique_model_price_version",
        )

    def create_price(
        self,
        provider: str,
        model: str,
        input_price_per_million_toman: int,
        output_price_per_million_toman: int,
        version: int,
    ) -> dict[str, Any]:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("Provider is required")

        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model is required")

        for field, value in {
            "input_price_per_million_toman": input_price_per_million_toman,
            "output_price_per_million_toman": output_price_per_million_toman,
        }.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"{field} must be a non-negative integer")

        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("Version must be a positive integer")

        provider = provider.strip().lower()
        model = model.strip()

        def activate_new_price(session) -> dict[str, Any]:
            latest = self.collection.find_one(
                {"provider": provider, "model": model},
                sort=[("version", DESCENDING)],
                session=session,
            )

            if latest is not None and version <= latest["version"]:
                raise ValueError(
                    "New pricing version must be greater than the latest version"
                )

            now = datetime.now(timezone.utc)

            # Deactivate the previous price inside the same transaction.
            self.collection.update_many(
                {
                    "provider": provider,
                    "model": model,
                    "is_active": True,
                },
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": now,
                    }
                },
                session=session,
            )

            document = {
                "provider": provider,
                "model": model,
                "input_price_per_million_toman": (
                    input_price_per_million_toman
                ),
                "output_price_per_million_toman": (
                    output_price_per_million_toman
                ),
                "version": version,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }

            result = self.collection.insert_one(
                document,
                session=session,
            )
            document["id"] = str(result.inserted_id)
            return document

        with client.start_session() as session:
            return session.with_transaction(activate_new_price)
