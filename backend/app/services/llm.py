"""A small HTTP adapter for OpenAI-compatible model gateways."""

import hashlib
import json
from typing import Any

import httpx
from redis.asyncio import Redis
from redis.exceptions import LockError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from app.core.config import get_settings


class MalformedModelResponseError(ValueError):
    """A gateway response cannot be parsed as the requested JSON object."""


def transient_model_error(exc: BaseException) -> bool:
    """Retry gateway throttling/outages, never invalid credentials or payloads."""
    return isinstance(exc, (httpx.TransportError, MalformedModelResponseError)) or (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in {429, 502, 503, 504}
    )


@retry(
    retry=retry_if_exception(transient_model_error),
    wait=wait_random_exponential(multiplier=2, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def complete_json(system: str, prompt: str) -> dict[str, Any]:
    """Request structured output; callers validate it with their own schema."""
    settings = get_settings()
    if not settings.LLM_API_KEY.get_secret_value():
        raise RuntimeError("LLM_API_KEY is not configured")
    if settings.RATE_LIMIT_BACKEND == "redis":
        client = Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
        digest = hashlib.sha256(
            settings.LLM_API_KEY.get_secret_value().encode()
        ).hexdigest()[:24]
        lock = client.lock(
            "miningintel:llm:" + digest,
            timeout=settings.LLM_TIMEOUT + 30,
            blocking_timeout=settings.LLM_TIMEOUT,
            thread_local=False,
        )
        try:
            if not await lock.acquire():
                raise RuntimeError("Model concurrency slot is busy")
            return await request_json(system, prompt)
        finally:
            try:
                if await lock.owned():
                    await lock.release()
            except LockError:
                pass
            await client.aclose()
    return await request_json(system, prompt)


async def request_json(system: str, prompt: str) -> dict[str, Any]:
    """Perform one bounded gateway request; credentials never enter output logs."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        response = await client.post(
            f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY.get_secret_value()}"
            },
            json=settings.LLM_EXTRA_BODY
            | {
                "model": settings.LLM_MODEL,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        try:
            result = json.loads(response.json()["choices"][0]["message"]["content"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise MalformedModelResponseError(
                "Invalid structured model response"
            ) from exc
        if not isinstance(result, dict):
            raise MalformedModelResponseError("Model response must be a JSON object")
        # Some compatible gateways add one presentation envelope despite JSON
        # mode. Unwrap only these single-key objects; caller evidence/schema
        # validation still applies to every field and fact.
        for _ in range(2):
            if len(result) == 1:
                wrapped = result.get("answer", result.get("result"))
                if isinstance(wrapped, dict):
                    result = wrapped
                    continue
            break
        return result
