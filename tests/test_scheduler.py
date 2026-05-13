from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.models import FetchJobRecord, SourceStateRecord
from intel_engine.scheduler import claim_fetch_jobs, mark_job_failed, mark_job_succeeded, schedule_due_sources
from intel_engine.settings import Settings
from intel_engine.sources import SourceRegistry, SourceUpsert


def _session_factory(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'test.sqlite3'}")
    engine = create_engine_from_settings(settings)
    init_schema(engine)
    return sessionmaker_for_engine(engine)


def _add_source(session, source_id="openai_news", enabled=True, next_fetch_at=None, interval=60):
    registry = SourceRegistry(session)
    registry.upsert_source(
        SourceUpsert(
            id=source_id,
            channel="ai",
            source_type="html",
            tier="T1",
            name="OpenAI News",
            url=f"https://example.com/{source_id}",
            language="en",
            region="global",
            marketplace=None,
            authority_weight=95,
            noise_level=0.05,
            fetch_adapter="http_article",
            parser_type="website",
            default_categories=["ai_models"],
            fetch_interval_minutes=interval,
            enabled=enabled,
            visibility="public",
            notes=None,
        )
    )
    if next_fetch_at is not None:
        registry.update_state(source_id, next_fetch_at=next_fetch_at)


def test_schedule_due_sources_creates_idempotent_jobs(tmp_path):
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)

    with SessionLocal() as session:
        _add_source(session, next_fetch_at=now - timedelta(minutes=1))
        first = schedule_due_sources(session, now=now)
        second = schedule_due_sources(session, now=now)
        jobs = session.scalars(select(FetchJobRecord)).all()

    assert first.created == 1
    assert second.created == 0
    assert len(jobs) == 1
    assert jobs[0].status == "pending"
    assert jobs[0].run_after == now


def test_claim_fetch_jobs_marks_jobs_running_once(tmp_path):
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)

    with SessionLocal() as session:
        _add_source(session, next_fetch_at=now)
        schedule_due_sources(session, now=now)
        first_claim = claim_fetch_jobs(session, worker_id="worker-a", limit=10, now=now)
        second_claim = claim_fetch_jobs(session, worker_id="worker-b", limit=10, now=now)

    assert [job.id for job in first_claim] == [1]
    assert second_claim == []
    assert first_claim[0].status == "running"
    assert first_claim[0].locked_by == "worker-a"
    assert first_claim[0].attempt_count == 1


def test_mark_job_succeeded_updates_source_state_and_next_fetch(tmp_path):
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)

    with SessionLocal() as session:
        _add_source(session, next_fetch_at=now, interval=120)
        schedule_due_sources(session, now=now)
        job = claim_fetch_jobs(session, worker_id="worker-a", limit=1, now=now)[0]
        mark_job_succeeded(session, job.id, now=now, item_count=3, avg_latency_ms=250)
        state = session.get(SourceStateRecord, "openai_news")

    assert job.status == "succeeded"
    assert state is not None
    assert state.last_success_at == now
    assert state.error_streak == 0
    assert state.items_per_run == 3
    assert state.avg_latency_ms == 250
    assert state.next_fetch_at == now + timedelta(minutes=120)


def test_mark_job_failed_requeues_with_backoff(tmp_path):
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)

    with SessionLocal() as session:
        _add_source(session, next_fetch_at=now)
        schedule_due_sources(session, now=now)
        job = claim_fetch_jobs(session, worker_id="worker-a", limit=1, now=now)[0]
        mark_job_failed(session, job.id, error_message="timeout", now=now, max_attempts=3)
        state = session.get(SourceStateRecord, "openai_news")

    assert job.status == "pending"
    assert job.last_error == "timeout"
    assert job.run_after == now + timedelta(minutes=5)
    assert state is not None
    assert state.error_streak == 1
    assert state.backoff_until == now + timedelta(minutes=5)
