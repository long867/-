"""Optional Qdrant mirror; PostgreSQL remains the authority for visibility."""

from datetime import datetime
from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings


def create_client() -> AsyncQdrantClient:
    """Create a bounded-time client without logging credentials."""
    settings = get_settings()
    if not settings.QDRANT_URL:
        raise ValueError("QDRANT_URL is not configured")
    return AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
        timeout=settings.QDRANT_TIMEOUT,
    )


class QdrantStore:
    """Manage article vectors and original evidence vectors in two collections."""

    def __init__(self, client: AsyncQdrantClient) -> None:
        self.client = client
        self.articles = get_settings().QDRANT_COLLECTION
        self.chunks = self.articles + "_chunks"

    async def ensure_collections(self) -> None:
        """Create 1024-dimensional cosine indexes, never destructively recreate."""
        for name in (self.articles, self.chunks):
            if not await self.client.collection_exists(name):
                try:
                    await self.client.create_collection(
                        name,
                        vectors_config=models.VectorParams(
                            size=1024, distance=models.Distance.COSINE
                        ),
                    )
                except Exception:
                    # Multiple workers may race to create the same collection.
                    if not await self.client.collection_exists(name):
                        raise
            info = await self.client.get_collection(name)
            vector = info.config.params.vectors
            if not isinstance(vector, models.VectorParams) or vector.size != 1024:
                raise ValueError("Qdrant collection must use unnamed 1024-D vectors")
            if vector.distance != models.Distance.COSINE:
                raise ValueError("Qdrant collection must use cosine distance")
            for field in (
                "article_id",
                "status",
                "minerals",
                "regions",
                "category",
                "embedding_model",
            ):
                if field in info.payload_schema:
                    continue
                await self.client.create_payload_index(
                    name,
                    field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                    wait=True,
                )
            if "published_ts" not in info.payload_schema:
                await self.client.create_payload_index(
                    name,
                    "published_ts",
                    field_schema=models.PayloadSchemaType.FLOAT,
                    wait=True,
                )

    async def replace_article(
        self,
        article_id: UUID,
        vector: list[float] | None,
        metadata: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> None:
        """Idempotently replace an article and remove obsolete evidence points."""
        selector = models.Filter(
            must=[
                models.FieldCondition(
                    key="article_id", match=models.MatchValue(value=str(article_id))
                )
            ]
        )
        await self.client.delete(
            self.chunks, models.FilterSelector(filter=selector), wait=True
        )
        if vector is None:
            await self.client.delete(
                self.articles, models.PointIdsList(points=[str(article_id)]), wait=True
            )
            return
        await self.client.upsert(
            self.articles,
            points=[
                models.PointStruct(id=str(article_id), vector=vector, payload=metadata)
            ],
            wait=True,
        )
        if chunks:
            await self.client.upsert(
                self.chunks,
                points=[
                    models.PointStruct(
                        id=item["id"],
                        vector=item["vector"],
                        payload={
                            **metadata,
                            "text": item["text"],
                            "start_char": item["start_char"],
                            "end_char": item["end_char"],
                        },
                    )
                    for item in chunks
                ],
                wait=True,
            )

    async def search(
        self,
        vector: list[float],
        *,
        minerals: list[str],
        regions: list[str],
        category: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[tuple[UUID, str]]:
        """Return candidate IDs and revisions; callers must recheck them in SQL."""
        conditions = [
            models.FieldCondition(
                key="status", match=models.MatchValue(value="published")
            ),
            models.FieldCondition(
                key="embedding_model",
                match=models.MatchValue(value=get_settings().EMBEDDING_MODEL),
            ),
        ]
        for field, values in (("minerals", minerals), ("regions", regions)):
            if values:
                conditions.append(
                    models.FieldCondition(key=field, match=models.MatchAny(any=values))
                )
        if category:
            conditions.append(
                models.FieldCondition(
                    key="category", match=models.MatchValue(value=category)
                )
            )
        if start or end:
            conditions.append(
                models.FieldCondition(
                    key="published_ts",
                    range=models.Range(
                        gte=start.timestamp() if start else None,
                        lt=end.timestamp() if end else None,
                    ),
                )
            )
        result = await self.client.query_points(
            self.chunks,
            query=vector,
            query_filter=models.Filter(must=conditions),
            limit=limit,
            with_payload=True,
            score_threshold=0.35,
        )
        return [
            (UUID(str(item.id)), str((item.payload or {}).get("revision", "")))
            for item in result.points
        ]
