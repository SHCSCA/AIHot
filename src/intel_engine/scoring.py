from __future__ import annotations

from dataclasses import dataclass


SCORE_WEIGHTS = {
    "source_score": 0.20,
    "relevance_score": 0.20,
    "impact_score": 0.25,
    "novelty_score": 0.15,
    "actionability_score": 0.15,
    "freshness_score": 0.05,
}


@dataclass(frozen=True)
class ScoreInput:
    source_score: float
    relevance_score: float
    impact_score: float
    novelty_score: float
    actionability_score: float
    freshness_score: float


def _validate_score(name: str, value: float) -> None:
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100")


def calculate_final_score(score_input: ScoreInput) -> float:
    values = score_input.__dict__
    for name, value in values.items():
        _validate_score(name, value)

    total = sum(values[name] * weight for name, weight in SCORE_WEIGHTS.items())
    return round(total, 2)


def seller_action_level(final_score: float, impact_score: float, actionability_score: float) -> str:
    _validate_score("final_score", final_score)
    _validate_score("impact_score", impact_score)
    _validate_score("actionability_score", actionability_score)

    if final_score >= 88 or (impact_score >= 90 and actionability_score >= 85):
        return "urgent"
    if final_score >= 78 or (impact_score >= 80 and actionability_score >= 75):
        return "act_soon"
    if final_score >= 62 or impact_score >= 65:
        return "review"
    return "watch"

