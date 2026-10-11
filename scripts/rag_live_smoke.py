"""Verify a real LLM against explicitly synthetic, UUID-scoped database evidence.

No fabricated article is retained: temporary sources, users and messages are
removed in finally. The report is a software check, not a mineral price report.
"""

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.models import Article, ArticleChunk, Source, User
from app.rag.qa_chain import INSUFFICIENT, answer_question
from app.schemas.api import ChatInput
from sqlalchemy import delete, select

BODY = (
    "【虚构测试资料，不是真实行情】2026年1月2日，测试锂矿报价从100美元/吨"
    "上涨到110美元/吨，涨幅10%。这组数值仅用于软件引用校验，不能用于投资判断。"
)


async def run() -> None:
    """Check grounded generation, a follow-up, and off-topic insufficiency."""
    settings = get_settings()
    if settings.APP_ENV == "production":
        raise ValueError(
            "Run live smoke fixtures only in an isolated development database"
        )
    if not settings.LLM_API_KEY.get_secret_value():
        raise ValueError("Configure LLM_API_KEY before running the live smoke check")
    source_id, user_id, article_id = uuid4(), uuid4(), uuid4()
    scope = "live-test-" + str(source_id)
    semantic_check: dict = {"enabled": settings.ML_ENABLED}
    try:
        async with SessionFactory.begin() as db:
            db.add(
                Source(
                    id=source_id,
                    name="实时 LLM 软件测试（虚构资料）",
                    url=f"https://example.com/live-test/{source_id}",
                    type="api",
                    category="price",
                    active=False,
                    language="zh",
                )
            )
            db.add(
                User(id=user_id, email=f"{user_id}@example.com", password_hash="unused")
            )
            await db.flush()
            db.add(
                Article(
                    id=article_id,
                    source_id=source_id,
                    title="虚构测试：2026年锂矿报价",
                    title_zh="虚构测试：2026年锂矿报价",
                    summary_zh=BODY,
                    content=BODY,
                    content_zh=BODY,
                    language="zh",
                    category="price",
                    status="published",
                    minerals=["锂"],
                    regions=[scope],
                    url=f"https://example.com/live-test/{article_id}",
                    published_at=datetime(2026, 1, 2, tzinfo=UTC),
                )
            )
            await db.flush()
            db.add(
                ArticleChunk(
                    article_id=article_id,
                    chunk_index=0,
                    text=BODY,
                    search_text=BODY,
                    start_char=0,
                    end_char=len(BODY),
                )
            )
        if settings.ML_ENABLED:
            from app.rag.indexer import index_article
            from app.rag.retriever import HybridRetriever

            assert await index_article(article_id) == "indexed"
            async with SessionFactory() as db:
                article = await db.get(Article, article_id)
                chunk = await db.scalar(
                    select(ArticleChunk).where(ArticleChunk.article_id == article_id)
                )
                assert len(article.embedding) == len(chunk.embedding) == 1024
                nodes = await HybridRetriever(db, ["锂"], [scope]).aretrieve(
                    "电池原材料行情变化"
                )
                assert nodes and nodes[0].metadata["article_id"] == str(article_id)
                semantic_check.update(
                    {
                        "dimensions": len(article.embedding),
                        "pgvector_semantic_recall": True,
                        "reranker_score": nodes[0].score,
                    }
                )
        async with SessionFactory.begin() as db:
            first = await answer_question(
                db,
                user_id,
                ChatInput(question="2026年锂矿价格走势如何", regions=[scope]),
            )
        assert first.mode == "grounded", "LLM did not return a valid grounded answer"
        assert first.sources and first.sources[0].article_id == article_id
        assert "[1]" in first.answer
        async with SessionFactory.begin() as db:
            followup = await answer_question(
                db,
                user_id,
                ChatInput(
                    question="那涨幅是多少？",
                    session_id=first.session_id,
                    regions=[scope],
                ),
            )
        assert followup.mode == "grounded" and followup.sources
        async with SessionFactory.begin() as db:
            weather = await answer_question(
                db,
                user_id,
                ChatInput(question="今天天气怎么样", session_id=first.session_id),
            )
        assert weather.answer == INSUFFICIENT and not weather.sources
        print(
            json.dumps(
                {
                    "test_data": "explicitly synthetic; removed after verification",
                    "model": settings.LLM_MODEL,
                    "semantic": semantic_check,
                    "first_mode": first.mode,
                    "first_answer": first.answer,
                    "followup_mode": followup.mode,
                    "followup_answer": followup.answer,
                    "weather_answer": weather.answer,
                    "citation_original_span_valid": all(
                        BODY[item.start_char : item.end_char] == item.snippet
                        for item in first.sources
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        async with SessionFactory.begin() as db:
            await db.execute(delete(User).where(User.id == user_id))
            await db.execute(delete(Article).where(Article.id == article_id))
            await db.execute(delete(Source).where(Source.id == source_id))


if __name__ == "__main__":
    asyncio.run(run())
