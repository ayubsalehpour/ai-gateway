
from app.providers.base import BaseProvider
from app.providers.claude_provider import ClaudeProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.openai_provider import OpenAIProvider


class ProviderFactory:
    _providers: dict[str, type[BaseProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": ClaudeProvider,
        "gemini": GeminiProvider,
    }

    @classmethod
    def create(cls, provider_name: str) -> BaseProvider:
        if not isinstance(provider_name, str):
            raise ValueError("Provider name must be a string")

        normalized_name = provider_name.strip().lower()

        provider_class = cls._providers.get(normalized_name)

        if provider_class is None:
            raise ValueError(
                f"Unsupported provider: {normalized_name or '<empty>'}"
            )

        return provider_class()

    @classmethod
    def supported_providers(cls) -> list[str]:
        return sorted(cls._providers.keys())
