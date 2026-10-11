"""Review and publish only existing quotes from the verified public PPI adapter."""

import asyncio

from sqlalchemy import select

from app.core.cache import invalidate_public_cache
from app.core.db import SessionFactory
from app.models import Article, Source
from app.rag.indexer import enqueue_sync
from app.tasks.ingest import process_one


async def main() -> None:
    """Reapply deterministic numeric validation before making price cards public."""
    async with SessionFactory() as db:
        ids = (
            await db.scalars(
                select(Article.id)
                .join(Source)
                .where(
                    Source.name == "生意社碳酸锂公开现货价格",
                    Source.config_json["adapter"].astext == "ppi_lithium_spot",
                    Article.category == "price",
                    Article.status != "published",
                )
            )
        ).all()
    for article_id in ids:
        async with SessionFactory.begin() as db:
            item = await db.get(Article, article_id, with_for_update=True)
            item.status = "pending"
        result = await process_one(article_id)
        if result["status"] != "processed":
            continue
        async with SessionFactory.begin() as db:
            item = await db.get(Article, article_id, with_for_update=True)
            if (
                not item.title_zh
                or not 100 <= len(item.summary_zh or "") <= 200
                or item.minerals != ["锂"]
            ):
                raise ValueError("Unverified price article cannot be published")
            item.status = "published"
            item.indexed_at = None
            await enqueue_sync(db, item)
    await invalidate_public_cache()
    print({"reviewed_real_price_articles": len(ids)})


if __name__ == "__main__":
    asyncio.run(main())
