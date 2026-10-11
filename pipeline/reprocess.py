"""Backfill articles collected before an LLM was configured, without refetching."""

import argparse
import asyncio
import json
from uuid import UUID

import httpx
import structlog
from app.core.config import get_settings
from app.core.db import SessionFactory
from app.models import Article, Source
from app.tasks.ingest import process_one
from sqlalchemy import and_, or_, select

logger = structlog.get_logger()


def needs_processing(article: Article) -> bool:
    """Never reopen reviewed articles or already translated processed articles."""
    return article.status == "pending" or (
        article.status == "processed"
        and not article.language.lower().startswith("zh")
        and not article.is_translated
    )


async def run(
    *,
    source: str | None = None,
    article_id: UUID | None = None,
    limit: int = 20,
    dry_run: bool = False,
) -> dict:
    """Resume bounded unpublished work and preserve raw evidence on failures."""
    if not dry_run and not get_settings().LLM_API_KEY.get_secret_value():
        raise ValueError("Configure LLM_API_KEY before reprocessing translations")
    query = (
        select(Article.id)
        .join(Source)
        .where(
            or_(
                Article.status == "pending",
                and_(
                    Article.status == "processed",
                    Article.is_translated.is_(False),
                    ~Article.language.ilike("zh%"),
                ),
            )
        )
        .order_by(Article.fetched_at, Article.id)
        .limit(limit)
    )
    if source:
        query = query.where(Source.name == source)
    if article_id:
        query = query.where(Article.id == article_id)
    async with SessionFactory() as db:
        ids = list((await db.scalars(query)).all())
    result = {
        "candidates": len(ids),
        "processed": 0,
        "errors": 0,
        "skipped": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        return result | {"article_ids": list(map(str, ids))}
    for selected in ids:
        async with SessionFactory.begin() as db:
            article = await db.get(Article, selected, with_for_update=True)
            if article is None or not needs_processing(article):
                result["skipped"] += 1
                continue
            article.status = "pending"
        try:
            processed = await process_one(selected)
            key = (
                "processed"
                if processed["status"] in {"processed", "published"}
                else "skipped"
            )
            result[key] += 1
        except Exception as exc:
            result["errors"] += 1
            async with SessionFactory.begin() as db:
                article = await db.get(Article, selected)
                if article is not None and article.status == "pending":
                    article.processing_error = type(exc).__name__
            logger.warning(
                "reprocessing_failed",
                article_id=str(selected),
                error_type=type(exc).__name__,
                validation_reason=str(exc)[:500]
                if isinstance(exc, ValueError)
                else None,
                model_status=exc.response.status_code
                if isinstance(exc, httpx.HTTPStatusError)
                else None,
                model_error_code=exc.response.json().get("error", {}).get("code")
                if isinstance(exc, httpx.HTTPStatusError)
                and exc.response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else None,
            )
    return result


def main() -> None:
    """Expose a bounded, review-preserving backfill and a read-only preview."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Exact existing source name")
    parser.add_argument("--article-id", type=UUID)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    result = asyncio.run(
        run(
            source=args.source,
            article_id=args.article_id,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
