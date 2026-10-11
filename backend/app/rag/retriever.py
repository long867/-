"""Filtered cosine + PostgreSQL FTS retrieval, RRF fusion and BGE reranking."""

import asyncio
import re
from collections import defaultdict
from datetime import datetime
from uuid import UUID

import jieba
import structlog
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Article, ArticleChunk, Source
from app.rag.embedding import embed, rerank
from app.rag.qdrant_store import QdrantStore, create_client
from pipeline.processors.entities import extract_entities, lexicon

STOPWORDS = {
    "的",
    "了",
    "和",
    "在",
    "是",
    "对",
    "有",
    "什么",
    "哪些",
    "如何",
    "最近",
    "请",
    "我",
    "它",
    "the",
    "and",
    "is",
    "what",
    "how",
}
PRICE_WORDS = (
    "价格",
    "报价",
    "涨价",
    "跌价",
    "上涨",
    "下跌",
    "price",
    "pricing",
    "$/",
    "usd",
    "cny",
    "每吨",
    "元/吨",
    "per tonne",
)


def search_terms(query: str) -> list[str]:
    """Expand canonical labels into Chinese and original-language search terms."""
    terms = [
        word.strip()
        for word in jieba.cut(query)
        if len(word.strip()) > 1 and word.lower() not in STOPWORDS
    ]
    for kind, names in extract_entities(query).items():
        for name in names:
            terms.extend(lexicon()[kind][name])
    return list(dict.fromkeys(terms))[:30]


def reciprocal_rank_fusion(
    rankings: list[list[UUID]], k: int = 60
) -> dict[UUID, float]:
    """Fuse incomparable channel scores using reciprocal rank positions."""
    scores: dict[UUID, float] = defaultdict(float)
    for ranking in rankings:
        for rank, key in enumerate(dict.fromkeys(ranking), start=1):
            scores[key] += 1 / (k + rank)
    return dict(scores)


class HybridRetriever(BaseRetriever):
    """Return original chunks with metadata, always enforcing SQL visibility."""

    def __init__(
        self,
        db: AsyncSession,
        minerals: list[str] | None = None,
        regions: list[str] | None = None,
        *,
        category: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> None:
        super().__init__()
        self.db = db
        self.minerals, self.regions = minerals or [], regions or []
        self.category, self.start, self.end = category, start, end
        self.evidence: dict[str, tuple[ArticleChunk, Article]] = {}

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        raise RuntimeError("Use await retriever.aretrieve(query)")

    def conditions(self, query: str) -> list:
        """Apply filters before ranking; price questions require price evidence."""
        conditions = [Article.status == "published"]
        if self.minerals:
            conditions.append(Article.minerals.overlap(self.minerals))
        if self.regions:
            conditions.append(Article.regions.overlap(self.regions))
        if self.category:
            conditions.append(Article.category == self.category)
        if self.start:
            conditions.append(Article.published_at >= self.start)
        if self.end:
            conditions.append(Article.published_at < self.end)
        if re.search(r"价格|报价|price|pricing", query, re.I):
            conditions.append(
                or_(*[ArticleChunk.text.ilike(f"%{word}%") for word in PRICE_WORDS])
            )
            # A generic instruction to "check the price basis" is not a quote
            # or a price movement observation. Do not use it to invent a trend.
            observation = Article.raw_json["price_observation"]
            table_quote = and_(
                Article.category == "price",
                observation["price"].as_string().op("~")(r"^\d+(?:\.\d+)?$"),
                observation["currency"].as_string().in_(["CNY", "USD", "EUR", "CAD"]),
                observation["unit"].as_string().in_(["吨", "kg", "千克", "磅", "盎司"]),
                observation["date"].as_string().is_not(None),
                ArticleChunk.text.contains(observation["price"].as_string()),
                ArticleChunk.text.contains(observation["unit"].as_string()),
            )
            # A verified table may put its numeric row and unit note on separate
            # lines. Retain both in the cited chunk instead of requiring adjacent
            # currency text, which incorrectly excludes real tabular spot quotes.
            conditions.append(
                or_(
                    table_quote,
                    ArticleChunk.text.op("~*")(
                        r"([$€£¥￥]\s*\d|\d[\d,.]*\s*(USD|CNY|EUR|GBP|美元|人民币|元))"
                        r"|((price|pricing|报价|价格|锂价|铜价).{0,50}"
                        r"(rise|rose|fall|fell|declin|increas|decreas|"
                        r"上涨|下跌|增长|下滑|攀升|走高|走低|稳定|持平|上升|回落))"
                    ),
                )
            )
        return conditions

    async def _aretrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        settings = get_settings()
        query = query_bundle.query_str
        terms = await asyncio.to_thread(search_terms, query) or [query]
        base = (
            select(ArticleChunk, Article, Source.name)
            .join(Article, ArticleChunk.article_id == Article.id)
            .join(Source, Article.source_id == Source.id)
            .where(*self.conditions(query))
        )
        escaped = [
            term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            for term in terms
        ]
        ts_query = func.websearch_to_tsquery(
            text("'simple'::regconfig"), " OR ".join(terms)
        )
        document = func.to_tsvector(
            text("'simple'::regconfig"), ArticleChunk.search_text
        )
        lexical = list(
            (
                await self.db.execute(
                    base.where(
                        or_(
                            document.op("@@")(ts_query),
                            *[
                                ArticleChunk.search_text.ilike(f"%{term}%", escape="\\")
                                for term in escaped
                            ],
                        )
                    )
                    .order_by(
                        func.ts_rank_cd(document, ts_query).desc(),
                        Article.published_at.desc().nullslast(),
                        ArticleChunk.id,
                    )
                    .limit(settings.RAG_CANDIDATES)
                )
            ).all()
        )
        semantic = []
        try:
            vectors = await embed([query])
        except Exception as exc:
            structlog.get_logger().warning(
                "rag_encoder_unavailable", error_type=type(exc).__name__
            )
            vectors = [None]
        if vectors[0] is not None:
            distance = ArticleChunk.embedding.cosine_distance(vectors[0])
            fresh = [
                Article.embedding_model == settings.EMBEDDING_MODEL,
                Article.indexed_at.is_not(None),
                Article.indexed_at >= Article.updated_at,
            ]
            semantic = list(
                (
                    await self.db.execute(
                        base.where(
                            *fresh, ArticleChunk.embedding.is_not(None), distance < 0.65
                        )
                        .order_by(distance, ArticleChunk.id)
                        .limit(settings.RAG_CANDIDATES)
                    )
                ).all()
            )
            if settings.QDRANT_URL:
                client = create_client()
                try:
                    hits = await QdrantStore(client).search(
                        vectors[0],
                        minerals=self.minerals,
                        regions=self.regions,
                        category=self.category,
                        start=self.start,
                        end=self.end,
                        limit=settings.RAG_CANDIDATES,
                    )
                    rows = (
                        list(
                            (
                                await self.db.execute(
                                    base.where(
                                        *fresh,
                                        ArticleChunk.id.in_([key for key, _ in hits]),
                                    )
                                )
                            ).all()
                        )
                        if hits
                        else []
                    )
                    by_id = {row[0].id: row for row in rows}
                    mirrored = [
                        by_id[key]
                        for key, revision in hits
                        if key in by_id and by_id[key][1].embedding_hash == revision
                    ]
                    semantic = list(
                        {row[0].id: row for row in mirrored + semantic}.values()
                    )
                    semantic = semantic[: settings.RAG_CANDIDATES]
                except Exception as exc:
                    structlog.get_logger().warning(
                        "qdrant_search_fallback", error_type=type(exc).__name__
                    )
                finally:
                    await client.close()
        scores = reciprocal_rank_fusion(
            [[row[0].id for row in lexical], [row[0].id for row in semantic]]
        )
        candidates = {row[0].id: row for row in lexical + semantic}
        ordered = sorted(candidates, key=lambda key: scores[key], reverse=True)
        ordered = ordered[: settings.RAG_RERANK_CANDIDATES]
        final_scores = dict(scores)
        try:
            reranked = await rerank(query, [candidates[key][0].text for key in ordered])
            if reranked is not None:
                final_scores.update(zip(ordered, reranked, strict=True))
                ordered.sort(key=lambda key: final_scores[key], reverse=True)
        except Exception as exc:
            structlog.get_logger().warning(
                "rag_reranker_unavailable", error_type=type(exc).__name__
            )
            final_scores = dict(scores)
        selected: list[UUID] = []
        article_counts: dict[UUID, int] = defaultdict(int)
        for key in ordered:
            article_id = candidates[key][1].id
            if article_counts[article_id] < 2:
                selected.append(key)
                article_counts[article_id] += 1
            if len(selected) >= settings.RAG_TOP_K:
                break
        self.evidence = {
            str(key): (candidates[key][0], candidates[key][1]) for key in selected
        }
        result = []
        for key in selected:
            chunk, article, source_name = candidates[key]
            result.append(
                NodeWithScore(
                    node=TextNode(
                        id_=str(key),
                        text=chunk.text,
                        metadata={
                            "article_id": str(article.id),
                            "title": article.title_zh or article.title,
                            "title_zh": article.title_zh,
                            "url": article.url,
                            "source_name": source_name,
                            "published_at": article.published_at.isoformat()
                            if article.published_at
                            else None,
                            "minerals": article.minerals,
                            "regions": article.regions,
                            "category": article.category,
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                            "rrf_score": scores[key],
                        },
                        excluded_llm_metadata_keys=["rrf_score"],
                        excluded_embed_metadata_keys=["rrf_score"],
                    ),
                    score=final_scores[key],
                )
            )
        return result
