"""Multilingual country detection avoids substring and jurisdiction collisions."""

import pytest

from app.rag.conversation_context import ConversationContext, remember
from pipeline.config.countries import country_catalog
from pipeline.processors.entities import extract_regions


def test_un_directory_is_not_a_coverage_claim():
    rows = country_catalog()
    assert len(rows) == 250
    assert len({r["iso2"] for r in rows}) == len(rows)
    assert len({r["name"] for r in rows}) == len(rows)
    assert next(r for r in rows if r["iso2"] == "CD")["name"] == "刚果（金）"
    assert next(r for r in rows if r["iso2"] == "EU")["kind"] == "organization"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Copper exploration in Papua New Guinea", ["巴布亚新几内亚"]),
        ("赤道几内亚和几内亚比绍的矿业项目", ["几内亚比绍", "赤道几内亚"]),
        (
            "Democratic Republic of the Congo and Republic of Congo",
            ["刚果（布）", "刚果（金）"],
        ),
        ("The Democratic Republic of the Congo copper mine", ["刚果（金）"]),
        ("South Korea and North Korea", ["朝鲜", "韩国"]),
        ("Santa Elena mine, Mexico", ["墨西哥"]),
        ("Georgia state, Jordan Smith and Chad Jones", []),
        ("Una reunión de inversores en el proyecto Montserrat", []),
        ("Georgia's country of Georgia investment", ["格鲁吉亚"]),
        (
            "Mali, Burkina Faso, Malawi and Senegal gold mining",
            ["塞内加尔", "布基纳法索", "马拉维", "马里"],
        ),
        ("Côte d'Ivoire, Казахстан, كازاخستان", ["哈萨克斯坦", "科特迪瓦"]),
    ],
)
def test_country_names_are_grounded_and_disambiguated(text, expected):
    assert extract_regions(text) == sorted(expected)


def test_country_context_reaches_consultation_memory():
    context = remember(ConversationContext(), "分析马拉维的石墨矿与塞内加尔的金矿政策")
    assert {"马拉维", "塞内加尔"} <= set(context.regions)


def test_reported_policy_is_not_imported_as_a_legal_document():
    from pipeline.processors.backfill import EditorialDocument, validate_editorial
    from pipeline.schemas import RawArticle, SourceDefinition

    summary = (
        "马拉维铜矿项目正在推进。报道关注当地勘探工作、项目主体的公开信息以及开发进度。"
        "原始报道介绍了矿产开发的相关情况，尚未提供新的法定生效日期或完整法规文本。"
        "该条资料属于矿业新闻，涉及的政策动向仍需结合政府文件进一步核对。"
    )
    source = SourceDefinition(
        name="Country news",
        url="https://example.com/feed",
        type="rss",
        category="news",
        authority_score=7,
        parser_config={"require_mineral_match": True},
    )
    article = RawArticle(
        source_name=source.name,
        url="https://example.com/copper",
        title="铜矿项目动态",
        content=summary,
        language="zh",
        category="news",
    )
    result = validate_editorial(
        EditorialDocument(article, source),
        {"title_zh": article.title, "summary_zh": summary, "category": "policy"},
        {},
    )
    assert result["category"] == "news"
