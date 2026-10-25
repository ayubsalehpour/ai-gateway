
import os
import uuid

import pytest
from pymongo.errors import DuplicateKeyError

from app.core.database import client, database
from app.repositories.pricing_repository import PricingRepository


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MONGODB_INTEGRATION_TESTS") != "1",
    reason="Set RUN_MONGODB_INTEGRATION_TESTS=1 to run MongoDB integration tests",
)


@pytest.fixture
def pricing_repository():
    # Use a separate temporary collection; do not touch model_pricing.
    collection_name = f"test_model_pricing_{uuid.uuid4().hex}"
    collection = database[collection_name]
    repository = PricingRepository()
    repository.collection = collection

    try:
        hello = client.admin.command("hello")
        if not hello.get("isWritablePrimary"):
            pytest.skip("MongoDB is not writable primary")
        if not hello.get("setName"):
            pytest.skip("MongoDB transactions require a replica set")

        repository.create_indexes()
        yield repository
    finally:
        collection.drop()


def create_price(repository, version, input_price, output_price):
    return repository.create_price(
        provider="openai",
        model="integration-test-model",
        input_price_per_million_toman=input_price,
        output_price_per_million_toman=output_price,
        version=version,
    )


def test_new_version_activates_and_preserves_history(pricing_repository):
    repository = pricing_repository

    first = create_price(repository, 1, 100, 200)
    second = create_price(repository, 2, 300, 600)

    old_price = repository.collection.find_one({"_id": __import__(
        "bson"
    ).ObjectId(first["id"])})
    new_price = repository.collection.find_one({"_id": __import__(
        "bson"
    ).ObjectId(second["id"])})

    assert old_price is not None
    assert old_price["is_active"] is False
    assert old_price["version"] == 1

    assert new_price is not None
    assert new_price["is_active"] is True
    assert new_price["version"] == 2

    active_prices = list(
        repository.collection.find(
            {
                "provider": "openai",
                "model": "integration-test-model",
                "is_active": True,
            }
        )
    )
    assert len(active_prices) == 1


def test_unique_index_rejects_second_active_price(pricing_repository):
    repository = pricing_repository
    create_price(repository, 1, 100, 200)

    with pytest.raises(DuplicateKeyError):
        repository.collection.insert_one(
            {
                "provider": "openai",
                "model": "integration-test-model",
                "input_price_per_million_toman": 999,
                "output_price_per_million_toman": 999,
                "version": 99,
                "is_active": True,
            }
        )


def test_failed_insert_rolls_back_deactivation(pricing_repository):
    repository = pricing_repository
    first = create_price(repository, 1, 100, 200)

    real_collection = repository.collection

    class FailingInsertCollection:
        def __getattr__(self, name):
            return getattr(real_collection, name)

        def insert_one(self, *args, **kwargs):
            raise RuntimeError("Simulated insert failure")

    repository.collection = FailingInsertCollection()

    with pytest.raises(RuntimeError, match="Simulated insert failure"):
        create_price(repository, 2, 300, 600)

    repository.collection = real_collection

    old_price = real_collection.find_one(
        {"_id": __import__("bson").ObjectId(first["id"])}
    )

    assert old_price is not None
    assert old_price["is_active"] is True
    assert old_price["version"] == 1

    active_prices = list(
        real_collection.find(
            {
                "provider": "openai",
                "model": "integration-test-model",
                "is_active": True,
            }
        )
    )
    assert len(active_prices) == 1
