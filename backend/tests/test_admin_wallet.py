
from datetime import datetime, timezone

from app.api.admin import wallet_service
from app.api.dependencies import get_current_user
from app.main import app


def test_regular_user_cannot_credit_wallet(client):
    app.dependency_overrides[get_current_user] = lambda: {
        "_id": "507f1f77bcf86cd799439011",
        "username": "regular_user",
        "email": "user@example.com",
        "role": "user",
    }

    response = client.post(
        "/admin/wallets/credit",
        json={
            "user_id": "507f1f77bcf86cd799439012",
            "amount_toman": 100_000,
            "description": "Manual wallet charge",
            "idempotency_key": "admin-charge-test-0001",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_can_credit_wallet(client, monkeypatch):
    admin_id = "507f1f77bcf86cd799439011"
    user_id = "507f1f77bcf86cd799439012"
    idempotency_key = "admin-charge-test-0002"
    now = datetime.now(timezone.utc)

    app.dependency_overrides[get_current_user] = lambda: {
        "_id": admin_id,
        "username": "test_admin",
        "email": "admin@example.com",
        "role": "admin",
    }

    expected_result = {
        "wallet": {
            "id": "507f1f77bcf86cd799439013",
            "user_id": user_id,
            "balance_toman": 100_000,
            "created_at": now,
            "updated_at": now,
        },
        "transaction": {
            "id": "507f1f77bcf86cd799439014",
            "wallet_id": "507f1f77bcf86cd799439013",
            "user_id": user_id,
            "type": "credit",
            "amount_toman": 100_000,
            "balance_after": 100_000,
            "description": "Manual wallet charge",
            "reference": None,
            "created_at": now,
        },
    }

    calls = {}

    def fake_credit_wallet(**kwargs):
        calls.update(kwargs)
        return expected_result

    monkeypatch.setattr(
        wallet_service,
        "credit_wallet",
        fake_credit_wallet,
    )

    response = client.post(
        "/admin/wallets/credit",
        json={
            "user_id": user_id,
            "amount_toman": 100_000,
            "description": "Manual wallet charge",
            "idempotency_key": idempotency_key,
        },
    )

    assert response.status_code == 200
    assert response.json()["wallet"]["balance_toman"] == 100_000
    assert response.json()["transaction"]["amount_toman"] == 100_000
    assert calls["admin_id"] == admin_id
    assert calls["user_id"] == user_id
    assert calls["idempotency_key"] == idempotency_key


def test_admin_credit_rejects_invalid_amount(client):
    app.dependency_overrides[get_current_user] = lambda: {
        "_id": "507f1f77bcf86cd799439011",
        "username": "test_admin",
        "email": "admin@example.com",
        "role": "admin",
    }

    response = client.post(
        "/admin/wallets/credit",
        json={
            "user_id": "507f1f77bcf86cd799439012",
            "amount_toman": 0,
            "description": "Invalid charge",
            "idempotency_key": "admin-charge-test-0003",
        },
    )

    assert response.status_code == 422
