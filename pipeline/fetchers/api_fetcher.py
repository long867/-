"""JSON APIs with bounded pagination, authentication and incremental cursors."""

import hashlib
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from pipeline.fetchers.base import BaseFetcher, timestamp
from pipeline.fetchers.http import canonical_url
from pipeline.schemas import RawArticle


def lookup(value: Any, path: str, default: Any = None) -> Any:
    """Resolve dotted paths, including numeric list indexes."""
    for key in path.split(".") if path else []:
        try:
            value = value[int(key)] if isinstance(value, list) else value[key]
        except (KeyError, IndexError, TypeError, ValueError):
            return default
    return value


def query_url(url: str, key: str, value: Any) -> str:
    """Replace one pagination parameter while retaining other identifiers."""
    parts = urlsplit(url)
    pairs = [(k, v) for k, v in parse_qsl(parts.query) if k != key]
    pairs.append((key, str(value)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), ""))


class APIFetcher(BaseFetcher):
    async def fetch(self) -> list[RawArticle]:
        """Fetch a bounded window; partial failures never advance its checkpoint."""
        pagination = self.config.get("pagination", {})
        mode = pagination.get("mode", "none")
        if mode not in {"none", "page", "cursor", "next_url"}:
            raise ValueError("Unsupported pagination mode")
        url = self.source.url
        page = int(pagination.get("start", 1))
        if mode == "page":
            url = query_url(url, pagination.get("param", "page"), page)
        if mode == "cursor" and self.result.state.get("cursor"):
            url = query_url(
                url, pagination.get("param", "cursor"), self.result.state["cursor"]
            )
        if mode in {"page", "next_url"} and self.result.state.get("next_url"):
            url = self.result.state["next_url"]
            page = int(self.result.state.get("next_page", page))
        visited: set[str] = set()
        articles: list[RawArticle] = []
        pages = min(max(int(pagination.get("max_pages", 5)), 1), 50)
        max_items = min(max(int(self.config.get("max_items", 100)), 1), 5000)
        consumed = 0
        for index in range(pages):
            if url in visited:
                raise ValueError("API pagination cycle")
            if urlsplit(url).netloc != urlsplit(self.source.url).netloc:
                raise ValueError("Cross-origin pagination is forbidden")
            visited.add(url)
            conditional = self.headers if index == 0 and mode == "none" else {}
            response = await self.transport.get(url, conditional)
            if index == 0:
                if not self.checkpoint(response):
                    return []
            else:
                response.raise_for_status()
            payload = response.json()
            if self.config.get("adapter") == "yahoo_chart":
                await self.yahoo_chart(payload, response.text, url)
                break
            records = lookup(payload, self.config.get("records_path", ""))
            if self.config.get("record_format") == "columnar":
                if not isinstance(records, dict):
                    raise ValueError("Expected columnar JSON")
                lengths = {len(v) for v in records.values() if isinstance(v, list)}
                if len(lengths) != 1:
                    raise ValueError("Inconsistent columnar lengths")
                records = [
                    {
                        key: value[i]
                        for key, value in records.items()
                        if isinstance(value, list)
                    }
                    for i in range(next(iter(lengths), 0))
                ]
            if not isinstance(records, list):
                raise ValueError("records_path must resolve to an array")
            if self.config.get("adapter") == "sec_submissions":
                allowed = self.config.get(
                    "forms", ["10-K", "10-Q", "8-K", "20-F", "6-K"]
                )
                records = [row for row in records if row.get("form") in allowed]
            if not records:
                self.result.state.pop("cursor", None)
                self.result.state.pop("next_url", None)
                self.result.state.pop("next_page", None)
                break
            if mode != "none" and consumed + len(records) > max_items:
                if consumed == 0:
                    raise ValueError(
                        "API page exceeds item budget; reduce provider page size"
                    )
                self.result.state["next_url"] = url
                break
            window = records if mode != "none" else records[:max_items]
            consumed += len(window)
            for row in window:
                if not isinstance(row, dict):
                    raise ValueError("API records must be objects")
                if self.config.get("adapter") == "sec_submissions":
                    article = await self.sec_filing(row, payload)
                    if article:
                        articles.append(article)
                elif self.source.category == "price":
                    fields = self.config.get("fields", {})
                    observation = {
                        key: lookup(row, fields.get(key, key))
                        for key in ("mineral", "price", "unit", "currency", "date")
                    }
                    observation.update(self.config.get("constants", {}))
                    observation["source"] = self.source.url
                    self.result.prices.append(observation)
                else:
                    fields = self.config.get("fields", {})
                    required = {
                        key: lookup(row, fields.get(key, key))
                        for key in ("title", "content", "url")
                    }
                    if any(
                        not isinstance(value, str) or not value.strip()
                        for value in required.values()
                    ):
                        raise ValueError(
                            "API article title/content/url must be nonempty strings"
                        )
                    articles.append(
                        await self.article(
                            title=required["title"],
                            content=required["content"],
                            url=canonical_url(urljoin(url, required["url"])),
                            published_at=timestamp(
                                lookup(row, fields.get("published_at", "published_at"))
                            ),
                            raw_json={"record": row},
                        )
                    )
            if self.source.category == "price":
                digest = hashlib.sha256(response.content).hexdigest()[:24]
                articles.append(
                    await self.article(
                        title=self.source.name + " · 价格数据快照",
                        content=response.text,
                        url=f"{canonical_url(url)}#snapshot-{digest}",
                        raw_json={"snapshot_digest": digest},
                    )
                )
            token = lookup(payload, pagination.get("next_path", "next"))
            if mode == "none":
                break
            if mode == "page":
                page += 1
                url = query_url(self.source.url, pagination.get("param", "page"), page)
                self.result.state["next_page"] = page
            elif not token:
                self.result.state.pop("cursor", None)
                self.result.state.pop("next_url", None)
                self.result.state.pop("next_page", None)
                break
            elif mode == "next_url":
                url = canonical_url(urljoin(url, str(token)))
            else:
                self.result.state["cursor"] = str(token)
                url = query_url(
                    self.source.url, pagination.get("param", "cursor"), token
                )
            self.result.state["next_url"] = url
            if consumed >= max_items:
                break
        if mode != "none":
            self.result.etag = self.result.last_modified = None
        if self.config.get("adapter") != "yahoo_chart":
            self.result.articles = articles
        return self.result.articles

    async def yahoo_chart(self, payload: dict[str, Any], body: str, url: str) -> None:
        """Map aligned daily closes to futures observations without changing units."""
        records = lookup(payload, "chart.result")
        if not records or lookup(payload, "chart.error"):
            raise ValueError("Yahoo chart returned no data")
        record = records[0]
        dates = record.get("timestamp", [])
        closes = lookup(record, "indicators.quote.0.close", [])
        if len(dates) != len(closes):
            raise ValueError("Yahoo quote/date arrays are not aligned")
        constants = self.config.get("constants", {})
        for date, close in zip(dates, closes, strict=True):
            if close is not None:
                self.result.prices.append(
                    {
                        "mineral": constants["mineral"],
                        "unit": constants["unit"],
                        "currency": record["meta"]["currency"],
                        "price": str(
                            Decimal(str(close)).quantize(
                                Decimal("0.000001"), rounding=ROUND_HALF_UP
                            )
                        ),
                        "date": timestamp(date).date().isoformat(),
                        "source": self.source.url,
                    }
                )
        digest = hashlib.sha256(body.encode()).hexdigest()[:24]
        self.result.articles = [
            await self.article(
                title=self.source.name + " · 期货日收盘价格",
                content=body,
                url=f"{canonical_url(url)}#snapshot-{digest}",
                raw_json={
                    "snapshot_digest": digest,
                    "instrument": record["meta"].get("symbol"),
                },
            )
        ]

    async def sec_filing(
        self, row: dict[str, Any], payload: dict[str, Any]
    ) -> RawArticle | None:
        """Expand EDGAR metadata into original evidence for configured filing forms."""
        from pipeline.fetchers.web_fetcher import WebFetcher

        if row.get("form") not in self.config.get(
            "forms", ["10-K", "10-Q", "8-K", "20-F", "6-K"]
        ):
            return None
        cik = str(int(payload["cik"]))
        accession = row["accessionNumber"].replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{row['primaryDocument']}"
        response = await self.transport.get(url)
        response.raise_for_status()
        article = await WebFetcher(self.source, self.transport).parse_page(
            url, response.text
        )
        article.title = f"{payload['name']} · {row['form']} · {row['filingDate']}"
        article.published_at = timestamp(row["filingDate"])
        article.raw_json = {"record": row, "issuer": payload["name"], "cik": cik}
        return article
