"""Stage original public evidence for durable processing, never raw publication."""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.db import SessionFactory
from app.models import Article, Source
from pipeline.fetchers.http import canonical_url
from pipeline.processors.dedup import normalize_title, normalize_url, simhash
from pipeline.processors.entities import extract_entities
from pipeline.schemas import RawArticle, SourceDefinition


async def seed_record(value: dict) -> str:
    """Persist a canonical original as pending; publication requires NLP validation."""
    definition = SourceDefinition.model_validate(value["source"])
    raw = RawArticle.model_validate(value["article"])
    if raw.source_name != definition.name:
        raise ValueError("Publisher does not match original evidence")
    if (
        len(raw.content) < 160
        or not extract_entities(raw.title + "\n" + raw.content)["minerals"]
    ):
        return "unrelated"
    url = canonical_url(normalize_url(raw.url))
    async with SessionFactory.begin() as db:
        if await db.scalar(select(Article.id).where(Article.url == url)):
            return "duplicate"
        source = await db.scalar(select(Source).where(Source.url == definition.url))
        if source is None:
            config = dict(definition.parser_config)
            config.pop("pagination", None)
            config.pop("emit_progress", None)
            config["max_items"] = min(40, int(config.get("max_items", 10)))
            source = Source(
                **definition.model_dump(exclude={"parser_config", "active"}),
                active=False,
                config_json=config,
            )
            db.add(source)
            await db.flush()
        fingerprint = simhash(raw.content)
        if await db.scalar(
            select(Article.id).where(Article.content_fingerprint == fingerprint)
        ):
            return "duplicate"
        metadata = {k: v for k, v in raw.raw_json.items() if k != "feed_summary"}
        article_id = await db.scalar(
            insert(Article)
            .values(
                source_id=source.id,
                title=raw.title,
                content=raw.content[:100000],
                url=url,
                published_at=raw.published_at,
                language=raw.language,
                category=raw.category,
                raw_json=metadata
                | {
                    "backfill": True,
                    "initialization_requested": True,
                    "collection_source_url": definition.url,
                },
                content_fingerprint=fingerprint,
                title_normalized=normalize_title(raw.title),
                status="pending",
            )
            .on_conflict_do_nothing(index_elements=[Article.url])
            .returning(Article.id)
        )
        return "pending" if article_id else "duplicate"


async def run(path: Path) -> dict:
    """Stream a bounded archive; queued work survives worker and host restarts."""
    counts = Counter()
    with path.open(encoding="utf-8") as source:
        for index, line in enumerate(source, 1):
            if not line.strip():
                continue
            counts[await seed_record(json.loads(line))] += 1
            if index % 100 == 0:
                print(
                    json.dumps({"examined": index, "outcomes": dict(counts)}),
                    flush=True,
                )
    print(json.dumps({"finished": True, "outcomes": dict(counts)}), flush=True)
    return dict(counts)


def main() -> None:
    """Load staged originals; Beat dispatches only a bounded number at a time."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    asyncio.run(run(parser.parse_args().input))


if __name__ == "__main__":
    main()
