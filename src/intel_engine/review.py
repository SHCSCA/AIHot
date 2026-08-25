from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from intel_engine.llm import ModelScore, ScreeningResult
from intel_engine.models import (
    EventClusterRecord,
    ModelScoreRecord,
    NormalizedItemRecord,
    RankedItemRecord,
    RawScreeningResultRecord,
    SourceRecord,
)
from intel_engine.quality import is_publishable_original_url


ROLLING_WINDOW_HOURS = 24
AMAZON_ROLLING_WINDOW_HOURS = 168
PUBLIC_WINDOW_LABEL = "最近 24 小时"
AMAZON_PUBLIC_WINDOW_LABEL = "最近 7 天"

AI_CATEGORIES = {"ai_models", "ai_products", "agent_tools", "papers", "industry", "monetization"}
AMAZON_CATEGORIES = {
    "policy",
    "account_health",
    "fba_logistics",
    "ads_ppc",
    "listing_seo",
    "fees_margin",
    "product_research",
    "tools",
    "compliance_trade",
}

ACCEPTED_BUCKETS = {"core", "related"}
SCREEN_REJECT_REASON = {
    "not_current_window",
    "missing_publish_time",
    "invalid_original_url",
    "channel_irrelevant",
    "low_information_value",
    "evergreen_tutorial",
    "marketing_or_ad",
    "duplicate_or_rewrite",
    "aggregator_without_signal",
    "model_failed",
    "schema_invalid",
    "low_confidence",
}


@dataclass(frozen=True)
class ScreeningValidation:
    accepted: bool
    reason_code: str | None = None
    reason_cn: str | None = None


@dataclass(frozen=True)
class AutoReviewDecision:
    status: str
    note: str


def channel_rolling_window_hours(channel: str | None) -> int:
    return AMAZON_ROLLING_WINDOW_HOURS if channel == "amazon" else ROLLING_WINDOW_HOURS


def public_window_label(channel: str | None, *, window: int | None = None) -> str:
    if window is not None:
        if window % 24 == 0:
            return f"最近 {window // 24} 天"
        return f"最近 {window} 小时"
    return AMAZON_PUBLIC_WINDOW_LABEL if channel == "amazon" else PUBLIC_WINDOW_LABEL


def is_within_rolling_window(published_at: datetime | None, observed_at: datetime, *, hours: int = ROLLING_WINDOW_HOURS) -> bool:
    if published_at is None:
        return False
    return timedelta(0) <= observed_at - published_at <= timedelta(hours=hours)


def channel_categories(channel: str) -> set[str]:
    if channel == "amazon":
        return AMAZON_CATEGORIES
    return AI_CATEGORIES


def validate_screening_result(
    result: ScreeningResult,
    *,
    channel: str,
    published_at: datetime | None,
    observed_at: datetime,
    original_url: str,
    source_url: str,
) -> ScreeningValidation:
    if published_at is None:
        return ScreeningValidation(False, "missing_publish_time", "缺少明确发布时间。")
    rolling_hours = channel_rolling_window_hours(channel)
    if not is_within_rolling_window(published_at, observed_at, hours=rolling_hours):
        return ScreeningValidation(False, "not_current_window", f"不在最近 {rolling_hours} 小时窗口内。")
    if not is_publishable_original_url(original_url, source_url):
        return ScreeningValidation(False, "invalid_original_url", "原文链接不是具体文章页。")
    if result.screen_status != "accepted" or result.screen_bucket not in ACCEPTED_BUCKETS:
        return ScreeningValidation(False, result.reason_code or "channel_irrelevant", result.reason_cn or "初筛拒绝。")
    if result.confidence_score < 70:
        return ScreeningValidation(False, "low_confidence", "初筛置信度不足。")
    if result.relevance_score < 70:
        return ScreeningValidation(False, "channel_irrelevant", "频道相关度不足。")
    if result.category not in channel_categories(channel):
        return ScreeningValidation(False, "schema_invalid", "模型分类不在当前频道分类集合内。")
    if not _has_required_text(result.title_cn, min_len=4) or not _has_required_text(result.summary_cn, min_len=12):
        return ScreeningValidation(False, "schema_invalid", "缺少合格的中文标题或摘要。")
    if not _valid_tags(result.tags):
        return ScreeningValidation(False, "schema_invalid", "缺少合格中文标签。")
    return ScreeningValidation(True)


def validate_model_score(score: ModelScore, *, channel: str) -> ScreeningValidation:
    if score.category not in channel_categories(channel):
        return ScreeningValidation(False, "schema_invalid", "精筛分类不在当前频道分类集合内。")
    if not _has_required_text(score.summary_cn, min_len=12) or not _has_required_text(score.reason, min_len=6):
        return ScreeningValidation(False, "schema_invalid", "缺少合格的中文摘要或推荐理由。")
    if score.title_cn is not None and not _has_required_text(score.title_cn, min_len=4):
        return ScreeningValidation(False, "schema_invalid", "中文标题不合格。")
    if not _valid_tags(score.tags):
        return ScreeningValidation(False, "schema_invalid", "精筛缺少合格标签。")
    return ScreeningValidation(True)


def adjusted_selected_threshold(
    *,
    channel: str,
    base_threshold: float,
    source_tier: str,
    screen_bucket: str,
    source_count: int,
    risk_flags: list[str],
) -> float:
    threshold = base_threshold
    threshold += {"T1": -3.0, "T1.5": -1.0, "T2": 0.0, "T3": 5.0}.get(source_tier, 5.0)
    if screen_bucket == "related":
        threshold += 4.0
    if source_count >= 2:
        threshold -= 2.0
    if risk_flags and channel != "amazon":
        threshold += 5.0
    return max(0.0, min(100.0, threshold))


def auto_review_decision(
    *,
    item: NormalizedItemRecord | None,
    source: SourceRecord | None,
    screening: RawScreeningResultRecord | None,
    score: ModelScoreRecord | None,
    ranked: RankedItemRecord | None,
) -> AutoReviewDecision:
    if item is None or source is None:
        return AutoReviewDecision("rejected", "缺少主条目或信源，自动拒绝。")
    if screening is None or screening.screen_status != "accepted":
        return AutoReviewDecision("rejected", "初筛未通过，自动拒绝。")
    if score is None or ranked is None:
        return AutoReviewDecision("pending", "精筛或排序结果缺失，暂不发布。")
    provider = score.raw_json.get("provider")
    if provider not in {"deepseek", "rules"} or score.raw_json.get("fallbackReason"):
        return AutoReviewDecision("rejected", "非正式精筛结果，自动拒绝。")
    if not is_publishable_original_url(item.canonical_url, source.url):
        return AutoReviewDecision("rejected", "原文链接未通过安全校验。")
    if not item.title_cn or not item.summary_cn or not score.reason:
        return AutoReviewDecision("rejected", "缺少标题、摘要或推荐理由。")
    if screening.confidence_score < 70:
        return AutoReviewDecision("rejected", "初筛置信度不足。")
    if provider == "rules":
        return AutoReviewDecision("approved", "基础规则初筛与精筛均通过，允许进入公开信息流。")
    return AutoReviewDecision("approved", "AI 初筛与精筛均通过，允许进入公开信息流。")


def public_cluster_ready(
    *,
    cluster: EventClusterRecord,
    item: NormalizedItemRecord | None,
    source: SourceRecord | None,
    screening: RawScreeningResultRecord | None,
    score: ModelScoreRecord | None,
    require_selected: bool,
    ranked: RankedItemRecord | None,
) -> bool:
    if cluster.review_status != "approved":
        return False
    if require_selected and (ranked is None or not ranked.selected):
        return False
    if item is None or source is None or screening is None or score is None:
        return False
    if screening.screen_status != "accepted":
        return False
    if score.raw_json.get("provider") not in {"deepseek", "rules"} or score.raw_json.get(
        "fallbackReason"
    ):
        return False
    if not item.title_cn or not item.summary_cn or not score.reason:
        return False
    return is_publishable_original_url(item.canonical_url, source.url)


def _has_required_text(value: str | None, *, min_len: int) -> bool:
    if not value:
        return False
    return len(value.strip()) >= min_len


def _valid_tags(tags: list[str]) -> bool:
    return 2 <= len([tag for tag in tags if _valid_tag(str(tag).strip())]) <= 5


def _valid_tag(tag: str) -> bool:
    if not tag:
        return False
    if tag.lower() in {"ai", "amazon", "news", "update", "updates", "article", "blog", "tool", "tools"}:
        return False
    if any("\u4e00" <= char <= "\u9fff" for char in tag):
        return True
    if len(tag) > 32:
        return False
    has_upper = any(char.isupper() for char in tag)
    has_lower = any(char.islower() for char in tag)
    has_digit = any(char.isdigit() for char in tag)
    if has_digit:
        return True
    if has_upper and has_lower:
        return True
    return tag.isupper() and 2 <= len(tag) <= 10
