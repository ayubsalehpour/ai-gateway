
from datetime import datetime, timezone

from app.repositories.usage_repository import UsageRepository


def test_create_usage_record(monkeypatch):
    repository = UsageRepository()
    inserted_record = {}

    class FakeResult:
        inserted_id = "fake-id"

    class FakeCollection:
        def insert_one(self, record):
            inserted_record.update(record)
            return FakeResult()

        def find_one(self, query):
            return {
                **inserted_record,
                "_id": "fake-id",
            }

    monkeypatch.setattr(
        "app.repositories.usage_repository.usage_records_collection",
        FakeCollection(),
    )

    result = repository.create_usage_record({
        "user_id": "507f1f77bcf86cd799439011",
        "request_id": "req_test_001",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "status": "success",
    })

    assert result["id"] == "fake-id"
    assert result["request_id"] == "req_test_001"
    assert isinstance(result["created_at"], datetime)
    assert result["created_at"].tzinfo is not None


def test_get_by_request_id(monkeypatch):
    repository = UsageRepository()

    class FakeCollection:
        def find_one(self, query):
            assert query == {"request_id": "req_test_001"}
            return {
                "_id": "fake-id",
                "request_id": "req_test_001",
                "total_tokens": 150,
            }

    monkeypatch.setattr(
        "app.repositories.usage_repository.usage_records_collection",
        FakeCollection(),
    )

    result = repository.get_by_request_id("req_test_001")

    assert result["id"] == "fake-id"
    assert result["total_tokens"] == 150


def test_get_by_request_id_returns_none(monkeypatch):
    repository = UsageRepository()

    class FakeCollection:
        def find_one(self, query):
            return None

    monkeypatch.setattr(
        "app.repositories.usage_repository.usage_records_collection",
        FakeCollection(),
    )

    assert repository.get_by_request_id("missing-request") is None


def test_create_indexes(monkeypatch):
    repository = UsageRepository()
    created_indexes = []

    class FakeCollection:
        def create_index(self, keys, **kwargs):
            created_indexes.append((keys, kwargs))

    monkeypatch.setattr(
        "app.repositories.usage_repository.usage_records_collection",
        FakeCollection(),
    )

    repository.create_indexes()

    assert len(created_indexes) == 2
    assert created_indexes[0][0] == [
        ("user_id", 1),
        ("created_at", -1),
    ]
    assert created_indexes[1] == (
        "request_id",
        {"unique": True},
    )


def test_get_user_usage(monkeypatch):
    repository = UsageRepository()
    user_id = "507f1f77bcf86cd799439011"

    records = [
        {
            "_id": "record-1",
            "user_id": user_id,
            "request_id": "req-001",
        },
        {
            "_id": "record-2",
            "user_id": user_id,
            "request_id": "req-002",
        },
    ]

    class FakeCursor:
        def sort(self, ordering):
            assert ordering == [
                ("created_at", -1),
                ("_id", -1),
            ]
            return self

        def skip(self, value):
            assert value == 0
            return self

        def limit(self, value):
            assert value == 20
            return self

        def __iter__(self):
            return iter(records)

    class FakeCollection:
        def find(self, query):
            assert query == {"user_id": user_id}
            return FakeCursor()

    monkeypatch.setattr(
        "app.repositories.usage_repository.usage_records_collection",
        FakeCollection(),
    )

    result = repository.get_user_usage(user_id=user_id)

    assert len(result) == 2
    assert result[0]["id"] == "record-1"
    assert result[1]["id"] == "record-2"
    assert "_id" not in result[0]
    assert "_id" not in result[1]
