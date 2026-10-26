
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.services.reconciliation_service import ReconciliationService


class FakeCursor:
    def __init__(self, documents, projection=None):
        self.documents = documents
        self.projection = projection

    def sort(self, key, direction=1):
        self.documents.sort(
            key=lambda document: document.get(key),
            reverse=direction < 0,
        )
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    def __iter__(self):
        for document in self.documents:
            if self.projection:
                included_fields = {
                    field
                    for field, enabled in self.projection.items()
                    if enabled
                }
                yield {
                    key: value
                    for key, value in document.items()
                    if key in included_fields
                }
            else:
                yield document


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = deepcopy(documents or [])
        self.created_indexes = []
        self.update_calls = []

    def create_index(self, keys, **kwargs):
        self.created_indexes.append((keys, kwargs))
        return "fake_index"

    def find(self, query, projection=None):
        matched_documents = []

        for document in self.documents:
            if document.get("status") != query.get("status"):
                continue

            updated_at_filter = query.get("updated_at", {})
            cutoff = updated_at_filter.get("$lte")

            if cutoff is not None:
                updated_at = document.get("updated_at")
                if updated_at is None or updated_at > cutoff:
                    continue

            matched_documents.append(document.copy())

        return FakeCursor(matched_documents, projection=projection)

    def update_one(self, query, update):
        self.update_calls.append(
            (deepcopy(query), deepcopy(update))
        )

        for document in self.documents:
            if document.get("_id") != query.get("_id"):
                continue

            # Simulate compare-and-set: update only if the
            # document still matches the complete query.
            if document.get("status") != query.get("status"):
                continue

            updated_at_filter = query.get("updated_at", {})
            cutoff = updated_at_filter.get("$lte")

            if cutoff is not None:
                current_updated_at = document.get("updated_at")
                if (
                    current_updated_at is None
                    or current_updated_at > cutoff
                ):
                    continue

            document.update(update.get("$set", {}))

            class Result:
                matched_count = 1
                modified_count = 1

            return Result()

        class Result:
            matched_count = 0
            modified_count = 0

        return Result()


@pytest.fixture
def now():
    return datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def stale_request(now):
    return {
        "_id": "request-stale",
        "status": "processing",
        "updated_at": now - timedelta(minutes=20),
        "user_id": "user-1",
    }


@pytest.fixture
def collection(stale_request, now):
    return FakeCollection(
        [
            stale_request,
            {
                "_id": "request-fresh",
                "status": "processing",
                "updated_at": now - timedelta(minutes=2),
            },
            {
                "_id": "request-completed",
                "status": "succeeded",
                "updated_at": now - timedelta(minutes=30),
            },
            {
                "_id": "request-failed",
                "status": "failed",
                "updated_at": now - timedelta(minutes=30),
            },
        ]
    )


@pytest.fixture
def service(collection):
    return ReconciliationService(
        requests_collection=collection
    )


def test_flags_stale_processing_request(
    service, collection, now
):
    result = service.flag_stale_processing_requests(
        older_than_minutes=10,
        limit=100,
        now=now,
    )

    stale = next(
        item
        for item in collection.documents
        if item["_id"] == "request-stale"
    )

    assert result == {"scanned": 1, "flagged": 1}
    assert stale["status"] == "reconciliation_required"
    assert stale["reconciliation_required_at"] == now
    assert stale["updated_at"] == now
    assert stale["reconciliation_reason"]


def test_does_not_flag_fresh_or_non_processing_requests(
    service, collection, now
):
    service.flag_stale_processing_requests(
        older_than_minutes=10,
        limit=100,
        now=now,
    )

    statuses = {
        item["_id"]: item["status"]
        for item in collection.documents
    }

    assert statuses["request-fresh"] == "processing"
    assert statuses["request-completed"] == "succeeded"
    assert statuses["request-failed"] == "failed"


def test_returns_zero_when_no_stale_requests_exist(now):
    collection = FakeCollection(
        [
            {
                "_id": "fresh",
                "status": "processing",
                "updated_at": now - timedelta(minutes=1),
            }
        ]
    )
    service = ReconciliationService(
        requests_collection=collection
    )

    result = service.flag_stale_processing_requests(
        older_than_minutes=10,
        limit=100,
        now=now,
    )

    assert result == {"scanned": 0, "flagged": 0}


def test_respects_limit(now):
    collection = FakeCollection(
        [
            {
                "_id": f"stale-{index}",
                "status": "processing",
                "updated_at": now - timedelta(minutes=30 + index),
            }
            for index in range(5)
        ]
    )
    service = ReconciliationService(
        requests_collection=collection
    )

    result = service.flag_stale_processing_requests(
        older_than_minutes=10,
        limit=2,
        now=now,
    )

    assert result == {"scanned": 2, "flagged": 2}

    flagged = [
        item
        for item in collection.documents
        if item["status"] == "reconciliation_required"
    ]
    assert len(flagged) == 2


@pytest.mark.parametrize(
    "older_than_minutes",
    [0, -1, -10],
)
def test_rejects_invalid_age_threshold(
    service, now, older_than_minutes
):
    with pytest.raises(ValueError):
        service.flag_stale_processing_requests(
            older_than_minutes=older_than_minutes,
            now=now,
        )


@pytest.mark.parametrize("limit", [0, -1, -100])
def test_rejects_invalid_limit(service, now, limit):
    with pytest.raises(ValueError):
        service.flag_stale_processing_requests(
            limit=limit,
            now=now,
        )


def test_rejects_naive_datetime(service):
    naive_now = datetime(2026, 10, 25, 12, 0)

    with pytest.raises(ValueError):
        service.flag_stale_processing_requests(
            now=naive_now
        )


def test_create_indexes_creates_status_updated_at_index(
    service, collection
):
    service.create_indexes()

    assert len(collection.created_indexes) == 2

    indexes = collection.created_indexes

    assert indexes[0][0] == [
        ("status", 1),
        ("updated_at", 1),
    ]

    assert indexes[1][0] == "request_id"
    assert indexes[1][1]["unique"] is True
    assert (
        indexes[1][1]["partialFilterExpression"]
        == {"request_id": {"$type": "string"}}
    )


def test_does_not_call_wallet_refund_or_provider_retry(
    service, collection, now
):
    service.flag_stale_processing_requests(
        older_than_minutes=10,
        limit=100,
        now=now,
    )

    # This service should only change request state.
    # It must not perform wallet refunds or provider retries.
    for _query, update in collection.update_calls:
        changed_fields = set(update.get("$set", {}).keys())

        assert "balance_toman" not in changed_fields
        assert "wallet_balance" not in changed_fields
        assert "provider_retry" not in changed_fields


def test_does_not_change_requests_outside_processing_state(
    service, collection, now
):
    completed_before = deepcopy(
        next(
            item
            for item in collection.documents
            if item["_id"] == "request-completed"
        )
    )

    service.flag_stale_processing_requests(
        older_than_minutes=10,
        limit=100,
        now=now,
    )

    completed_after = next(
        item
        for item in collection.documents
        if item["_id"] == "request-completed"
    )

    assert completed_after == completed_before
