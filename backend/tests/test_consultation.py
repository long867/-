"""Analysis must be useful without turning inference into fabricated market facts."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.rag.consultation import (
    AnswerBlock,
    evidence_spans,
    is_concept_question,
    quantities_match,
    validate_discussion,
)
from app.rag.qa_chain import (
    GroundedAnswer,
    GroundedSynthesizer,
    contextual_query,
    validate_conversation,
)
from app.schemas.api import ChatInput, Citation


def policy_source() -> Citation:
    """Return a literal permit fact, containing no actual market forecast."""
    quote = "Copper exports require permits according to the official policy."
    return Citation(
        index=1,
        article_id=uuid4(),
        chunk_id=uuid4(),
        title="铜出口许可政策",
        url="https://example.com/policy",
        quote=quote,
        start_char=20,
        end_char=20 + len(quote),
        source_name="Official policy",
        published_at=None,
    )


def test_analysis_can_explain_mechanism_without_a_literal_causal_quote():
    source = policy_source()
    result = GroundedAnswer(
        blocks=[
            AnswerBlock(
                kind="analysis",
                text="如果许可办理时间拉长，采购交付可能受到影响，但不能直接认定供应已经减少。",
                sources=[1],
            ),
            AnswerBlock(
                kind="fact", text="铜出口需要许可。", sources=[1], quote=source.quote
            ),
            AnswerBlock(
                kind="advice",
                text="建议先向供应商核对许可进度，再决定是否调整采购节奏。",
                sources=[1],
            ),
        ]
    )
    answer, sources, mode = validate_conversation(result, [source], "我们该怎么应对？")
    assert mode == "analytical"
    assert answer.startswith("分析判断：")
    assert "建议先向供应商" in answer and answer.count("[1]") == 3
    assert source.quote not in answer
    assert sources[0].quote == source.quote
    assert (sources[0].start_char, sources[0].end_char) == (
        source.start_char,
        source.end_char,
    )


def test_bad_fact_does_not_discard_independently_supported_analysis():
    source = policy_source()
    result = GroundedAnswer(
        blocks=[
            AnswerBlock(
                kind="fact",
                text="铜出口需要许可。",
                sources=[1],
                quote="This quotation was invented.",
            ),
            AnswerBlock(
                kind="analysis",
                text="出口许可可能增加交付的不确定性，需要结合办理时长判断。",
                sources=[1],
            ),
        ]
    )
    answer, sources, mode = validate_conversation(result, [source], "有什么影响？")
    assert "分析判断" in answer and "invented" not in answer
    assert mode == "analytical" and len(sources) == 1


def test_selected_fact_span_preserves_the_exact_original_occurrence():
    source = policy_source()
    repeated = source.quote + "\n" + source.quote
    source = source.model_copy(
        update={"quote": repeated, "end_char": source.start_char + len(repeated)}
    )
    result = GroundedAnswer(
        blocks=[
            AnswerBlock(kind="fact", text="铜出口需要许可。", sources=[1], span=2),
            AnswerBlock(kind="advice", text="建议先与供应商核对许可进度。"),
        ]
    )
    answer, sources, mode = validate_conversation(result, [source], "如何安排采购？")
    start, end = evidence_spans(source)[1]
    assert mode == "analytical" and "建议" in answer
    assert sources[0].quote == repeated[start:end]
    assert sources[0].start_char == source.start_char + start
    assert sources[0].end_char == source.start_char + end


def test_span_selection_never_allows_missing_evidence_or_changed_quantities():
    source = policy_source()
    for block in [
        AnswerBlock(kind="fact", text="出口需要许可。", sources=[1], span=999),
        AnswerBlock(kind="fact", text="铜出口量增加999吨。", sources=[1], span=1),
    ]:
        with pytest.raises(ValueError, match="No valid consultation paragraph"):
            validate_conversation(GroundedAnswer(blocks=[block]), [source], "铜出口？")


def test_long_literal_spans_are_bounded_without_rewriting_units():
    source = policy_source()
    quote = "Copper $8,500/tonne. " * 100
    source = source.model_copy(update={"quote": quote})
    spans = evidence_spans(source)
    assert spans and max(end - start for start, end in spans) <= 600
    assert "".join(quote[start:end] for start, end in spans) == quote


@pytest.mark.parametrize(
    ("original", "answer", "valid"),
    [
        ("6.71 billion pounds", "6.71十亿磅", True),
        ("6.71 billion pounds", "6.71亿磅", False),
        ("1,064 million tonnes", "1,064万吨", False),
        ("1,064 million tonnes", "1,064百万吨", True),
        ("6.71 billion pounds", "6.71十亿吨", False),
        ("1000 km", "1000千米", True),
    ],
)
def test_scaled_resource_numbers_cannot_silently_change_magnitude_or_unit(
    original, answer, valid
):
    assert quantities_match(original, answer) is valid


@pytest.mark.parametrize(
    "block",
    [
        AnswerBlock(kind="analysis", text="铜价预计上涨20%。", sources=[1]),
        AnswerBlock(kind="analysis", text="铜产量已经增长999吨。", sources=[1]),
        AnswerBlock(kind="advice", text="按这个策略可以保证收益。", sources=[1]),
        AnswerBlock(kind="analysis", text="供货可能承压。", sources=[9]),
        AnswerBlock(kind="analysis", text="供货可能承压 [99]。", sources=[1]),
        AnswerBlock(kind="background", text="最新报价为999元/吨。"),
        AnswerBlock(kind="background", text="政府已宣布新的出口禁令。"),
    ],
)
def test_analysis_rejects_false_precision_guarantees_and_fake_references(block):
    with pytest.raises(ValueError):
        validate_discussion(block, [policy_source()], "铜政策影响？")


def test_general_concepts_are_answered_without_pretending_to_have_live_sources():
    result = GroundedAnswer(
        blocks=[
            AnswerBlock(
                kind="background",
                text="稀土通常指17种金属元素，并非所有这些元素在地壳中的含量都很低。",
            ),
            AnswerBlock(
                kind="clarification", text="你更关心稀土的用途，还是它的供应链风险？"
            ),
        ]
    )
    answer, sources, mode = validate_conversation(result, [], "什么是稀土？")
    assert mode == "general" and sources == []
    assert "17种" in answer and "一般行业分析" in answer
    assert "未找到相关信息" not in answer


def test_qualitative_advice_does_not_require_an_arbitrary_article_citation():
    result = GroundedAnswer(
        blocks=[
            AnswerBlock(
                kind="analysis",
                text="如果供应商集中，采购交付可能更容易受单一渠道影响。",
            ),
            AnswerBlock(
                kind="advice", text="建议先整理供应商清单，再核对交期和替代渠道。"
            ),
        ]
    )
    answer, sources, mode = validate_conversation(
        result, [], "我们该如何做采购风险管理？"
    )
    assert mode == "general" and not sources and "[1]" not in answer
    assert "建议先整理供应商" in answer and "一般分析" in answer


def test_customer_scenario_quantity_is_not_mistaken_for_an_invented_market_quote():
    block = AnswerBlock(
        kind="advice", text="先核对你提到的10吨库存是否可用，再安排采购。"
    )
    assert validate_discussion(block, [], "我们目前库存10吨，该怎么安排？") == []
    with pytest.raises(ValueError):
        validate_discussion(block, [], "我们目前没有报库存数量，该怎么安排？")


def test_sparse_price_history_can_still_offer_an_explicit_analysis_framework():
    answer, sources, mode = validate_conversation(
        GroundedAnswer(
            blocks=[
                AnswerBlock(
                    kind="background",
                    text="判断趋势通常需要区分供给扩张、下游需求、库存和现货与期货口径，不能用单条报道替代价格序列。",
                )
            ]
        ),
        [],
        "2026年锂价走势如何？",
    )
    assert answer.startswith("根据现有资料，未找到相关信息")
    assert "判断趋势" in answer and mode == "general" and not sources


def test_advice_followups_keep_the_substantive_topic_and_country():
    history = [SimpleNamespace(question="加拿大铜矿项目情况如何？", mode="analytical")]
    query, filters = contextual_query(
        ChatInput(question="你觉得我们该怎么应对这些风险？"), history
    )
    assert "加拿大铜矿" in query
    assert filters["minerals"] == ["铜"] and filters["regions"] == ["加拿大"]
    assert contextual_query(ChatInput(question="今天天气怎么样"), history) == ("", {})


def test_concept_question_does_not_misclassify_dated_market_requests():
    assert is_concept_question("解释资源量与储量的区别及其对项目判断的影响")
    assert not is_concept_question("解释2026年锂价走势")
    assert not is_concept_question("解释最新稀土出口政策的影响")


def test_general_definition_with_wrong_model_role_never_invents_article_support():
    answer, sources, mode = validate_conversation(
        GroundedAnswer(
            blocks=[
                AnswerBlock(
                    kind="fact",
                    text="资源量分为推断、指示和测定，储量强调经济可采性。",
                    sources=[1],
                    span=1,
                )
            ]
        ),
        [],
        "解释资源量与储量的区别",
    )
    assert mode == "general" and sources == [] and "[1]" not in answer
    assert "指示" in answer and "一般行业分析" in answer
    with pytest.raises(ValueError):
        validate_conversation(
            GroundedAnswer(
                blocks=[
                    AnswerBlock(
                        kind="fact", text="最新铜价涨20%。", sources=[1], span=1
                    )
                ]
            ),
            [],
            "什么是期货？",
        )


async def test_concept_definition_never_attaches_an_unrelated_news_citation(
    monkeypatch,
):
    import app.rag.qa_chain as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    retrieval = AsyncMock(
        side_effect=AssertionError("No news supports a code definition")
    )
    monkeypatch.setattr(module, "HybridRetriever", retrieval)
    monkeypatch.setattr(module, "localize_citations", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        module,
        "complete_json",
        AsyncMock(
            return_value={
                "blocks": [
                    {
                        "kind": "background",
                        "text": (
                            "资源量体现地质证据与最终经济开采前景；"
                            "储量强调经研究和修正因素评估后经济可采的部分。"
                        ),
                    }
                ]
            }
        ),
    )

    def add(item):
        item.id = uuid4()

    db = SimpleNamespace(
        add=add,
        flush=AsyncMock(),
        execute=AsyncMock(),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])),
    )
    result = await module.answer_question(
        db, uuid4(), ChatInput(question="资源量与储量是什么，有什么区别？")
    )
    assert result.mode == "general" and result.sources == []
    retrieval.assert_not_called()


async def test_no_documents_does_not_disable_model_for_industry_concepts(monkeypatch):
    import app.rag.qa_chain as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    monkeypatch.setattr(module, "localize_citations", AsyncMock(return_value=[]))
    generate = AsyncMock(
        return_value={
            "blocks": [
                {
                    "kind": "background",
                    "text": (
                        "储量通常强调可经济开采的部分，资源量更侧重地质发现与估计；"
                        "判断时需要核对采用的分类标准。"
                    ),
                    "sources": [],
                }
            ]
        }
    )
    monkeypatch.setattr(module, "complete_json", generate)
    response = await GroundedSynthesizer("解释一下资源量与储量的区别", []).asynthesize(
        "资源量 储量", []
    )
    assert response.metadata["mode"] == "general" and not response.metadata["sources"]
    assert "储量" in str(response) and "资源量" in str(response)
    assert "一般行业分析" in str(response)
    assert json.loads(generate.await_args.args[1])["evidence"] == []
