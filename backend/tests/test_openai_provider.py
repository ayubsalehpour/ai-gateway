
import anyio
import pytest

from app.providers.openai_provider import OpenAIProvider


def test_generate_rejects_missing_api_key():
    provider = OpenAIProvider(api_key="")

    async def run_test():
        with pytest.raises(ValueError, match="API key"):
            await provider.generate(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
            )

    anyio.run(run_test)


def test_generate_success(monkeypatch):
    provider = OpenAIProvider(api_key="test-key")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "id": "chatcmpl_test123",
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "message": {
                            "content": "Hello!",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, headers, json):
            assert url.endswith("/chat/completions")
            assert headers["Authorization"] == "Bearer test-key"
            assert json["model"] == "gpt-4o-mini"
            return FakeResponse()

    monkeypatch.setattr(
        "app.providers.openai_provider.httpx.AsyncClient",
        FakeClient,
    )

    async def run_test():
        result = await provider.generate(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert result["provider"] == "openai"
        assert result["request_id"] == "chatcmpl_test123"
        assert result["model"] == "gpt-4o-mini"
        assert result["content"] == "Hello!"
        assert result["input_tokens"] == 10
        assert result["output_tokens"] == 5
        assert result["total_tokens"] == 15

    anyio.run(run_test)


def test_generate_rejects_empty_messages():
    provider = OpenAIProvider(api_key="test-key")

    async def run_test():
        with pytest.raises(ValueError, match="Messages"):
            await provider.generate(
                model="gpt-4o-mini",
                messages=[],
            )

    anyio.run(run_test)


def test_generate_rejects_empty_model():
    provider = OpenAIProvider(api_key="test-key")

    async def run_test():
        with pytest.raises(ValueError, match="Model"):
            await provider.generate(
                model=" ",
                messages=[{"role": "user", "content": "Hello"}],
            )

    anyio.run(run_test)




def test_generate_rejects_invalid_temperature():
    provider = OpenAIProvider(api_key="test-key")

    async def run_test():
        with pytest.raises(ValueError, match="Temperature"):
            await provider.generate(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
                temperature=3,
            )

    anyio.run(run_test)


def test_generate_rejects_invalid_message_content():
    provider = OpenAIProvider(api_key="test-key")

    async def run_test():
        with pytest.raises(ValueError, match="content"):
            await provider.generate(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": 123}],
            )

    anyio.run(run_test)


def test_generate_handles_http_status_error(monkeypatch):
    import httpx

    provider = OpenAIProvider(api_key="test-key")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, headers, json):
            request = httpx.Request("POST", url)
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError(
                "Unauthorized",
                request=request,
                response=response,
            )

    monkeypatch.setattr(
        "app.providers.openai_provider.httpx.AsyncClient",
        FakeClient,
    )

    async def run_test():
        with pytest.raises(RuntimeError, match="HTTP status 401"):
            await provider.generate(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
            )

    anyio.run(run_test)


def test_generate_rejects_missing_usage(monkeypatch):
    provider = OpenAIProvider(api_key="test-key")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "id": "chatcmpl_test123",
                "model": "gpt-4o-mini",
                "choices": [
                    {"message": {"content": "Hello!"}}
                ],
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, headers, json):
            return FakeResponse()

    monkeypatch.setattr(
        "app.providers.openai_provider.httpx.AsyncClient",
        FakeClient,
    )

    async def run_test():
        with pytest.raises(RuntimeError, match="Invalid response"):
            await provider.generate(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
            )

    anyio.run(run_test)
