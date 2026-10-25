
from decimal import Decimal

import pytest

from app.services.pricing_service import PricingService


class FakePricingRepository:
    def __init__(self, price=None):
        self.price = price

    def get_active_price(self, provider, model):
        return self.price


VALID_PRICE = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "input_price_per_million_toman": 2_000_000,
    "output_price_per_million_toman": 8_000_000,
    "version": 1,
}


def make_service(monkeypatch, price=VALID_PRICE):
    monkeypatch.setattr(
        "app.services.pricing_service.PricingRepository",
        lambda: FakePricingRepository(price),
    )
    return PricingService()


def test_calculate_cost_success(monkeypatch):
    service = make_service(monkeypatch)

    result = service.calculate_cost(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=500,
    )

    assert result["input_cost_toman"] == Decimal("2000")
    assert result["output_cost_toman"] == Decimal("4000")
    assert result["total_cost_toman"] == 6000
    assert result["pricing_version"] == 1


def test_calculate_cost_rounds_fraction_up(monkeypatch):
    price = {
        **VALID_PRICE,
        "input_price_per_million_toman": 1,
        "output_price_per_million_toman": 0,
    }
    service = make_service(monkeypatch, price)

    result = service.calculate_cost(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=1,
        output_tokens=0,
    )

    assert result["total_cost_toman"] == 1


def test_calculate_cost_rejects_unknown_model(monkeypatch):
    service = make_service(monkeypatch, None)

    with pytest.raises(ValueError, match="No active price"):
        service.calculate_cost(
            provider="openai",
            model="unknown-model",
            input_tokens=10,
            output_tokens=5,
        )


@pytest.mark.parametrize("provider", ["", "  ", None])
def test_calculate_cost_rejects_invalid_provider(monkeypatch, provider):
    service = make_service(monkeypatch)

    with pytest.raises(ValueError, match="Provider"):
        service.calculate_cost(
            provider=provider,
            model="gpt-4o-mini",
            input_tokens=10,
            output_tokens=5,
        )


@pytest.mark.parametrize("model", ["", "  ", None])
def test_calculate_cost_rejects_invalid_model(monkeypatch, model):
    service = make_service(monkeypatch)

    with pytest.raises(ValueError, match="Model"):
        service.calculate_cost(
            provider="openai",
            model=model,
            input_tokens=10,
            output_tokens=5,
        )


@pytest.mark.parametrize(
    ("input_tokens", "output_tokens"),
    [
        (-1, 0),
        (0, -1),
        (True, 0),
        (0, False),
        (1.5, 0),
        (0, "10"),
    ],
)
def test_calculate_cost_rejects_invalid_tokens(
    monkeypatch,
    input_tokens,
    output_tokens,
):
    service = make_service(monkeypatch)

    with pytest.raises(ValueError, match="non-negative integer"):
        service.calculate_cost(
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


@pytest.mark.parametrize(
    "invalid_price",
    [-1, True, 1.5, "100"],
)
def test_calculate_cost_rejects_invalid_price(monkeypatch, invalid_price):
    price = {
        **VALID_PRICE,
        "input_price_per_million_toman": invalid_price,
    }
    service = make_service(monkeypatch, price)

    with pytest.raises(ValueError, match="Invalid pricing field"):
        service.calculate_cost(
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
        )
