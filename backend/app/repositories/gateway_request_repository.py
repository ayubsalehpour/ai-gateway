from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from app.core.database import database


class GatewayRequestRepository:
    """Persists gateway request state and the exact response for replay."""

    def __init__(self):
        self.collection = database["gateway_requests"]

    def create_indexes(self) -> None:
        self.collection.create_index(
            [("idempotency_key", ASCENDING)],
            unique=True,
            name="unique_gateway_idempotency_key",
        )
        self.collection.create_index(
            [("request_id", ASCENDING)],
            unique=True,
            name="unique_gateway_request_id",
        )
        self.collection.create_index(
            [("user_id", ASCENDING), ("created_at", ASCENDING)],
            name="gateway_requests_user_created_at",
        )
        self.collection.create_index(
            [("status", ASCENDING), ("updated_at", ASCENDING)],
            name="gateway_requests_status_updated_at",
        )

    @staticmethod
    def _serialize(document: dict | None) -> dict | None:
        if document is None:
            return None
        result = dict(document)
        if "_id" in result:
            result["id"] = str(result.pop("_id"))
        return result

    def get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        return self._serialize(
            self.collection.find_one({"idempotency_key": idempotency_key})
        )

    def claim(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        fingerprint: str,
        request_id: str,
        request_data: dict[str, Any],
    ) -> dict:
        now = datetime.now(timezone.utc)
        document = {
            "user_id": user_id,
            "idempotency_key": idempotency_key,
            "fingerprint": fingerprint,
            "request_id": request_id,
            "request": request_data,
            "status": "processing",
            "response": None,
            "error": None,
            "provider_request_id": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            result = self.collection.insert_one(document)
            document["_id"] = result.inserted_id
            return {"created": True, "request": self._serialize(document)}
        except DuplicateKeyError:
            existing = self.get_by_idempotency_key(idempotency_key)
            if existing is None:
                # A different unique constraint was hit; never misreport it as replay.
                raise
            if existing.get("user_id") != user_id:
                raise ValueError("Idempotency key has already been used")
            if existing.get("fingerprint") != fingerprint:
                raise ValueError(
                    "Idempotency key has already been used for a different request"
                )
            return {"created": False, "request": existing}

    def update_status(
        self,
        request_id: str,
        status: str,
        *,
        response: dict | None = None,
        error: str | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        allowed = {
            "processing",
            "succeeded",
            "failed",
            "reconciliation_required",
        }
        if status not in allowed:
            raise ValueError("Invalid gateway request status")

        update: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        if response is not None:
            update["response"] = response
        if error is not None:
            update["error"] = error[:1000]
        if provider_request_id is not None:
            update["provider_request_id"] = provider_request_id

        result = self.collection.update_one(
            {"request_id": request_id},
            {"$set": update},
        )
        if result.matched_count != 1:
            raise LookupError("Gateway request record not found")
