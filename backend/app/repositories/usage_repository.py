
from datetime import datetime, timezone

from app.core.database import usage_records_collection


class UsageRepository:
    def create_usage_record(self, usage_data: dict) -> dict:
        record = {
            **usage_data,
            "created_at": datetime.now(timezone.utc),
        }

        result = usage_records_collection.insert_one(record)

        saved_record = usage_records_collection.find_one(
            {"_id": result.inserted_id}
        )

        if saved_record is None:
            raise RuntimeError("Failed to retrieve usage record")

        saved_record["id"] = str(saved_record.pop("_id"))
        return saved_record

    def get_by_request_id(self, request_id: str) -> dict | None:
        record = usage_records_collection.find_one(
            {"request_id": request_id}
        )

        if record is None:
            return None

        record["id"] = str(record.pop("_id"))
        return record

    def get_user_usage(
        self,
        user_id: str,
        limit: int = 20,
        skip: int = 0,
    ) -> list[dict]:
        records = usage_records_collection.find(
            {"user_id": user_id}
        ).sort([
            ("created_at", -1),
            ("_id", -1),
        ]).skip(skip).limit(limit)

        results = []

        for record in records:
            record["id"] = str(record.pop("_id"))
            results.append(record)

        return results

    def create_indexes(self) -> None:
        usage_records_collection.create_index(
            [("user_id", 1), ("created_at", -1)]
        )

        usage_records_collection.create_index(
            "request_id",
            unique=True,
        )
