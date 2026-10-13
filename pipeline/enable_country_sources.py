"""Register verified country-monitor feeds without changing existing source switches."""

import asyncio

from sqlalchemy import select

from app.core.cache import invalidate_public_cache
from app.core.db import SessionFactory
from app.models import Source
from pipeline.config.catalog import load_sources, sync_sources


async def enable_new_sources() -> dict[str, int]:
    """Enable only newly inserted verified feeds; retain administrator overrides."""
    definitions = [
        row
        for row in load_sources()
        if row.active
        and str(row.parser_config.get("verification", "")).startswith(
            "public_country_feed_"
        )
    ]
    async with SessionFactory.begin() as db:
        existing = set(
            (
                await db.scalars(
                    select(Source.url).where(
                        Source.url.in_([row.url for row in definitions])
                    )
                )
            ).all()
        )
        await sync_sources(db, definitions)
    await invalidate_public_cache()
    return {
        "verified_country_feeds": len(definitions),
        "newly_enabled": sum(row.url not in existing for row in definitions),
    }


def main() -> None:
    """Run a small, idempotent post-release source registration."""
    print(asyncio.run(enable_new_sources()))


if __name__ == "__main__":
    main()
