
import math
from typing import Any

from google import genai
from google.genai import types

from app.core.config import settings
from app.providers.base import BaseProvider


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = (
            api_key if api_key is not None else settings.gemini_api_key
        )

    async def generate(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        if not self.api_key or not self.api_key.strip():
            raise ValueError("Gemini API key is not configured")

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
            or not 1 <= max_tokens <= 65536
        ):
            raise ValueError("max_tokens must be between 1 and 65536")

        system_messages = []
        contents = []

        for message in messages:
            role = message["role"]
            content = message["content"]

            if role == "system":
                system_messages.append(content)
            elif role == "user":
                contents.append(
                    {"role": "user", "parts": [{"text": content}]}
                )
            elif role == "assistant":
                contents.append(
                    {"role": "model", "parts": [{"text": content}]}
                )

        if not contents:
            raise ValueError(
                "At least one user or assistant message is required"
            )

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=(
                "\n\n".join(system_messages) if system_messages else None
            ),
        )

        try:
            async with genai.Client(api_key=self.api_key).aio as client:
                response = await client.models.generate_content(
                    model=model.strip(),
                    contents=contents,
                    config=config,
                )
        except Exception as exc:
            raise RuntimeError("Gemini API request failed") from exc

        content = getattr(response, "text", None)
        usage = getattr(response, "usage_metadata", None)

        if not isinstance(content, str) or not content:
            raise RuntimeError("Invalid or empty response received from Gemini")

        input_tokens = getattr(usage, "prompt_token_count", None)
        output_tokens = getattr(usage, "candidates_token_count", None)
        request_id = getattr(response, "response_id", None)
        response_model = getattr(response, "model_version", None)

        for value in (input_tokens, output_tokens):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise RuntimeError(
                    "Invalid token usage received from Gemini"
                )

        if not isinstance(request_id, str) or not request_id:
            raise RuntimeError("Missing Gemini request ID")

        if not isinstance(response_model, str) or not response_model:
            raise RuntimeError("Missing Gemini response model")

        return {
            "provider": "gemini",
            "request_id": request_id,
            "model": response_model,
            "content": content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
