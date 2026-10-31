from datetime import datetime, timezone

import pytest

from app.services.gateway_reconciliation import mark_request_for_reconciliation


class FakeUpdateResult:
    def __init__(self, modified_count):
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents
        self.last_query = None

    def update_one(self, query, update):
        self.last_query = query
        for document in self.documents:
            if (
                document.get("request_id") == query["request_id"]
                and document.get("status") == query["status"]
            ):
                document.update(update["$set"])
                return FakeUpdateResult(1)
        return FakeUpdateResult(0)


def test_marks_processing_request_for_reconciliation():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    collection = FakeCollection([{"request_id": "req-1", "status": "processing"}])

    changed = mark_request_for_reconciliation(
        collection, "req-1",
        reason="actual_cost_exceeds_reserved",
        now=now,
    )

    assert changed is True
    assert collection.documents[0]["status"] == "reconciliation_required"
    assert collection.documents[0]["reconciliation_reason"] == "actual_cost_exceeds_reserved"
    assert collection.documents[0]["updated_at"] == now
    assert collection.last_query == {"request_id": "req-1", "status": "processing"}


def test_does_not_overwrite_completed_request():
    collection = FakeCollection([{"request_id": "req-2", "status": "succeeded"}])
    changed = mark_request_for_reconciliation(
        collection, "req-2", reason="manual_review"
    )
    assert changed is False
    assert collection.documents[0]["status"] == "succeeded"


@pytest.mark.parametrize(
    ("request_id", "reason"),
    [("", "manual_review"), ("req-1", "")],
)
def test_requires_request_id_and_reason(request_id, reason):
    with pytest.raises(ValueError):
        mark_request_for_reconciliation(
            FakeCollection([]), request_id, reason=reason
        )


def test_rejects_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        mark_request_for_reconciliation(
            FakeCollection([]),
            "req-1",
            reason="manual_review",
            now=datetime(2026, 1, 1),
        )
