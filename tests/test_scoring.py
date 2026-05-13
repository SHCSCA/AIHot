import pytest

from intel_engine.scoring import ScoreInput, calculate_final_score, seller_action_level


def test_calculates_weighted_score():
    result = calculate_final_score(
        ScoreInput(
            source_score=90,
            relevance_score=80,
            impact_score=100,
            novelty_score=70,
            actionability_score=60,
            freshness_score=50,
        )
    )

    assert result == 81.0


def test_rejects_out_of_range_scores():
    with pytest.raises(ValueError, match="impact_score"):
        calculate_final_score(
            ScoreInput(
                source_score=90,
                relevance_score=80,
                impact_score=101,
                novelty_score=70,
                actionability_score=60,
                freshness_score=50,
            )
        )


def test_seller_action_level_marks_high_impact_items_urgent():
    assert seller_action_level(final_score=84, impact_score=92, actionability_score=88) == "urgent"


def test_seller_action_level_defaults_low_scores_to_watch():
    assert seller_action_level(final_score=40, impact_score=50, actionability_score=35) == "watch"

