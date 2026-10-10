
from app.api.dependencies import get_current_user
from app.main import app


def test_regular_user_cannot_access_admin_dashboard(client):
    app.dependency_overrides[get_current_user] = lambda: {
        "_id": "test-user-id",
        "username": "test_user",
        "email": "test@example.com",
        "role": "user",
    }

    response = client.get("/admin/dashboard")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_can_access_admin_dashboard(client):
    app.dependency_overrides[get_current_user] = lambda: {
        "_id": "test-admin-id",
        "username": "test_admin",
        "email": "admin@example.com",
        "role": "admin",
    }

    response = client.get("/admin/dashboard")

    assert response.status_code == 200
    assert response.json()["admin"] == "test_admin"
