"""Idempotent source ingestion and separately retryable NLP tasks."""

import asyncio
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID, uuid4

import redis
import structlog
from celery import Task
from celery.result import AsyncResult
from redis.lock import Lock
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.task_dispatch import enqueue_article as dispatch_article
from app.models import Article, ArticleChunk, PipelineRun, Policy, Source
from app.rag.chunking import split_evidence
from app.rag.embedding import embed
from app.schemas.api import PriceInput
from app.services.prices import store_price
from app.tasks.celery_app import celery_app
from pipeline.analyzers.events import cluster_article
from pipeline.fetchers.collect import collect
from pipeline.metrics import (
    DUPLICATES,
    DURATION,
    ERRORS,
    FETCH_RUNS,
    FETCHED,
    INSERTED,
    TRANSLATIONS,
)
from pipeline.processors.dedup import (
    hamming_distance,
    is_duplicate_title,
    normalize_title,
    normalize_url,
    simhash,
)
from pipeline.processors.enrich import enrich
from pipeline.schemas import SourceDefinition

logger = structlog.get_logger()


def queue_lock(key: str) -> Lock:
    """Return a bounded distributed lock; stale workers cannot remove new locks."""
    return redis.Redis.from_url(get_settings().REDIS_URL).lock(
        key, timeout=660, blocking=False
    )


async def ingest_source(
    source_id: UUID, task_id: str, *, enqueue: bool = True, force: bool = False
) -> dict:
    """Persist a run, conditionally fetch, upsert raw records, then enqueue NLP."""
    run_id = uuid4()
    started = monotonic()
    async with SessionFactory.begin() as db:
        source = await db.get(Source, source_id)
        if source is None or (not source.active and not force):
            return {"status": "skipped"}
        source.last_attempted_at = datetime.now(UTC)
        db.add(
            PipelineRun(
                id=run_id,
                source_id=source_id,
                task_id=task_id,
                status="running",
                fetched_count=0,
            )
        )
    try:
        batch = await collect(source)
        ids: list[UUID] = []
        upgraded_ids: list[UUID] = []
        duplicates = 0
        async with SessionFactory.begin() as db:
            await db.execute(text("SELECT pg_advisory_xact_lock(31415926)"))
            for document in batch.documents:
                if not document.content.strip():
                    continue
                fingerprint = simhash(document.content)
                normalized = normalize_title(document.title)
                url = normalize_url(document.url)
                if digest := document.metadata.get("snapshot_digest"):
                    url += "#snapshot-" + digest
                existing = await db.scalar(select(Article).where(Article.url == url))
                if existing:
                    duplicates += 1
                    if (
                        existing.status != "published"
                        and existing.raw_json.get("full_text") is False
                        and document.metadata.get("full_text") is True
                    ):
                        existing.content = document.content[:100000]
                        existing.raw_json = document.metadata
                        existing.content_fingerprint = fingerprint
                        existing.status = "pending"
                        existing.processing_error = None
                        upgraded_ids.append(existing.id)
                    continue
                candidates = (
                    await db.scalars(
                        select(Article)
                        .where(
                            Article.fetched_at >= datetime.now(UTC) - timedelta(days=7),
                            or_(
                                Article.content_fingerprint == fingerprint,
                                func.similarity(Article.title_normalized, normalized)
                                >= 0.3,
                            ),
                        )
                        .order_by(Article.fetched_at.desc())
                        .limit(200)
                    )
                ).all()
                copied = source.category != "price" and any(
                    is_duplicate_title(row.title, document.title)
                    and row.content_fingerprint is not None
                    and min(len(row.content), len(document.content)) >= 200
                    and hamming_distance(row.content_fingerprint, fingerprint) <= 3
                    for row in candidates
                )
                if copied:
                    duplicates += 1
                    continue
                article_id = await db.scalar(
                    insert(Article)
                    .values(
                        source_id=source_id,
                        title=document.title,
                        content=document.content[:100000],
                        url=url,
                        content_fingerprint=fingerprint,
                        title_normalized=normalized,
                        raw_json=document.metadata,
                        published_at=document.published_at,
                        category=source.category,
                        language=document.language or source.language,
                    )
                    .on_conflict_do_nothing(index_elements=[Article.url])
                    .returning(Article.id)
                )
                if article_id:
                    ids.append(article_id)
                else:
                    duplicates += 1
                if source.category == "policy":
                    from pipeline.fetchers.collect import timestamp

                    effective = timestamp(document.metadata.get("effective_date"))
                    await db.execute(
                        insert(Policy)
                        .values(
                            title=document.title,
                            url=url,
                            country=document.metadata.get("country")
                            or source.region
                            or "未知",
                            region=source.region,
                            effective_date=effective.date() if effective else None,
                            impact_score=0,
                        )
                        .on_conflict_do_nothing(index_elements=[Policy.url])
                    )
            for observation in batch.prices:
                await store_price(db, PriceInput.model_validate(observation))
            current = await db.get(Source, source_id)
            current.last_fetched_at = datetime.now(UTC)
            current.failure_count = current.failure_count + 1 if batch.errors else 0
            current.last_error = None
            current.next_retry_at = None
            if not batch.not_modified and not batch.errors:
                current.etag = batch.etag
                current.last_modified = batch.last_modified
                current.fetch_state = batch.state
            elif batch.errors:
                current.etag = current.last_modified = None
                current.last_error = "PartialFetch"
            run = await db.get(PipelineRun, run_id)
            run.status = "partial" if batch.errors else "succeeded"
            run.fetched_count = len(batch.documents)
            run.new_count = len(ids)
            run.duplicate_count = duplicates
            run.error_count = len(batch.errors)
            run.finished_at = datetime.now(UTC)
        # Raw rows are durable before queue dispatch; Beat recovers missed jobs.
        if enqueue:
            for article_id in ids + upgraded_ids:
                try:
                    enqueue_article(str(article_id))
                except Exception as exc:
                    logger.warning(
                        "nlp_dispatch_deferred",
                        source=source.name,
                        error_type=type(exc).__name__,
                    )
        FETCHED.labels(source.name).inc(len(batch.documents))
        FETCH_RUNS.labels(source.name, "partial" if batch.errors else "success").inc()
        INSERTED.labels(source.name).inc(len(ids))
        DUPLICATES.labels(source.name).inc(duplicates)
        ERRORS.labels(source.name, "fetch").inc(len(batch.errors))
        DURATION.labels(source.name).observe(monotonic() - started)
        from app.core.cache import invalidate_public_cache

        await invalidate_public_cache()
        logger.info(
            "source_run_complete",
            source=source.name,
            fetched=len(batch.documents),
            new=len(ids),
            duplicates=duplicates,
            errors=len(batch.errors),
            upgraded=len(upgraded_ids),
            not_modified=batch.not_modified,
        )
        return {
            "status": "partial" if batch.errors else "succeeded",
            "fetched": len(batch.documents),
            "duplicates": duplicates,
            "errors": len(batch.errors),
            "article_ids": [str(value) for value in ids + upgraded_ids],
            "upgraded_articles": len(upgraded_ids),
            "new_articles": len(ids),
            "prices": len(batch.prices),
        }
    except Exception as exc:
        async with SessionFactory.begin() as db:
            run = await db.get(PipelineRun, run_id)
            run.status = "failed"
            run.error = type(exc).__name__
            run.error_count = 1
            run.finished_at = datetime.now(UTC)
            current = await db.get(Source, source_id)
            if current:
                current.failure_count += 1
                current.last_error = type(exc).__name__
                cooldown = min(
                    86400, source.fetch_interval * 2 ** min(current.failure_count, 6)
                )
                current.next_retry_at = datetime.now(UTC) + timedelta(seconds=cooldown)
        ERRORS.labels(source.name, "fetch").inc()
        FETCH_RUNS.labels(source.name, "failure").inc()
        DURATION.labels(source.name).observe(monotonic() - started)
        logger.exception(
            "source_ingestion_failed",
            source_id=str(source_id),
            error_type=type(exc).__name__,
        )
        raise


@celery_app.task(
    bind=True,
    name="miningintel.fetch_source",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def fetch_source(self: Task, source_id: str) -> dict:
    """Fetch a source once even if Beat and an administrator schedule it together."""
    lock = queue_lock(f"fetch:{source_id}")
    if not lock.acquire():
        return {"status": "locked"}
    try:
        return asyncio.run(ingest_source(UUID(source_id), self.request.id))
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            logger.warning("fetch_lock_expired", source_id=source_id)


async def process_one(article_id: UUID) -> dict:
    """Enrich outside a transaction, then atomically publish all derived data."""
    async with SessionFactory() as db:
        article = await db.get(Article, article_id)
        if article is None or article.status != "pending":
            return {"status": "skipped"}
        source = await db.get(Source, article.source_id)
    definition = SourceDefinition(
        name=source.name,
        url=source.url,
        type=source.type,
        category=source.category,
        region=source.region,
        language=source.language,
        authority_score=source.authority_score,
        parser_config=source.config_json,
    )
    if source.config_json.get("adapter") in {
        "ppi_lithium_spot",
        "ppi_spot_market",
        "sunsirs_mineral_daily",
    }:
        from pipeline.processors.price_processor import process_price

        values = process_price(
            article.title,
            article.content,
            article.raw_json,
            source.authority_score,
            article.published_at,
            source.region,
        )
    else:
        values = await enrich(
            article.title,
            article.content,
            article.language,
            source.authority_score,
            published_at=article.published_at,
            category=article.category,
            source=definition,
            url=article.url,
            metadata=article.raw_json,
        )
    spans = await asyncio.to_thread(split_evidence, article.content)
    vectors = await embed(
        [article.title + "\n" + (values["summary_zh"] or values["summary"])]
        + [span.text for span in spans]
    )
    async with SessionFactory.begin() as db:
        current = await db.get(Article, article_id, with_for_update=True)
        if current.status != "pending":
            return {"status": "skipped"}
        if (current.title, current.content, current.language) != (
            article.title,
            article.content,
            article.language,
        ):
            # A full-text upgrade won the race; Beat will process the newer evidence.
            return {"status": "stale"}
        for key, value in values.items():
            setattr(current, key, value)
        current.embedding = vectors[0]
        await db.execute(
            delete(ArticleChunk).where(ArticleChunk.article_id == article_id)
        )
        for index, span in enumerate(spans):
            db.add(
                ArticleChunk(
                    article_id=article_id,
                    chunk_index=index,
                    text=span.text,
                    search_text=current.title
                    + "\n"
                    + (current.title_zh or "")
                    + "\n"
                    + (current.summary_zh or "")
                    + "\n"
                    + span.text,
                    start_char=span.start,
                    end_char=span.end,
                    embedding=vectors[index + 1],
                )
            )
        await cluster_article(db, current)
        policy = await db.scalar(select(Policy).where(Policy.url == current.url))
        if current.category != "policy" and policy:
            await db.delete(policy)
        elif current.category == "policy" and policy:
            policy.title_zh = current.title_zh
            policy.summary_zh = current.summary_zh
            policy.minerals = current.minerals
        elif current.category == "policy":
            db.add(
                Policy(
                    title=current.title,
                    title_zh=current.title_zh,
                    url=current.url,
                    country=current.raw_json.get("policy_country")
                    or (current.regions[0] if current.regions else "未知"),
                    region=source.region,
                    minerals=current.minerals,
                    summary_zh=current.summary_zh,
                    impact_score=0,
                )
            )
        settings = get_settings()
        from pipeline.processors.policy_document import general_mineral_policy

        editorial_ready = (
            settings.ENRICHMENT_MODE == "editorial"
            and bool(current.title_zh)
            and bool(current.summary_zh)
            and 100 <= len(current.summary_zh) <= 200
        )
        from pipeline.fetchers.scholarly_fetcher import scholarly_source

        academic_ready = (
            scholarly_source(definition)
            and current.raw_json.get("document_kind") == "research_paper"
            and bool(current.title_zh)
            and bool(current.summary_zh)
        )
        threshold = (
            settings.INITIALIZATION_QUALITY_THRESHOLD
            if editorial_ready
            and current.raw_json.get("initialization_requested") is True
            and source.authority_score >= 7
            else settings.PUBLISH_QUALITY_THRESHOLD
        )
        current.status = (
            "published"
            if settings.AUTO_PUBLISH
            and (
                current.language.startswith("zh")
                or current.is_translated
                or editorial_ready
                or academic_ready
            )
            and (
                bool(current.minerals)
                or academic_ready
                or (
                    current.category == "policy"
                    and general_mineral_policy(
                        definition, current.title, current.content
                    )
                    and current.relevance_score > 0
                )
            )
            and current.quality_score >= threshold
            and current.relevance_score > 0
            else "processed"
        )
        current.processing_error = None
        if editorial_ready:
            current.raw_json = current.raw_json | {
                "editorial_translation": "title_and_summary",
                "body_translation": "original",
            }
        # The dedicated indexer uses the finalized Chinese fields and model version.
        current.indexed_at = None
    if not article.language.startswith("zh"):
        TRANSLATIONS.labels(
            "success"
            if current.is_translated or editorial_ready or academic_ready
            else "skipped"
        ).inc()
    from app.core.cache import invalidate_public_cache

    await invalidate_public_cache()
    logger.info(
        "article_processing_complete",
        source=source.name,
        article_id=str(article_id),
        status=current.status,
        translated=current.is_translated,
        minerals=len(current.minerals),
        regions=len(current.regions),
        companies=len(current.companies),
    )
    return {"status": current.status, "chunks": len(spans)}


@celery_app.task(
    bind=True,
    name="miningintel.process_article",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_jitter=True,
    max_retries=3,
)
def process_article(self: Task, article_id: str) -> dict:
    """Process independently so model outages do not repeat network collection."""
    lock = queue_lock(f"process:{article_id}")
    if not lock.acquire():
        return {"status": "locked"}
    try:
        return asyncio.run(process_one(UUID(article_id)))
    except Exception as error:
        error_type = type(error).__name__

        async def record_error() -> None:
            async with SessionFactory.begin() as db:
                article = await db.get(Article, UUID(article_id))
                if article:
                    if not article.language.startswith("zh"):
                        TRANSLATIONS.labels("failure").inc()
                    article.processing_error = error_type
                    source = await db.get(Source, article.source_id)
                    ERRORS.labels(source.name, "nlp").inc()
                    logger.error(
                        "article_processing_failed",
                        source=source.name,
                        article_id=article_id,
                        error_type=error_type,
                    )

        asyncio.run(record_error())
        raise
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            logger.warning("processing_lock_expired", article_id=article_id)


def enqueue_article(article_id: str) -> AsyncResult | None:
    """Publish once while queued/retrying; roll back the lease on broker failure."""
    return dispatch_article(article_id, publisher=process_article.apply_async)


@celery_app.task(name="miningintel.dispatch_sources")
def dispatch_sources() -> int:
    """Respect each source's interval instead of fetching every source each minute."""

    async def due() -> list[str]:
        now = datetime.now(UTC)
        async with SessionFactory() as db:
            sources = (
                await db.scalars(select(Source).where(Source.active.is_(True)))
            ).all()
            attempts = dict(
                (
                    await db.execute(
                        select(
                            PipelineRun.source_id, func.max(PipelineRun.created_at)
                        ).group_by(PipelineRun.source_id)
                    )
                ).all()
            )
            ids = []
            for source in sources:
                if source.next_retry_at and source.next_retry_at > now:
                    continue
                latest = attempts.get(source.id) or source.last_fetched_at
                if (
                    latest is None
                    or (now - latest).total_seconds() >= source.fetch_interval
                ):
                    ids.append(str(source.id))
            return ids

    ids = asyncio.run(due())
    client = redis.Redis.from_url(get_settings().REDIS_URL)
    for source_id in ids:
        if not client.exists(f"fetch:{source_id}"):
            fetch_source.delay(source_id)
    return len(ids)


@celery_app.task(name="miningintel.recover_pending")
def recover_pending() -> int:
    """Recover queue dispatch gaps; failed processing needs manual retry."""

    async def pending() -> list[str]:
        async with SessionFactory() as db:
            return [
                str(value)
                for value in (
                    await db.scalars(
                        select(Article.id)
                        .where(
                            Article.status == "pending",
                            Article.processing_error.is_(None),
                        )
                        .order_by(Article.fetched_at.desc(), Article.id)
                        .limit(1000)
                    )
                ).all()
            ]

    ids = asyncio.run(pending())
    queued = 0
    for article_id in ids:
        if enqueue_article(article_id) is not None:
            queued += 1
            if queued >= 100:
                break
    return queued
