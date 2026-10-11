"""Assemble the public website API and key-protected open API from shared routes."""

from fastapi import APIRouter, Depends

from app.api import (
    articles,
    digest,
    events,
    minerals,
    policies,
    regions,
    search,
    trends,
)
from app.api.api_keys import optional_api_key, required_api_key

router = APIRouter(prefix="/api", dependencies=[Depends(optional_api_key)])
open_router = APIRouter(prefix="/api/open", dependencies=[Depends(required_api_key)])
for module in (articles, events, minerals, regions, policies, digest, trends, search):
    router.include_router(module.router)
    open_router.include_router(module.router)
