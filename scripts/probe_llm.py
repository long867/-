"""Check structured model access without printing keys or request headers."""

import asyncio

import httpx

from app.core.config import get_settings
from app.services.llm import complete_json


async def main() -> None:
    try:
        result = await complete_json(
            "只返回JSON对象，不要解释。", '返回{"status":"ok"}'
        )
        print({"model": get_settings().LLM_MODEL, "result": result})
    except httpx.HTTPStatusError as exc:
        error = exc.response.json().get("error", {})
        print(
            {
                "status": exc.response.status_code,
                "error_code": error.get("code"),
                "message": str(error.get("message", "")).replace(
                    get_settings().LLM_API_KEY.get_secret_value(), "[REDACTED]"
                ),
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
