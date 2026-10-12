"""Evidence, scoring and normalization tests with realistic adversarial inputs."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.rag.chunking import split_evidence
from app.rag.embedding import embed, validate_vector
from app.rag.qa import Claim, GroundedAnswer, validate_claims
from app.rag.retriever import reciprocal_rank_fusion, search_terms
from app.schemas.api import Citation, Credentials, PriceInput, SourceInput
from pipeline.fetchers.collect import timestamp
from pipeline.fetchers.http import canonical_url
from pipeline.processors.enrich import enrich
from pipeline.processors.entities import extract_entities


@pytest.mark.parametrize(
    "content",
    [
        "铜矿政策更新。\n\n保留原始数字 123.45 USD/吨。" * 60,
        "Copper mining in Chile.\nRepeated  spaces  matter. " * 70,
        "这是没有英文分隔符的中文正文" * 100,
    ],
    ids=["chinese-paragraphs", "repeated-spaces", "chinese-contiguous"],
)
def test_evidence_offsets_are_verbatim(content: str) -> None:
    spans = split_evidence(content)
    assert len(spans) > 1
    for span in spans:
        assert content[span.start : span.end] == span.text
        assert span.start >= 0 and span.end > span.start
    assert spans[0].start == 0
    assert spans[-1].end == len(content.rstrip())


@pytest.mark.parametrize("matcher", ["spacy", "dictionary"])
def test_bilingual_entity_boundaries(monkeypatch, matcher: str) -> None:
    """Both matchers preserve canonical names and reject partial English words."""
    monkeypatch.setenv("ENTITY_MATCHER", matcher)
    entities = extract_entities(
        "BHP expands a copper project in Chile. 铀和稀土政策。 golden opportunity."
    )
    assert "铜" in entities["minerals"]
    assert "智利" in entities["regions"]
    assert "BHP" in entities["companies"]
    assert "铀" in entities["minerals"]
    assert "金" not in entities["minerals"]


def test_chinese_queries_expand_into_original_language() -> None:
    terms = search_terms("智利铜矿的产量如何变化？")
    assert "copper" in terms and "chile" in terms


def test_rank_fusion_rewards_cross_channel_evidence() -> None:
    first, second, shared = uuid4(), uuid4(), uuid4()
    scores = reciprocal_rank_fusion([[first, shared], [second, shared]])
    assert max(scores, key=scores.get) == shared


@pytest.mark.parametrize("bad", [[0.0] * 1024, [1.0] * 10, [float("nan")] * 1024])
def test_embedding_rejects_bad_vectors(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        validate_vector(bad)


async def test_keyword_mode_does_not_fake_embeddings(monkeypatch) -> None:
    import app.rag.embedding as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(ML_ENABLED=False, _env_file=None)
    )
    assert await embed(["copper"]) == [None]


def citation() -> Citation:
    return Citation(
        index=1,
        article_id=uuid4(),
        chunk_id=uuid4(),
        title="Evidence",
        url="https://example.com/policy",
        quote="Original text: Copper exports require permits.",
        start_char=100,
        end_char=146,
        published_at=datetime.now(UTC),
    )


def test_exact_citation_subspan() -> None:
    source = citation()
    claim = Claim(
        text="铜出口需许可", evidence=1, quote="Copper exports require permits."
    )
    answer, sources = validate_claims(GroundedAnswer(claims=[claim]), [source])
    assert answer.endswith("[1]")
    assert sources[0].start_char == 115
    assert sources[0].end_char == 146


@pytest.mark.parametrize(
    "index,quote",
    [(2, "Copper exports require permits."), (1, "Copper exports are banned forever.")],
)
def test_invented_citations_rejected(index: int, quote: str) -> None:
    with pytest.raises(ValueError):
        validate_claims(
            GroundedAnswer(claims=[Claim(text="claim", evidence=index, quote=quote)]),
            [citation()],
        )


def test_url_normalization_retains_content_identifiers() -> None:
    assert (
        canonical_url("https://EXAMPLE.com/news?id=12&utm_source=x#top")
        == "https://example.com/news?id=12"
    )
    with pytest.raises(ValueError):
        canonical_url("http://user:secret@example.com")


@pytest.mark.parametrize(
    "value", ["file:///etc/passwd", "ftp://example.com", "/relative"]
)
def test_non_http_urls_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        canonical_url(value)


def test_timestamp_does_not_invent_unknown_dates() -> None:
    assert timestamp(None) is None
    assert timestamp("invalid") is None
    assert timestamp("2026-10-09T12:00:00+08:00") == datetime(
        2026, 10, 9, 4, tzinfo=UTC
    )


async def test_no_llm_leaves_foreign_language_untranslated(monkeypatch) -> None:
    import pipeline.processors.enrich as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="", _env_file=None)
    )
    result = await enrich("Copper in Chile", "Copper supply expands in Chile.", "en", 8)
    assert result["title_zh"] is None
    assert result["is_translated"] is False
    assert "铜" in result["minerals"]
    assert 0 <= result["quality_score"] <= 100


def test_production_defaults_fail_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            SECRET_KEY="a" * 32,
            CORS_ORIGINS=["*"],
            _env_file=None,
        )


def test_password_and_token_round_trip() -> None:
    stored = hash_password("correct-long-password")
    assert verify_password("correct-long-password", stored)
    assert not verify_password("wrong", stored)
    user_id = uuid4()
    assert decode_token(create_token(user_id)) == user_id


def test_input_validation_and_email_case() -> None:
    assert (
        Credentials(email="Analyst@example.com", password="secret-password").email
        == "analyst@example.com"
    )
    with pytest.raises(ValidationError):
        SourceInput(name="bad", url="https://example.com", authority_score=11)
    with pytest.raises(ValidationError):
        PriceInput(
            mineral="铜",
            price=-1,
            unit="吨",
            currency="USD",
            date="2026-10-10",
            source="provider",
        )
