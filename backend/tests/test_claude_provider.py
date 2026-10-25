
import anyio
import pytest

from app.providers.base import BaseProvider
from app.providers.claude_provider import ClaudeProvider


def test_claude_provider_implements_base_provider():
    provider = ClaudeProvider(api_key="test-key")
    assert isinstance(provider, BaseProvider)


def test_generate_rejects_missing_api_key():
    provider = ClaudeProvider(api_key="")

    async def run_test():
        with pytest.raises(ValueError, match="API key"):
            await provider.generate(
                model="claude-sonnet-4-5",
                messages=[{"role": "user", "content": "Hello"}],
            )

    anyio.run(run_test)


def test_generate_rejects_empty_messages():
    provider = ClaudeProvider(api_key="test-key")

    async def run_test():
        with pytest.raises(ValueError, match="Messages"):
            await provider.generate(
                model="claude-sonnet-4-5",
                messages=[],
            )

    anyio.run(run_test)


def test_generate_rejects_invalid_temperature():
    provider = ClaudeProvider(api_key="test-key")

    async def run_test():
        with pytest.raises(ValueError, match="Temperature"):
            await provider.generate(
                model="claude-sonnet-4-5",
                messages=[{"role": "user", "content": "Hello"}],
                temperature=2,
            )

    anyio.run(run_test)




def test_generate_success(monkeypatch):
    from types import SimpleNamespace

    import app.providers.claude_provider as claude_module

    provider = ClaudeProvider(api_key="test-key")

    fake_response = SimpleNamespace(
        id="msg_test123",
        model="claude-sonnet-4-5",
        content=[
            SimpleNamespace(type="text", text="Hello "),
            SimpleNamespace(type="text", text="from Claude!"),
        ],
        usage=SimpleNamespace(
            input_tokens=12,
            output_tokens=7,
        ),
    )

    class FakeMessages:
        async def create(self, **kwargs):
            assert kwargs["model"] == "claude-sonnet-4-5"
            assert kwargs["max_tokens"] == 1024
            assert kwargs["temperature"] == 0.7
            assert kwargs["messages"] == [
                {"role": "user", "content": "Hello"}
            ]
            assert kwargs["system"] == "Be concise."
            return fake_response

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "test-key"
            self.messages = FakeMessages()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        claude_module.anthropic,
        "AsyncAnthropic",
        FakeClient,
    )

    async def run_test():
        result = await provider.generate(
            model="claude-sonnet-4-5",
            messages=[
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Hello"},
            ],
        )

        assert result == {
            "provider": "anthropic",
            "request_id": "msg_test123",
            "model": "claude-sonnet-4-5",
            "content": "Hello from Claude!",
            "input_tokens": 12,
            "output_tokens": 7,
            "total_tokens": 19,
        }

    anyio.run(run_test)




def test_generate_handles_http_status_error(monkeypatch):
    import anthropic

    import app.providers.claude_provider as claude_module

    provider = ClaudeProvider(api_key="test-key")

    class FakeMessages:
        async def create(self, **kwargs):
            raise anthropic.APIStatusError(
                message="Unauthorized",
                response=__import__("httpx").Response(
                    401,
                    request=__import__("httpx").Request(
                        "POST", "https://api.anthropic.com/v1/messages"
                    ),
                ),
                body={"error": {"message": "Unauthorized"}},
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        claude_module.anthropic,
        "AsyncAnthropic",
        FakeClient,
    )

    async def run_test():
        with pytest.raises(RuntimeError, match="HTTP status 401"):
            await provider.generate(
                model="claude-sonnet-4-5",
                messages=[{"role": "user", "content": "Hello"}],
            )

    anyio.run(run_test)


def test_generate_rejects_invalid_token_usage(monkeypatch):
    from types import SimpleNamespace

    import app.providers.claude_provider as claude_module

    provider = ClaudeProvider(api_key="test-key")

    fake_response = SimpleNamespace(
        id="msg_test123",
        model="claude-sonnet-4-5",
        content=[SimpleNamespace(type="text", text="Hello")],
        usage=SimpleNamespace(input_tokens=-1, output_tokens=7),
    )

    class FakeMessages:
        async def create(self, **kwargs):
            return fake_response

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        claude_module.anthropic,
        "AsyncAnthropic",
        FakeClient,
    )

    async def run_test():
        with pytest.raises(RuntimeError, match="Invalid token usage"):
            await provider.generate(
                model="claude-sonnet-4-5",
                messages=[{"role": "user", "content": "Hello"}],
            )

    anyio.run(run_test)
