
import math
from typing import Any

import anthropic

from app.core.config import settings
from app.providers.base import BaseProvider


class ClaudeProvider(BaseProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = (
            api_key if api_key is not None else settings.anthropic_api_key
        )

    async def generate(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        if not self.api_key or not self.api_key.strip():
            raise ValueError("Anthropic API key is not configured")

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
            or not 0 <= temperature <= 1
        ):
            raise ValueError("Temperature must be between 0 and 1")

        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 200000
        ):
            raise ValueError("max_tokens must be between 1 and 200000")

        system_messages = [
            message["content"]
            for message in messages
            if message["role"] == "system"
        ]
        claude_messages = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
            if message["role"] in {"user", "assistant"}
        ]

        if not claude_messages:
            raise ValueError(
                "At least one user or assistant message is required"
            )

        try:
            async with anthropic.AsyncAnthropic(
                api_key=self.api_key,
                timeout=60.0,
            ) as client:
                request_kwargs = {
                    "model": model.strip(),
                    "max_tokens": max_tokens,
                    "messages": claude_messages,
                    "temperature": temperature,
                }
                if system_messages:
                    request_kwargs["system"] = "\n\n".join(system_messages)
                response = await client.messages.create(**request_kwargs)
        except anthropic.APITimeoutError as exc:
            raise RuntimeError("Anthropic request timed out") from exc
        except anthropic.APIStatusError as exc:
            raise RuntimeError(
                f"Anthropic request failed with HTTP status {exc.status_code}"
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise RuntimeError("Could not connect to Anthropic") from exc

        content_blocks = getattr(response, "content", None)
        if not isinstance(content_blocks, list):
            raise RuntimeError("Invalid response received from Anthropic")

        text_parts = [
            block.text
            for block in content_blocks
            if getattr(block, "type", None) == "text"
            and isinstance(getattr(block, "text", None), str)
        ]

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        request_id = getattr(response, "id", None)
        response_model = getattr(response, "model", None)

        for value in (input_tokens, output_tokens):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise RuntimeError(
                    "Invalid token usage received from Anthropic"
                )

        if not isinstance(request_id, str) or not request_id:
            raise RuntimeError("Missing Anthropic request ID")

        if not isinstance(response_model, str) or not response_model:
            raise RuntimeError("Missing Anthropic response model")

        if not text_parts:
            raise RuntimeError("No text content received from Anthropic")

        return {
            "provider": "anthropic",
            "request_id": request_id,
            "model": response_model,
            "content": "".join(text_parts),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
