from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from intel_engine.models import FetchJobRecord, SourceRecord, SourceStateRecord


ACTIVE_JOB_STATUSES = ("pending", "locked", "running")


@dataclass(frozen=True)
class ScheduleStats:
    created: int
    skipped: int


def _priority_for_source(source: SourceRecord) -> int:
    return {
        "T1": 10,
        "T1.5": 20,
        "T2": 50,
        "T3": 80,
    }.get(source.tier, 100)


def schedule_due_sources(session: Session, *, now: datetime, limit: int | None = None) -> ScheduleStats:
    stmt = (
        select(SourceRecord, SourceStateRecord)
        .join(SourceStateRecord, SourceStateRecord.source_id == SourceRecord.id)
        .where(SourceRecord.enabled.is_(True))
        .where(SourceStateRecord.next_fetch_at <= now)
        .where(or_(SourceStateRecord.backoff_until.is_(None), SourceStateRecord.backoff_until <= now))
        .order_by(SourceStateRecord.next_fetch_at, SourceRecord.id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    created = 0
    skipped = 0
    for source, _state in session.execute(stmt).all():
        active_job = session.scalar(
            select(FetchJobRecord.id)
            .where(FetchJobRecord.source_id == source.id)
            .where(FetchJobRecord.status.in_(ACTIVE_JOB_STATUSES))
            .limit(1)
        )
        if active_job is not None:
            skipped += 1
            continue

        session.add(
            FetchJobRecord(
                source_id=source.id,
                status="pending",
                priority=_priority_for_source(source),
                run_after=now,
            )
        )
        created += 1

    session.flush()
    return ScheduleStats(created=created, skipped=skipped)


def claim_fetch_jobs(session: Session, *, worker_id: str, limit: int, now: datetime) -> list[FetchJobRecord]:
    stmt = (
        select(FetchJobRecord)
        .where(FetchJobRecord.status == "pending")
        .where(FetchJobRecord.run_after <= now)
        .order_by(FetchJobRecord.priority, FetchJobRecord.run_after, FetchJobRecord.id)
        .limit(limit)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)

    jobs = list(session.scalars(stmt).all())
    for job in jobs:
        job.status = "running"
        job.locked_at = now
        job.locked_by = worker_id
        job.attempt_count += 1
        job.updated_at = now

    session.flush()
    return jobs


def mark_job_succeeded(
    session: Session,
    job_id: int,
    *,
    now: datetime,
    item_count: int = 0,
    avg_latency_ms: float | None = None,
) -> FetchJobRecord:
    job = _get_job(session, job_id)
    source = _get_source(session, job.source_id)
    state = _get_state(session, job.source_id)

    job.status = "succeeded"
    job.locked_at = None
    job.locked_by = None
    job.updated_at = now
    job.last_error = None

    state.last_success_at = now
    state.error_streak = 0
    state.backoff_until = None
    state.next_fetch_at = now + timedelta(minutes=source.fetch_interval_minutes)
    state.items_per_run = item_count
    if avg_latency_ms is not None:
        state.avg_latency_ms = avg_latency_ms
    state.updated_at = now

    session.flush()
    return job


def mark_job_failed(
    session: Session,
    job_id: int,
    *,
    error_message: str,
    now: datetime,
    max_attempts: int = 3,
) -> FetchJobRecord:
    job = _get_job(session, job_id)
    state = _get_state(session, job.source_id)
    next_streak = state.error_streak + 1
    backoff_until = now + timedelta(minutes=min(240, 5 * (2 ** (next_streak - 1))))

    job.last_error = error_message
    job.locked_at = None
    job.locked_by = None
    job.updated_at = now
    if job.attempt_count >= max_attempts:
        job.status = "dead"
    else:
        job.status = "pending"
        job.run_after = backoff_until

    state.last_error_at = now
    state.error_streak = next_streak
    state.backoff_until = backoff_until
    state.updated_at = now

    session.flush()
    return job


def _get_job(session: Session, job_id: int) -> FetchJobRecord:
    job = session.get(FetchJobRecord, job_id)
    if job is None:
        raise KeyError(f"Unknown fetch job: {job_id}")
    return job


def _get_source(session: Session, source_id: str) -> SourceRecord:
    source = session.get(SourceRecord, source_id)
    if source is None:
        raise KeyError(f"Unknown source: {source_id}")
    return source


def _get_state(session: Session, source_id: str) -> SourceStateRecord:
    state = session.get(SourceStateRecord, source_id)
    if state is None:
        raise KeyError(f"Unknown source state: {source_id}")
    return state
