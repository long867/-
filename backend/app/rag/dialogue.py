"""Turn goals and reproducible calculations from explicit customer inputs."""

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.rag.conversation_context import ConversationContext

Intent = Literal["answer", "explain", "compare", "action", "outlook", "summarize"]


def turn_intent(question: str) -> Intent:
    """Identify the requested work, including terse follow-ups."""
    if re.search(r"汇报|总结|整理|简短|简洁|少说|一句话|重点|提炼", question):
        return "summarize"
    if re.search(r"相比|对比|比较|哪个|哪一个|优先|更好|区别|不同|取舍", question):
        return "compare"
    if re.search(r"怎么办|怎么做|怎么安排|下一步|建议|方案|应对|采购|补货", question):
        return "action"
    if re.search(r"如果|假如|假设|一旦|未来|接下来|预测|会不会|可能会|前景", question):
        return "outlook"
    if re.search(r"为什么|原因|影响|分析|研判|具体|详细|展开|逻辑", question):
        return "explain"
    return "answer"


def _amount(text: str, subject: str) -> tuple[Decimal, str] | None:
    """Read one unambiguous quantity, retaining the declared physical unit."""
    matches = re.findall(
        rf"(?:{subject})\s*(?:是|为|有|约|大约|还有)?\s*"
        r"((?:\d{1,3}(?:,\d{3}){1,3}|\d{1,12})(?:\.\d{1,6})?)"
        r"(?![\d.,])\s*(吨|千克|公斤|kg|t)(?![a-z])",
        text,
        re.I,
    )
    values = {
        (Decimal(value.replace(",", "")), unit.lower()) for value, unit in matches
    }
    if len(values) != 1:
        return None
    value, unit = next(iter(values))
    if value <= 0:
        return None
    return (value * 1000 if unit in {"吨", "t"} else value), "kg"


def _formatted(value: Decimal) -> str:
    """Bound display precision without changing the underlying calculation."""
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(rounded, "f").rstrip("0").rstrip(".")


def _lead_days(text: str) -> Decimal | None:
    """Normalize one explicit lead time; exclude ranges and ambiguous schedules."""
    matches = re.findall(
        r"(?:交期|交货期|到货周期|交货周期)\s*(?:是|为|约|大约)?\s*"
        r"(\d{1,3}|[一二两三四五六七八九十])\s*(天|周|星期)",
        text,
    )
    digits = {word: index for index, word in enumerate("零一二三四五六七八九十")}
    digits["两"] = 2
    values = {
        Decimal(int(value) if value.isdigit() else digits[value])
        * (7 if unit in {"周", "星期"} else 1)
        for value, unit in matches
    }
    if len(values) != 1 or not 0 < next(iter(values)) <= 90:
        return None
    return next(iter(values))


def scenario_calculations(context: ConversationContext) -> list[dict[str, str]]:
    """Calculate stock coverage only when compatible, explicit inputs exist.

    The calculation is a customer scenario, not a forecast or a market quote.
    Ambiguous quantities, zero consumption and multiple products are excluded.
    """
    if len(context.minerals) > 1 or len(context.products) > 1:
        return []
    text = "。".join(context.scenarios)
    stock = _amount(text, "(?:可用)?库存")
    usage = _amount(text, "日耗|每日用量|每天用量|每日消耗|每天消耗|每天用|每日用")
    if not stock or not usage:
        return []
    days = stock[0] / usage[0]
    value = _formatted(days)
    metrics = [
        {
            "name": "库存覆盖天数",
            "value": value,
            "unit": "天",
            "basis": "用户提供的库存 ÷ 用户提供的每日用量，四舍五入至两位小数",
            "statement": f"按用户提供的库存与日耗计算，库存覆盖约{value}天。",
        }
    ]
    lead = _lead_days(text)
    if lead is not None:
        gap_days = max(Decimal(0), lead - days)
        gap_tonnes = max(Decimal(0), usage[0] * lead - stock[0]) / 1000
        for name, quantity, unit in (
            ("交期换算", lead, "天"),
            ("交期与库存覆盖缺口", gap_days, "天"),
            ("理论物料缺口", gap_tonnes, "吨"),
        ):
            display = _formatted(quantity)
            metrics.append(
                {
                    "name": name,
                    "value": display,
                    "unit": unit,
                    "basis": (
                        "仅按客户库存、稳定日耗及交期计算，"
                        "假设库存全部可用且无在途到货。"
                    ),
                    "statement": (
                        "按用户提供条件、假设无在途到货且日耗稳定，"
                        f"{name}为{display}{unit}。"
                    ),
                }
            )
    return metrics


def response_plan(question: str, context: ConversationContext) -> dict:
    """Give synthesis an explicit answer goal without another model round-trip."""
    intent = turn_intent(question)
    goals = {
        "answer": "直接解决本轮问题，只补充必要依据和限制。",
        "explain": "先给关键判断，串起事实→作用机制→业务影响；说明什么条件会改变判断。",
        "compare": (
            "沿用上文所比较的对象，按共同维度比较利弊，给有条件的取舍理由；"
            "不要凭空造对象。"
        ),
        "action": (
            "给具体行动顺序、优先级和触发条件；沿用客户已交代的产品、库存与交期。"
        ),
        "outlook": (
            "区分基础情景、改善条件与恶化条件，说明验证信号；不捏造概率或确定涨跌。"
        ),
        "summarize": (
            "压缩前文结论和依据，保留重要限制，不重新介绍行业常识或补入无关报道。"
        ),
    }
    return {
        "intent": intent,
        "goal": goals[intent],
        "style": context.style,
        "customer_calculations": scenario_calculations(context),
        "calculation_rule": (
            "只可使用系统提供的计算结果，标明按用户提供条件计算；"
            "不将场景结果当作行业统计，不自行计算其他数字。"
        ),
    }
