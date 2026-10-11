"""Inspect public price markup through the production robots-aware transport."""

import asyncio
from pathlib import Path

from bs4 import BeautifulSoup

from pipeline.fetchers.transport import FetchTransport
from pipeline.fetchers.web_fetcher import WebFetcher
from pipeline.schemas import SourceDefinition


async def main() -> None:
    transport = FetchTransport({"min_interval": 1})
    response = await transport.get("https://www.100ppi.com/sf/")
    response.raise_for_status()
    html = response.text
    if "现期表" not in html:
        fetcher = WebFetcher(
            SourceDefinition(
                name="PPI probe",
                url="https://www.100ppi.com/sf/",
                type="web",
                category="price",
                authority_score=8,
                parser_config={"wait_for_selector": "table"},
            ),
            transport,
        )
        html = await fetcher.render("https://www.100ppi.com/sf/")
    folder = Path("artifacts")
    folder.mkdir(exist_ok=True)
    (folder / "ppi-public.html").write_text(html, encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    print(
        {
            "status": response.status_code,
            "title": soup.title.get_text() if soup.title else None,
        }
    )
    for row in soup.select("tr"):
        if "碳酸锂" in row.get_text():
            print(str(row)[:4000])
    for anchor in soup.select("a[href]"):
        if anchor.get_text(strip=True) == "现期表":
            print({"href": anchor["href"]})


if __name__ == "__main__":
    asyncio.run(main())
