
import os
import uuid

import pytest
from pymongo import MongoClient

from app.core.config import settings
from app.repositories import billing_repository as billing_module
from app.repositories.billing_repository import BillingRepository

from pymongo.errors import DuplicateKeyError
from concurrent.futures import ThreadPoolExecutor


@pytest.fixture
def mongo_test_db(monkeypatch):
    uri = os.getenv("MONGODB_TEST_URL", settings.mongodb_url)
    database_name = "ai_gateway_test"

    if database_name == settings.mongodb_database:
        pytest.fail("Integration tests must not use the production database")

    client = MongoClient(uri, serverSelectionTimeoutMS=3000)

    try:
        client.admin.command("ping")
    except Exception as exc:
        client.close()
        pytest.skip(f"MongoDB is unavailable: {exc}")

    try:
        hello = client.admin.command("hello")
        if not hello.get("setName"):
            pytest.skip(
                "MongoDB integration tests require a replica set"
            )

        db = client[database_name]

        # Clean only the dedicated test database.
        client.drop_database(database_name)

        monkeypatch.setattr(billing_module, "client", client)
        monkeypatch.setattr(
            billing_module,
            "wallets_collection",
            db["wallets"],
        )
        monkeypatch.setattr(
            billing_module,
            "wallet_reservations_collection",
            db["wallet_reservations"],
        )
        monkeypatch.setattr(
            billing_module,
            "wallet_transactions_collection",
            db["wallet_transactions"],
        )
        monkeypatch.setattr(
            billing_module,
            "usage_records_collection",
            db["usage_records"],
        )

        repository = BillingRepository()
        repository.create_indexes()

        db["wallet_transactions"].create_index(
            "idempotency_key",
            unique=True,
        )

        yield db, repository

    finally:
        # This database name is deliberately isolated from the app database.
        client.drop_database(database_name)
        client.close()


def test_real_mongodb_reserve_and_settle(mongo_test_db):
    db, repository = mongo_test_db

    user_id = str(uuid.uuid4())
    request_id = f"it-{uuid.uuid4().hex}"

    db["wallets"].insert_one(
        {
            "user_id": user_id,
            "balance_toman": 100_000,
        }
    )

    reservation_key = f"reserve-{uuid.uuid4().hex}"

    reserve_result = repository.reserve(
        user_id=user_id,
        amount_toman=10_000,
        idempotency_key=reservation_key,
        request_id=request_id,
    )

    assert reserve_result is not None
    assert reserve_result["duplicate"] is False
    assert reserve_result["wallet"]["balance_toman"] == 90_000

    settle_result = repository.settle(
        idempotency_key=reservation_key,
        actual_cost_toman=3_000,
        usage_data={
            "user_id": user_id,
            "request_id": request_id,
            "provider": "openai",
            "model": "gpt-4o-mini",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "status": "success",
        },
    )

    assert settle_result["duplicate"] is False
    assert settle_result["reservation"]["status"] == "settled"
    assert settle_result["reservation"]["refund_amount_toman"] == 7_000

    wallet = db["wallets"].find_one({"user_id": user_id})
    assert wallet["balance_toman"] == 97_000

    usage = db["usage_records"].find_one({"request_id": request_id})
    assert usage is not None
    assert usage["total_cost_toman"] == 3_000

    transactions = list(
        db["wallet_transactions"].find(
            {"user_id": user_id}
        ).sort("created_at", 1)
    )

    assert len(transactions) == 2
    assert sum(
        tx["amount_toman"]
        for tx in transactions
        if tx["type"] == "debit"
    ) == 10_000
    assert sum(
        tx["amount_toman"]
        for tx in transactions
        if tx["type"] == "credit"
    ) == 7_000


def test_real_mongodb_release_refunds_full_reservation(mongo_test_db):
    db, repository = mongo_test_db

    user_id = str(uuid.uuid4())
    request_id = f"it-{uuid.uuid4().hex}"

    db["wallets"].insert_one(
        {
            "user_id": user_id,
            "balance_toman": 50_000,
        }
    )

    reservation_key = f"reserve-{uuid.uuid4().hex}"

    repository.reserve(
        user_id=user_id,
        amount_toman=8_000,
        idempotency_key=reservation_key,
        request_id=request_id,
    )

    result = repository.release(reservation_key)

    assert result["duplicate"] is False
    assert result["reservation"]["status"] == "released"

    wallet = db["wallets"].find_one({"user_id": user_id})
    assert wallet["balance_toman"] == 50_000

    transactions = list(
        db["wallet_transactions"].find({"user_id": user_id})
    )

    assert len(transactions) == 2
    assert sum(
        tx["amount_toman"]
        for tx in transactions
        if tx["type"] == "debit"
    ) == 8_000
    assert sum(
        tx["amount_toman"]
        for tx in transactions
        if tx["type"] == "credit"
    ) == 8_000



def test_real_mongodb_settlement_rolls_back_on_duplicate_usage(
    mongo_test_db,
):
    db, repository = mongo_test_db

    user_id = str(uuid.uuid4())
    request_id = f"rollback-{uuid.uuid4().hex}"
    reservation_key = f"reserve-{uuid.uuid4().hex}"

    db["wallets"].insert_one(
        {
            "user_id": user_id,
            "balance_toman": 100_000,
        }
    )

    # Reserve funds first.
    repository.reserve(
        user_id=user_id,
        amount_toman=10_000,
        idempotency_key=reservation_key,
        request_id=request_id,
    )

    wallet_after_reserve = db["wallets"].find_one(
        {"user_id": user_id}
    )
    assert wallet_after_reserve["balance_toman"] == 90_000

    # Simulate a conflicting usage record.
    # The unique request_id index should reject settlement's insert.
    db["usage_records"].insert_one(
        {
            "user_id": user_id,
            "request_id": request_id,
            "total_cost_toman": 999,
        }
    )

    # Settlement should fail, causing the entire transaction to roll back.
    with pytest.raises(DuplicateKeyError):
        repository.settle(
            idempotency_key=reservation_key,
            actual_cost_toman=3_000,
            usage_data={
                "user_id": user_id,
                "request_id": request_id,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "status": "success",
            },
        )

    # The attempted 7,000 Toman refund must have rolled back.
    wallet = db["wallets"].find_one({"user_id": user_id})
    assert wallet["balance_toman"] == 90_000

    # The reservation must remain unchanged.
    reservation = db["wallet_reservations"].find_one(
        {"idempotency_key": reservation_key}
    )
    assert reservation["status"] == "reserved"
    assert "actual_cost_toman" not in reservation

    # Only the original reservation debit should exist.
    transactions = list(
        db["wallet_transactions"].find(
            {"user_id": user_id}
        )
    )
    assert len(transactions) == 1
    assert transactions[0]["type"] == "debit"
    assert transactions[0]["amount_toman"] == 10_000

    # The conflicting record remains; settlement must not create another.
    assert db["usage_records"].count_documents(
        {"request_id": request_id}
    ) == 1



def test_real_mongodb_concurrent_reservations_cannot_overspend(
    mongo_test_db,
):
    db, repository = mongo_test_db

    user_id = str(uuid.uuid4())
    initial_balance = 10_000
    reservation_amount = 10_000

    db["wallets"].insert_one(
        {
            "user_id": user_id,
            "balance_toman": initial_balance,
        }
    )

    def reserve_once(index):
        return repository.reserve(
            user_id=user_id,
            amount_toman=reservation_amount,
            idempotency_key=f"concurrent-{uuid.uuid4().hex}",
            request_id=f"concurrent-{index}-{uuid.uuid4().hex}",
        )

    # Run two independent reservations concurrently.
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(reserve_once, index)
            for index in range(2)
        ]
        results = [future.result() for future in futures]

    successful_reservations = [
        result for result in results if result is not None
    ]

    # Exactly one request should reserve the available funds.
    assert len(successful_reservations) == 1

    wallet = db["wallets"].find_one({"user_id": user_id})
    assert wallet["balance_toman"] == 0
    assert wallet["balance_toman"] >= 0

    reservations = list(
        db["wallet_reservations"].find({"user_id": user_id})
    )
    assert len(reservations) == 1

    transactions = list(
        db["wallet_transactions"].find({"user_id": user_id})
    )
    assert len(transactions) == 1
    assert transactions[0]["type"] == "debit"
    assert transactions[0]["amount_toman"] == reservation_amount



def test_real_mongodb_concurrent_same_idempotency_key(
    mongo_test_db,
):
    db, repository = mongo_test_db

    user_id = str(uuid.uuid4())
    request_id = f"idem-{uuid.uuid4().hex}"
    idempotency_key = f"idem-key-{uuid.uuid4().hex}"
    amount_toman = 10_000

    db["wallets"].insert_one(
        {
            "user_id": user_id,
            "balance_toman": 50_000,
        }
    )

    def reserve_once():
        return repository.reserve(
            user_id=user_id,
            amount_toman=amount_toman,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )

    # Send two concurrent calls with the same idempotency key.
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(reserve_once),
            executor.submit(reserve_once),
        ]
        results = [future.result() for future in futures]

    assert all(result is not None for result in results)

    # One request creates the reservation; the other is a duplicate.
    assert sorted(result["duplicate"] for result in results) == [
        False,
        True,
    ]

    assert all(
        result["reservation"]["idempotency_key"] == idempotency_key
        for result in results
    )

    wallet = db["wallets"].find_one({"user_id": user_id})
    assert wallet["balance_toman"] == 40_000

    assert db["wallet_reservations"].count_documents(
        {"idempotency_key": idempotency_key}
    ) == 1

    assert db["wallet_reservations"].count_documents(
        {"request_id": request_id}
    ) == 1

    transactions = list(
        db["wallet_transactions"].find(
            {"user_id": user_id}
        )
    )

    assert len(transactions) == 1
    assert transactions[0]["type"] == "debit"
    assert transactions[0]["amount_toman"] == amount_toman
