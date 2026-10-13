"""Small, user-owned session memory from explicit customer statements only."""

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from pipeline.processors.entities import extract_entities


class ConversationContext(BaseModel):
    """Business context is customer input, never independently verified market data."""

    minerals: list[str] = Field(default_factory=list, max_length=8)
    regions: list[str] = Field(default_factory=list, max_length=8)
    products: list[str] = Field(default_factory=list, max_length=6)
    role: str | None = Field(default=None, max_length=30)
    purpose: str | None = Field(default=None, max_length=30)
    style: Literal["normal", "concise", "detailed"] = "normal"
    scenarios: list[str] = Field(default_factory=list, max_length=6)
    focus_year: int | None = Field(default=None, ge=1900, le=2100)
    updated_at: datetime | None = None


PRODUCTS = re.compile(
    r"电池级碳酸锂|工业级碳酸锂|碳酸锂|氢氧化锂|锂辉石|锂云母|"
    r"铜精矿|电解铜|铜矿石|镍铁|硫酸镍|氧化钕|氧化镝|镨钕合金|"
    r"镨钕氧化物|黑钨精矿|白钨精矿|仲钨酸铵|黄金|白银"
)
PRIVATE_OR_INSTRUCTION = re.compile(
    r"密码|密钥|token|api.?key|私钥|身份证|忽略.*(?:指令|规则)|"
    r"system.?prompt|系统提示|你必须|越权|[\w.+-]+@[\w.-]+",
    re.I,
)
BUSINESS = re.compile(
    r"采购|供应|交期|库存|用量|消耗|预算|产品|规格|合同|矿山|项目|研究|汇报|成本|冶炼"
)


def remember(context: ConversationContext, question: str) -> ConversationContext:
    """Update bounded topic and explicit business facts; never use assistant answers."""
    next_context = context.model_copy(deep=True)
    entities = extract_entities(question)
    if entities["minerals"]:
        switched = bool(
            context.minerals and set(context.minerals) != set(entities["minerals"])
        )
        next_context.minerals = entities["minerals"][:8]
        if switched:
            next_context.regions = []
            next_context.products = []
            next_context.focus_year = None
            next_context.scenarios = []
    if entities["regions"]:
        next_context.regions = entities["regions"][:8]
    products = list(dict.fromkeys(PRODUCTS.findall(question)))
    if products:
        # The alternation puts explicitly named grades before generic product names.
        next_context.products = products[:6]
    role = re.search(
        r"(?:我|我们)(?:主要|现在)?(?:负责|从事|做|是)([^。！？\n]{0,20})", question
    )
    if role:
        for name in (
            "采购",
            "供应链",
            "矿山运营",
            "项目开发",
            "行业研究",
            "投资",
            "销售",
            "管理",
        ):
            if name in role[1]:
                next_context.role = name
                break
    for name in (
        "采购决策",
        "供应风险",
        "项目评估",
        "风险管理",
        "行业研究",
        "向领导汇报",
        "投资观察",
    ):
        if name in question:
            next_context.purpose = name
            break
    if re.search(r"(?:请|以后|回答|说|讲).{0,8}(?:简洁|简短|少一点)|少说点", question):
        next_context.style = "concise"
    elif re.search(r"请.{0,5}详细|讲详细|展开(?:说|讲)|多解释", question):
        next_context.style = "detailed"
    years = re.findall(r"(?<!\d)(20\d{2})年", question)
    if years:
        next_context.focus_year = int(years[-1])
    elif re.search(r"今日|今天|最新|最近|当前|现在", question):
        next_context.focus_year = None
    for sentence in re.split(r"[。！？\n]", question):
        declarative = bool(
            re.search(
                r"(?:^|[，,:：])\s*(?:我|我们|本公司|我公司)(?:的)?"
                r"(?:现在|目前|现有|主要)?(?:负责|从事|做|是|有|库存|交期|"
                r"交货期|预算|用量|每日用|每天用|日耗|产品|需求|需要|计划|准备|采购|关注)",
                sentence,
            )
        )
        short_condition = bool(
            re.match(
                r"\s*(?:库存|交期|交货期|预算|用量|每日用|每天用|日耗)"
                r"[^。！？\n]{0,12}(?:\d|[一二三四五六七八九十百])",
                sentence,
            )
        )
        if (
            (declarative or short_condition)
            and BUSINESS.search(sentence)
            and not re.search(r"怎么|如何|多少|什么|是否|请结合|请考虑|帮我", sentence)
            and not PRIVATE_OR_INSTRUCTION.search(sentence)
        ):
            snippet = sentence.strip()[:160]
            if snippet and snippet not in next_context.scenarios:
                for subject in ("库存", "交期", "交货期", "预算", "用量"):
                    if subject in snippet:
                        next_context.scenarios = [
                            item
                            for item in next_context.scenarios
                            if subject not in item
                        ]
                next_context.scenarios = (next_context.scenarios + [snippet])[-6:]
    next_context.updated_at = datetime.now(UTC)
    return next_context


def business_guidance(context: ConversationContext, question: str) -> str:
    """Adapt an action answer to known constraints without inventing missing inputs."""
    if context.role == "采购" and re.search(
        r"下一步|怎么做|怎么安排|采购|补货|方案", question
    ):
        return (
            "本轮要具体采购步骤，避免重讲价格原理。已有客户库存条件要沿用，"
            "先核对实际可用库存、日耗和到货周期，再核对合同价格条款与供应商交期，"
            "按库存能否覆盖补货周期说明何时需要补货或备选渠道。"
            "未给日耗和交期时不能算覆盖天数或采购数量；先给核对步骤，"
            "最后只问一个最关键的缺失条件。不要只说综合考虑、密切关注或灵活调整。"
        )
    return ""


def clarification(question: str, context: ConversationContext) -> str | None:
    """Ask one essential question for underspecified price or action requests."""
    text = question.strip(" ？?！!。.")
    if not context.minerals and re.fullmatch(
        r"(?:请|帮我)?(?:查一下|查查|看看|分析一下)?(?:现在|最近|今天|最新|当前)?"
        r"(?:的)?(?:价格|报价|行情)(?:怎么样|如何|多少|是什么|多少钱|走势)?(?:啊|呢)?",
        text,
    ):
        return (
            "你想查哪种矿产的价格？例如铜、黄金或碳酸锂；"
            "确定品种后，我再给你对应报价、日期和变化分析。"
        )
    if (
        context.minerals == ["锂"]
        and not context.products
        and re.search(r"多少钱|报价是多少|价格多少", question)
    ):
        return (
            "你想查碳酸锂、氢氧化锂，还是锂矿石？"
            "这些产品的规格和价格口径不同，确认后我再帮你查对应报价。"
        )
    if not context.minerals and re.fullmatch(
        r"(?:那|现在|我们)?(?:要不要买|该不该买|怎么采购|采购怎么做)", text
    ):
        return (
            "你准备采购哪种矿产或材料？告诉我产品名称，"
            "我先结合对应行情分析，再一起核对交期和供应条件。"
        )
    return None


def next_questions(question: str, mode: str) -> list[str]:
    """Offer actionable follow-ups without inventing facts or initiating requests."""
    if mode in {"insufficient", "identity", "clarification"}:
        return []
    if re.search(r"采购|下一步|怎么做|清单|应对|方案", question):
        return [
            "哪些变化出现时，需要调整这个方案？",
            "帮我整理成一份可执行的核对清单。",
        ]
    if re.search(r"政策|限制|出口|税", question):
        return ["对供应和成本可能有什么影响？", "我们需要优先核对哪些政策条款？"]
    if re.search(r"价格|报价|走势|行情", question):
        return ["这些报价变化可能带来什么影响？", "结合我的业务场景，下一步怎么做？"]
    return ["哪些风险需要优先排查？", "把结论整理得简洁一点。"]
