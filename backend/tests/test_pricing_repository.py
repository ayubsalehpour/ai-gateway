
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.repositories.pricing_repository import PricingRepository


@pytest.fixture
def repository():
    with patch(
        "app.repositories.pricing_repository.database"
    ) as mock_database:
        repo = PricingRepository()
        repo.collection = mock_database.__getitem__.return_value
        yield repo


def test_get_active_price_queries_provider_and_model(repository):
    repository.collection.find_one.return_value = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "is_active": True,
    }

    result = repository.get_active_price("openai", "gpt-4o-mini")

    assert result is not None
    repository.collection.find_one.assert_called_once_with(
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "is_active": True,
        }
    )


def test_create_indexes_defines_unique_active_price(repository):
    repository.create_indexes()

    index_calls = repository.collection.create_index.call_args_list

    assert any(
        call.kwargs.get("unique") is True
        and call.kwargs.get("partialFilterExpression") == {"is_active": True}
        and call.kwargs.get("name") == "unique_active_model_price"
        for call in index_calls
    )


def test_create_indexes_defines_unique_version(repository):
    repository.create_indexes()

    index_calls = repository.collection.create_index.call_args_list

    assert any(
        call.kwargs.get("unique") is True
        and call.kwargs.get("name") == "unique_model_price_version"
        for call in index_calls
    )


@pytest.mark.parametrize(
    ("provider", "model", "input_price", "output_price", "version"),
    [
        ("", "gpt-4o-mini", 100, 200, 1),
        ("openai", "  ", 100, 200, 1),
        ("openai", "gpt-4o-mini", -1, 200, 1),
        ("openai", "gpt-4o-mini", 100, -1, 1),
        ("openai", "gpt-4o-mini", True, 200, 1),
        ("openai", "gpt-4o-mini", 100, 1.5, 1),
        ("openai", "gpt-4o-mini", 100, 200, 0),
        ("openai", "gpt-4o-mini", 100, 200, True),
    ],
)
def test_create_price_rejects_invalid_values(
    repository,
    provider,
    model,
    input_price,
    output_price,
    version,
):
    with pytest.raises(ValueError):
        repository.create_price(
            provider=provider,
            model=model,
            input_price_per_million_toman=input_price,
            output_price_per_million_toman=output_price,
            version=version,
        )


def test_create_price_rejects_non_increasing_version(repository):
    session = MagicMock()
    session.with_transaction.side_effect = lambda callback: callback(session)

    with (
        patch(
            "app.repositories.pricing_repository.client.start_session"
        ) as start_session,
    ):
        start_session.return_value.__enter__.return_value = session

        repository.collection.find_one.return_value = {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "version": 2,
            "is_active": True,
        }

        with pytest.raises(ValueError, match="greater than the latest version"):
            repository.create_price(
                provider="openai",
                model="gpt-4o-mini",
                input_price_per_million_toman=100,
                output_price_per_million_toman=200,
                version=2,
            )

        repository.collection.insert_one.assert_not_called()


def test_create_price_deactivates_old_price_and_inserts_new_one(repository):
    session = MagicMock()
    session.with_transaction.side_effect = lambda callback: callback(session)

    with patch(
        "app.repositories.pricing_repository.client.start_session"
    ) as start_session:
        start_session.return_value.__enter__.return_value = session

        repository.collection.find_one.return_value = {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "version": 1,
            "is_active": True,
        }
        repository.collection.insert_one.return_value.inserted_id = "new-price-id"

        result = repository.create_price(
            provider="openai",
            model="gpt-4o-mini",
            input_price_per_million_toman=300,
            output_price_per_million_toman=600,
            version=2,
        )

    repository.collection.update_many.assert_called_once_with(
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "is_active": True,
        },
        {
            "$set": {
                "is_active": False,
                "updated_at": repository.collection.update_many.call_args.args[1][
                    "$set"
                ]["updated_at"],
            }
        },
        session=session,
    )

    inserted_document = repository.collection.insert_one.call_args.args[0]

    assert inserted_document["version"] == 2
    assert inserted_document["is_active"] is True
    assert inserted_document["input_price_per_million_toman"] == 300
    assert result["id"] == "new-price-id"
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4o-mini"
