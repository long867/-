"""Bounded Crossref journal tracking with exact DOI and publication precision."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlsplit

from pipeline.config.research import RESEARCH_DIRECTIONS
from pipeline.fetchers.base import BaseFetcher, plain_text
from pipeline.schemas import RawArticle, SourceDefinition

PATTERNS = {
    "exploration": (
        r"exploration|deposit|geochron|orebody|metallogen|pegmatite|geolog|litholog"
    ),
    "processing": r"flotation|leaching|hydrometall|extraction|beneficiation|smelting",
    "recycling": r"recycl|spent batter|circular|recovery from|secondary resource",
    "environment": r"tailings|environment|sustainab|carbon|remediation|waste",
    "digital": r"machine learning|deep learning|neural|intelligen|safety|rock fracture",
    "governance": r"policy|policies|governance|politic|supply chain|economic|social",
}


def scholarly_source(source: SourceDefinition) -> bool:
    """Restrict academic processing to the supported public journal endpoint."""
    parts = urlsplit(source.url)
    return bool(
        source.type == "api"
        and source.category == "report"
        and source.parser_config.get("adapter") == "crossref_journal"
        and parts.scheme == "https"
        and parts.hostname == "api.crossref.org"
        and re.fullmatch(r"/journals/\d{4}-\d{3}[\dXx]/works", parts.path)
    )


def publication(row: dict[str, Any]) -> tuple[datetime | None, str | None, str]:
    """Prefer online publication; preserve month/year-only dates as such."""
    for key in ("published-online", "published", "published-print", "issued"):
        parts = row.get(key, {}).get("date-parts", [])
        if not parts or not isinstance(parts[0], list) or not parts[0]:
            continue
        values = parts[0]
        try:
            year = int(values[0])
            month = int(values[1]) if len(values) > 1 else 1
            day = int(values[2]) if len(values) > 2 else 1
            stamp = datetime(year, month, day, tzinfo=UTC)
        except (TypeError, ValueError, OverflowError):
            continue
        precision = "day" if len(values) > 2 else "month" if len(values) > 1 else "year"
        length = {"day": 10, "month": 7, "year": 4}[precision]
        return stamp, stamp.date().isoformat()[:length], precision
    return None, None, "unknown"


def directions(text: str, default: str) -> list[str]:
    """Identify research themes without inventing studied minerals or locations."""
    result = [
        key for key, pattern in PATTERNS.items() if re.search(pattern, text, re.I)
    ]
    if not result and default in RESEARCH_DIRECTIONS:
        result.append(default)
    return result


class ScholarlyFetcher(BaseFetcher):
    async def fetch(self) -> list[RawArticle]:
        """Read recent deposited metadata; never crawl paywalled full texts."""
        if not scholarly_source(self.source):
            raise ValueError("Unsupported scholarly endpoint")
        now = datetime.now(UTC)
        days = min(max(int(self.config.get("lookback_days", 365)), 1), 730)
        limit = min(max(int(self.config.get("max_items", 8)), 1), 50)
        since = (now - timedelta(days=days)).date()
        params = {
            "filter": (
                f"type:journal-article,from-pub-date:{since},"
                f"until-pub-date:{now.date()}"
            ),
            "sort": "published",
            "order": "desc",
            "rows": limit,
        }
        url = self.source.url + "?" + urlencode(params)
        response = await self.transport.get(url, {})
        response.raise_for_status()
        rows = response.json().get("message", {}).get("items")
        if not isinstance(rows, list):
            raise ValueError("Crossref did not return journal metadata")
        seen: set[str] = set()
        articles = []
        for row in rows:
            if not isinstance(row, dict) or row.get("type") != "journal-article":
                continue
            doi = str(row.get("DOI", "")).strip().lower()
            titles = row.get("title", [])
            title = plain_text(str(titles[0])) if titles else ""
            if (
                not re.fullmatch(r"10\.\d{4,9}/[^\s<>]+", doi)
                or doi in seen
                or not title
                or re.match(
                    r"^(retraction|corrigendum|erratum|editorial)\b", title, re.I
                )
                or any(
                    update.get("type") == "retraction"
                    for update in row.get("update-to", [])
                )
            ):
                continue
            stamp, date_label, precision = publication(row)
            if stamp is None or stamp > now:
                continue
            seen.add(doi)
            abstract = plain_text(str(row.get("abstract") or ""))[:16000]
            authors, institutions = [], []
            for author in row.get("author", [])[:40]:
                name = (
                    " ".join(
                        str(author.get(key) or "").strip()
                        for key in ("given", "family")
                    ).strip()
                    or str(author.get("name") or "").strip()
                )
                if name:
                    authors.append(name[:200])
                for affiliation in author.get("affiliation", []):
                    if affiliation.get("name"):
                        institutions.append(str(affiliation["name"])[:300])
            journals = row.get("container-title", [])
            metadata = {
                "document_kind": "research_paper",
                "provider": "Crossref",
                "doi": doi,
                "journal": str(journals[0]) if journals else self.source.name,
                "publisher": str(row.get("publisher") or "")[:300],
                "authors": authors,
                "institutions": sorted(set(institutions))[:30],
                "research_directions": directions(
                    title + "\n" + abstract, self.config.get("direction", "")
                ),
                "abstract_available": bool(abstract),
                "evidence_scope": "abstract" if abstract else "bibliographic",
                "published_date": date_label,
                "date_precision": precision,
                "publication_type": "journal-article",
                "full_text": False,
            }
            articles.append(
                await self.article(
                    title=title,
                    content=abstract or title,
                    url="https://doi.org/" + doi,
                    published_at=stamp,
                    raw_json=metadata,
                )
            )
        self.result.articles = articles
        return articles
