"""FastAPI entry point with CORS, structured errors and Prometheus metrics."""

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from threading import Lock
from uuid import uuid4

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api.api_keys import router as api_keys_router
from app.api.business import open_router
from app.api.business import router as business_router
from app.api.chat import router as chat_router
from app.api.notifications import router as notifications_router
from app.api.operations import router as operations_router
from app.api.research import router as research_router
from app.api.routes import router
from app.api.subscriptions import router as subscriptions_router
from app.core.config import get_settings
from app.core.db import SessionFactory, engine
from app.core.logging import configure_logging
from app.core.observability import database_metrics
from app.core.rate_limit import build_rate_limit_guard, client_route_key
from app.core.task_history import record_http

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = structlog.get_logger()
REQUESTS = Counter(
    "miningintel_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
LATENCY = Histogram("miningintel_http_duration_seconds", "Request latency", ["route"])
_local_windows: dict[str, tuple[int, int]] = {}
_local_lock = Lock()


def memory_limited(client_ip: str, group: str, now: float) -> bool:
    """Bounded single-process development limiter; production requires Redis."""
    window = int(now // 60)
    key = client_ip + ":" + group
    with _local_lock:
        for expired in [
            item for item, (stamp, _) in _local_windows.items() if stamp < window
        ]:
            del _local_windows[expired]
        stamp, count = _local_windows.get(key, (window, 0))
        count = count + 1 if stamp == window else 1
        if key not in _local_windows and len(_local_windows) >= 10000:
            return True
        _local_windows[key] = (window, count)
    return count > 10


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create shared Redis clients and close infrastructure on shutdown."""
    application.state.redis = Redis.from_url(
        settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2
    )
    yield
    await application.state.redis.aclose()
    await engine.dispose()


limiter = Limiter(
    key_func=client_route_key,
    storage_uri=settings.REDIS_URL
    if settings.RATE_LIMIT_BACKEND == "redis"
    else "memory://",
    storage_options={"socket_connect_timeout": 1, "socket_timeout": 1}
    if settings.RATE_LIMIT_BACKEND == "redis"
    else {},
)
app = FastAPI(
    title="MiningIntel API",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(build_rate_limit_guard(limiter, settings.API_RATE_LIMIT))],
)
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"],
    expose_headers=["X-Cache", "X-Cache-TTL", "X-Request-ID", "Retry-After"],
)
app.include_router(router)
app.include_router(business_router)
app.include_router(open_router)
app.include_router(api_keys_router)
app.include_router(subscriptions_router)
app.include_router(notifications_router)
app.include_router(operations_router)
app.include_router(research_router)
app.include_router(chat_router, prefix="/api/chat")
app.include_router(chat_router, prefix="/api/v1/chat")


def public_openapi() -> dict:
    """Document optional website credentials and required open API credentials."""
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        for path, operations in schema["paths"].items():
            if path.startswith("/api/") and not path.startswith("/api/open/"):
                for operation in operations.values():
                    if isinstance(operation, dict) and operation.get("security") == [
                        {"MiningIntelAPIKey": []}
                    ]:
                        operation["security"].append({})
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = public_openapi


def metric_route(path: str, template: str) -> str:
    """Restore nested-router prefixes without including raw IDs in metric labels."""
    if template == "/api" or template.startswith("/api/"):
        return template
    for prefix in ("/api/v1/chat", "/api/chat", "/api/v1", "/api/open", "/api"):
        if path == prefix or path.startswith(prefix + "/"):
            if not template:
                return prefix
            return prefix + (template if template.startswith("/") else "/unmatched")
    return template


@app.exception_handler(RateLimitExceeded)
async def rate_limit_error(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Expose consistent global API throttling without echoing credentials."""
    return JSONResponse(
        {
            "detail": "请求过于频繁，请稍后重试",
            "request_id": getattr(request.state, "request_id", None),
        },
        status_code=429,
        headers={"Retry-After": "60"},
    )


async def limited(request: Request) -> bool:
    """Apply an atomic fixed-window limit to login and model-consuming requests."""
    path = request.url.path
    if request.method != "POST" or not (
        path.startswith("/api/v1/auth/")
        or path
        in {
            "/api/chat",
            "/api/chat/stream",
            "/api/v1/chat",
            "/api/v1/chat/stream",
            "/api/research",
        }
    ):
        return False
    client_ip = request.client.host if request.client else "unknown"
    group = (
        "research" if path == "/api/research" else "chat" if "/chat" in path else "auth"
    )
    if settings.RATE_LIMIT_BACKEND == "memory":
        return memory_limited(client_ip, group, time.time())
    key = f"rate:{client_ip}:{group}:{int(time.time() // 60)}"
    script = (
        "local n=redis.call('INCR',KEYS[1]); "
        "if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n"
    )
    try:
        count = await request.app.state.redis.eval(script, 1, key)
    except Exception as exc:
        raise HTTPException(503, "登录和咨询服务暂时不可用") from exc
    return count > 10


@app.middleware("http")
async def observe(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Correlate errors and record low-cardinality route metrics."""
    request_id = str(uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        if await limited(request):
            response = JSONResponse(
                {"detail": "请求过于频繁，请稍后重试", "request_id": request_id},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        else:
            response = await call_next(request)
    except HTTPException as exc:
        response = JSONResponse(
            {"detail": exc.detail, "request_id": request_id},
            status_code=exc.status_code,
        )
    except RedisError:
        response = JSONResponse(
            {"detail": "限流服务暂时不可用", "request_id": request_id}, status_code=503
        )
    except Exception as exc:
        logger.error("unhandled_error", error_type=type(exc).__name__)
        response = JSONResponse(
            {"detail": "服务内部错误", "request_id": request_id}, status_code=500
        )
    route = getattr(request.scope.get("route"), "path", "unmatched")
    route = metric_route(request.url.path, route)
    REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    LATENCY.labels(route).observe(time.perf_counter() - start)
    if route.startswith("/api/"):
        await asyncio.to_thread(
            record_http, response.status_code, time.perf_counter() - start
        )
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed",
        method=request.method,
        route=route,
        status=response.status_code,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return field locations without echoing passwords or raw input."""
    return JSONResponse(
        {
            "detail": [
                {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                for error in exc.errors()
            ],
            "request_id": request.state.request_id,
        },
        status_code=422,
    )


@app.exception_handler(IntegrityError)
async def conflict(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        {"detail": "记录已存在或违反数据约束", "request_id": request.state.request_id},
        status_code=409,
    )


@app.exception_handler(OperationalError)
async def unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    return JSONResponse(
        {"detail": "数据库暂时不可用", "request_id": request.state.request_id},
        status_code=503,
    )


@app.get("/health/live", tags=["health"])
async def live() -> dict:
    """Process liveness is independent of external infrastructure."""
    return {
        "status": "ok",
        "service": "miningintel",
        "version": "0.1.0",
        "retrieval_mode": "hybrid" if settings.ML_ENABLED else "keyword",
    }


@app.get("/health/ready", tags=["health"])
async def ready(request: Request) -> JSONResponse:
    """Readiness requires both a migrated database and a working Redis instance."""
    try:
        async with SessionFactory() as db:
            await db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        await request.app.state.redis.ping()
        return JSONResponse({"status": "ready"})
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Include durable gauges so freshness alerts survive worker restarts."""
    return Response(
        generate_latest() + await database_metrics(), media_type=CONTENT_TYPE_LATEST
    )
