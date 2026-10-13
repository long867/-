"""A small HTTP adapter for OpenAI-compatible model gateways."""

import asyncio
import hashlib
import json
import time
from typing import Any, Literal
from uuid import uuid4

import httpx
from redis.asyncio import Redis
from redis.exceptions import LockError, RedisError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from app.core.config import get_settings


class MalformedModelResponseError(ValueError):
    """A gateway response cannot be parsed as the requested JSON object."""


class ModelConcurrencyBusyError(RuntimeError):
    """The shared gateway slot is temporarily occupied, not a bad article."""


def transient_model_error(exc: BaseException) -> bool:
    """Retry gateway throttling/outages, never invalid credentials or payloads."""
    return isinstance(
        exc,
        (httpx.TransportError, MalformedModelResponseError, ModelConcurrencyBusyError),
    ) or (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in {429, 502, 503, 504}
    )


@retry(
    retry=retry_if_exception(transient_model_error),
    wait=wait_random_exponential(multiplier=2, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def complete_json(
    system: str, prompt: str, *, profile: Literal["default", "chat"] = "default"
) -> dict[str, Any]:
    """Request structured output; callers validate it with their own schema."""
    settings = get_settings()
    if not settings.LLM_API_KEY.get_secret_value():
        raise RuntimeError("LLM_API_KEY is not configured")
    if settings.RATE_LIMIT_BACKEND == "redis":
        timeout = (
            settings.CHAT_LLM_TIMEOUT if profile == "chat" else settings.LLM_TIMEOUT
        )
        client = Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
        digest = hashlib.sha256(
            settings.LLM_API_KEY.get_secret_value().encode()
        ).hexdigest()[:24]
        lock = client.lock(
            "miningintel:llm:" + digest,
            timeout=timeout + 30,
            thread_local=False,
        )
        waiters = "miningintel:llm:interactive:" + digest
        token = str(uuid4()) if profile == "chat" else None
        try:
            if token:
                await client.zadd(waiters, {token: time.time() + timeout * 2 + 30})
                await client.expire(waiters, int(timeout * 2 + 90))
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                pending = (
                    0 if token else await client.zcount(waiters, time.time(), "+inf")
                )
                if not pending and await lock.acquire(blocking=False):
                    break
                await asyncio.sleep(0.1)
            else:
                raise ModelConcurrencyBusyError("Model concurrency slot is busy")
            return await request_json(system, prompt, profile=profile)
        finally:
            try:
                if await lock.owned():
                    await lock.release()
                if token:
                    await client.zrem(waiters, token)
            except (LockError, RedisError):
                pass
            await client.aclose()
    return await request_json(system, prompt, profile=profile)


async def request_json(
    system: str, prompt: str, *, profile: Literal["default", "chat"] = "default"
) -> dict[str, Any]:
    """Perform one bounded gateway request; credentials never enter output logs."""
    settings = get_settings()
    chat = profile == "chat"
    extra = settings.LLM_EXTRA_BODY | (settings.CHAT_LLM_EXTRA_BODY if chat else {})
    timeout = settings.CHAT_LLM_TIMEOUT if chat else settings.LLM_TIMEOUT
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY.get_secret_value()}"
            },
            json=extra
            | {
                "model": settings.CHAT_LLM_MODEL or settings.LLM_MODEL
                if chat
                else settings.LLM_MODEL,
                "temperature": 0.2 if chat else 0,
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
