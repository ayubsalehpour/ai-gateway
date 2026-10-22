
from datetime import datetime, timezone

from app.api.dependencies import get_current_user
from app.api.wallet import wallet_service
from app.main import app


def test_user_can_get_own_wallet_transactions(client, monkeypatch):
    user_id = "507f1f77bcf86cd799439012"
    now = datetime.now(timezone.utc)

    app.dependency_overrides[get_current_user] = lambda: {
        "_id": user_id,
        "username": "test_user",
        "email": "user@example.com",
        "role": "user",
    }

    expected_transactions = [
        {
            "id": "507f1f77bcf86cd799439014",
            "wallet_id": "507f1f77bcf86cd799439013",
            "user_id": user_id,
            "type": "credit",
            "amount_toman": 100_000,
            "balance_after": 100_000,
            "description": "Manual wallet charge",
            "reference": None,
            "created_at": now,
        }
    ]

    calls = {}

    def fake_get_transactions(**kwargs):
        calls.update(kwargs)
        return expected_transactions

    monkeypatch.setattr(
        wallet_service,
        "get_transactions",
        fake_get_transactions,
    )

    response = client.get("/wallet/transactions?limit=10")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["amount_toman"] == 100_000
    assert calls["user_id"] == user_id
    assert calls["limit"] == 10


def test_wallet_transactions_reject_invalid_limit(client):
    app.dependency_overrides[get_current_user] = lambda: {
        "_id": "507f1f77bcf86cd799439012",
        "username": "test_user",
        "email": "user@example.com",
        "role": "user",
    }

    response = client.get("/wallet/transactions?limit=101")

    assert response.status_code == 422


def test_wallet_transactions_require_authentication(client):
    response = client.get("/wallet/transactions")

    assert response.status_code == 401


def test_wallet_transactions_reject_zero_limit(client):
    app.dependency_overrides[get_current_user] = lambda: {
        "_id": "507f1f77bcf86cd799439012",
        "username": "test_user",
        "email": "user@example.com",
        "role": "user",
    }

    response = client.get("/wallet/transactions?limit=0")

    assert response.status_code == 422



def test_wallet_transactions_passes_pagination_parameters(
    client,
    monkeypatch,
):
    user_id = "507f1f77bcf86cd799439012"

    app.dependency_overrides[get_current_user] = lambda: {
        "_id": user_id,
        "username": "test_user",
        "email": "user@example.com",
        "role": "user",
    }

    calls = {}

    def fake_get_transactions(**kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr(
        wallet_service,
        "get_transactions",
        fake_get_transactions,
    )

    response = client.get(
        "/wallet/transactions?limit=10&skip=20"
    )

    assert response.status_code == 200
    assert calls["user_id"] == user_id
    assert calls["limit"] == 10
    assert calls["skip"] == 20
