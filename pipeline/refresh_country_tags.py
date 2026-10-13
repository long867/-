"""Refresh country tags without changing original evidence or quotation offsets."""

import argparse
import asyncio
from collections import Counter

from sqlalchemy import func, select

from app.core.cache import invalidate_public_cache
from app.core.db import SessionFactory
from app.models import Article, Event
from pipeline.processors.entities import extract_regions


async def refresh(*, dry_run: bool = False) -> dict[str, int]:
    """Read at most fifty articles per batch and reconcile existing event tags."""
    counts: Counter[str] = Counter()
    after = None
    while True:
        async with SessionFactory.begin() as db:
            statement = select(Article).order_by(Article.id).limit(50)
            if after:
                statement = statement.where(Article.id > after)
            rows = (await db.scalars(statement)).all()
            if not rows:
                break
            for article in rows:
                counts["examined"] += 1
                # Price origin and curated legal jurisdiction are explicit provenance.
                if article.category == "price":
                    continue
                regions = extract_regions(article.title + "\n" + article.content)
                if country := article.raw_json.get("policy_country"):
                    regions = sorted(set(regions) | {country})
                if sorted(article.regions) != regions:
                    counts["changed"] += 1
                    if not dry_run:
                        article.regions = regions
            after = rows[-1].id
    if not dry_run:
        async with SessionFactory.begin() as db:
            grouped = (
                select(
                    Article.event_id.label("id"),
                    func.unnest(Article.regions).label("region"),
                )
                .where(Article.event_id.is_not(None), Article.status == "published")
                .subquery()
            )
            rows = (
                await db.execute(
                    select(
                        grouped.c.id, func.array_agg(func.distinct(grouped.c.region))
                    ).group_by(grouped.c.id)
                )
            ).all()
            for event_id, regions in rows:
                if event := await db.get(Event, event_id):
                    event.regions = sorted(regions)
        await invalidate_public_cache()
    return dict(counts)


def main() -> None:
    """Require an explicit command; dry-run reports counts without writing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(asyncio.run(refresh(dry_run=args.dry_run)))


if __name__ == "__main__":
    main()
