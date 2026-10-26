from fastapi.testclient import TestClient

from app.api.dependencies import require_admin
from app.api.reconciliation import reconciliation_service
from app.main import app


class FakeReconciliationService:
    def __init__(self):
        self.calls = []

    def flag_stale_processing_requests(self, *, older_than_minutes, limit):
        self.calls.append(
            {
                "older_than_minutes": older_than_minutes,
                "limit": limit,
            }
        )
        return {"scanned": 5, "flagged": 2}


def test_admin_can_run_reconciliation(monkeypatch):
    fake_service = FakeReconciliationService()
    monkeypatch.setattr(
        "app.api.reconciliation.reconciliation_service",
        fake_service,
    )
    app.dependency_overrides[require_admin] = lambda: {
        "_id": "admin-id",
        "username": "admin",
        "role": "admin",
    }

    try:
        with TestClient(app) as client:
            response = client.post(
                "/admin/reconciliation/run?older_than_minutes=15&limit=25"
            )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert response.json() == {"scanned": 5, "flagged": 2}
    assert fake_service.calls == [
        {"older_than_minutes": 15, "limit": 25}
    ]


def test_reconciliation_rejects_invalid_query_parameters():
    app.dependency_overrides[require_admin] = lambda: {
        "_id": "admin-id",
        "username": "admin",
        "role": "admin",
    }

    try:
        with TestClient(app) as client:
            response = client.post(
                "/admin/reconciliation/run?older_than_minutes=0"
            )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 422


def test_reconciliation_requires_admin_authentication():
    with TestClient(app) as client:
        response = client.post("/admin/reconciliation/run")

    assert response.status_code == 401
