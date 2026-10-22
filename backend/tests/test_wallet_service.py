
import pytest

from app.services.wallet_service import WalletService


USER_ID = "507f1f77bcf86cd799439012"
ADMIN_ID = "507f1f77bcf86cd799439011"
WALLET_ID = "507f1f77bcf86cd799439013"
TRANSACTION_ID = "507f1f77bcf86cd799439014"
IDEMPOTENCY_KEY = "admin-charge-test-0001"


class FakeWalletRepository:
    def __init__(self, transaction):
        self.transaction = transaction
        self.credit_calls = 0

    def credit_wallet_transaction(self, **kwargs):
        self.credit_calls += 1
        return {
            "duplicate": True,
            "transaction": self.transaction.copy(),
        }

    def get_by_user_id(self, user_id):
        return {
            "_id": WALLET_ID,
            "user_id": user_id,
            "balance_toman": 100_000,
            "created_at": None,
            "updated_at": None,
        }


def make_transaction():
    return {
        "_id": TRANSACTION_ID,
        "wallet_id": WALLET_ID,
        "user_id": USER_ID,
        "type": "credit",
        "amount_toman": 100_000,
        "balance_after": 100_000,
        "description": "Manual wallet charge",
        "reference": None,
        "admin_id": ADMIN_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
    }


def test_duplicate_idempotency_key_does_not_credit_again():
    service = WalletService()
    repository = FakeWalletRepository(make_transaction())
    service.repository = repository

    result = service.credit_wallet(
        user_id=USER_ID,
        amount_toman=100_000,
        description="Manual wallet charge",
        admin_id=ADMIN_ID,
        idempotency_key=IDEMPOTENCY_KEY,
    )

    assert repository.credit_calls == 1
    assert result["transaction"]["id"] == TRANSACTION_ID
    assert result["wallet"]["balance_toman"] == 100_000


def test_reusing_idempotency_key_for_different_amount_is_rejected():
    service = WalletService()
    repository = FakeWalletRepository(make_transaction())
    service.repository = repository

    with pytest.raises(ValueError, match="Idempotency key"):
        service.credit_wallet(
            user_id=USER_ID,
            amount_toman=500_000,
            description="Manual wallet charge",
            admin_id=ADMIN_ID,
            idempotency_key=IDEMPOTENCY_KEY,
        )

    assert repository.credit_calls == 1


class FakeDebitWalletRepository:
    def __init__(self, result):
        self.result = result
        self.debit_calls = 0
        self.debit_kwargs = None

    def debit_wallet_transaction(self, **kwargs):
        self.debit_calls += 1
        self.debit_kwargs = kwargs
        return self.result


def make_debit_transaction():
    return {
        "_id": TRANSACTION_ID,
        "wallet_id": WALLET_ID,
        "user_id": USER_ID,
        "type": "debit",
        "amount_toman": 30_000,
        "balance_after": 70_000,
        "description": "API usage",
        "reference": None,
        "idempotency_key": "debit-service-test-0001",
    }


def test_debit_wallet_success():
    transaction = make_debit_transaction()
    wallet = {
        "id": WALLET_ID,
        "user_id": USER_ID,
        "balance_toman": 70_000,
    }

    service = WalletService()
    repository = FakeDebitWalletRepository(
        {
            "duplicate": False,
            "wallet": wallet,
            "transaction": {
                **transaction,
                "id": TRANSACTION_ID,
            },
        }
    )
    service.repository = repository

    result = service.debit_wallet(
        user_id=USER_ID,
        amount_toman=30_000,
        description="API usage",
        idempotency_key="debit-service-test-0001",
    )

    assert repository.debit_calls == 1
    assert repository.debit_kwargs["amount_toman"] == 30_000
    assert result["wallet"]["balance_toman"] == 70_000
    assert result["transaction"]["type"] == "debit"


def test_debit_wallet_rejects_reused_key_for_different_request():
    transaction = make_debit_transaction()

    service = WalletService()
    repository = FakeDebitWalletRepository(
        {
            "duplicate": True,
            "transaction": transaction,
        }
    )
    service.repository = repository

    with pytest.raises(ValueError, match="Idempotency key"):
        service.debit_wallet(
            user_id=USER_ID,
            amount_toman=50_000,
            description="API usage",
            idempotency_key="debit-service-test-0001",
        )

    assert repository.debit_calls == 1


@pytest.mark.parametrize("amount", [0, -1, 1.5, True, "100"])
def test_debit_wallet_rejects_invalid_amount(amount):
    service = WalletService()
    repository = FakeDebitWalletRepository(None)
    service.repository = repository

    with pytest.raises(ValueError, match="Amount"):
        service.debit_wallet(
            user_id=USER_ID,
            amount_toman=amount,
            description="API usage",
            idempotency_key="debit-service-test-0002",
        )

    assert repository.debit_calls == 0
