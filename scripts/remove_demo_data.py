"""Remove only the explicit MiningIntel synthetic seed namespace."""

import argparse
import asyncio

from sqlalchemy import Text, delete, func, select

from app.core.cache import invalidate_public_cache
from app.core.config import get_settings
from app.core.db import SessionFactory
from app.models import Article, Event, Policy, PriceRecord, Report, Source
from app.services.article_service import DEMO_PREFIX


async def remove_demo(*, dry_run: bool = False) -> dict[str, int]:
    """Preserve real source articles and users; delete only known synthetic data."""
    if get_settings().APP_ENV == "production":
        raise ValueError("Synthetic preview cleanup is restricted to development")
    async with SessionFactory.begin() as db:
        sources = select(Source.id).where(Source.url.startswith(DEMO_PREFIX))
        articles = (
            await db.scalars(select(Article).where(Article.source_id.in_(sources)))
        ).all()
        event_ids = {item.event_id for item in articles if item.event_id}
        predicates = {
            "policies": (Policy, Policy.url.startswith(DEMO_PREFIX)),
            "prices": (PriceRecord, PriceRecord.source.startswith(DEMO_PREFIX)),
            "reports": (Report, Report.sources_json.cast(Text).contains(DEMO_PREFIX)),
        }
        counts = {
            "articles": len(articles),
            "sources": await db.scalar(
                select(func.count())
                .select_from(Source)
                .where(Source.url.startswith(DEMO_PREFIX))
            ),
        }
        for name, (model, condition) in predicates.items():
            counts[name] = await db.scalar(
                select(func.count()).select_from(model).where(condition)
            )
            if not dry_run:
                await db.execute(delete(model).where(condition))
        if not dry_run:
            await db.execute(delete(Article).where(Article.source_id.in_(sources)))
            for event_id in event_ids:
                remaining = await db.scalar(
                    select(func.count())
                    .select_from(Article)
                    .where(Article.event_id == event_id)
                )
                event = await db.get(Event, event_id)
                if event and not remaining:
                    await db.delete(event)
                elif event:
                    event.article_count = remaining
            await db.execute(delete(Source).where(Source.url.startswith(DEMO_PREFIX)))
    if not dry_run:
        await invalidate_public_cache()
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    print(asyncio.run(remove_demo(dry_run=parser.parse_args().dry_run)))
