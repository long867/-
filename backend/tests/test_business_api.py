"""Real PostgreSQL business contracts, ownership and Redis cache behavior."""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from app.core.cache import invalidate_public_cache
from app.core.db import get_db
from app.core.security import create_token, hash_password
from app.main import app
from app.models import (
    APIKey,
    Article,
    Event,
    Policy,
    PriceRecord,
    Report,
    Source,
    Subscription,
    User,
)
from app.schemas.api import PriceInput
from app.services.prices import store_price
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def business():
    """Isolate evidence and accounts, retaining every pre-existing real article."""
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    source_id, event_id, user_id, other_id = [uuid4() for _ in range(4)]
    region = "business-" + uuid4().hex
    root = "https://example.com/" + region
    now = datetime.now(UTC)
    ids = [uuid4() for _ in range(4)]
    email = region + "@example.com"
    async with factory.begin() as db:
        db.add(
            Source(
                id=source_id,
                name="BUSINESS TEST FIXTURE",
                url=root + "/feed",
                type="rss",
                category="news",
            )
        )
        db.add(
            Event(
                id=event_id,
                title_zh="PRIVATE EVENT TITLE",
                summary_zh="PRIVATE SUMMARY",
                article_count=99,
            )
        )
        db.add_all(
            [
                User(
                    id=user_id,
                    email=email,
                    password_hash=hash_password("Test-password-123"),
                    is_admin=True,
                ),
                User(
                    id=other_id,
                    email="other-" + email,
                    password_hash=hash_password("Test-password-123"),
                ),
            ]
        )
        await db.flush()
        for index, article_id in enumerate(ids):
            db.add(
                Article(
                    id=article_id,
                    source_id=source_id,
                    event_id=event_id,
                    title=f"BHP copper update {index}",
                    title_zh=f"铜矿产量增长100% {index}",
                    summary="Copper production report.",
                    summary_zh="铜矿公开生产报告。",
                    content="BHP copper production report in Chile.",
                    content_zh="BHP铜矿生产报告。",
                    language="en",
                    category="policy" if index == 1 else "news",
                    status="pending" if index == 3 else "published",
                    url=f"{root}/{index}",
                    minerals=["铜", "锂"],
                    regions=[region],
                    companies=["BHP"],
                    quality_score=70 + index * 5,
                    relevance_score=90,
                    published_at=now - timedelta(minutes=5 + index)
                    if index < 2
                    else now - timedelta(hours=49),
                    is_translated=True,
                )
            )
        await db.flush()
        db.add_all(
            [
                Policy(
                    title="Copper policy",
                    title_zh="铜矿政策",
                    url=root + "/1",
                    country=region,
                    region=region,
                    minerals=["铜"],
                    effective_date=(now + timedelta(days=90)).date(),
                ),
                Policy(
                    title="Private policy",
                    url=root + "/3",
                    country=region,
                    minerals=["铜"],
                ),
            ]
        )
        for offset, value in [(1, "100"), (0, "110")]:
            await store_price(
                db,
                PriceInput(
                    mineral="锂",
                    price=Decimal(value),
                    unit="吨",
                    currency="CNY",
                    date=(now - timedelta(days=offset)).date(),
                    source=root + "/prices",
                    product="TEST FIXTURE",
                    source_url=root + "/quote",
                ),
            )

    async def session():
        async with factory() as db:
            try:
                yield db
                await db.commit()
                if db.info.pop("public_changed", False):
                    await invalidate_public_cache()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = session
    await invalidate_public_cache()
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield {
                    "client": client,
                    "factory": factory,
                    "region": region,
                    "ids": ids,
                    "event_id": event_id,
                    "email": email,
                    "user_id": user_id,
                    "other_id": other_id,
                    "root": root,
                    "headers": {"Authorization": "Bearer " + create_token(user_id)},
                    "other_headers": {
                        "Authorization": "Bearer " + create_token(other_id)
                    },
                }
    finally:
        app.dependency_overrides.clear()
        async with factory.begin() as db:
            await db.execute(delete(Policy).where(Policy.url.startswith(root)))
            await db.execute(
                delete(PriceRecord).where(PriceRecord.source.startswith(root))
            )
            await db.execute(delete(Article).where(Article.source_id == source_id))
            await db.execute(delete(Event).where(Event.id == event_id))
            await db.execute(delete(Source).where(Source.id == source_id))
            await db.execute(delete(User).where(User.id.in_([user_id, other_id])))
        await invalidate_public_cache()
        await engine.dispose()


async def test_article_filters_paging_sorting_and_literal_search(business):
    client, region = business["client"], business["region"]
    base = {"region": region, "page_size": 1, "sort_by": "quality_score"}
    first = (await client.get("/api/articles", params=base)).json()
    second = (await client.get("/api/articles", params={**base, "page": 2})).json()
    assert first["total"] == 3 and first["items"][0]["id"] != second["items"][0]["id"]
    assert first["items"][0]["quality_score"] > second["items"][0]["quality_score"]
    assert first["items"][0]["source_name"] == "BUSINESS TEST FIXTURE"
    for params, count in [
        ({"company": "BHP", "mineral": "锂"}, 3),
        ({"company": "none"}, 0),
        ({"category": "policy"}, 1),
        ({"search": "100%"}, 3),
        ({"search": "%' OR 1=1 --"}, 0),
    ]:
        response = await client.get(
            "/api/articles", params={"region": region, **params}
        )
        assert response.status_code == 200 and response.json()["total"] == count
    response = await client.get(
        "/api/articles",
        params={"region": region, "date_from": "2026-12-31", "date_to": "2026-01-01"},
    )
    assert response.status_code == 422
    assert (
        await client.get("/api/articles", params={"page_size": 101})
    ).status_code == 422
    assert (
        await client.get("/api/articles", params={"sort_by": "DROP TABLE"})
    ).status_code == 422
    assert (
        await client.get("/api/articles/" + str(business["ids"][3]))
    ).status_code == 404


async def test_notification_claims_once_and_never_includes_withdrawn_evidence(
    business, monkeypatch
):
    """Exercise the durable SMTP boundary without sending an external email."""
    from datetime import date
    from unittest.mock import Mock

    import app.services.subscription_service as module
    from app.core.config import Settings

    factory = business["factory"]
    report_id, subscription_id = uuid4(), uuid4()
    async with factory.begin() as db:
        db.add(
            Subscription(
                id=subscription_id,
                user_id=business["user_id"],
                email_enabled=True,
                subscribed_minerals=["铜"],
                subscribed_regions=[business["region"]],
                frequency="daily",
            )
        )
        db.add(
            Report(
                id=report_id,
                kind="daily",
                period_start=date(1999, 1, 1),
                period_end=date(1999, 1, 2),
                title="TEST FIXTURE",
                content="PRIVATE DRAFT",
                sources_json=[{"article_id": str(item)} for item in business["ids"]],
            )
        )
    sender = Mock()
    monkeypatch.setattr(module, "SessionFactory", factory)
    monkeypatch.setattr(module, "send_email", sender)
    settings = Settings(_env_file=None)
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    try:
        assert (await module.deliver_report(subscription_id, report_id))[
            "status"
        ] == "disabled"
        settings.EMAIL_NOTIFICATIONS_ENABLED = True
        assert (await module.deliver_report(subscription_id, report_id))[
            "status"
        ] == "sent"
        assert (await module.deliver_report(subscription_id, report_id))[
            "status"
        ] == "already_claimed"
        assert sender.call_count == 1
        address, _, body, _ = sender.call_args.args
        assert address == business["email"]
        assert business["root"] + "/0" in body
        assert business["root"] + "/3" not in body and "PRIVATE DRAFT" not in body
    finally:
        async with factory.begin() as db:
            await db.execute(delete(Report).where(Report.id == report_id))


async def test_timeline_region_event_and_policy_publication_gates(business):
    client, region = business["client"], business["region"]
    response = await client.get(
        "/api/articles/timeline", params={"region": region, "group_by": "week"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 3
    assert sum(item["article_count"] for item in response.json()["items"]) == 3
    assert (await client.get(f"/api/regions/{region}/articles")).json()["total"] == 3
    events = (await client.get("/api/events", params={"region": region})).json()
    assert events["total"] == 1 and events["items"][0]["article_count"] == 3
    detail = await client.get("/api/events/" + str(business["event_id"]))
    assert len(detail.json()["articles"]) == 3 and "PRIVATE" not in detail.text
    policies = (await client.get("/api/policies", params={"region": region})).json()
    assert policies["total"] == 1
    assert (
        await client.get("/api/policies/" + policies["items"][0]["id"])
    ).status_code == 200
    assert (
        await client.get("/api/minerals/铜/policies", params={"region": region})
    ).json()["total"] == 1
    searched = (await client.get("/api/search", params={"q": "PRIVATE"})).json()
    assert all(
        "PRIVATE" not in str(item)
        for values in (searched["articles"], searched["events"], searched["policies"])
        for item in values
    )


async def test_price_provenance_facets_and_current_digest_stats(business):
    client = business["client"]
    prices = (
        await client.get(
            "/api/minerals/锂/prices", params={"source": business["root"] + "/prices"}
        )
    ).json()
    assert len(prices) == 2 and Decimal(prices[0]["change_pct"]) == 10
    assert prices[0]["product"] == "TEST FIXTURE" and prices[0]["source_url"].endswith(
        "/quote"
    )
    regions = (await client.get("/api/regions")).json()
    region = next(item for item in regions if item["name"] == business["region"])
    assert region["article_count"] == 3 and region["trend"] == "up"
    for kind in ("daily", "weekly", "monthly"):
        response = await client.get("/api/digest/" + kind)
        assert response.status_code == 200, response.text
        assert (
            response.json()["kind"] == kind
            and response.json()["timezone"] == "Asia/Shanghai"
        )
        assert all(
            item["article_id"] != str(business["ids"][3])
            for item in response.json()["sources"]
        )
    for path in (
        "/api/trends/hot-minerals",
        "/api/trends/price-alerts",
        "/api/trends/policy-updates",
    ):
        assert (await client.get(path)).status_code == 200


async def test_real_redis_cache_ttl_and_withdrawal_invalidation(business):
    await app.state.redis.ping()
    client = business["client"]
    for path, ttl in [
        ("/api/articles/hot", 300),
        ("/api/trends/hot-minerals", 1800),
        ("/api/digest/daily", 3600),
    ]:
        await invalidate_public_cache()
        first = await client.get(path)
        second = await client.get(path)
        assert first.headers["x-cache"] == "MISS"
        assert second.headers["x-cache"] == "HIT"
        assert ttl - 2 <= int(second.headers["x-cache-ttl"]) <= ttl
    first_id = str(business["ids"][0])
    assert first_id in (await client.get("/api/articles/hot")).text
    withdrawn = await client.patch(
        "/api/v1/admin/articles/" + first_id,
        json={"status": "processed"},
        headers=business["headers"],
    )
    assert withdrawn.status_code == 200
    assert first_id not in (await client.get("/api/articles/hot")).text


async def test_api_keys_and_email_subscription_ownership(business):
    client, headers = business["client"], business["headers"]
    assert (await client.get("/api/open/articles")).status_code == 401
    response = await client.post(
        "/api/api-keys", json={"name": "test client"}, headers=headers
    )
    assert response.status_code == 201, response.text
    secret, key_id = response.json()["key"], response.json()["id"]
    key_header = {"X-API-Key": secret}
    assert (
        await client.get("/api/open/articles", headers=key_header)
    ).status_code == 200
    listed = (await client.get("/api/api-keys", headers=headers)).json()
    assert "key" not in listed[0] and "token_hash" not in listed[0]
    async with business["factory"]() as db:
        stored = await db.get(APIKey, key_id)
        assert stored.token_hash != secret
    assert (
        await client.delete(
            "/api/api-keys/" + key_id, headers=business["other_headers"]
        )
    ).status_code == 404
    assert (
        await client.delete("/api/api-keys/" + key_id, headers=headers)
    ).status_code == 204
    assert (
        await client.get("/api/open/articles", headers=key_header)
    ).status_code == 401
    assert (
        await client.get("/api/articles", headers={"X-API-Key": "invalid-key-" * 3})
    ).status_code == 401
    payload = {
        "email": business["email"],
        "subscribed_minerals": ["锂", "锂"],
        "subscribed_regions": ["中国"],
    }
    subscribed = await client.post("/api/subscriptions", json=payload, headers=headers)
    assert subscribed.status_code == 200 and subscribed.json()[
        "subscribed_minerals"
    ] == ["锂"]
    path = "/api/subscriptions/" + business["email"]
    assert (
        await client.get(path, headers=business["other_headers"])
    ).status_code == 403
    assert (await client.get(path, headers=headers)).json()["email"] == business[
        "email"
    ]
    assert (await client.delete(path, headers=headers)).status_code == 204
    assert (await client.get(path, headers=headers)).status_code == 404


async def test_multi_select_filters_keep_group_intersection(business):
    """Multi-select is OR within a group and AND across groups."""
    client, region = business["client"], business["region"]
    response = await client.get(
        "/api/articles",
        params=[("regions", region), ("minerals", "unlisted"), ("minerals", "铜")],
    )
    assert response.status_code == 200
    assert response.json()["total"] == 3
    empty = await client.get(
        "/api/articles", params=[("regions", "unlisted"), ("minerals", "铜")]
    )
    assert empty.json()["total"] == 0
    invalid = await client.get("/api/articles", params={"minerals": " "})
    assert invalid.status_code == 422


async def test_project_coordinates_require_published_source_metadata(business):
    """Do not fabricate markers or leak coordinates from pending evidence."""
    async with business["factory"].begin() as db:
        public = await db.get(Article, business["ids"][0])
        public.projects = ["Verified Mine", "Unlocated Mine", "Invalid Mine"]
        public.raw_json = {
            "project_locations": [
                {"name": "Verified Mine", "latitude": -22.4, "longitude": -68.9},
                {"name": "Invalid Mine", "latitude": True, "longitude": 190},
            ]
        }
        private = await db.get(Article, business["ids"][3])
        private.projects = ["Private Mine"]
    response = await business["client"].get(
        "/api/regions/" + business["region"] + "/projects"
    )
    assert response.status_code == 200
    rows = {x["name"]: x for x in response.json()}
    assert set(rows) == {"Verified Mine", "Unlocated Mine", "Invalid Mine"}
    assert rows["Verified Mine"]["latitude"] == -22.4
    assert rows["Unlocated Mine"]["latitude"] is None
    assert rows["Invalid Mine"]["longitude"] is None


async def test_source_delete_requires_admin_and_preserves_provenance(business):
    """Deletion cannot remove a source still cited by stored articles."""
    async with business["factory"]() as db:
        article = await db.get(Article, business["ids"][0])
        source_id = article.source_id
    endpoint = f"/api/v1/admin/sources/{source_id}"
    assert (await business["client"].delete(endpoint)).status_code == 401
    assert (
        await business["client"].delete(endpoint, headers=business["other_headers"])
    ).status_code == 403
    assert (
        await business["client"].delete(endpoint, headers=business["headers"])
    ).status_code == 409


async def test_source_forms_crud_and_duplicate_address(business, monkeypatch):
    """Return a clear conflict and support the actual source editor contract."""
    from app.api import routes

    async def trusted_dns(url):
        return None

    monkeypatch.setattr(routes, "validate_public_url", trusted_dns)
    async with business["factory"]() as db:
        article = await db.get(Article, business["ids"][0])
        existing = await db.get(Source, article.source_id)
        existing_url = existing.url
    values = {
        "name": "EDITOR TEST",
        "url": existing_url,
        "type": "rss",
        "category": "news",
        "language": "en",
        "authority_score": 5,
        "fetch_interval": 900,
        "active": True,
        "config_json": {},
    }
    client, headers = business["client"], business["headers"]
    duplicate = await client.post("/api/v1/admin/sources", json=values, headers=headers)
    assert duplicate.status_code == 409
    values["url"] = business["root"] + "/unused-feed"
    created = await client.post("/api/v1/admin/sources", json=values, headers=headers)
    assert created.status_code == 201
    identity = created.json()["id"]
    try:
        values.update(authority_score=8, active=False)
        edited = await client.put(
            "/api/v1/admin/sources/" + identity, json=values, headers=headers
        )
        assert edited.status_code == 200
        assert edited.json()["authority_score"] == 8
        assert edited.json()["active"] is False
        conflict = await client.put(
            "/api/v1/admin/sources/" + identity,
            json={**values, "url": existing_url},
            headers=headers,
        )
        assert conflict.status_code == 409
        removed = await client.delete(
            "/api/v1/admin/sources/" + identity, headers=headers
        )
        assert removed.status_code == 204
    finally:
        async with business["factory"].begin() as db:
            await db.execute(delete(Source).where(Source.url == values["url"]))
