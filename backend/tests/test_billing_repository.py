
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from app.repositories import billing_repository as billing_module
from app.repositories.billing_repository import BillingRepository


@pytest.fixture
def repository(monkeypatch):
    monkeypatch.setattr(
        billing_module,
        "client",
        MagicMock(),
    )
    monkeypatch.setattr(
        billing_module,
        "wallets_collection",
        MagicMock(),
    )
    monkeypatch.setattr(
        billing_module,
        "wallet_reservations_collection",
        MagicMock(),
    )
    monkeypatch.setattr(
        billing_module,
        "wallet_transactions_collection",
        MagicMock(),
    )
    monkeypatch.setattr(
        billing_module,
        "usage_records_collection",
        MagicMock(),
    )

    return BillingRepository()


def test_reserve_rejects_zero_amount(repository):
    with pytest.raises(ValueError, match="greater than zero"):
        repository.reserve(
            user_id=str(ObjectId()),
            amount_toman=0,
            idempotency_key="reservation-key-001",
            request_id="request-001",
        )


def test_reserve_rejects_negative_amount(repository):
    with pytest.raises(ValueError, match="greater than zero"):
        repository.reserve(
            user_id=str(ObjectId()),
            amount_toman=-100,
            idempotency_key="reservation-key-002",
            request_id="request-002",
        )


def test_reserve_rejects_boolean_amount(repository):
    with pytest.raises(ValueError, match="integer"):
        repository.reserve(
            user_id=str(ObjectId()),
            amount_toman=True,
            idempotency_key="reservation-key-003",
            request_id="request-003",
        )


def test_reserve_rejects_float_amount(repository):
    with pytest.raises(ValueError, match="integer"):
        repository.reserve(
            user_id=str(ObjectId()),
            amount_toman=100.5,
            idempotency_key="reservation-key-004",
            request_id="request-004",
        )


def test_reserve_rejects_missing_request_id(repository):
    with pytest.raises(ValueError, match="required"):
        repository.reserve(
            user_id=str(ObjectId()),
            amount_toman=1000,
            idempotency_key="reservation-key-005",
            request_id="",
        )



def test_reserve_returns_none_when_balance_is_insufficient(repository):
    billing_module.wallet_reservations_collection.find_one.return_value = None

    billing_module.wallets_collection.find_one_and_update.return_value = None

    result = repository.reserve(
        user_id=str(ObjectId()),
        amount_toman=5000,
        idempotency_key="reservation-key-006",
        request_id="request-006",
    )

    assert result is None

    billing_module.wallet_reservations_collection.insert_one.assert_not_called()
    billing_module.wallet_transactions_collection.insert_one.assert_not_called()



def test_settle_rejects_negative_actual_cost(repository):
    with pytest.raises(ValueError, match="non-negative integer"):
        repository.settle(
            idempotency_key="reservation-key-007",
            actual_cost_toman=-1,
            usage_data={
                "user_id": str(ObjectId()),
                "request_id": "request-007",
            },
        )


def test_settle_rejects_boolean_actual_cost(repository):
    with pytest.raises(ValueError, match="non-negative integer"):
        repository.settle(
            idempotency_key="reservation-key-008",
            actual_cost_toman=True,
            usage_data={
                "user_id": str(ObjectId()),
                "request_id": "request-008",
            },
        )


def test_settle_rejects_missing_request_id(repository):
    with pytest.raises(ValueError, match="request_id is required"):
        repository.settle(
            idempotency_key="reservation-key-009",
            actual_cost_toman=100,
            usage_data={
                "user_id": str(ObjectId()),
                "request_id": "",
            },
        )


def test_settle_rejects_cost_above_reservation(repository):
    user_id = str(ObjectId())
    reservation_id = ObjectId()

    billing_module.wallet_reservations_collection.find_one.return_value = {
        "_id": reservation_id,
        "user_id": user_id,
        "request_id": "request-010",
        "idempotency_key": "reservation-key-010",
        "amount_toman": 1000,
        "status": "reserved",
    }

    with pytest.raises(ValueError, match="exceeds reserved amount"):
        repository.settle(
            idempotency_key="reservation-key-010",
            actual_cost_toman=1001,
            usage_data={
                "user_id": user_id,
                "request_id": "request-010",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "status": "success",
            },
        )

    billing_module.wallets_collection.find_one_and_update.assert_not_called()
    billing_module.usage_records_collection.insert_one.assert_not_called()
    billing_module.wallet_transactions_collection.insert_one.assert_not_called()


def test_settle_rejects_usage_for_another_user(repository):
    billing_module.wallet_reservations_collection.find_one.return_value = {
        "_id": ObjectId(),
        "user_id": str(ObjectId()),
        "request_id": "request-011",
        "idempotency_key": "reservation-key-011",
        "amount_toman": 1000,
        "status": "reserved",
    }

    with pytest.raises(ValueError, match="does not match"):
        repository.settle(
            idempotency_key="reservation-key-011",
            actual_cost_toman=500,
            usage_data={
                "user_id": str(ObjectId()),
                "request_id": "request-011",
            },
        )


def test_release_rejects_settled_reservation(repository):
    billing_module.wallet_reservations_collection.find_one.return_value = {
        "_id": ObjectId(),
        "user_id": str(ObjectId()),
        "request_id": "request-012",
        "idempotency_key": "reservation-key-012",
        "amount_toman": 1000,
        "status": "settled",
    }

    with pytest.raises(ValueError, match="Only reserved requests"):
        repository.release("reservation-key-012")

    billing_module.wallets_collection.find_one_and_update.assert_not_called()
    billing_module.wallet_transactions_collection.insert_one.assert_not_called()


def test_release_rejects_unknown_reservation(repository):
    billing_module.wallet_reservations_collection.find_one.return_value = None

    with pytest.raises(LookupError, match="Reservation not found"):
        repository.release("reservation-key-013")



def test_reserve_success_records_reservation_debit(repository):
    user_id = str(ObjectId())
    wallet_id = ObjectId()
    reservation_id = ObjectId()

    billing_module.wallet_reservations_collection.find_one.return_value = None
    billing_module.wallets_collection.find_one_and_update.return_value = {
        "_id": wallet_id,
        "user_id": user_id,
        "balance_toman": 90000,
    }
    billing_module.wallet_reservations_collection.insert_one.return_value = (
        MagicMock(inserted_id=reservation_id)
    )

    result = repository.reserve(
        user_id=user_id,
        amount_toman=10000,
        idempotency_key="reserve-success-001",
        request_id="request-success-001",
    )

    assert result["duplicate"] is False
    assert result["reservation"]["status"] == "reserved"
    assert result["reservation"]["amount_toman"] == 10000
    assert result["wallet"]["balance_toman"] == 90000

    update_call = (
        billing_module.wallets_collection.find_one_and_update.call_args
    )
    assert update_call.args[0]["balance_toman"] == {"$gte": 10000}
    assert update_call.args[1]["$inc"]["balance_toman"] == -10000

    ledger_call = (
        billing_module.wallet_transactions_collection.insert_one.call_args
    )
    assert ledger_call.args[0]["type"] == "debit"
    assert ledger_call.args[0]["amount_toman"] == 10000


def test_settle_success_refunds_unused_reservation_without_double_debit(
    repository,
):
    user_id = str(ObjectId())
    wallet_id = ObjectId()
    reservation_id = ObjectId()
    usage_id = ObjectId()

    billing_module.wallet_reservations_collection.find_one.return_value = {
        "_id": reservation_id,
        "user_id": user_id,
        "wallet_id": str(wallet_id),
        "request_id": "request-settle-001",
        "idempotency_key": "settle-key-001",
        "amount_toman": 10000,
        "status": "reserved",
    }

    billing_module.wallets_collection.find_one.return_value = {
        "_id": wallet_id,
        "user_id": user_id,
        "balance_toman": 90000,
    }

    billing_module.wallets_collection.find_one_and_update.return_value = {
        "_id": wallet_id,
        "user_id": user_id,
        "balance_toman": 97000,
    }

    billing_module.usage_records_collection.insert_one.return_value = (
        MagicMock(inserted_id=usage_id)
    )

    billing_module.wallet_reservations_collection.find_one_and_update.return_value = {
        "_id": reservation_id,
        "user_id": user_id,
        "request_id": "request-settle-001",
        "amount_toman": 10000,
        "actual_cost_toman": 3000,
        "refund_amount_toman": 7000,
        "status": "settled",
    }

    result = repository.settle(
        idempotency_key="settle-key-001",
        actual_cost_toman=3000,
        usage_data={
            "user_id": user_id,
            "request_id": "request-settle-001",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "status": "success",
        },
    )

    assert result["duplicate"] is False
    assert result["reservation"]["status"] == "settled"
    assert result["reservation"]["actual_cost_toman"] == 3000
    assert result["reservation"]["refund_amount_toman"] == 7000
    assert result["wallet"]["balance_toman"] == 97000
    assert result["usage"]["total_cost_toman"] == 3000

    # The reserve already debited the reserved amount.
    # Settlement must only credit the unused amount.
    ledger = billing_module.wallet_transactions_collection.insert_one
    ledger.assert_called_once()
    transaction = ledger.call_args.args[0]
    assert transaction["type"] == "credit"
    assert transaction["amount_toman"] == 7000

    wallet_update = (
        billing_module.wallets_collection.find_one_and_update.call_args
    )
    assert wallet_update.args[1]["$inc"]["balance_toman"] == 7000


def test_release_success_refunds_full_reservation(repository):
    user_id = str(ObjectId())
    wallet_id = ObjectId()
    reservation_id = ObjectId()

    billing_module.wallet_reservations_collection.find_one.return_value = {
        "_id": reservation_id,
        "user_id": user_id,
        "wallet_id": str(wallet_id),
        "request_id": "request-release-001",
        "idempotency_key": "release-key-001",
        "amount_toman": 10000,
        "status": "reserved",
    }

    billing_module.wallet_reservations_collection.find_one_and_update.return_value = {
        "_id": reservation_id,
        "user_id": user_id,
        "request_id": "request-release-001",
        "amount_toman": 10000,
        "status": "released",
    }

    billing_module.wallets_collection.find_one_and_update.return_value = {
        "_id": wallet_id,
        "user_id": user_id,
        "balance_toman": 100000,
    }

    result = repository.release("release-key-001")

    assert result["duplicate"] is False
    assert result["reservation"]["status"] == "released"
    assert result["wallet"]["balance_toman"] == 100000

    wallet_update = (
        billing_module.wallets_collection.find_one_and_update.call_args
    )
    assert wallet_update.args[1]["$inc"]["balance_toman"] == 10000

    transaction = (
        billing_module.wallet_transactions_collection.insert_one.call_args.args[0]
    )
    assert transaction["type"] == "credit"
    assert transaction["amount_toman"] == 10000


def test_settle_repeated_request_does_not_change_wallet(repository):
    user_id = str(ObjectId())
    wallet_id = ObjectId()
    reservation_id = ObjectId()
    usage_id = ObjectId()

    billing_module.wallet_reservations_collection.find_one.return_value = {
        "_id": reservation_id,
        "user_id": user_id,
        "request_id": "request-repeat-001",
        "idempotency_key": "repeat-key-001",
        "amount_toman": 10000,
        "actual_cost_toman": 3000,
        "status": "settled",
    }

    billing_module.usage_records_collection.find_one.return_value = {
        "_id": usage_id,
        "user_id": user_id,
        "request_id": "request-repeat-001",
        "total_cost_toman": 3000,
    }

    billing_module.wallets_collection.find_one.return_value = {
        "_id": wallet_id,
        "user_id": user_id,
        "balance_toman": 97000,
    }

    result = repository.settle(
        idempotency_key="repeat-key-001",
        actual_cost_toman=3000,
        usage_data={
            "user_id": user_id,
            "request_id": "request-repeat-001",
        },
    )

    assert result["duplicate"] is True
    assert result["reservation"]["status"] == "settled"
    assert result["usage"]["total_cost_toman"] == 3000

    billing_module.wallets_collection.find_one_and_update.assert_not_called()
    billing_module.wallet_transactions_collection.insert_one.assert_not_called()
    billing_module.usage_records_collection.insert_one.assert_not_called()


def test_release_repeated_request_does_not_refund_twice(repository):
    user_id = str(ObjectId())
    wallet_id = ObjectId()
    reservation_id = ObjectId()

    billing_module.wallet_reservations_collection.find_one.return_value = {
        "_id": reservation_id,
        "user_id": user_id,
        "request_id": "request-release-repeat-001",
        "idempotency_key": "release-repeat-key-001",
        "amount_toman": 10000,
        "status": "released",
    }

    billing_module.wallets_collection.find_one.return_value = {
        "_id": wallet_id,
        "user_id": user_id,
        "balance_toman": 100000,
    }

    result = repository.release("release-repeat-key-001")

    assert result["duplicate"] is True
    assert result["reservation"]["status"] == "released"

    billing_module.wallets_collection.find_one_and_update.assert_not_called()
    billing_module.wallet_transactions_collection.insert_one.assert_not_called()



def test_settle_rejects_different_cost_on_repeated_request(repository):
    user_id = str(ObjectId())
    wallet_id = ObjectId()
    reservation_id = ObjectId()

    billing_module.wallet_reservations_collection.find_one.return_value = {
        "_id": reservation_id,
        "user_id": user_id,
        "request_id": "request-different-cost-001",
        "idempotency_key": "different-cost-key-001",
        "amount_toman": 10000,
        "actual_cost_toman": 3000,
        "status": "settled",
    }

    with pytest.raises(ValueError, match="different cost"):
        repository.settle(
            idempotency_key="different-cost-key-001",
            actual_cost_toman=4000,
            usage_data={
                "user_id": user_id,
                "request_id": "request-different-cost-001",
            },
        )

    billing_module.wallets_collection.find_one_and_update.assert_not_called()
    billing_module.wallet_transactions_collection.insert_one.assert_not_called()
    billing_module.usage_records_collection.insert_one.assert_not_called()
