import hashlib
import json
import math
from typing import Any
from uuid import uuid4

from app.providers.factory import ProviderFactory
from app.repositories.billing_repository import BillingRepository
from app.repositories.gateway_request_repository import GatewayRequestRepository
from app.services.pricing_service import PricingService


class GatewayService:
    def __init__(
        self,
        pricing_service: PricingService | None = None,
        billing_repository: BillingRepository | None = None,
        request_repository: GatewayRequestRepository | None = None,
    ):
        self.pricing_service = pricing_service or PricingService()
        self.billing_repository = billing_repository or BillingRepository()
        self.request_repository = request_repository or GatewayRequestRepository()

    @staticmethod
    def _fingerprint(request_data: dict[str, Any]) -> str:
        encoded = json.dumps(
            request_data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def generate(
        self,
        user_id: str,
        idempotency_key: str,
        provider_name: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("User ID is required")
        user_id = user_id.strip()

        if (
            not isinstance(idempotency_key, str)
            or not 16 <= len(idempotency_key) <= 128
        ):
            raise ValueError("Idempotency-Key must contain 16 to 128 characters")

        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("Provider is required")
        provider_name = provider_name.strip().lower()
        if provider_name not in {"openai", "anthropic", "gemini"}:
            raise ValueError("Unsupported provider")

        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model is required")
        model = model.strip()

        if not isinstance(messages, list) or not messages:
            raise ValueError("Messages are required")
        if len(messages) > 100:
            raise ValueError("At most 100 messages are allowed")
        normalized_messages: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("Each message must be a dictionary")
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant"}:
                raise ValueError("Each message must have a valid role")
            if not isinstance(content, str) or not content:
                raise ValueError("Each message must have non-empty string content")
            normalized_messages.append({"role": role, "content": content})

        if (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or not math.isfinite(temperature)
            or not 0 <= temperature <= 2
        ):
            raise ValueError("Temperature must be between 0 and 2")
        temperature = float(temperature)

        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 200_000
        ):
            raise ValueError("max_tokens must be between 1 and 200000")

        request_data = {
            "provider": provider_name,
            "model": model,
            "messages": normalized_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        request_id = str(uuid4())
        claim = self.request_repository.claim(
            user_id=user_id,
            idempotency_key=idempotency_key,
            fingerprint=self._fingerprint(request_data),
            request_id=request_id,
            request_data=request_data,
        )
        if not claim["created"]:
            previous = claim["request"]
            state = previous.get("status")
            if state == "succeeded" and isinstance(previous.get("response"), dict):
                return previous["response"]
            if state == "failed":
                raise ValueError(
                    previous.get("error") or "This idempotent request previously failed"
                )
            raise RuntimeError(
                "This idempotent request is already in progress or requires reconciliation; "
                f"request_id={previous.get('request_id', 'unknown')}"
            )

        try:
            snapshot = self.pricing_service.calculate_reservation(
                provider=provider_name,
                model=model,
                messages=normalized_messages,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            self.request_repository.update_status(
                request_id, "failed", error=str(exc)
            )
            raise

        reservation = self.billing_repository.reserve(
            user_id=user_id,
            amount_toman=snapshot["reserve_amount_toman"],
            idempotency_key=idempotency_key,
            request_id=request_id,
            metadata={
                "provider": provider_name,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "pricing_snapshot": {
                    "provider": snapshot["provider"],
                    "model": snapshot["model"],
                    "input_price_per_million_toman": snapshot[
                        "input_price_per_million_toman"
                    ],
                    "output_price_per_million_toman": snapshot[
                        "output_price_per_million_toman"
                    ],
                    "pricing_version": snapshot["pricing_version"],
                },
            },
        )
        if reservation is None:
            self.request_repository.update_status(
                request_id, "failed", error="Insufficient wallet balance"
            )
            raise LookupError("Insufficient wallet balance")
        if reservation.get("duplicate"):
            self.request_repository.update_status(
                request_id,
                "reconciliation_required",
                error="A billing reservation exists without a matching gateway request",
            )
            raise RuntimeError(
                "A billing reservation already exists for this key; reconciliation required"
            )

        provider_request_id = None
        try:
            provider = ProviderFactory.create(provider_name)
            result = await provider.generate(
                model=model,
                messages=normalized_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if not isinstance(result, dict):
                raise ValueError("Provider response is invalid")

            input_tokens = result.get("input_tokens")
            output_tokens = result.get("output_tokens")
            for field, value in {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }.items():
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                ):
                    raise ValueError(f"Provider returned invalid {field}")

            actual_provider = result.get("provider", provider_name)
            if actual_provider != provider_name:
                raise ValueError("Provider returned an unexpected provider")
            content = result.get("content", result.get("text"))
            if not isinstance(content, str):
                raise ValueError("Provider returned invalid content")
            provider_request_id = result.get("request_id")
            if provider_request_id is not None and not isinstance(provider_request_id, str):
                provider_request_id = None

            cost = self.pricing_service.calculate_cost_from_snapshot(
                snapshot=snapshot,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            if cost["total_cost_toman"] > snapshot["reserve_amount_toman"]:
                raise ValueError("Actual cost exceeds reserved amount")

            usage_data = {
                "request_id": request_id,
                "user_id": user_id,
                "provider": provider_name,
                "model": model,
                "provider_model": result.get("model"),
                "provider_request_id": provider_request_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "status": "success",
                "pricing_version": snapshot["pricing_version"],
            }
            self.billing_repository.settle(
                idempotency_key=idempotency_key,
                actual_cost_toman=cost["total_cost_toman"],
                usage_data=usage_data,
            )

            response = {
                "request_id": request_id,
                "provider": provider_name,
                "model": model,
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cost": {
                    "input_cost_toman": int(math.ceil(cost["input_cost_toman"])),
                    "output_cost_toman": int(math.ceil(cost["output_cost_toman"])),
                    "total_cost_toman": cost["total_cost_toman"],
                    "pricing_version": cost["pricing_version"],
                },
            }
            self.request_repository.update_status(
                request_id,
                "succeeded",
                response=response,
                provider_request_id=provider_request_id,
            )
            return response
        except Exception as exc:
            # After a provider call begins, a failure may be ambiguous. Do not
            # refund automatically: an operator/reconciler must inspect it.
            self.request_repository.update_status(
                request_id,
                "reconciliation_required",
                error=str(exc),
                provider_request_id=provider_request_id,
            )
            raise
