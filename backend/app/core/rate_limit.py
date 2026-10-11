"""SlowAPI guards run after routing, including lazily included FastAPI routers."""

from collections.abc import Callable

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address


def client_route_key(request: Request) -> str:
    """Count one client and route template; varying IDs cannot evade the limit."""
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    return f"{get_remote_address(request)}:{request.method}:{path}"


def build_rate_limit_guard(limiter: Limiter, limit: str) -> Callable:
    """Use SlowAPI's public decorator through a global FastAPI dependency.

    Older SlowAPI middleware only detects flat routes and skips newer FastAPI
    included routers. Dependencies execute after endpoint resolution, so this
    guard applies to both old and new router representations.
    """

    @limiter.shared_limit(limit, scope="api")
    def guard(request: Request, response: Response) -> None:
        """The decorator checks the shared store before the endpoint executes."""

    return guard
