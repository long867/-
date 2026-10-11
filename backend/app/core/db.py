"""One async database session per request or task transaction."""

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

# Celery tasks use asyncio.run repeatedly; NullPool avoids cross-loop connections.
engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(Session, "before_flush")
def mark_public_changes(
    session: Session, flush_context: object, instances: object
) -> None:
    """Track ORM intelligence edits so publication withdrawal invalidates cache."""
    from app.models import Article, Event, Policy, PriceRecord, Report, Source

    if any(
        isinstance(item, (Article, Event, Policy, PriceRecord, Report, Source))
        for item in session.new | session.dirty | session.deleted
    ):
        session.info["public_changed"] = True


async def get_db() -> AsyncIterator[AsyncSession]:
    """Commit successful requests and roll back failures."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
            if session.info.pop("public_changed", False):
                from app.core.cache import invalidate_public_cache

                await invalidate_public_cache()
        except Exception:
            await session.rollback()
            raise
