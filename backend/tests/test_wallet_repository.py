
import pytest

from pymongo import ReturnDocument

from app.repositories import wallet_repository as wallet_repo_module
from app.repositories.wallet_repository import WalletRepository


USER_ID = "507f1f77bcf86cd799439012"


class FakeWalletsCollection:
    def __init__(self, result=None):
        self.result = result
        self.query = None
        self.update = None
        self.options = None
        self.calls = 0

    def find_one_and_update(
        self,
        query,
        update,
        **kwargs,
    ):
        self.calls += 1
        self.query = query
        self.update = update
        self.options = kwargs
        return self.result


def test_debit_balance_success(monkeypatch):
    expected_wallet = {
        "user_id": USER_ID,
        "balance_toman": 20_000,
    }
    fake_collection = FakeWalletsCollection(expected_wallet)

    monkeypatch.setattr(
        wallet_repo_module,
        "wallets_collection",
        fake_collection,
    )

    repository = WalletRepository()
    result = repository.debit_balance(USER_ID, 30_000)

    assert result == expected_wallet
    assert fake_collection.calls == 1
    assert fake_collection.query == {
        "user_id": USER_ID,
        "balance_toman": {"$gte": 30_000},
    }
    assert fake_collection.update["$inc"]["balance_toman"] == -30_000
    assert fake_collection.options["return_document"] == ReturnDocument.AFTER


def test_debit_balance_insufficient_funds(monkeypatch):
    fake_collection = FakeWalletsCollection(result=None)

    monkeypatch.setattr(
        wallet_repo_module,
        "wallets_collection",
        fake_collection,
    )

    repository = WalletRepository()
    result = repository.debit_balance(USER_ID, 30_000)

    assert result is None
    assert fake_collection.calls == 1


@pytest.mark.parametrize("amount", [0, -1, 1.5, True, "100"])
def test_debit_balance_rejects_invalid_amount(amount, monkeypatch):
    fake_collection = FakeWalletsCollection()

    monkeypatch.setattr(
        wallet_repo_module,
        "wallets_collection",
        fake_collection,
    )

    repository = WalletRepository()

    with pytest.raises(ValueError):
        repository.debit_balance(USER_ID, amount)

    assert fake_collection.calls == 0



from contextlib import contextmanager
from unittest.mock import MagicMock


def test_debit_wallet_transaction_success(monkeypatch):
    wallet_id = "507f1f77bcf86cd799439013"
    inserted_id = "507f1f77bcf86cd799439014"

    wallet = {
        "_id": wallet_id,
        "user_id": USER_ID,
        "balance_toman": 70_000,
    }

    session = MagicMock()
    transaction_context = MagicMock()

    @contextmanager
    def fake_start_transaction():
        yield

    session.start_transaction.side_effect = fake_start_transaction

    client = MagicMock()
    client.start_session.return_value.__enter__.return_value = session

    wallets_collection = MagicMock()
    wallets_collection.find_one_and_update.return_value = wallet.copy()

    transactions_collection = MagicMock()
    transactions_collection.find_one.return_value = None
    transactions_collection.insert_one.return_value.inserted_id = inserted_id

    monkeypatch.setattr(wallet_repo_module, "client", client)
    monkeypatch.setattr(
        wallet_repo_module,
        "wallets_collection",
        wallets_collection,
    )
    monkeypatch.setattr(
        wallet_repo_module,
        "wallet_transactions_collection",
        transactions_collection,
    )

    repository = WalletRepository()

    result = repository.debit_wallet_transaction(
        user_id=USER_ID,
        amount_toman=30_000,
        description="API usage",
        idempotency_key="debit-test-key-0001",
    )

    assert result["duplicate"] is False
    assert result["wallet"]["balance_toman"] == 70_000
    assert result["transaction"]["type"] == "debit"
    assert result["transaction"]["amount_toman"] == 30_000
    assert result["transaction"]["balance_after"] == 70_000

    update_call = wallets_collection.find_one_and_update.call_args
    assert update_call.args[0]["balance_toman"] == {"$gte": 30_000}
    assert update_call.args[1]["$inc"]["balance_toman"] == -30_000
    assert update_call.kwargs["session"] is session

    insert_call = transactions_collection.insert_one.call_args
    assert insert_call.args[0]["type"] == "debit"
    assert insert_call.kwargs["session"] is session



def test_debit_wallet_transaction_insufficient_funds(monkeypatch):
    session = MagicMock()

    @contextmanager
    def fake_start_transaction():
        yield

    session.start_transaction.side_effect = fake_start_transaction

    client = MagicMock()
    client.start_session.return_value.__enter__.return_value = session

    wallets_collection = MagicMock()
    wallets_collection.find_one_and_update.return_value = None

    transactions_collection = MagicMock()
    transactions_collection.find_one.return_value = None

    monkeypatch.setattr(wallet_repo_module, "client", client)
    monkeypatch.setattr(
        wallet_repo_module,
        "wallets_collection",
        wallets_collection,
    )
    monkeypatch.setattr(
        wallet_repo_module,
        "wallet_transactions_collection",
        transactions_collection,
    )

    repository = WalletRepository()

    result = repository.debit_wallet_transaction(
        user_id=USER_ID,
        amount_toman=30_000,
        description="API usage",
        idempotency_key="debit-test-key-0002",
    )

    assert result is None
    wallets_collection.find_one_and_update.assert_called_once()
    transactions_collection.insert_one.assert_not_called()



def test_debit_wallet_transaction_duplicate_key(monkeypatch):
    existing_transaction = {
        "_id": "507f1f77bcf86cd799439014",
        "user_id": USER_ID,
        "type": "debit",
        "amount_toman": 30_000,
        "description": "API usage",
        "reference": None,
        "idempotency_key": "debit-test-key-0001",
    }

    session = MagicMock()

    @contextmanager
    def fake_start_transaction():
        yield

    session.start_transaction.side_effect = fake_start_transaction

    client = MagicMock()
    client.start_session.return_value.__enter__.return_value = session

    wallets_collection = MagicMock()
    transactions_collection = MagicMock()
    transactions_collection.find_one.return_value = existing_transaction

    monkeypatch.setattr(wallet_repo_module, "client", client)
    monkeypatch.setattr(
        wallet_repo_module,
        "wallets_collection",
        wallets_collection,
    )
    monkeypatch.setattr(
        wallet_repo_module,
        "wallet_transactions_collection",
        transactions_collection,
    )

    repository = WalletRepository()

    result = repository.debit_wallet_transaction(
        user_id=USER_ID,
        amount_toman=30_000,
        description="API usage",
        idempotency_key="debit-test-key-0001",
    )

    assert result["duplicate"] is True
    assert result["transaction"] == existing_transaction

    wallets_collection.find_one_and_update.assert_not_called()
    transactions_collection.insert_one.assert_not_called()
