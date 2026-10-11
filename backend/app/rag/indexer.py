"""Incremental BGE indexing and durable PostgreSQL-to-Qdrant synchronization.

CLI: python -m app.rag.indexer --rebuild [--batch-size 100]
"""

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from prometheus_client import Counter
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.models import Article, ArticleChunk, Source, VectorSyncJob
from app.rag.chunking import split_evidence
from app.rag.embedding import embed, validate_vector
from app.rag.qdrant_store import QdrantStore, create_client

logger = structlog.get_logger()
INDEXED = Counter("miningintel_index_articles_total", "Index outcomes", ["status"])
SYNCED = Counter("miningintel_vector_sync_total", "Qdrant sync outcomes", ["status"])


def index_text(article: Article) -> str:
    """Concatenate Chinese fields; never disguise untranslated text as Chinese."""
    chinese = article.language.lower().startswith("zh")
    title = article.title_zh or (article.title if chinese else "")
    summary = article.summary_zh or (article.summary if chinese else "")
    content = article.content_zh or (article.content if chinese else "")
    if not title.strip() or not content.strip():
        raise ValueError("Chinese title and body are required before semantic indexing")
    return "\n\n".join(value for value in (title, summary, content) if value)


def index_metadata(article: Article, source_name: str) -> dict:
    """Build filterable, serializable article metadata for both vector stores."""
    return {
        "article_id": str(article.id),
        "title_zh": article.title_zh or article.title,
        "source_name": source_name,
        "published_at": article.published_at.isoformat()
        if article.published_at
        else None,
        "published_ts": article.published_at.timestamp()
        if article.published_at
        else None,
        "minerals": article.minerals,
        "regions": article.regions,
        "category": article.category,
        "url": article.url,
        "status": article.status,
        "embedding_model": get_settings().EMBEDDING_MODEL,
    }


def revision_hash(article: Article, source_name: str) -> str:
    """Detect content, filter, source and encoder changes before committing vectors."""
    value = {
        "text": index_text(article),
        "original": article.content,
        "metadata": index_metadata(article, source_name),
        "max_tokens": 512,
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


async def enqueue_sync(db: AsyncSession, article: Article) -> None:
    """Atomically replace the pending mirror revision with the latest state."""
    await db.execute(
        insert(VectorSyncJob)
        .values(
            article_id=article.id,
            revision=article.embedding_hash or "unindexed",
        )
        .on_conflict_do_update(
            index_elements=[VectorSyncJob.article_id],
            set_={
                "revision": article.embedding_hash or "unindexed",
                "attempts": 0,
                "next_retry_at": func.now(),
                "last_error": None,
            },
        )
    )


async def index_article(article_id: UUID, *, force: bool = False) -> str:
    """Compute outside SQL transactions, then commit only an unchanged snapshot."""
    settings = get_settings()
    if not settings.ML_ENABLED:
        return "disabled"
    async with SessionFactory() as db:
        row = (
            await db.execute(
                select(Article, Source.name)
                .join(Source)
                .where(
                    Article.id == article_id,
                    Article.status.in_(["processed", "published"]),
                )
            )
        ).first()
        if row is None:
            return "skipped"
        article, source_name = row
        try:
            revision = revision_hash(article, source_name)
        except ValueError:
            return "untranslated"
        if not force and article.embedding_hash == revision and article.indexed_at:
            # Repair stale timestamps after an irrelevant metadata update.
            article.indexed_at = func.now()
            await enqueue_sync(db, article)
            await db.commit()
            return "unchanged"
        spans = await asyncio.to_thread(split_evidence, article.content)
        texts = [index_text(article), *[span.text for span in spans]]
    vectors = await embed(texts, max_tokens=512)
    if any(vector is None for vector in vectors):
        raise ValueError("Semantic indexing requires a configured real encoder")
    vectors = [validate_vector(vector) for vector in vectors if vector is not None]
    async with SessionFactory.begin() as db:
        current = await db.get(Article, article_id, with_for_update=True)
        source = await db.get(Source, current.source_id) if current else None
        if (
            current is None
            or source is None
            or current.status not in {"processed", "published"}
        ):
            return "stale"
        try:
            if revision_hash(current, source.name) != revision:
                return "stale"
        except ValueError:
            return "stale"
        existing = {
            chunk.chunk_index: chunk
            for chunk in (
                await db.scalars(
                    select(ArticleChunk).where(ArticleChunk.article_id == article_id)
                )
            ).all()
        }
        for index, (span, vector) in enumerate(zip(spans, vectors[1:], strict=True)):
            chunk = existing.pop(index, None)
            if chunk is None:
                chunk = ArticleChunk(article_id=article_id, chunk_index=index)
                db.add(chunk)
            chunk.text = span.text
            chunk.search_text = "\n".join(
                value
                for value in (
                    current.title,
                    current.title_zh,
                    current.summary_zh,
                    span.text,
                )
                if value
            )
            chunk.start_char, chunk.end_char = span.start, span.end
            chunk.embedding = vector
        for chunk in existing.values():
            await db.delete(chunk)
        current.embedding = vectors[0]
        current.embedding_model = settings.EMBEDDING_MODEL
        current.embedding_hash = revision
        current.indexed_at = func.now()
        await enqueue_sync(db, current)
    INDEXED.labels("indexed").inc()
    logger.info("article_indexed", article_id=str(article_id), chunks=len(spans))
    return "indexed"


async def pending_ids(limit: int) -> list[UUID]:
    """Find new, modified, or model-version-stale articles for the hourly task."""
    async with SessionFactory() as db:
        return list(
            (
                await db.scalars(
                    select(Article.id)
                    .where(
                        Article.status.in_(["processed", "published"]),
                        or_(
                            Article.language.ilike("zh%")
                            & (func.length(func.trim(Article.title)) > 0)
                            & (func.length(func.trim(Article.content)) > 0),
                            (func.length(func.trim(Article.title_zh)) > 0)
                            & (func.length(func.trim(Article.content_zh)) > 0),
                        ),
                        or_(
                            Article.indexed_at.is_(None),
                            Article.updated_at > Article.indexed_at,
                            Article.embedding_model.is_distinct_from(
                                get_settings().EMBEDDING_MODEL
                            ),
                        ),
                    )
                    .order_by(Article.updated_at, Article.id)
                    .limit(limit)
                )
            ).all()
        )


async def sync_outbox(
    limit: int = 100,
    *,
    store: QdrantStore | None = None,
    article_id: UUID | None = None,
) -> dict:
    """Retry idempotent mirror writes; row locks serialize each article's revisions.

    Each bounded HTTP operation runs under its outbox row lock. A crash before
    acknowledgement leaves the job available for another worker to repeat.
    """
    if store is None and not get_settings().QDRANT_URL:
        return {"synced": 0, "errors": 0, "disabled": True}
    owned = store is None
    if store is None:
        store = QdrantStore(create_client())
    result = {"synced": 0, "errors": 0}
    try:
        await store.ensure_collections()
        for _ in range(limit):
            async with SessionFactory.begin() as db:
                statement = select(VectorSyncJob).where(
                    VectorSyncJob.next_retry_at <= func.now()
                )
                if article_id:
                    statement = statement.where(VectorSyncJob.article_id == article_id)
                job = await db.scalar(
                    statement.order_by(VectorSyncJob.next_retry_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                if job is None:
                    break
                row = (
                    await db.execute(
                        select(Article, Source.name)
                        .join(Source)
                        .where(Article.id == job.article_id)
                    )
                ).one()
                article, source_name = row
                metadata = index_metadata(article, source_name)
                metadata["embedding_model"] = article.embedding_model
                metadata["revision"] = article.embedding_hash
                chunks = list(
                    (
                        await db.scalars(
                            select(ArticleChunk).where(
                                ArticleChunk.article_id == article.id,
                                ArticleChunk.embedding.is_not(None),
                            )
                        )
                    ).all()
                )
                ready = (
                    article.indexed_at is not None
                    and article.embedding is not None
                    and article.status in {"processed", "published"}
                )
                try:
                    await store.replace_article(
                        article.id,
                        list(article.embedding) if ready else None,
                        metadata,
                        [
                            {
                                "id": str(chunk.id),
                                "vector": list(chunk.embedding),
                                "text": chunk.text,
                                "start_char": chunk.start_char,
                                "end_char": chunk.end_char,
                            }
                            for chunk in chunks
                        ]
                        if ready
                        else [],
                    )
                except Exception as exc:
                    job.attempts += 1
                    job.next_retry_at = datetime.now(UTC) + timedelta(
                        seconds=min(3600, 15 * 2 ** min(job.attempts, 8))
                    )
                    job.last_error = type(exc).__name__
                    result["errors"] += 1
                    SYNCED.labels("error").inc()
                    logger.warning(
                        "qdrant_sync_retry",
                        article_id=str(article.id),
                        error_type=job.last_error,
                        attempt=job.attempts,
                    )
                else:
                    await db.execute(
                        delete(VectorSyncJob).where(
                            VectorSyncJob.article_id == article.id
                        )
                    )
                    result["synced"] += 1
                    SYNCED.labels("success").inc()
    finally:
        if owned:
            await store.client.close()
    return result


async def rebuild(
    *,
    batch_size: int = 100,
    force: bool = True,
    source_id: UUID | None = None,
) -> dict[str, int]:
    """Rebuild in bounded keyset batches; retain published evidence and history."""
    if not get_settings().ML_ENABLED:
        raise ValueError("Enable ML_ENABLED and install backend[ml] before indexing")
    counts: dict[str, int] = {}
    cursor: UUID | None = None
    while True:
        async with SessionFactory() as db:
            stmt = (
                select(Article.id)
                .where(Article.status.in_(["processed", "published"]))
                .order_by(Article.id)
                .limit(batch_size)
            )
            if cursor:
                stmt = stmt.where(Article.id > cursor)
            if source_id:
                stmt = stmt.where(Article.source_id == source_id)
            ids = list((await db.scalars(stmt)).all())
        if not ids:
            break
        for article_id in ids:
            try:
                status = await index_article(article_id, force=force)
            except Exception as exc:
                logger.error(
                    "index_failed",
                    article_id=str(article_id),
                    error_type=type(exc).__name__,
                )
                status = "error"
            counts[status] = counts.get(status, 0) + 1
        cursor = ids[-1]
    return counts


def main() -> None:
    """Expose full rebuild and outbox recovery without requiring Celery."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--sync-only", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--source-id", type=UUID)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 1000:
        parser.error("--batch-size must be between 1 and 1000")
    if args.rebuild == args.sync_only:
        parser.error("Specify exactly one of --rebuild or --sync-only")
    try:
        result = asyncio.run(
            sync_outbox(args.batch_size)
            if args.sync_only
            else rebuild(batch_size=args.batch_size, source_id=args.source_id)
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False))
    if result.get("error", 0) or result.get("errors", 0):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
