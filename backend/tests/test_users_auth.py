
from bson import ObjectId

from app.api.users import user_service
from app.api.auth import auth_service
from app.core.security import hash_password


def test_register_user(client, monkeypatch):
    monkeypatch.setattr(
        user_service.repository,
        "get_by_email",
        lambda email: None,
    )

    def fake_create(user_data):
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
