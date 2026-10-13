"""Conversational analysis with separate evidence, inference and industry knowledge."""

import re
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field

from app.rag.localization import chinese_prose
from app.schemas.api import Citation
from pipeline.processors.translator import (
    NUMBER,
    UNIT_ALIASES,
    numbers,
    summary_measurements_valid,
)


class AnswerBlock(BaseModel):
    """One ordered response paragraph, with an explicit epistemic role."""

    kind: Literal["fact", "analysis", "advice", "background", "clarification"]
    text: str = Field(min_length=1, max_length=1800)
    sources: list[int] = Field(default_factory=list, max_length=5)
    quote: str | None = Field(default=None, max_length=600)
    span: int | None = Field(default=None, ge=1)


GUARANTEES = re.compile(
    r"稳赚|保证(?:盈利|收益|回报)|无风险|一定会|必然会|必定|"
    r"肯定(?:上涨|下跌|赚钱)|确定(?:上涨|下跌)|不会亏"
)
QUANTIFIED_FORECAST = re.compile(
    r"(?:预计|预测|将|未来|明年|下个月|下周|目标价|概率)"
    r"[^。！？\n]{0,45}(?:\d[\d,.]*\s*(?:%|％|美元|元|USD|CNY)|概率\s*\d)",
    re.I,
)
CURRENT_CLAIM = re.compile(
    r"最新(?:价格|报价|政策|数据)|(?:今日|今天|昨天|本周|今年).{0,15}"
    r"(?:报价|价格|涨|跌|产量|发布|实施)|数据显示|报告显示|公告显示|"
    r"(?:已宣布|已生效|已实施|已导致|实际上涨|实际下跌)"
    r"|(?:已经?|已)(?:完成|建成|投产|达产|签署|收购|获批|批准|开工|停产|关闭)"
)
MARKET_QUANTITY = re.compile(
    r"US\$|USD|CNY|人民币|\d[\d,.]*\s*(?:%|％|美元|万元|亿元|"
    r"吨|万吨|亿吨|盎司|年|月|日)|20\d{2}[-/.]\d",
    re.I,
)
SCALES = {
    "thousand": 1000,
    "million": 1000000,
    "billion": 1000000000,
    "千": 1000,
    "万": 10000,
    "百万": 1000000,
    "千万": 10000000,
    "亿": 100000000,
    "十亿": 1000000000,
    "百亿": 10000000000,
}
SCALE_PATTERN = "|".join(
    re.escape(label)
    + (r"\b" if label.isascii() else r"(?!米|克)" if label == "千" else "")
    for label in sorted(SCALES, key=len, reverse=True)
)
PHYSICAL_UNITS = "|".join(
    re.escape(unit)
    for unit in sorted(UNIT_ALIASES, key=len, reverse=True)
    if unit not in SCALES
)
SCALED_QUANTITY = re.compile(
    rf"(?P<number>{NUMBER})\s*(?P<scale>{SCALE_PATTERN})"
    rf"(?:\s*(?P<unit>{PHYSICAL_UNITS}))?",
    re.I,
)


def scaled_quantities(text: str) -> Counter[tuple[str, int, str]]:
    """Keep million/billion and their following physical unit in the same anchor."""
    result: Counter[tuple[str, int, str]] = Counter()
    for match in SCALED_QUANTITY.finditer(text):
        unit = (match.group("unit") or "").casefold()
        canonical = next(
            (value for name, value in UNIT_ALIASES.items() if name.casefold() == unit),
            unit,
        )
        value = next(iter(numbers(match.group("number"))))
        result[(value, SCALES[match.group("scale").casefold()], canonical)] += 1
    return result


def quantities_match(original: str, answer: str, language: str = "en") -> bool:
    """Reject silent million→万, billion→亿 and scaled tonnage→pounds changes."""
    # The shared validator now retains both magnitude and physical unit.
    # Duplicating that parser here rejects faithful Spanish compound quantities.
    return summary_measurements_valid(original, answer, language)


def evidence_spans(source: Citation) -> list[tuple[int, int]]:
    """Expose selectable literal spans instead of asking a model to copy quotes.

    Offsets are relative to the retrieved chunk. Every span remains a continuous
    original substring, including punctuation, currency and unit spellings.
    """
    boundaries = [0]
    for match in re.finditer(
        r"[。！？!?]\s*|(?<!\d)\.(?=\s+[A-Z])\s+|\n+", source.quote
    ):
        boundaries.append(match.end())
    boundaries.append(len(source.quote))
    spans: list[tuple[int, int]] = []
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        while start < end:
            stop = min(start + 600, end)
            if stop < end:
                space = source.quote.rfind(" ", start + 8, stop)
                if space > start:
                    stop = space + 1
            if len(source.quote[start:stop].strip()) >= 8:
                spans.append((start, stop))
            start = stop
    return spans


def needs_current_evidence(question: str) -> bool:
    """Identify requests for dated market observations rather than general concepts."""
    if re.search(r"计划|规划|方案|怎么做|怎么办|建议|安排", question) and not re.search(
        r"最新|实时报价|价格走势|行情|价格多少|报价多少|现价", question
    ):
        return False
    return bool(
        re.search(
            r"最新|实时|今天|今日|昨天|本周|本月|今年|20\d{2}年|现价|报价|"
            r"报道|新闻|公告|进展|动向|投产情况",
            question,
        )
        or (
            re.search(r"价格|行情|走势", question)
            and not re.search(r"什么是|原理|因素|一般|通常|如何分析|怎么分析", question)
        )
    )


def can_offer_background(question: str) -> bool:
    """Explain concepts and analysis frameworks when retrieval is sparse."""
    return bool(
        re.search(
            r"什么是|是什么|解释|区别|原理|因素|为什么|原因|影响|分析|研判|"
            r"怎么办|怎么做|应对|建议|风险|机会|走势|看法|你觉得|"
            r"如何|怎么|怎样|评估|规划|方案|总结|整理|汇报|有哪些|用途|值不值得|有用|"
            r"what is|explain|why|impact|analy[sz]|recommend",
            question,
            re.I,
        )
    )


def is_concept_question(question: str) -> bool:
    """Keep basic terminology explanations separate from unrelated news results."""
    if re.search(
        r"最新|最近|实时|今天|今年|20\d{2}年|这个项目|这项政策|该公告", question
    ):
        return False
    return bool(
        re.search(r"什么是|是什么|解释|区别|原理|定义|科普", question)
        and re.search(
            r"资源量|储量|品位|稀土|现货|期货|选矿|冶炼|边界品位|矿石|"
            r"mineral resource|ore reserve",
            question,
            re.I,
        )
    )


def turn_guidance(question: str) -> str:
    """Keep the current conversational intent prominent after long evidence text."""
    if re.search(r"下一步|怎么做|怎么办|可执行|建议|应对|安排|方案", question):
        return (
            "本轮重点是行动方案，不是再次介绍新闻。给出具体行动顺序、核对的信息和"
            "决策条件，不复述上一轮的背景。采购场景从客户所需规格、交期、现有合同"
            "定价条款和可替代渠道出发；核对新项目的实际可交付产量，"
            "再决定是否改变采购节奏，不能把资源量当成当前供货量。"
            "缺少客户条件时说明条件或问一个关键问题，而不是只让客户密切关注。"
        )
    if re.search(r"价格|行情|走势|报价", question):
        if re.search(
            r"报价是多少|价格是多少|多少钱|什么价格", question
        ) and not re.search(r"影响|原因|为什么|趋势|走势|因素", question):
            return (
                "本轮只核对报价，用一两段给出产品、数值、单位、原始报价日期与来源。"
                "不要附加用户没有询问的采购建议或行业常识。旧报价不能说成今日价格，"
                "用户指定的品级或市场没有对应资料时明确说明，不能拿其他规格代替。"
            )
        return (
            "先说明现有报价的品种、单位、日期和样本覆盖，再给条件性的原因与影响分析。"
            "少量价格点不足以概括整个年份趋势；项目测算中的假设价格不是实际行情。"
            "无法确定未来方向时解释不同供需情景，不编造确定走势或涨跌幅。"
        )
    if re.search(r"什么是|解释|区别|原理|用途", question):
        guidance = (
            "本轮是概念解释。用行业知识直接解释概念、区别和它为什么影响实际决策。"
            "不需要列举新闻来凑引用，也不要因缺少报道而拒绝回答概念。"
            "术语定义用background段、sources: []；没有新闻证据时不能使用fact或span。"
        )
        if re.search(r"资源量|储量|mineral resource|ore reserve", question, re.I):
            # Reviewed against Geoscience Australia's JORC definitions:
            # https://www.ga.gov.au/aimr2023/appendices
            guidance += (
                "概念依据：以JORC分类为例，资源量基于地质证据和采样，具有最终经济"
                "开采的合理前景；不是所有资源量都未经勘探证实。资源量地质可信度"
                "由低到高是推断（Inferred）、指示（Indicated）、测定（Measured）。"
                "潜在资源量不是这个体系中的资源量分类。储量是Measured或Indicated"
                "资源量经预可行性或可行性研究、考虑采矿、加工、经济、法律、环境等"
                "修正因素后，确定可以经济开采的部分，分Probable和Proved。推断资源量"
                "不能直接转为储量。不同国家标准术语可能不同，需核对报告采用的标准。"
                "解释这些区别如何影响项目可行性、风险和供货判断，不把资源量当储量。"
            )
        return guidance
    return (
        "围绕本轮问题给出判断和作用机制，指出哪些条件会改变判断，并说明业务影响。"
        "资料事实只选能解释这个问题的内容，不要照搬公告或填充无关行业常识。"
    )


def validate_discussion(
    block: AnswerBlock, citations: list[Citation], question: str
) -> list[Citation]:
    """Check inference references and quantities without literal causal quotes.

    These checks enforce traceability and presentation boundaries. They do not
    establish semantic entailment of a model's qualitative analysis.
    """
    if not chinese_prose(block.text):
        raise ValueError("discussion_not_chinese")
    if re.search(r"\[\d+\]|https?://", block.text):
        raise ValueError("discussion_invented_reference")
    if GUARANTEES.search(block.text) or QUANTIFIED_FORECAST.search(block.text):
        raise ValueError("discussion_unsupported_forecast")
    indexes = list(dict.fromkeys(block.sources))
    if any(index < 1 or index > len(citations) for index in indexes):
        raise ValueError("discussion_unknown_source")
    selected = [citations[index - 1] for index in indexes]
    if block.kind in {"background", "clarification"} and selected:
        raise ValueError("general_knowledge_must_not_claim_document_support")
    evidence = "\n".join(
        item.quote
        + "\n"
        + item.title
        + "\n"
        + (item.published_at.isoformat() if item.published_at else "")
        for item in selected
    )
    if block.kind == "clarification":
        if not block.text.rstrip().endswith(("?", "？")):
            raise ValueError("clarification_must_be_question")
        evidence = question
    elif not selected and block.kind in {"analysis", "advice"}:
        # Process advice and qualitative industry reasoning need no invented source.
        # User-provided scenario quantities remain distinguishable from market data.
        evidence = question
    prose = re.sub(r"(?m)^\s*(?:[-*•]\s*)?\d{1,2}[.)、]\s*", "", block.text)
    if block.kind != "background" and set(numbers(prose)) - set(numbers(evidence)):
        raise ValueError("discussion_unsupported_number")
    if block.kind != "background" and not quantities_match(evidence, prose):
        raise ValueError("discussion_changed_measurement")
    if (
        not selected
        and block.kind != "clarification"
        and CURRENT_CLAIM.search(block.text)
    ):
        for match in CURRENT_CLAIM.finditer(block.text):
            prefix = re.split(r"[。！？!?；;\n]", block.text[: match.start()])[-1]
            conditional = re.search(r"如果|假如|假设|若|一旦|是否", prefix)
            verification_advice = block.kind == "advice" and re.search(
                r"(?:建议|应|需|请|先|再|务必).{0,16}(?:核实|确认|核对)", prefix
            )
            if not conditional and not verification_advice:
                raise ValueError("unsourced_current_claim")
    if block.kind == "background" and MARKET_QUANTITY.search(block.text):
        raise ValueError("general_knowledge_contains_current_claim")
    return selected


def discussion_paragraph(block: AnswerBlock, citations: list[Citation]) -> str:
    """Label the first clause so inference cannot masquerade as reported fact."""
    labels = {
        "analysis": "分析判断",
        "advice": "建议",
        "background": "一般行业分析",
        "clarification": "",
    }
    label = labels[block.kind]
    if block.kind == "analysis" and not citations:
        label = "一般分析"
    text = block.text.strip()
    if label and not text.startswith(label):
        text = label + "：" + text
    marker = "".join(f"[{item.index}]" for item in citations)
    return text + (" " + marker if marker else "")
