from __future__ import annotations

from datetime import datetime

from intel_engine.llm import ModelScore, ScreeningResult
from intel_engine.models import (
    NormalizedItemRecord,
    RawDocumentRecord,
    SourceRecord,
)


AI_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "ai_models",
        (
            "model",
            "models",
            "llm",
            "gpt",
            "claude",
            "gemini",
            "deepseek",
            "mistral",
            "模型",
            "大模型",
            "发布",
            "release",
        ),
    ),
    (
        "ai_products",
        (
            "product",
            "platform",
            "app",
            "feature",
            "产品",
            "平台",
            "功能",
            "上线",
            "更新",
        ),
    ),
    (
        "agent_tools",
        (
            "agent",
            "copilot",
            "coding",
            "developer tool",
            "agent",
            "工具",
            "编程",
            "自动化",
        ),
    ),
    (
        "papers",
        (
            "paper",
            "research",
            "arxiv",
            "论文",
            "研究",
            "技术报告",
        ),
    ),
    (
        "monetization",
        (
            "price",
            "pricing",
            "funding",
            "revenue",
            "价格",
            "融资",
            "营收",
            "商业化",
        ),
    ),
)

AMAZON_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "account_health",
        (
            "account health",
            "suspension",
            "appeal",
            "账号健康",
            "封号",
            "申诉",
        ),
    ),
    (
        "fba_logistics",
        (
            "fba",
            "fulfillment",
            "inventory",
            "inbound",
            "storage",
            "库存",
            "物流",
            "仓储",
            "入库",
        ),
    ),
    (
        "ads_ppc",
        (
            "advertising",
            "campaign",
            "ppc",
            "amazon ads",
            "广告",
            "投放",
        ),
    ),
    (
        "fees_margin",
        (
            "fee",
            "commission",
            "reimbursement",
            "margin",
            "费用",
            "佣金",
            "赔付",
            "利润",
        ),
    ),
    (
        "listing_seo",
        (
            "listing",
            "keyword",
            "search",
            "review",
            "标题",
            "关键词",
            "评价",
        ),
    ),
    (
        "tools",
        (
            "sp-api",
            "seller central",
            "brand registry",
            "工具",
            "接口",
        ),
    ),
    (
        "policy",
        (
            "policy",
            "compliance",
            "requirement",
            "政策",
            "合规",
            "要求",
        ),
    ),
)

GENERIC_CONTENT_TERMS = (
    "how to",
    "best practices",
    "tutorial",
    "教程",
    "指南",
    "top 10",
    "模板",
    "webinar",
    "促销",
    "优惠",
)
AI_EVENT_TERMS = (
    "announce",
    "announced",
    "launch",
    "launched",
    "release",
    "released",
    "update",
    "updated",
    "上线",
    "发布",
    "更新",
    "推出",
    "开放",
)
AMAZON_SELLER_CONTEXT_TERMS = (
    "amazon seller",
    "seller central",
    "selling partner",
    "sp-api",
    "fba",
    "fulfillment by amazon",
    "amazon ads",
    "ppc",
    "亚马逊卖家",
    "卖家中心",
)
AMAZON_OPERATIONAL_TERMS = (
    "account health",
    "advertising",
    "campaign",
    "coupon",
    "deprecation",
    "fee",
    "fulfillment center",
    "inbound",
    "inventory",
    "listing",
    "placement",
    "pricing",
    "prime day",
    "reimbursement",
    "release notes",
    "review",
    "return",
    "storage",
    "账号健康",
    "广告",
    "费用",
    "库存",
    "Listing",
    "政策",
    "物流",
)


def rule_based_screening(
    raw_document: RawDocumentRecord,
    source: SourceRecord,
    *,
    now: datetime,
) -> ScreeningResult:
    title = str(raw_document.response_headers_json.get("x-intel-title") or "").strip()
    body = (raw_document.body_text or "").strip()
    text = " ".join((title, body, raw_document.canonical_url or "")).lower()
    category, category_hits = _infer_category(source.channel, text, source.default_categories)
    event_hits = _count_hits(text, AI_EVENT_TERMS)
    signal_hits = category_hits + event_hits
    has_url = bool((raw_document.canonical_url or "").strip())
    has_content = len(" ".join((title, body)).strip()) >= 12
    seller_relevant = source.channel != "amazon" or (
        _has_any(text, AMAZON_SELLER_CONTEXT_TERMS)
        and _has_any(text, AMAZON_OPERATIONAL_TERMS)
    )
    generic_only = _has_any(text, GENERIC_CONTENT_TERMS) and event_hits == 0

    if not has_url:
        return _rule_screening_rejection(
            title, body, "invalid_original_url", "规则判定缺少可追溯的原文链接。"
        )
    if not has_content:
        return _rule_screening_rejection(
            title, body, "low_information_value", "规则判定正文信息不足，暂不入库。"
        )
    if not seller_relevant:
        return _rule_screening_rejection(
            title, body, "channel_irrelevant", "规则判定内容缺少明确的 Amazon 卖家运营信号。"
        )
    if generic_only:
        return _rule_screening_rejection(
            title, body, "evergreen_tutorial", "规则判定内容偏教程或泛泛经验，缺少近期事件信号。"
        )

    authority = max(0.0, min(100.0, float(source.authority_weight)))
    relevance = _clamp(62 + authority * 0.2 + min(signal_hits * 4, 16))
    confidence = _clamp(68 + authority * 0.16 + min(signal_hits * 3, 15))
    if source.channel == "amazon" and seller_relevant:
        relevance = max(relevance, 78)
        confidence = max(confidence, 76)
    accepted = relevance >= 70 and confidence >= 70
    tags = [_category_tag(category), "规则筛选"]
    if event_hits:
        tags.append("近期动态")
    raw_json = {
        "provider": "rules",
        "model": "rules-v1",
        "analysisMode": "rules",
        "ruleSignals": {
            "categoryHits": category_hits,
            "eventHits": event_hits,
            "authorityWeight": authority,
        },
        "observedAt": now.isoformat(),
    }
    return ScreeningResult(
        screen_status="accepted" if accepted else "rejected",
        screen_bucket="core" if relevance >= 82 else "related",
        relevance_score=round(relevance, 2),
        confidence_score=round(confidence, 2),
        category=category,
        title_cn=title or source.name,
        summary_cn=_summary(title, body),
        tags=tags[:5],
        reason_code="rules_accepted" if accepted else "low_confidence",
        reason_cn=(
            "基础规则识别到明确的近期变化与频道相关信号。"
            if accepted
            else "基础规则识别到的频道相关信号不足。"
        ),
        raw_json=raw_json,
    )


def rule_based_score(item: NormalizedItemRecord, source: SourceRecord) -> ModelScore:
    text = " ".join(
        (
            item.title_original or "",
            item.summary_original or "",
            item.canonical_url or "",
        )
    ).lower()
    category, category_hits = _infer_category(item.channel, text, source.default_categories)
    event_hits = _count_hits(text, AI_EVENT_TERMS)
    signal_hits = category_hits + event_hits
    authority = max(0.0, min(100.0, float(source.authority_weight)))
    relevance = _clamp(62 + authority * 0.2 + min(signal_hits * 4, 16))
    impact_base = 72 if item.channel == "amazon" else 74
    impact = _clamp(impact_base + min(signal_hits * 3, 15) + (8 if source.tier == "T1" else 0))
    novelty = _clamp(64 + min(event_hits * 7, 21) + min(category_hits * 2, 8))
    actionability = _clamp(
        (78 if item.channel == "amazon" and _has_any(text, AMAZON_OPERATIONAL_TERMS) else 68)
        + min(signal_hits * 2, 12)
    )
    confidence = _clamp(70 + authority * 0.15 + min(signal_hits * 3, 12))
    tags = [_category_tag(category), "规则评分"]
    if item.channel == "amazon":
        tags.append("卖家运营")
    elif event_hits:
        tags.append("近期动态")
    risk_flags: list[str] = []
    if item.channel == "amazon" and _has_any(
        text, ("suspension", "appeal", "account health", "封号", "申诉", "账号健康")
    ):
        risk_flags.append("账号风险")
    summary = _summary(item.title_original, item.summary_original)
    return ModelScore(
        category=category,
        relevance_score=round(relevance, 2),
        impact_score=round(impact, 2),
        novelty_score=round(novelty, 2),
        actionability_score=round(actionability, 2),
        credibility_score=round(authority, 2),
        summary_cn=summary,
        title_cn=item.title_original,
        reason=(
            "基础规则综合信源权威度、近期事件词、频道相关词和可执行性完成评分。"
        ),
        seller_action_level=_seller_action_level(item.channel, text),
        confidence_score=round(confidence, 2),
        tags=tags[:5],
        event_type=category,
        key_facts=[item.title_original] if item.title_original else [],
        risk_flags=risk_flags,
        raw_json={
            "provider": "rules",
            "model": "rules-v1",
            "analysisMode": "rules",
            "ruleSignals": {
                "categoryHits": category_hits,
                "eventHits": event_hits,
                "authorityWeight": authority,
            },
        },
    )


def _rule_screening_rejection(
    title: str,
    body: str,
    reason_code: str,
    reason_cn: str,
) -> ScreeningResult:
    return ScreeningResult(
        screen_status="rejected",
        screen_bucket="irrelevant" if reason_code == "channel_irrelevant" else "invalid",
        relevance_score=0,
        confidence_score=88,
        category="industry",
        title_cn=title or "规则筛选未通过",
        summary_cn=_summary(title, body),
        tags=["规则筛选", "质量控制"],
        reason_code=reason_code,
        reason_cn=reason_cn,
        raw_json={"provider": "rules", "model": "rules-v1", "analysisMode": "rules"},
    )


def _infer_category(
    channel: str,
    text: str,
    default_categories: list[str] | None,
) -> tuple[str, int]:
    rules = AMAZON_CATEGORY_RULES if channel == "amazon" else AI_CATEGORY_RULES
    best_category = (default_categories or [rules[0][0]])[0]
    best_hits = 0
    for category, terms in rules:
        hits = _count_hits(text, terms)
        if hits > best_hits:
            best_category, best_hits = category, hits
    allowed = {category for category, _terms in rules}
    if best_category not in allowed:
        best_category = rules[0][0]
    return best_category, best_hits


def _seller_action_level(channel: str, text: str) -> str:
    if channel == "amazon" and _has_any(
        text, ("suspension", "appeal", "封号", "申诉", "deadline", "截止")
    ):
        return "urgent"
    if channel == "amazon" and _has_any(text, AMAZON_OPERATIONAL_TERMS):
        return "act_soon"
    return "review"


def _summary(title: str, body: str) -> str:
    text = "。".join(part for part in (title.strip(), body.strip()) if part)
    return text[:1200]


def _category_tag(category: str) -> str:
    return {
        "ai_models": "模型动态",
        "ai_products": "产品动态",
        "agent_tools": "Agent 工具",
        "papers": "论文研究",
        "industry": "行业动态",
        "monetization": "商业化",
        "account_health": "账号健康",
        "fba_logistics": "FBA 物流",
        "ads_ppc": "广告投放",
        "listing_seo": "Listing 优化",
        "fees_margin": "费用利润",
        "tools": "卖家工具",
        "policy": "平台政策",
    }.get(category, "规则情报")


def _count_hits(text: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if term.lower() in text)


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in text for term in terms)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))
