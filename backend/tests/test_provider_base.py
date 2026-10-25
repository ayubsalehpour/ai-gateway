
import pytest

from app.providers.base import BaseProvider
from app.providers.openai_provider import OpenAIProvider


def test_openai_provider_implements_base_provider():
    provider = OpenAIProvider(api_key="test-key")

    assert isinstance(provider, BaseProvider)


def test_base_provider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseProvider()
