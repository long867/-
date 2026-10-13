"""Model presentation envelopes do not bypass caller evidence validation."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.core.config import Settings
from app.services.llm import MalformedModelResponseError, request_json


@pytest.mark.parametrize("wrapper", ["answer", "result"])
@respx.mock
async def test_structured_gateway_unwraps_only_single_key_object(wrapper, monkeypatch):
    import app.services.llm as module

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: Settings(
            LLM_BASE_URL="https://model.example.test/v1",
            LLM_API_KEY="fixture",
            _env_file=None,
        ),
    )
    respx.post("https://model.example.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"'
                            + wrapper
                            + '": {"content_zh": "铜矿中文译文。"}}'
                        }
                    }
                ]
            },
        )
    )
    assert await request_json("JSON", "资料") == {"content_zh": "铜矿中文译文。"}


@respx.mock
async def test_scalar_model_response_remains_invalid(monkeypatch):
    import app.services.llm as module

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: Settings(
            LLM_BASE_URL="https://model.example.test/v1",
            LLM_API_KEY="fixture",
            _env_file=None,
        ),
    )
    respx.post("https://model.example.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": '"not an object"'}}]}
        )
    )
    with pytest.raises(MalformedModelResponseError):
        await request_json("JSON", "资料")


@respx.mock
async def test_dedicated_chat_model_does_not_change_background_translation(monkeypatch):
    import app.services.llm as module

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: Settings(
            LLM_BASE_URL="https://model.example.test/v1",
            LLM_API_KEY="fixture",
            LLM_MODEL="translation-model",
            CHAT_LLM_MODEL="advanced-chat",
            CHAT_LLM_EXTRA_BODY={"thinking": {"type": "disabled"}, "max_tokens": 4096},
            _env_file=None,
        ),
    )
    route = respx.post("https://model.example.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": '{"blocks":[]}'}}]}
        )
    )
    await request_json("JSON", "资料")
    background = json.loads(route.calls[-1].request.content)
    await request_json("JSON", "提问", profile="chat")
    chat = json.loads(route.calls[-1].request.content)
    assert background["model"] == "translation-model" and "thinking" not in background
    assert chat["model"] == "advanced-chat" and chat["max_tokens"] == 4096
    assert chat["thinking"] == {"type": "disabled"}
    assert chat["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("profile", ["default", "chat"])
async def test_waiting_chat_has_priority_and_waiter_is_cleaned_up(profile, monkeypatch):
    import app.services.llm as module

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: Settings(
            LLM_API_KEY="fixture",
            RATE_LIMIT_BACKEND="redis",
            _env_file=None,
        ),
    )
    lock = SimpleNamespace(
        acquire=AsyncMock(return_value=True),
        owned=AsyncMock(return_value=True),
        release=AsyncMock(),
    )
    redis_client = SimpleNamespace(
        lock=lambda *_args, **_kwargs: lock,
        zadd=AsyncMock(),
        expire=AsyncMock(),
        zrem=AsyncMock(),
        zcount=AsyncMock(side_effect=[1, 0]),
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(
        module.Redis, "from_url", lambda *_args, **_kwargs: redis_client
    )
    sleep = AsyncMock()
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    request = AsyncMock(return_value={"blocks": []})
    monkeypatch.setattr(module, "request_json", request)
    await module.complete_json("JSON", "问题", profile=profile)
    if profile == "default":
        assert redis_client.zcount.await_count == 2
        sleep.assert_awaited_once()
        redis_client.zadd.assert_not_awaited()
    else:
        redis_client.zadd.assert_awaited_once()
        redis_client.zrem.assert_awaited_once()
        redis_client.zcount.assert_not_awaited()
    lock.acquire.assert_awaited_once_with(blocking=False)
    lock.release.assert_awaited_once()
    redis_client.aclose.assert_awaited_once()
