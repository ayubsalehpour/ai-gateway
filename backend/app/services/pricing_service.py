
from decimal import Decimal, ROUND_CEILING
from typing import Any

from app.repositories.pricing_repository import PricingRepository


class PricingService:
    TOKENS_PER_MILLION = Decimal("1000000")

    def __init__(self):
        self.repository = PricingRepository()

    @staticmethod
    def _validate_rate(value: Any, field: str) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise ValueError(f"Invalid pricing field: {field}")
        return value

    @staticmethod
    def _validate_token_count(value: Any, field: str) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise ValueError(f"{field} must be a non-negative integer")
        return value

    def get_price_snapshot(
        self,
        provider: str,
        model: str,
    ) -> dict[str, Any]:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("Provider is required")

        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model is required")

        provider = provider.strip().lower()
        model = model.strip()

        price = self.repository.get_active_price(
            provider=provider,
            model=model,
        )

        if price is None:
            raise ValueError("No active price configured for this model")

        return {
            "provider": provider,
            "model": model,
            "input_price_per_million_toman": self._validate_rate(
                price.get("input_price_per_million_toman"),
                "input_price_per_million_toman",
            ),
            "output_price_per_million_toman": self._validate_rate(
                price.get("output_price_per_million_toman"),
                "output_price_per_million_toman",
            ),
            "pricing_version": price.get("version"),
        }

    def calculate_cost_from_snapshot(
        self,
        snapshot: dict[str, Any],
        input_tokens: int,
        output_tokens: int,
    ) -> dict[str, Any]:
        if not isinstance(snapshot, dict):
            raise ValueError("Pricing snapshot must be a dictionary")

        input_tokens = self._validate_token_count(
            input_tokens, "input_tokens"
        )
        output_tokens = self._validate_token_count(
            output_tokens, "output_tokens"
        )

        input_rate = self._validate_rate(
            snapshot.get("input_price_per_million_toman"),
            "input_price_per_million_toman",
        )
        output_rate = self._validate_rate(
            snapshot.get("output_price_per_million_toman"),
            "output_price_per_million_toman",
        )

        input_cost = (
            Decimal(input_tokens)
            * Decimal(input_rate)
            / self.TOKENS_PER_MILLION
        )
        output_cost = (
            Decimal(output_tokens)
            * Decimal(output_rate)
            / self.TOKENS_PER_MILLION
        )

        total_cost = int(
            (input_cost + output_cost).quantize(
                Decimal("1"),
                rounding=ROUND_CEILING,
            )
        )

        return {
            "provider": snapshot.get("provider"),
            "model": snapshot.get("model"),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_price_per_million_toman": input_rate,
            "output_price_per_million_toman": output_rate,
            "input_cost_toman": input_cost,
            "output_cost_toman": output_cost,
            "total_cost_toman": total_cost,
            "pricing_version": snapshot.get("pricing_version"),
        }

    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> dict[str, Any]:
        snapshot = self.get_price_snapshot(provider, model)

        return self.calculate_cost_from_snapshot(
            snapshot=snapshot,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def calculate_reservation(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> dict[str, Any]:
        if not isinstance(messages, list) or not messages:
            raise ValueError("Messages must be a non-empty list")

        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 200_000
        ):
            raise ValueError("max_tokens must be between 1 and 200000")

        snapshot = self.get_price_snapshot(provider, model)

        estimated_input_tokens = 0

        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("Each message must be a dictionary")

            content = message.get("content", "")
            role = message.get("role", "")

            if not isinstance(content, str) or not isinstance(role, str):
                raise ValueError("Message role and content must be strings")

            # Conservative heuristic only; this is not a real tokenizer.
            estimated_input_tokens += 2 * (len(content) + len(role))

        input_rate = snapshot["input_price_per_million_toman"]
        output_rate = snapshot["output_price_per_million_toman"]

        estimated_input_cost = (
            estimated_input_tokens * input_rate + 999_999
        ) // 1_000_000

        maximum_output_cost = (
            max_tokens * output_rate + 999_999
        ) // 1_000_000

        calculated_reserve = (
            estimated_input_cost + maximum_output_cost
        )

        # BillingRepository currently requires a positive reservation.
        # Even a free/very-low-cost model reserves 1 Toman; settlement
        # refunds any unused amount.
        reserve_amount = max(1, calculated_reserve)

        return {
            **snapshot,
            "estimated_input_tokens": estimated_input_tokens,
            "max_tokens": max_tokens,
            "reserve_amount_toman": reserve_amount,
        }
