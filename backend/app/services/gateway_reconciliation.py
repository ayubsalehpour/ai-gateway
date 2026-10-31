"""Safe status transition helpers for gateway reconciliation."""

from datetime import datetime, timezone
from typing import Any


def mark_request_for_reconciliation(
    requests_collection: Any,
    request_id: str,
    *,
    reason: str,
    now: datetime | None = None,
) -> bool:
    """Atomically move a processing request to reconciliation_required.

    This function never refunds wallet funds, releases reservations,
    or retries provider requests.
    """
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id is required")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason is required")

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    result = requests_collection.update_one(
        {"request_id": request_id, "status": "processing"},
        {"$set": {
            "status": "reconciliation_required",
            "reconciliation_reason": reason.strip(),
            "updated_at": current_time,
        }},
    )
    return result.modified_count == 1
