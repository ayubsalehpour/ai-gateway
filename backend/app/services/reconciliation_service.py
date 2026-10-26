"""Conservative recovery for gateway requests left in processing.

This service deliberately does not mutate wallet reservations. A stale request may
have reached the provider even if the application never received the response.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class ReconciliationService:
    """Flag stale processing requests for manual/worker reconciliation.

    Args:
        requests_collection: A PyMongo collection containing gateway request records.
    """

    def __init__(self, requests_collection: Any) -> None:
        self.requests_collection = requests_collection

    def create_indexes(self) -> None:
        """Create indexes used by the stale-request scan."""
        self.requests_collection.create_index(
            [("status", 1), ("updated_at", 1)]
        )
        self.requests_collection.create_index(
            "request_id",
            unique=True,
            partialFilterExpression={"request_id": {"$type": "string"}},
        )

    def flag_stale_processing_requests(
        self,
        *,
        older_than_minutes: int = 10,
        limit: int = 100,
        now: datetime | None = None,
    ) -> dict[str, int]:
        """Flag old `processing` requests without refunding or retrying them.

        A compare-and-set update protects requests that completed after the scan
        selected them but before this method updated them.
        """
        if (
            isinstance(older_than_minutes, bool)
            or not isinstance(older_than_minutes, int)
            or older_than_minutes <= 0
        ):
            raise ValueError("older_than_minutes must be a positive integer")

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")

        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware")

        cutoff = current_time - timedelta(minutes=older_than_minutes)
        cursor = (
            self.requests_collection.find(
                {
                    "status": "processing",
                    "updated_at": {"$lte": cutoff},
                },
                {"_id": 1, "request_id": 1},
            )
            .sort("updated_at", 1)
            .limit(limit)
        )

        scanned = 0
        flagged = 0

        for document in cursor:
            scanned += 1
            result = self.requests_collection.update_one(
                {
                    "_id": document["_id"],
                    "status": "processing",
                    "updated_at": {"$lte": cutoff},
                },
                {
                    "$set": {
                        "status": "reconciliation_required",
                        "reconciliation_required_at": current_time,
                        "reconciliation_reason": (
                            "Request remained processing beyond the recovery threshold"
                        ),
                        "updated_at": current_time,
                    }
                },
            )
            flagged += int(result.modified_count == 1)

        return {"scanned": scanned, "flagged": flagged}
