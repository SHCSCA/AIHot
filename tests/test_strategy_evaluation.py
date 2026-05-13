from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from intel_engine.evaluation import activate_strategy_version, run_evaluation
from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.main import create_app
from intel_engine.models import (
    EvaluationRunRecord,
    EventClusterRecord,
    FeedbackEventRecord,
    StrategyVersionRecord,
)
from intel_engine.settings import Settings


def _auth_header() -> dict[str, str]:
    token = base64.b64encode(b"admin:admin").decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _session_factory(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}")
    engine = create_engine_from_settings(settings)
    init_schema(engine)
    return sessionmaker_for_engine(engine)


def _strategy(strategy_id: str, status: str) -> StrategyVersionRecord:
    return StrategyVersionRecord(
        id=strategy_id,
        channel="ai",
        name=strategy_id,
        status=status,
        prefilter_prompt_version="prefilter-v1",
        score_prompt_version="score-v1",
        rank_formula_version="rank-v1",
        thresholds_json={"selected": 72},
        model_config_json={"provider": "fake"},
    )


def test_activate_strategy_version_retires_existing_active_strategy(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        session.add_all([_strategy("ai-default-v1", "active"), _strategy("ai-next-v1", "draft")])
        session.commit()
        activated = activate_strategy_version(session, "ai-next-v1", now=now)
        strategies = session.scalars(select(StrategyVersionRecord)).all()

    assert activated.status == "active"
    assert {strategy.id: strategy.status for strategy in strategies} == {
        "ai-default-v1": "retired",
        "ai-next-v1": "active",
    }


def test_run_evaluation_generates_feedback_and_distribution_metrics(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        session.add(_strategy("ai-default-v1", "active"))
        session.add(
            EventClusterRecord(
                channel="ai",
                canonical_title="OpenAI 发布 GPT-5",
                main_item_id=None,
                category="ai_models",
                first_seen_at=now,
                last_seen_at=now,
                member_count=1,
                source_count=1,
                cluster_score=90,
                embedding=None,
            )
        )
        session.add(
            FeedbackEventRecord(
                channel="ai",
                feedback_type="false_positive",
                reason="噪声",
                actor="operator",
                created_at=now,
            )
        )
        session.flush()
        run = EvaluationRunRecord(
            channel="ai",
            strategy_version="ai-default-v1",
            name="smoke",
            status="pending",
            request_json={"windowHours": 24},
            metrics_json={},
        )
        session.add(run)
        session.commit()
        completed = run_evaluation(session, run.id, now=now)

    assert completed.status == "succeeded"
    assert completed.metrics_json["selectedEventCount"] == 1
    assert completed.metrics_json["falsePositiveCount"] == 1
    assert completed.metrics_json["categoryDistribution"] == {"ai_models": 1}


def test_strategy_activation_and_evaluation_run_api(tmp_path):
    app = create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
    )
    client = TestClient(app)
    client.post(
        "/api/v1/internal/strategy-versions",
        json={
            "id": "ai-next-v1",
            "channel": "ai",
            "name": "Next",
            "status": "draft",
            "prefilterPromptVersion": "prefilter-v1",
            "scorePromptVersion": "score-v1",
            "rankFormulaVersion": "rank-v1",
            "thresholds": {"selected": 72},
            "modelConfig": {"provider": "fake"},
        },
        headers=_auth_header(),
    )
    activated = client.post("/api/v1/internal/strategy-versions/ai-next-v1/activate", headers=_auth_header())
    evaluation = client.post(
        "/api/v1/internal/evaluation-runs",
        json={"channel": "ai", "strategyVersion": "ai-next-v1", "name": "smoke", "request": {}},
        headers=_auth_header(),
    )
    run_id = evaluation.json()["evaluationRun"]["id"]
    completed = client.post(f"/api/v1/internal/evaluation-runs/{run_id}/run", headers=_auth_header())

    assert activated.status_code == 200
    assert activated.json()["strategyVersion"]["status"] == "active"
    assert completed.json()["evaluationRun"]["status"] == "succeeded"
