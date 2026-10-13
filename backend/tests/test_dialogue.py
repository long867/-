"""Evaluate follow-up understanding, customer arithmetic and draft repair."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.rag.conversation_context import ConversationContext, recall_customer, remember
from app.rag.dialogue import response_plan, scenario_calculations, turn_intent
from app.rag.qa_chain import GroundedSynthesizer, contextual_query
from app.rag.retriever import search_terms
from app.schemas.api import ChatInput


@pytest.mark.parametrize(
    "question,intent",
    [
        ("哪个更值得关注？", "compare"),
        ("具体一点，为什么会影响交付？", "explain"),
        ("那下一步怎么做？", "action"),
        ("如果许可放松了呢？", "outlook"),
        ("帮我写成一段给领导的汇报。", "summarize"),
    ],
)
def test_short_followups_have_distinct_answer_goals(question, intent):
    assert turn_intent(question) == intent


def test_comparison_retains_both_objects_and_ignores_intervening_definitions():
    history = [
        SimpleNamespace(question="智利铜矿和锂矿的供应风险有哪些？", mode="analytical"),
        SimpleNamespace(question="解释一下资源量与储量的区别", mode="general"),
    ]
    query, filters = contextual_query(ChatInput(question="哪个更值得关注？"), history)
    assert set(filters["minerals"]) == {"铜", "锂"}
    assert filters["regions"] == ["智利"]
    assert "资源量与储量" not in query


def test_followup_to_named_company_keeps_subject_even_without_a_mineral():
    history = [SimpleNamespace(question="BHP的公告有什么进展？", mode="analytical")]
    query, _ = contextual_query(ChatInput(question="具体说说影响。"), history)
    assert "BHP" in query


def test_constraints_in_the_same_turn_as_a_request_are_retained_and_calculated():
    context = remember(
        ConversationContext(),
        "我负责铜采购，我们库存20吨，日耗5吨，交期两周，现在该怎么安排？",
    )
    metrics = scenario_calculations(context)
    assert metrics[0]["value"] == "4" and metrics[0]["unit"] == "天"
    assert all("怎么安排" not in row for row in context.scenarios)
    assert response_plan("下一步怎么做？", context)["customer_calculations"] == metrics
    corrected = remember(context, "更正一下，我们库存30吨。")
    assert scenario_calculations(corrected)[0]["value"] == "6"


def test_arithmetic_converts_mass_units_but_never_invents_missing_inputs():
    context = ConversationContext(
        minerals=["铜"], scenarios=["我们库存2吨", "日耗500公斤"]
    )
    assert scenario_calculations(context)[0]["value"] == "4"
    for snippets in (
        ["库存2吨"],
        ["库存2吨", "日耗0吨"],
        ["库存20吨和30吨", "日耗5吨"],
    ):
        # Multiple stock readings require clarification rather than guessing.
        candidate = context.model_copy(update={"scenarios": snippets})
        if snippets[0] == "库存20吨和30吨":
            candidate.scenarios = ["库存20吨", "库存30吨", "日耗5吨"]
        assert scenario_calculations(candidate) == []


def test_recalling_customer_conditions_does_not_replace_analysis_or_invent_memory():
    context = remember(ConversationContext(), "我们库存20吨，日耗5吨。")
    assert "20吨" in recall_customer("我刚才说的库存是多少？", context)
    assert "还没有" in recall_customer("我之前提过的预算是多少？", context)
    assert recall_customer("结合我前面说的库存，该怎么安排？", context) is None


def test_thousands_separator_is_not_mistaken_for_a_clause_boundary():
    context = remember(
        ConversationContext(), "我们库存20,000公斤,日耗5,000公斤,该怎么做？"
    )
    assert scenario_calculations(context)[0]["value"] == "4"


def test_lead_time_gap_is_computed_with_explicit_scenario_assumptions():
    context = remember(
        ConversationContext(), "我负责铜采购，我们库存30吨，日耗5吨，交期两周。"
    )
    metrics = {row["name"]: row for row in scenario_calculations(context)}
    assert metrics["交期换算"]["value"] == "14"
    assert metrics["交期与库存覆盖缺口"]["value"] == "8"
    assert metrics["理论物料缺口"]["value"] == "40"
    assert "无在途到货" in metrics["理论物料缺口"]["basis"]
    context = remember(context, "我们库存80吨。")
    metrics = {row["name"]: row for row in scenario_calculations(context)}
    assert metrics["理论物料缺口"]["value"] == "0"


def test_named_project_terms_survive_alias_expansion_and_style_instructions():
    terms = search_terms("请根据已有报道分析Guanajuato连接San Ignacio和Bolañitos的影响")
    assert "Guanajuato" in terms and "Bolañitos" in terms
    assert "分析" not in terms and "影响" not in terms


async def test_invalid_draft_is_repaired_instead_of_returning_raw_excerpts(monkeypatch):
    import app.rag.qa_chain as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    monkeypatch.setattr(
        module, "localize_citations", AsyncMock(side_effect=lambda rows, **_: rows)
    )
    generate = AsyncMock(
        side_effect=[
            {"blocks": [{"kind": "advice", "text": "按你的库存计算，可以支撑999天。"}]},
            {
                "blocks": [
                    {
                        "kind": "advice",
                        "text": (
                            "按你提供的库存与日耗，库存约能覆盖4天；"
                            "先确认到货周期能否覆盖缺口，再决定补货与备选渠道。"
                        ),
                    }
                ]
            },
        ]
    )
    monkeypatch.setattr(module, "complete_json", generate)
    context = remember(ConversationContext(), "我负责铜采购，我们库存20吨，日耗5吨。")
    response = await GroundedSynthesizer("那下一步怎么做？", [], context).asynthesize(
        "铜采购", []
    )
    assert generate.await_count == 2
    assert "4天" in str(response) and "999" not in str(response)
    assert response.metadata["mode"] == "general"
    request = json.loads(generate.await_args_list[0].args[1])
    assert request["response_plan"]["intent"] == "action"
    assert request["response_plan"]["customer_calculations"][0]["value"] == "4"


async def test_usable_answer_survives_model_outage_during_optional_repair(monkeypatch):
    import app.rag.qa_chain as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    monkeypatch.setattr(
        module, "localize_citations", AsyncMock(side_effect=lambda rows, **_: rows)
    )
    generate = AsyncMock(
        side_effect=[
            {
                "blocks": [
                    {
                        "kind": "background",
                        "text": "供应渠道集中时，替代供应的可用性会影响交付风险。",
                    }
                ]
            },
            TimeoutError("fixture outage"),
        ]
    )
    monkeypatch.setattr(module, "complete_json", generate)
    response = await GroundedSynthesizer("我们下一步怎么做？", []).asynthesize(
        "采购", []
    )
    assert generate.await_count == 2 and "替代供应" in str(response)
    assert response.metadata["mode"] == "general"
