"""Public PPI spot quotes: dated source rows, exact units and stable series IDs."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from pipeline.fetchers.base import BaseFetcher
from pipeline.fetchers.web_fetcher import WebFetcher
from pipeline.schemas import RawArticle


def parse_ppi_quote(html: str, page_url: str) -> tuple[dict, str, str, datetime]:
    """Reject challenge pages, missing dates, ambiguous rows and changed units."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日商品现货与期货价格对比表", title)
    if not match:
        raise ValueError("PPI page has no dated spot table")
    day = datetime(*map(int, match.groups()), tzinfo=ZoneInfo("Asia/Shanghai"))
    if day.date() > datetime.now(ZoneInfo("Asia/Shanghai")).date():
        raise ValueError("Future-dated PPI quote")
    text = soup.get_text(" ", strip=True)
    units = re.search(r"黄金为元/克[^。]+其余元/吨。", text)
    if not units:
        raise ValueError("PPI quote unit could not be verified")
    rows: list[tuple[str, str]] = []
    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) >= 4 and cells[0].get_text(strip=True) == "碳酸锂":
            price = cells[1].get_text(strip=True)
            if re.fullmatch(r"\d+(?:\.\d+)?", price):
                rows.append((price, row.get_text(" ", strip=True)))
    if len(rows) != 1 or Decimal(rows[0][0]) <= 0:
        raise ValueError("PPI lithium spot row is missing or ambiguous")
    value, original_row = rows[0]
    observation = {
        "mineral": "锂",
        "product": "碳酸锂（生意社现期表现货口径）",
        "price_type": "spot",
        "price": value,
        "unit": "吨",
        "currency": "CNY",
        "date": day.date().isoformat(),
        "source": "https://www.100ppi.com/sf/1162.html#spot",
        "source_url": page_url,
    }
    evidence = (
        f"{title}\n原表字段：商品、现货价格、期货合约、期货结算价格、"
        f"现期差及现期差百分比。\n{original_row}\n{units.group()}"
    )
    return observation, evidence, title, day.astimezone(UTC)


class PPIPriceFetcher(BaseFetcher):
    """Discover recent public tables; never substitute futures for missing spot data."""

    async def html(self, url: str, body: str) -> str:
        """Use ordinary browser rendering only when the table requires JavaScript."""
        if (
            "商品现货与期货价格对比表" in body
            and BeautifulSoup(body, "html.parser").title
        ):
            return body
        if not self.config.get("dynamic"):
            raise ValueError("PPI public table requires browser rendering")
        return await WebFetcher(self.source, self.transport).render(url)

    async def fetch(self) -> list[RawArticle]:
        response = await self.transport.get(self.source.url, self.headers)
        if not self.checkpoint(response):
            return []
        html = await self.html(str(response.url), response.text)
        latest, _, _, _ = parse_ppi_quote(html, str(response.url))
        urls = [str(response.url)]
        for anchor in BeautifulSoup(html, "html.parser").select("a[href]"):
            url = urljoin(self.source.url, str(anchor["href"]))
            if (
                urlsplit(url).netloc == urlsplit(self.source.url).netloc
                and re.fullmatch(r"/sf/day-\d{4}-\d{2}-\d{2}\.html", urlsplit(url).path)
                and url not in urls
            ):
                urls.append(url)
        seen_dates: set[str] = set()
        articles: list[RawArticle] = []
        budget = int(self.config.get("max_items", 10))
        for url in urls[: budget + 1]:
            try:
                if url != str(response.url):
                    page = await self.transport.get(url)
                    page.raise_for_status()
                    page_html = await self.html(str(page.url), page.text)
                else:
                    page_html = html
                quote, evidence, _, published = parse_ppi_quote(page_html, url)
                if quote["date"] in seen_dates:
                    continue
                seen_dates.add(quote["date"])
                # A stable dated article URL prevents current-page snapshot duplicates.
                article_url = (
                    f"https://www.100ppi.com/sf/day-{quote['date']}.html#lithium-spot"
                )
                article = await self.article(
                    url=article_url,
                    title=f"{quote['date']} 生意社碳酸锂现货价格为"
                    f"{quote['price']}元/吨",
                    content=evidence,
                    published_at=published,
                    raw_json={
                        "price_observation": quote,
                        "date_precision": "day",
                        "original_row": evidence,
                        "product_grade": "not_specified_by_source",
                    },
                )
                article.language = "zh"
                articles.append(article)
                self.result.prices.append(quote)
                if len(articles) >= budget:
                    break
            except (ValueError, OSError, httpx.HTTPError) as exc:
                self.result.errors.append("ppi_price:" + type(exc).__name__)
        self.result.articles = articles
        return articles
