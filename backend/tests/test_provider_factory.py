
import pytest

from app.providers.base import BaseProvider
from app.providers.factory import ProviderFactory
from app.providers.claude_provider import ClaudeProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.openai_provider import OpenAIProvider


@pytest.mark.parametrize(
    ("name", "expected_class"),
    [
        ("openai", OpenAIProvider),
        ("anthropic", ClaudeProvider),
        ("gemini", GeminiProvider),
    ],
)
def test_factory_creates_correct_provider(name, expected_class):
    provider = ProviderFactory.create(name)

    assert isinstance(provider, expected_class)
    assert isinstance(provider, BaseProvider)


def test_factory_normalizes_provider_name():
    assert isinstance(
        ProviderFactory.create("  OPENAI  "),
        OpenAIProvider,
    )


def test_factory_rejects_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        ProviderFactory.create("unsupported")


def test_factory_rejects_non_string_provider():
    with pytest.raises(ValueError, match="Provider name"):
        ProviderFactory.create(None)


def test_factory_lists_supported_providers():
    assert ProviderFactory.supported_providers() == [
        "anthropic",
        "gemini",
        "openai",
    ]
