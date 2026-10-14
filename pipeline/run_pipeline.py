"""Run catalog collection locally or dispatch independent Celery source tasks."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

# IDEs may execute this file directly instead of using Python's module mode.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.logging import configure_logging
from app.models import Source
from app.tasks.ingest import fetch_source, ingest_source, process_one
from pipeline.config.catalog import DEFAULT_CATALOG, load_sources, sync_sources
from pipeline.fetchers.collect import create_fetcher
from pipeline.processors.dedup import normalize_url
from pipeline.processors.enrich import enrich, llm_available
from pipeline.schemas import SourceDefinition

logger = structlog.get_logger()


async def dry_run(source: SourceDefinition) -> dict:
    """Exercise collection and enrichment without connecting to a database."""
    fetcher = create_fetcher(source)
    rows = await fetcher.fetch()
    seen: set[str] = set()
    output: list[dict] = []
    errors = len(fetcher.result.errors)
    for row in rows:
        url = row.url if row.raw_json.get("snapshot_digest") else normalize_url(row.url)
        if url in seen:
            continue
        seen.add(url)
        try:
            values = await enrich(
                row.title,
                row.content,
                row.language,
                source.authority_score,
                published_at=row.published_at,
                category=row.category,
                source=source,
                url=row.url,
                metadata=row.raw_json,
            )
            output.append(row.model_dump(mode="json") | values)
        except Exception as exc:
            errors += 1
            logger.error(
                "dry_run_processing_failed",
                source=source.name,
                error_type=type(exc).__name__,
            )
    logger.info(
        "source_run_complete",
        source=source.name,
        dry_run=True,
        fetched=len(rows),
        new=0,
        candidates=len(output),
        duplicates=len(rows) - len(seen),
        errors=errors,
        llm_enabled=llm_available(),
    )
    return {
        "source": source.name,
        "fetched": len(rows),
        "errors": errors,
        "articles": output,
        "prices": fetcher.result.prices,
    }


async def run(args: argparse.Namespace) -> list[dict]:
    """Choose exact source names and keep every source failure isolated."""
    catalog = load_sources(args.config)
    selected = [s for s in catalog if s.active or args.include_inactive]
    if args.source:
        selected = [s for s in catalog if s.name.casefold() == args.source.casefold()]
        if not selected:
            raise ValueError("Unknown source name; use --list-sources")
        if not selected[0].active and not args.include_inactive:
            raise ValueError(
                "Source disabled; review access/configuration before --include-inactive"
            )
    if args.list_sources:
        for source in catalog:
            status = "active" if source.active else "disabled"
            print(f"{source.name}\t{source.type}\t{status}")
        return []
    if args.dry_run:
        results = []
        for source in selected:
            try:
                results.append(await dry_run(source))
            except Exception as exc:
                logger.error(
                    "source_run_complete",
                    source=source.name,
                    dry_run=True,
                    fetched=0,
                    new=0,
                    errors=1,
                    error_type=type(exc).__name__,
                )
                results.append({"source": source.name, "errors": 1, "articles": []})
        return results
    async with SessionFactory.begin() as db:
        await sync_sources(db, catalog)
    if args.sync_only:
        return [{"synced": len(catalog)}]
    results = []
    for definition in selected:
        async with SessionFactory() as db:
            source = await db.scalar(select(Source).where(Source.url == definition.url))
        if not source.active and not args.include_inactive:
            logger.warning("source_disabled_in_database", source=source.name)
            continue
        if args.parallel:
            job = fetch_source.delay(str(source.id))
            results.append(
                {"source": source.name, "task_id": job.id, "status": "queued"}
            )
            continue
        try:
            result = await ingest_source(
                source.id, str(uuid4()), enqueue=False, force=args.include_inactive
            )
            processing_errors = 0
            for article_id in result.get("article_ids", []):
                try:
                    await process_one(UUID(article_id))
                except Exception as exc:
                    processing_errors += 1
                    async with SessionFactory.begin() as db:
                        from app.models import Article

                        article = await db.get(Article, UUID(article_id))
                        article.processing_error = type(exc).__name__
                    logger.error(
                        "article_processing_failed",
                        source=source.name,
                        article_id=article_id,
                        error_type=type(exc).__name__,
                    )
            result["errors"] = result.get("errors", 0) + processing_errors
            logger.info(
                "pipeline_source_complete",
                source=source.name,
                **{key: value for key, value in result.items() if key != "article_ids"},
            )
            results.append({"source": source.name, **result})
        except Exception as exc:
            results.append(
                {"source": source.name, "errors": 1, "error_type": type(exc).__name__}
            )
    return results


def main() -> None:
    """Expose debug, read-only preview, catalog sync and Celery dispatch modes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--source", help="Exact catalog source name")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--parallel", action="store_true", help="Dispatch through Celery"
    )
    parser.add_argument("--sync-only", action="store_true")
    parser.add_argument("--list-sources", action="store_true")
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Explicit debug of reviewed disabled entries",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON preview/statistics")
    args = parser.parse_args()
    if args.dry_run and (args.parallel or args.sync_only):
        parser.error("--dry-run cannot dispatch tasks or sync the catalog")
    if args.include_inactive and args.parallel:
        parser.error("Inactive source debugging requires a synchronous run")
    configure_logging(get_settings().LOG_LEVEL)
    if not llm_available() and not args.list_sources:
        logger.warning(
            "rules_only_mode",
            translation_enabled=False,
            semantic_embedding_enabled=get_settings().ML_ENABLED,
        )
    results = asyncio.run(run(args))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if any(item.get("errors", 0) for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
