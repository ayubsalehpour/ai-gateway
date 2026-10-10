
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def reset_dependency_overrides():
    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()



@pytest.fixture
def client(monkeypatch):
    from app.repositories.user_repository import UserRepository

    monkeypatch.setattr(
        UserRepository,
        "create_email_index",
        lambda self: None,
    )

    with TestClient(app) as test_client:
        yield test_client

