"""Do not confuse a government's document issue and page metadata dates."""

import pytest

from pipeline.fetchers.web_fetcher import WebFetcher
from pipeline.schemas import SourceDefinition


@pytest.mark.parametrize("include_evidence", [True, False])
async def test_publication_and_effective_dates_require_literal_document_evidence(
    include_evidence,
):
    source = SourceDefinition(
        name="政策原文",
        url="https://www.gov.cn/example",
        type="web",
        category="policy",
        region="中国",
        language="zh",
        authority_score=10,
        parser_config={
            "document_kind": "regulation",
            "content_selector": ".policy",
            "publication_date": "2024-11-08",
            "publication_date_evidence": "2024年11月8日修订通过",
            "effective_date": "2025-07-01",
            "effective_date_evidence": "本法自2025年7月1日起施行",
        },
    )
    text = (
        "中华人民共和国矿产资源法。为了促进矿产资源合理开发利用，加强矿产资源保护，推动矿业高质量发展。"
        * 3
    )
    if include_evidence:
        text += "2024年11月8日修订通过。本法自2025年7月1日起施行。"
    html = (
        '<html><head><title>矿产资源法</title><meta property="article:published_time" '
        'content="2026-07-24T00:00:00Z"></head><body>'
        f'<div class="policy">{text}</div></body></html>'
    )
    fetcher = WebFetcher(source)
    row = await fetcher.parse_page(source.url, html)
    assert row.raw_json["document_kind"] == "regulation"
    if include_evidence:
        assert row.published_at.date().isoformat() == "2024-11-08"
        assert row.raw_json["effective_date"] == "2025-07-01"
        assert row.raw_json["publication_basis"] == "document_issue_date"
    else:
        assert "effective_date" not in row.raw_json
        assert "publication_basis" not in row.raw_json
