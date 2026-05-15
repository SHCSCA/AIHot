from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from intel_engine.llm import ModelScore
from intel_engine.prescreen import PreScreenDecision


SOURCE_TIER_WEIGHT = {
    "T1": 95.0,
    "T1.5": 88.0,
    "T2": 75.0,
    "T3": 55.0,
}

DEFAULT_CATEGORY_WEIGHT = {
    "ai_models": 80.0,
    "ai_products": 75.0,
    "agent_tools": 75.0,
    "papers": 68.0,
    "industry": 65.0,
    "policy": 85.0,
    "account_health": 88.0,
    "fba_logistics": 75.0,
    "ads_ppc": 75.0,
    "listing_seo": 70.0,
    "fees_margin": 78.0,
    "product_research": 70.0,
    "tools": 68.0,
    "compliance_trade": 82.0,
}


@dataclass(frozen=True)
class RankPolicyInput:
    channel: str
    source_tier: str
    category: str
    observed_at: datetime
    published_at: datetime | None
    prefilter: PreScreenDecision
    model_score: ModelScore
    duplicate_penalty: float = 0.0


@dataclass(frozen=True)
class RankDecision:
    source_weight: float
    category_weight: float
    freshness_weight: float
    duplicate_penalty: float
    channel_impact_weight: float
    final_score: float
    selected: bool
    threshold_used: float
    selection_reason: str
    seller_action_level: str | None


class RankPolicy:
    def __init__(
        self,
        *,
        default_threshold: float = 72.0,
        category_thresholds: dict[str, float] | None = None,
        category_weights: dict[str, float] | None = None,
    ):
        self.default_threshold = default_threshold
        self.category_thresholds = category_thresholds or {}
        self.category_weights = {**DEFAULT_CATEGORY_WEIGHT, **(category_weights or {})}

    def evaluate(self, item: RankPolicyInput) -> RankDecision:
        source_weight = SOURCE_TIER_WEIGHT.get(item.source_tier, 50.0)
        category_weight = self.category_weights.get(item.category, 65.0)
        freshness_weight = _freshness_score(item.published_at, item.observed_at)
        channel_impact_weight = _channel_impact_weight(item.channel, item.model_score.impact_score)
        duplicate_penalty = _clamp(item.duplicate_penalty)

        final_score = (
            source_weight * 0.16
            + category_weight * 0.08
            + freshness_weight * 0.08
            + item.model_score.relevance_score * 0.20
            + item.model_score.impact_score * 0.22
            + item.model_score.novelty_score * 0.12
            + item.model_score.actionability_score * 0.10
            + item.model_score.credibility_score * 0.04
            - duplicate_penalty
        )
        final_score = round(_clamp(final_score), 2)
        threshold = self.category_thresholds.get(item.category, self.default_threshold)

        if not item.prefilter.is_relevant:
            selected = False
            reason = "预筛判定不相关"
        elif final_score >= threshold:
            selected = True
            reason = "达到精选阈值"
        else:
            selected = False
            reason = "低于精选阈值"

        return RankDecision(
            source_weight=source_weight,
            category_weight=category_weight,
            freshness_weight=freshness_weight,
            duplicate_penalty=duplicate_penalty,
            channel_impact_weight=channel_impact_weight,
            final_score=final_score,
            selected=selected,
            threshold_used=threshold,
            selection_reason=reason,
            seller_action_level=item.model_score.seller_action_level,
        )


def _freshness_score(published_at: datetime | None, observed_at: datetime) -> float:
    if published_at is None:
        return 50.0
    age_hours = max((observed_at - published_at).total_seconds() / 3600, 0)
    if age_hours <= 24:
        return 100.0
    if age_hours <= 72:
        return 85.0
    if age_hours <= 168:
        return 70.0
    return 45.0


def _channel_impact_weight(channel: str, impact_score: float) -> float:
    if channel == "amazon":
        return min(100.0, impact_score + 5)
    return impact_score


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))
