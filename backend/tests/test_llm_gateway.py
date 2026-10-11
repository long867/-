"""Model presentation envelopes do not bypass caller evidence validation."""

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
