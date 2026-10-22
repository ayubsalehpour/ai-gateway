
from bson import ObjectId

from app.api.users import user_service
from app.api.auth import auth_service
from app.core.security import hash_password
from app.services.user_service import UserService


def test_register_user(client, monkeypatch):
    monkeypatch.setattr(
        user_service.repository,
        "get_by_email",
        lambda email: None,
    )

    def fake_create(user_data, session=None):
        return {
            "_id": ObjectId(),
            "username": user_data["username"],
            "email": user_data["email"],
            "role": user_data["role"],
        }

    monkeypatch.setattr(
        user_service.repository,
        "create",
        fake_create,
    )

    response = client.post(
        "/users/",
        json={
            "username": "test_user",
            "email": "test@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "test_user"
    assert response.json()["role"] == "user"
    assert "password" not in response.json()


def test_register_duplicate_email_returns_409(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        user_service.repository,
        "get_by_email",
        lambda email: {"email": email},
    )

    response = client.post(
        "/users/",
        json={
            "username": "test_user",
            "email": "test@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 409


def test_login_success(client, monkeypatch):
    user = {
        "_id": ObjectId(),
        "username": "test_user",
        "email": "test@example.com",
        "password": hash_password("SecurePass123!"),
        "role": "user",
    }

    monkeypatch.setattr(
        auth_service.repository,
        "get_by_email",
        lambda email: user if email == user["email"] else None,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0


def test_login_wrong_password_returns_401(
    client,
    monkeypatch,
):
    user = {
        "_id": ObjectId(),
        "username": "test_user",
        "email": "test@example.com",
        "password": hash_password("SecurePass123!"),
        "role": "user",
    }

    monkeypatch.setattr(
        auth_service.repository,
        "get_by_email",
        lambda email: user if email == user["email"] else None,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


def test_register_user_creates_wallet(client, monkeypatch):
    from bson import ObjectId
    from app.api.users import user_service

    created_user_id = ObjectId()
    wallet_calls = []

    monkeypatch.setattr(
        user_service.repository,
        "get_by_email",
        lambda email: None,
    )

    def fake_create(user_data, session=None):
        return {
            "_id": created_user_id,
            "username": user_data["username"],
            "email": user_data["email"],
            "role": user_data["role"],
        }

    monkeypatch.setattr(
        user_service.repository,
        "create",
        fake_create,
    )

    monkeypatch.setattr(
        user_service.wallet_service,
        "create_wallet",
        lambda user_id, session=None: wallet_calls.append(user_id),
    )

    response = client.post(
        "/users/",
        json={
            "username": "wallet_test_user",
            "email": "wallet_test@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 201
    assert wallet_calls == [str(created_user_id)]




def test_register_rolls_back_when_wallet_creation_fails(monkeypatch):
    user_service_instance = UserService()
    created_user_id = ObjectId()
    events = []

    class FakeTransaction:
        def __enter__(self):
            events.append("transaction_started")

        def __exit__(self, exc_type, exc_value, traceback):
            if exc_type:
                events.append("transaction_aborted")
            else:
                events.append("transaction_committed")
            return False

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def start_transaction(self):
            return FakeTransaction()

    class FakeClient:
        def start_session(self):
            return FakeSession()

    monkeypatch.setattr(
        "app.services.user_service.client",
        FakeClient(),
    )

    monkeypatch.setattr(
        user_service_instance.repository,
        "create",
        lambda user_data, session=None: {
            "_id": created_user_id,
            "username": user_data["username"],
            "email": user_data["email"],
            "role": user_data["role"],
        },
    )

    def fail_wallet_creation(user_id, session=None):
        events.append("wallet_creation_failed")
        raise RuntimeError("Wallet creation failed")

    monkeypatch.setattr(
        user_service_instance.wallet_service,
        "create_wallet",
        fail_wallet_creation,
    )

    try:
        user_service_instance.create_user({
            "username": "rollback_user",
            "email": "rollback@example.com",
            "password": "SecurePass123!",
        })
    except RuntimeError as exc:
        assert str(exc) == "Wallet creation failed"
    else:
        raise AssertionError("Expected wallet creation to fail")

    assert events == [
        "transaction_started",
        "wallet_creation_failed",
        "transaction_aborted",
    ]
