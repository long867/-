"""Cross-check fully dated public SunSirs rows against explicit PPI unit evidence."""

import hashlib
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as BrowserTimeout
from playwright.async_api import async_playwright

from pipeline.fetchers.base import BaseFetcher
from pipeline.fetchers.http import validate_public_url
from pipeline.fetchers.resolver import public_addresses
from pipeline.fetchers.web_fetcher import WebFetcher
from pipeline.schemas import RawArticle


def parse_daily_table(html: str) -> tuple[date, date, dict[str, tuple[str, str, str]]]:
    """Read fully dated prices, using commodity IDs rather than ambiguous labels."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one(".name")
    match = re.search(
        r"Price Chart\s*-\s*(\d{2})/(\d{2})/(\d{4})",
        heading.get_text(" ", strip=True) if heading else "",
    )
    if not match:
        raise ValueError("Missing full daily quotation date")
    dd, mm, yyyy = map(int, match.groups())
    current = date(yyyy, mm, dd)
    if current > datetime.now(ZoneInfo("Asia/Shanghai")).date():
        raise ValueError("Future daily quotation date")
    table = None
    for candidate in soup.select("table"):
        header = candidate.find("tr")
        if (
            header
            and "Commodity" in header.get_text()
            and "Sectors" in header.get_text()
        ):
            table = candidate
            break
    if table is None:
        raise ValueError("Daily quotation columns missing")
    columns = [
        cell.get_text(strip=True)
        for cell in table.find("tr").find_all(["td", "th"], recursive=False)
    ]
    if len(columns) != 5 or columns[3] != current.strftime("%m-%d"):
        raise ValueError("Daily quotation column dates disagree")
    previous = date(current.year, *map(int, columns[2].split("-")))
    if previous > current:
        previous = previous.replace(year=current.year - 1)
    if not timedelta(0) < current - previous <= timedelta(days=31):
        raise ValueError("Ambiguous previous quotation date")
    rows = {}
    for row in table.select("tr")[1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) != 5:
            continue
        anchor = cells[0].find("a", href=True)
        key = (
            re.fullmatch(r"(?:/uk/)?prodetail-(\d+)\.html", anchor["href"])
            if anchor
            else None
        )
        if not key:
            continue
        values = [cell.get_text(strip=True).replace(",", "") for cell in cells[2:4]]
        if not all(
            re.fullmatch(r"\d+(?:\.\d+)?", v) and Decimal(v) > 0 for v in values
        ):
            continue
        if key[1] in rows:
            raise ValueError("Duplicate commodity ID in daily table")
        rows[key[1]] = (anchor.get_text(strip=True), values[0], values[1])
    return current, previous, rows


def verified_benchmark(
    html: str, day: date, literal: str, product: dict[str, str]
) -> tuple[str, str]:
    """Verify same-product value/date and unit without guessing a year or grade."""
    soup = BeautifulSoup(html, "html.parser")
    price, unit, stamp, name = (
        soup.select_one(selector)
        for selector in (
            ".price-fb01_1",
            ".price-fb01_2",
            ".post_date_li",
            ".pricename",
        )
    )
    if any(node is None for node in (price, unit, stamp, name)):
        raise ValueError("Incomplete reference quotation")
    if (
        product["verify_name"] not in name.get_text(strip=True)
        or Decimal(price.get_text(strip=True).replace(",", "")) != Decimal(literal)
        or not re.search(r"\b" + day.strftime("%m-%d") + r"\b", stamp.get_text())
    ):
        raise ValueError("Daily and reference quotation disagree")
    unit_text = unit.get_text(strip=True)
    if not re.fullmatch(r"元/(吨|千克|克|湿吨|标吨)", unit_text):
        raise ValueError("Unsupported or ambiguous quotation unit")
    evidence = (
        f"{name.get_text(' ', strip=True)} 基准价格 {literal} {unit_text} "
        f"{stamp.get_text(' ', strip=True)}"
    )
    return unit_text.split("/")[1], evidence


def parse_product_history(html: str, english: str) -> list[tuple[date, str]]:
    """Read explicitly dated product rows when the bulk table has not updated yet."""
    soup = BeautifulSoup(html, "html.parser")
    observations = []
    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)
        if (
            len(cells) != 4
            or cells[0].get_text(strip=True).casefold() != english.casefold()
        ):
            continue
        literal = cells[2].get_text(strip=True).replace(",", "")
        stamp = cells[3].get_text(strip=True)
        if not re.fullmatch(r"\d+(?:\.\d+)?", literal) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", stamp
        ):
            continue
        day = date.fromisoformat(stamp)
        if (
            day <= datetime.now(ZoneInfo("Asia/Shanghai")).date()
            and Decimal(literal) > 0
        ):
            observations.append((day, literal))
    if not observations:
        raise ValueError("No fully dated product history")
    return sorted(set(observations), reverse=True)


class DailyPriceFetcher(BaseFetcher):
    """Reuse one ordinary browser serially, keeping collection small-server friendly."""

    async def _html(self, url: str) -> str:
        await validate_public_url(url)
        await self.transport.robots(url)
        await self.transport.pace(url)
        response = await self._page.goto(
            url, wait_until="domcontentloaded", timeout=30000
        )
        if response is None or response.status >= 400:
            raise ValueError("Public quotation navigation failed")
        selector = ".price-fb01_1"
        if urlsplit(url).hostname == "www.sunsirs.com":
            selector = ".f-list .price" if "prodetail-" in url else ".name"
        await self._page.wait_for_selector(selector, timeout=15000)
        html = await self._page.content()
        if len(html.encode()) > self.transport.settings.FETCH_MAX_BYTES:
            raise ValueError("Quotation page exceeds configured response size")
        return html

    async def _collect(self) -> list[RawArticle]:
        products = self.config.get("products", [])
        if not products or len(products) > 40:
            raise ValueError("Public quotation batch must contain 1 to 40 products")
        current, previous, rows = parse_daily_table(await self._html(self.source.url))
        articles = []
        for product in products:
            key = str(product["id"])
            if not re.fullmatch(r"\d{1,6}", key):
                raise ValueError("Invalid public quotation product ID")
            if key not in rows:
                self.result.errors.append("daily_price:missing_product:" + key)
                continue
            english, old_value, value = rows[key]
            reference = f"https://www.100ppi.com/rawmex/detail-{key}.html"
            try:
                reference_html = await self._html(reference)
                observations = [(previous, old_value), (current, value)]
                try:
                    unit, proof = verified_benchmark(
                        reference_html, current, value, product
                    )
                except ValueError:
                    history_url = f"https://www.sunsirs.com/uk/prodetail-{key}.html"
                    history = parse_product_history(
                        await self._html(history_url), english
                    )
                    newest, newest_value = history[0]
                    unit, proof = verified_benchmark(
                        reference_html, newest, newest_value, product
                    )
                    observations = history[:7]
                for day, literal in observations:
                    quote: dict[str, Any] = {
                        "mineral": product["mineral"],
                        "product": product["name"],
                        "price": literal,
                        "unit": unit,
                        "currency": "CNY",
                        "date": day.isoformat(),
                        "price_type": "benchmark",
                        "source": f"https://www.sunsirs.com/uk/prodetail-{key}.html#daily",
                        "source_url": f"https://www.sunsirs.com/uk/prodetail-{key}.html",
                        "source_name": "生意社 / SunSirs",
                    }
                    evidence = (
                        f"生意社 / SunSirs 公开每日报价：{day.isoformat()}，"
                        f"{product['name']}（{english}）参考价 {literal}元/{unit}。\n"
                        f"原始报价产品 ID：{key}。原始日期 {day.isoformat()}，"
                        f"价格 {literal}；同产品中文单位核验如下。\n"
                        f"单位核验来自 {reference}：{proof}。\n"
                        "价格口径：公开参考价，不能等同于原矿报价或实际成交价。"
                    )
                    article = await self.article(
                        url=f"https://www.sunsirs.com/uk/prodetail-{key}.html",
                        title=f"{day.isoformat()} {product['name']}公开参考价 "
                        f"{literal}元/{unit}",
                        content=evidence,
                        published_at=datetime.combine(
                            day, datetime.min.time(), ZoneInfo("Asia/Shanghai")
                        ).astimezone(UTC),
                        raw_json={
                            "price_observation": quote,
                            "unit_evidence_url": reference,
                            "date_precision": "day",
                            "original_row": evidence,
                            "snapshot_digest": hashlib.sha256(
                                f"{key}|{day}".encode()
                            ).hexdigest()[:24],
                        },
                    )
                    article.language = "zh"
                    articles.append(article)
                    self.result.prices.append(quote)
            except (
                ValueError,
                InvalidOperation,
                OSError,
                httpx.HTTPError,
                BrowserTimeout,
            ) as exc:
                self.result.errors.append(f"daily_price:{key}:{type(exc).__name__}")
        if not self.result.prices:
            raise ValueError("No independently verified daily mineral quotations")
        self.result.articles = articles
        return articles

    async def fetch(self) -> list[RawArticle]:
        """Check robots on every URL and reject unsafe or external destinations."""
        rules = []
        for host in ("www.sunsirs.com", "www.100ppi.com"):
            addresses = await public_addresses(host)
            rules.append(f"MAP {host} {addresses[0]}")
        async with async_playwright() as api:
            browser = await api.chromium.launch(
                headless=True,
                channel=self.transport.settings.FETCH_BROWSER_CHANNEL
                or self.config.get("browser_channel"),
                args=["--host-resolver-rules=" + ", ".join(rules)],
            )
            context = await browser.new_context(
                user_agent=self.transport.settings.USER_AGENT
            )
            guard = WebFetcher(self.source, self.transport)

            async def route_handler(route):
                host = urlsplit(route.request.url).netloc
                if (
                    host not in {"www.sunsirs.com", "www.100ppi.com"}
                    or route.request.resource_type == "stylesheet"
                    or (
                        route.request.is_navigation_request()
                        and route.request.frame.parent_frame is not None
                    )
                ):
                    await route.abort()
                else:
                    await guard._guard(route, host)

            await context.route("**/*", route_handler)
            try:
                self._page = await context.new_page()
                return await self._collect()
            finally:
                await context.unroute_all(behavior="ignoreErrors")
                await browser.close()
