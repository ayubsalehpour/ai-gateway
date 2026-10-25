
import pytest

from app.services.usage_service import UsageService


@pytest.fixture
def service():
    return UsageService()


@pytest.fixture
def valid_usage():
    return {
        "user_id": "507f1f77bcf86cd799439011",
        "request_id": "req_test_001",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "status": "success",
    }


def test_create_usage_record_success(service, valid_usage, monkeypatch):
    expected = {**valid_usage, "id": "usage_001"}

    monkeypatch.setattr(
        service.repository,
        "create_usage_record",
        lambda data: {**data, "id": "usage_001"},
    )

    result = service.create_usage_record(**valid_usage)

    assert result["id"] == expected["id"]
    assert result["total_tokens"] == 150


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_tokens", -1),
        ("output_tokens", -1),
        ("total_tokens", -1),
        ("input_tokens", True),
        ("output_tokens", 1.5),
    ],
)
def test_create_usage_record_rejects_invalid_tokens(
    service, valid_usage, field, value
):
    valid_usage[field] = value

    with pytest.raises(ValueError):
        service.create_usage_record(**valid_usage)


def test_create_usage_record_rejects_incorrect_total(
    service, valid_usage
):
    valid_usage["total_tokens"] = 149

    with pytest.raises(ValueError, match="Total tokens"):
        service.create_usage_record(**valid_usage)


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_id", "invalid-id"),
        ("request_id", " "),
        ("provider", "unsupported"),
        ("model", " "),
        ("status", "pending"),
    ],
)
def test_create_usage_record_rejects_invalid_fields(
    service, valid_usage, field, value
):
    valid_usage[field] = value

    with pytest.raises(ValueError):
        service.create_usage_record(**valid_usage)


def test_get_usage_by_request_id_rejects_empty_id(service):
    with pytest.raises(ValueError, match="Request ID"):
        service.get_usage_by_request_id(" ")


@pytest.mark.parametrize("limit", [0, 101, -1, True, 1.5])
def test_get_user_usage_rejects_invalid_limit(service, limit):
    with pytest.raises(ValueError, match="Limit"):
        service.get_user_usage(
            user_id="507f1f77bcf86cd799439011",
            limit=limit,
        )


def test_get_user_usage_rejects_invalid_skip(service):
    with pytest.raises(ValueError, match="Skip"):
        service.get_user_usage(
            user_id="507f1f77bcf86cd799439011",
            skip=-1,
        )
