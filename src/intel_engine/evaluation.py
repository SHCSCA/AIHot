from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from intel_engine.models import (
    ClusterMemberRecord,
    EvaluationRunRecord,
    EventClusterRecord,
    FeedbackEventRecord,
    StrategyVersionRecord,
)


def activate_strategy_version(session: Session, strategy_id: str, *, now: datetime) -> StrategyVersionRecord:
    strategy = session.get(StrategyVersionRecord, strategy_id)
    if strategy is None:
        raise KeyError(f"Unknown strategy version: {strategy_id}")

    active_strategies = session.scalars(
        select(StrategyVersionRecord)
        .where(StrategyVersionRecord.channel == strategy.channel)
        .where(StrategyVersionRecord.status == "active")
    ).all()
    for active in active_strategies:
        if active.id != strategy.id:
            active.status = "retired"
            active.retired_at = now

    strategy.status = "active"
    strategy.activated_at = now
    strategy.retired_at = None
    session.flush()
    return strategy


def run_evaluation(session: Session, evaluation_run_id: int, *, now: datetime) -> EvaluationRunRecord:
    run = session.get(EvaluationRunRecord, evaluation_run_id)
    if run is None:
        raise KeyError(f"Unknown evaluation run: {evaluation_run_id}")

    run.status = "running"
    session.flush()

    clusters = list(
        session.scalars(
            select(EventClusterRecord)
            .where(EventClusterRecord.channel == run.channel)
            .where(EventClusterRecord.cluster_score >= 70)
        ).all()
    )
    feedback_events = list(
        session.scalars(select(FeedbackEventRecord).where(FeedbackEventRecord.channel == run.channel)).all()
    )
    source_contribution = Counter(
        member.source_id
        for member in session.scalars(
            select(ClusterMemberRecord).join(EventClusterRecord, EventClusterRecord.id == ClusterMemberRecord.cluster_id)
        ).all()
    )
    category_distribution = Counter(cluster.category for cluster in clusters)
    feedback_distribution = Counter(event.feedback_type for event in feedback_events)

    run.metrics_json = {
        "selectedEventCount": len(clusters),
        "falsePositiveCount": feedback_distribution.get("false_positive", 0),
        "falseNegativeCount": feedback_distribution.get("false_negative", 0),
        "feedbackCount": len(feedback_events),
        "categoryDistribution": dict(category_distribution),
        "sourceContribution": dict(source_contribution),
    }
    run.status = "succeeded"
    run.completed_at = now
    session.flush()
    return run
