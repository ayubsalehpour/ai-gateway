
import math
from typing import Any

import httpx

from app.core.config import settings
from app.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = (
            api_key if api_key is not None else settings.openai_api_key
        )

    async def generate(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        if not self.api_key or not self.api_key.strip():
            raise ValueError("OpenAI API key is not configured")

        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model is required")

        if not isinstance(messages, list) or not messages:
            raise ValueError("Messages cannot be empty")

        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("Each message must be a dictionary")

            if (
                not isinstance(message.get("role"), str)
                or not message["role"].strip()
            ):
                raise ValueError("Each message must have a valid role")

            if not isinstance(message.get("content"), str):
                raise ValueError("Each message must have string content")

        if (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or not math.isfinite(temperature)
            or not 0 <= temperature <= 2
        ):
            raise ValueError("Temperature must be between 0 and 2")

        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 200000
        ):
            raise ValueError("max_tokens must be between 1 and 200000")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model.strip(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()

        except httpx.TimeoutException as exc:
            raise RuntimeError("OpenAI request timed out") from exc

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise RuntimeError(
                f"OpenAI request failed with HTTP status {status_code}"
            ) from exc

        except httpx.RequestError as exc:
            raise RuntimeError("Could not connect to OpenAI") from exc

        try:
            data = response.json()

            if not isinstance(data, dict):
                raise ValueError("Invalid response object")

            choices = data.get("choices")
            usage = data.get("usage")

            if not isinstance(choices, list) or not choices:
                raise ValueError("Missing response choices")

            if not isinstance(usage, dict):
                raise ValueError("Missing token usage")

            choice = choices[0]
            if not isinstance(choice, dict):
                raise ValueError("Invalid response choice")

            message = choice.get("message")
            if not isinstance(message, dict):
                raise ValueError("Missing response message")

            content = message.get("content")
            if not isinstance(content, str):
                raise ValueError("Invalid response content")

            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")

            token_values = (input_tokens, output_tokens, total_tokens)

            if any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                for value in token_values
            ):
                raise ValueError("Invalid token usage values")

            if total_tokens != input_tokens + output_tokens:
                raise ValueError("Inconsistent token usage values")

            request_id = data.get("id")
            response_model = data.get("model")

            if not isinstance(request_id, str) or not request_id:
                raise ValueError("Missing provider request ID")

            if not isinstance(response_model, str) or not response_model:
                raise ValueError("Missing response model")

        except (ValueError, TypeError, KeyError) as exc:
            raise RuntimeError(
                "Invalid response received from OpenAI"
            ) from exc

        return {
            "provider": "openai",
            "request_id": request_id,
            "model": response_model,
            "content": content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }
