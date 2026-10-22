
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
