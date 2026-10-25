
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.gateway_service import GatewayService


USER_ID = "507f1f77bcf86cd799439011"
IDEMPOTENCY_KEY = "test-idempotency-key-001"


class FakePricingService:
    def __init__(self):
        self.calls = []

    def calculate_reservation(
        self,
        provider,
        model,
        messages,
        max_tokens,
    ):
        self.calls.append(
            {
                "method": "calculate_reservation",
                "provider": provider,
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
            }
        )
        return {
            "provider": provider,
            "model": model,
            "input_price_per_million_toman": 2_000_000,
            "output_price_per_million_toman": 8_000_000,
            "pricing_version": 1,
            "estimated_input_tokens": 100,
            "max_tokens": max_tokens,
            "reserve_amount_toman": 10_000,
        }

    def calculate_cost_from_snapshot(
        self,
        snapshot,
        input_tokens,
        output_tokens,
    ):
        self.calls.append(
            {
                "method": "calculate_cost_from_snapshot",
                "provider": snapshot["provider"],
                "model": snapshot["model"],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )
        return {
            "provider": snapshot["provider"],
            "model": snapshot["model"],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_price_per_million_toman": 2_000_000,
            "output_price_per_million_toman": 8_000_000,
            "input_cost_toman": Decimal("2000"),
            "output_cost_toman": Decimal("4000"),
            "total_cost_toman": 6000,
            "pricing_version": 1,
        }


class FakeGatewayRequestRepository:
    def __init__(self):
        self.requests = {}
        self.status_updates = []

    def claim(self, *, user_id, idempotency_key, fingerprint, request_id, request_data):
        existing = self.requests.get(idempotency_key)
        if existing is not None:
            if existing.get("user_id") != user_id:
                raise ValueError("Idempotency key has already been used")
            if existing.get("fingerprint") != fingerprint:
                raise ValueError("Idempotency key has already been used for a different request")
            return {"created": False, "request": existing}
        record = {
            "user_id": user_id,
            "idempotency_key": idempotency_key,
            "fingerprint": fingerprint,
            "request_id": request_id,
            "request": request_data,
            "status": "processing",
            "response": None,
            "error": None,
        }
        self.requests[idempotency_key] = record
        return {"created": True, "request": record}

    def update_status(self, request_id, status, *, response=None, error=None, provider_request_id=None):
        self.status_updates.append({"request_id": request_id, "status": status, "response": response, "error": error})
        for record in self.requests.values():
            if record["request_id"] == request_id:
                record["status"] = status
                if response is not None:
                    record["response"] = response
                if error is not None:
                    record["error"] = error
                if provider_request_id is not None:
                    record["provider_request_id"] = provider_request_id
                return
        raise LookupError("Gateway request record not found")


class FakeBillingRepository:
    def __init__(self):
        self.reservations = {}
        self.reserve_calls = []
        self.settle_calls = []

    def get_by_idempotency_key(self, idempotency_key):
        return self.reservations.get(idempotency_key)

    def reserve(
        self,
        user_id,
        amount_toman,
        idempotency_key,
        request_id,
        metadata=None,
    ):
        self.reserve_calls.append(
            {
                "user_id": user_id,
                "amount_toman": amount_toman,
                "idempotency_key": idempotency_key,
                "request_id": request_id,
                "metadata": metadata,
            }
        )

        if idempotency_key in self.reservations:
            return {"duplicate": True}

        reservation = {
            "user_id": user_id,
            "amount_toman": amount_toman,
            "idempotency_key": idempotency_key,
            "request_id": request_id,
            "status": "reserved",
            "duplicate": False,
        }
        self.reservations[idempotency_key] = reservation
        return reservation

    def settle(
        self,
        idempotency_key,
        actual_cost_toman,
        usage_data,
    ):
        self.settle_calls.append(
            {
                "idempotency_key": idempotency_key,
                "actual_cost_toman": actual_cost_toman,
                "usage_data": usage_data,
            }
        )
        reservation = self.reservations[idempotency_key]
        reservation["status"] = "settled"
        reservation["actual_cost_toman"] = actual_cost_toman
        return reservation


@pytest.fixture
def pricing_service():
    return FakePricingService()


@pytest.fixture
def billing_repository():
    return FakeBillingRepository()


@pytest.fixture
def gateway_request_repository():
    return FakeGatewayRequestRepository()


@pytest.fixture
def gateway_service(pricing_service, billing_repository, gateway_request_repository):
    return GatewayService(
        pricing_service=pricing_service,
        billing_repository=billing_repository,
        request_repository=gateway_request_repository,
    )


def generate_kwargs(**overrides):
    kwargs = {
        "user_id": USER_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "provider_name": "openai",
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    kwargs.update(overrides)
    return kwargs


@pytest.mark.anyio
async def test_generate_success(
    gateway_service,
    pricing_service,
    billing_repository,
    gateway_request_repository,
):
    provider_response = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "content": "Hello!",
        "input_tokens": 1000,
        "output_tokens": 500,
        "total_tokens": 1500,
    }

    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(return_value=provider_response)

    with patch(
        "app.services.gateway_service.ProviderFactory.create",
        return_value=mock_provider,
    ):
        result = await gateway_service.generate(**generate_kwargs())

    assert result["content"] == "Hello!"
    assert result["total_tokens"] == 1500
    assert result["cost"]["total_cost_toman"] == 6000
    assert result["cost"]["pricing_version"] == 1
    saved = gateway_request_repository.requests[IDEMPOTENCY_KEY]
    assert saved["status"] == "succeeded"
    assert saved["response"] == result

    assert len(billing_repository.reserve_calls) == 1
    assert billing_repository.reserve_calls[0]["user_id"] == USER_ID
    assert billing_repository.reserve_calls[0]["amount_toman"] == 10_000

    assert len(billing_repository.settle_calls) == 1
    assert billing_repository.settle_calls[0]["actual_cost_toman"] == 6000
    assert (
        billing_repository.settle_calls[0]["usage_data"]["total_tokens"]
        == 1500
    )

    assert [
        call["method"] for call in pricing_service.calls
    ] == [
        "calculate_reservation",
        "calculate_cost_from_snapshot",
    ]


@pytest.mark.parametrize("provider", ["", " ", None])
@pytest.mark.anyio
async def test_generate_rejects_invalid_provider(
    gateway_service,
    provider,
):
    with pytest.raises(ValueError, match="Provider"):
        await gateway_service.generate(
            **generate_kwargs(provider_name=provider)
        )


@pytest.mark.anyio
async def test_generate_rejects_unsupported_provider(gateway_service):
    with pytest.raises(ValueError, match="Unsupported provider"):
        await gateway_service.generate(
            **generate_kwargs(provider_name="unsupported")
        )


@pytest.mark.parametrize("model", ["", " ", None])
@pytest.mark.anyio
async def test_generate_rejects_invalid_model(gateway_service, model):
    with pytest.raises(ValueError, match="Model"):
        await gateway_service.generate(**generate_kwargs(model=model))


@pytest.mark.parametrize("messages", [[], None, "Hello"])
@pytest.mark.anyio
async def test_generate_rejects_invalid_messages(
    gateway_service,
    messages,
):
    with pytest.raises(ValueError, match="Messages"):
        await gateway_service.generate(
            **generate_kwargs(messages=messages)
        )


@pytest.mark.parametrize("temperature", [-0.1, 2.1, True, "0.7"])
@pytest.mark.anyio
async def test_generate_rejects_invalid_temperature(
    gateway_service,
    temperature,
):
    with pytest.raises(ValueError, match="Temperature"):
        await gateway_service.generate(
            **generate_kwargs(temperature=temperature)
        )


@pytest.mark.anyio
async def test_generate_propagates_provider_error(
    gateway_service,
    billing_repository,
):
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(
        side_effect=RuntimeError("Provider failed")
    )

    with patch(
        "app.services.gateway_service.ProviderFactory.create",
        return_value=mock_provider,
    ):
        with pytest.raises(RuntimeError, match="Provider failed"):
            await gateway_service.generate(**generate_kwargs())

    # Ambiguous provider failure: retain reservation for reconciliation.
    assert (
        billing_repository.reservations[IDEMPOTENCY_KEY]["status"]
        == "reserved"
    )


@pytest.mark.anyio
async def test_generate_rejects_invalid_token_usage(gateway_service):
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(
        return_value={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "content": "Hello",
            "input_tokens": -1,
            "output_tokens": 5,
            "total_tokens": 4,
        }
    )

    with patch(
        "app.services.gateway_service.ProviderFactory.create",
        return_value=mock_provider,
    ):
        with pytest.raises(ValueError, match="invalid input_tokens"):
            await gateway_service.generate(**generate_kwargs())


@pytest.mark.anyio
async def test_generate_rejects_duplicate_idempotency_key(
    gateway_service,
    billing_repository,
    gateway_request_repository,
):
    gateway_request_repository.requests[IDEMPOTENCY_KEY] = {
        "user_id": USER_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "fingerprint": gateway_service._fingerprint({
            "provider": "openai",
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "max_tokens": 1024,
        }),
        "request_id": "prior-request",
        "status": "processing",
        "response": None,
    }

    with pytest.raises(RuntimeError, match="already in progress"):
        await gateway_service.generate(**generate_kwargs())

    # A duplicate request must not reserve funds or call the provider.
    assert billing_repository.reserve_calls == []


@pytest.mark.anyio
async def test_generate_replays_saved_success_without_provider_call(
    gateway_service,
    gateway_request_repository,
    billing_repository,
):
    request_data = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    saved_response = {
        "request_id": "old-request",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "content": "Previously generated",
        "input_tokens": 2,
        "output_tokens": 3,
        "total_tokens": 5,
        "cost": {
            "input_cost_toman": 1,
            "output_cost_toman": 2,
            "total_cost_toman": 3,
            "pricing_version": 1,
        },
    }
    gateway_request_repository.requests[IDEMPOTENCY_KEY] = {
        "user_id": USER_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "fingerprint": gateway_service._fingerprint(request_data),
        "request_id": "old-request",
        "status": "succeeded",
        "response": saved_response,
    }

    result = await gateway_service.generate(**generate_kwargs())

    assert result == saved_response
    assert billing_repository.reserve_calls == []


@pytest.mark.anyio
async def test_idempotency_key_cannot_be_reused_for_different_payload(
    gateway_service,
    gateway_request_repository,
):
    request_data = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Different text"}],
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    gateway_request_repository.requests[IDEMPOTENCY_KEY] = {
        "user_id": USER_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "fingerprint": gateway_service._fingerprint(request_data),
        "request_id": "old-request",
        "status": "succeeded",
        "response": {"content": "old response"},
    }

    with pytest.raises(ValueError, match="different request"):
        await gateway_service.generate(**generate_kwargs())
