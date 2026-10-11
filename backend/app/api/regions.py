"""Region counts and filtered publication streams."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB
from app.models import Article
from app.schemas.api import ArticlePage
from app.schemas.intelligence import ArticleQuery, FacetOut
from app.services.article_service import list_articles, public_conditions
from app.services.trend_service import facets

router = APIRouter(tags=["regions"])


@router.get("/regions", response_model=list[FacetOut])
async def regions(db: DB) -> list[FacetOut]:
    return await facets(db, "regions")


@router.get("/regions/{name}/articles", response_model=ArticlePage)
async def articles(
    name: str, db: DB, query: Annotated[ArticleQuery, Query()]
) -> ArticlePage:
    return await list_articles(db, query.model_copy(update={"region": name}))


class ProjectLocation(BaseModel):
    name: str
    article_id: UUID
    title: str
    url: str
    latitude: float | None = None
    longitude: float | None = None


@router.get("/regions/{name}/projects", response_model=list[ProjectLocation])
async def projects(name: str, db: DB) -> list[ProjectLocation]:
    """Return extracted projects; coordinates must originate in source metadata."""
    rows = (
        await db.scalars(
            select(Article)
            .where(*public_conditions(), Article.regions.contains([name]))
            .order_by(Article.published_at.desc())
            .limit(500)
        )
    ).all()
    result: dict[str, ProjectLocation] = {}
    for article in rows:
        locations = (article.raw_json or {}).get("project_locations", [])
        locations = locations if isinstance(locations, list) else []
        for project in article.projects:
            if project in result:
                continue
            latitude = longitude = None
            for item in locations:
                if not isinstance(item, dict) or item.get("name") != project:
                    continue
                lat, lon = item.get("latitude"), item.get("longitude")
                if (
                    isinstance(lat, (int, float))
                    and not isinstance(lat, bool)
                    and isinstance(lon, (int, float))
                    and not isinstance(lon, bool)
                    and -90 <= lat <= 90
                    and -180 <= lon <= 180
                ):
                    latitude, longitude = float(lat), float(lon)
            result[project] = ProjectLocation(
                name=project,
                article_id=article.id,
                title=article.title_zh or article.title,
                url=article.url,
                latitude=latitude,
                longitude=longitude,
            )
    return list(result.values())[:100]
