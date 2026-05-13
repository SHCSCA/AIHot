from __future__ import annotations

from datetime import datetime, timezone

from intel_engine.llm import FakeLLMProvider, ModelScore
from intel_engine.prescreen import PreScreenDecision
from intel_engine.rank_policy import RankPolicy, RankPolicyInput


def _model_score(**overrides):
    data = {
        "category": "ai_models",
        "relevance_score": 90,
        "impact_score": 88,
        "novelty_score": 70,
        "actionability_score": 80,
        "credibility_score": 95,
        "summary_cn": "模型能力更新。",
        "title_cn": "模型更新",
        "reason": "对模型能力有直接影响。",
        "seller_action_level": "review",
        "raw_json": {"provider": "fake"},
    }
    data.update(overrides)
    return ModelScore(**data)


def test_fake_llm_provider_returns_structured_score():
    provider = FakeLLMProvider(_model_score())

    score = provider.score_item({"title": "OpenAI update"})

    assert score.category == "ai_models"
    assert score.raw_json == {"provider": "fake"}


def test_rank_policy_does_not_let_llm_directly_select_item():
    policy = RankPolicy(default_threshold=70)
    decision = policy.evaluate(
        RankPolicyInput(
            channel="ai",
            source_tier="T1",
            category="ai_models",
            observed_at=datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc),
            prefilter=PreScreenDecision(bucket="irrelevant", is_relevant=False, reason="广告软文"),
            model_score=_model_score(relevance_score=100, impact_score=100, actionability_score=100),
            duplicate_penalty=0,
        )
    )

    assert decision.final_score >= 70
    assert decision.selected is False
    assert decision.selection_reason == "预筛判定不相关"


def test_rank_policy_uses_source_tier_and_category_thresholds():
    observed_at = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
    published_at = datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc)
    prefilter = PreScreenDecision(bucket="relevant", is_relevant=True, reason="官方模型更新")
    score = _model_score(relevance_score=82, impact_score=80, novelty_score=70, actionability_score=75, credibility_score=90)
    policy = RankPolicy(default_threshold=72, category_thresholds={"ai_models": 78})

    official = policy.evaluate(
        RankPolicyInput(
            channel="ai",
            source_tier="T1",
            category="ai_models",
            observed_at=observed_at,
            published_at=published_at,
            prefilter=prefilter,
            model_score=score,
            duplicate_penalty=0,
        )
    )
    low_trust = policy.evaluate(
        RankPolicyInput(
            channel="ai",
            source_tier="T3",
            category="ai_models",
            observed_at=observed_at,
            published_at=published_at,
            prefilter=prefilter,
            model_score=score,
            duplicate_penalty=0,
        )
    )

    assert official.final_score > low_trust.final_score
    assert official.threshold_used == 78
    assert official.selected is True
    assert low_trust.selected is False
