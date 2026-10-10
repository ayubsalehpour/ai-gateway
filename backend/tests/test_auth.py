
def test_user_profile_requires_authentication(client):
    response = client.get("/users/me")

    assert response.status_code == 401


def test_user_profile_rejects_invalid_token(client):
    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_admin_dashboard_requires_authentication(client):
    response = client.get("/admin/dashboard")

    assert response.status_code == 401
