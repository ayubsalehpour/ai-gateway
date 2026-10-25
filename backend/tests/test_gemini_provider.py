
from types import SimpleNamespace

import anyio
import pytest

from app.providers.base import BaseProvider
from app.providers.gemini_provider import GeminiProvider


def test_gemini_provider_implements_base_provider():
    provider = GeminiProvider(api_key="test-key")
    assert isinstance(provider, BaseProvider)


def test_generate_rejects_missing_api_key():
    provider = GeminiProvider(api_key="")

    async def run_test():
        with pytest.raises(ValueError, match="API key"):
            await provider.generate(
                model="gemini-2.5-flash",
                messages=[{"role": "user", "content": "Hello"}],
            )

    anyio.run(run_test)


def test_generate_rejects_empty_messages():
    provider = GeminiProvider(api_key="test-key")

    async def run_test():
        with pytest.raises(ValueError, match="Messages"):
            await provider.generate(
                model="gemini-2.5-flash",
                messages=[],
            )

    anyio.run(run_test)


def test_generate_rejects_invalid_temperature():
    provider = GeminiProvider(api_key="test-key")

    async def run_test():
        with pytest.raises(ValueError, match="Temperature"):
            await provider.generate(
                model="gemini-2.5-flash",
                messages=[{"role": "user", "content": "Hello"}],
                temperature=3,
            )

    anyio.run(run_test)


def test_generate_success(monkeypatch):
    import app.providers.gemini_provider as gemini_module

    provider = GeminiProvider(api_key="test-key")

    fake_response = SimpleNamespace(
        text="Hello from Gemini!",
        response_id="gemini-test-123",
        model_version="gemini-2.5-flash",
        usage_metadata=SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=6,
        ),
    )

    class FakeModels:
        async def generate_content(self, model, contents, config):
            assert model == "gemini-2.5-flash"
            assert contents == [
                {"role": "user", "parts": [{"text": "Hello"}]}
            ]
            assert config.temperature == 0.7
            return fake_response

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.models = FakeModels()

        @property
        def aio(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        gemini_module.genai,
        "Client",
        FakeClient,
    )

    async def run_test():
        result = await provider.generate(
            model="gemini-2.5-flash",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert result == {
            "provider": "gemini",
            "request_id": "gemini-test-123",
            "model": "gemini-2.5-flash",
            "content": "Hello from Gemini!",
            "input_tokens": 10,
            "output_tokens": 6,
            "total_tokens": 16,
        }

    anyio.run(run_test)


def test_generate_handles_api_error(monkeypatch):
    import app.providers.gemini_provider as gemini_module

    provider = GeminiProvider(api_key="test-key")

    class FakeModels:
        async def generate_content(self, **kwargs):
            raise ConnectionError("Simulated connection failure")

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

        @property
        def aio(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        gemini_module.genai,
        "Client",
        FakeClient,
    )

    async def run_test():
        with pytest.raises(RuntimeError, match="Gemini API request failed"):
            await provider.generate(
                model="gemini-2.5-flash",
                messages=[{"role": "user", "content": "Hello"}],
            )

    anyio.run(run_test)
