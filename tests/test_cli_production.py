from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from intel_engine.cli import run_pipeline_once_command, run_schedule_command, run_seed_sources_command
from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.models import FetchJobRecord, SourceRecord
from intel_engine.settings import Settings
from tests.test_jobs import write_channel_config


def test_seed_sources_command_uses_production_database_url(tmp_path, monkeypatch, capsys):
    channels_dir = tmp_path / "channels"
    write_channel_config(channels_dir)
    db_url = f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    exit_code = run_seed_sources_command(["--channels-dir", str(channels_dir)])

    engine = create_engine_from_settings(Settings(database_url=db_url))
    init_schema(engine)
    SessionLocal = sessionmaker_for_engine(engine)
    with SessionLocal() as session:
        sources = session.scalars(select(SourceRecord)).all()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "信源导入完成" in output
    assert len(sources) == 2


def test_schedule_command_creates_fetch_jobs(tmp_path, monkeypatch, capsys):
    channels_dir = tmp_path / "channels"
    write_channel_config(channels_dir)
    db_url = f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    run_seed_sources_command(["--channels-dir", str(channels_dir)])

    exit_code = run_schedule_command(["--now", "2026-05-12T08:00:00+00:00"])

    engine = create_engine_from_settings(Settings(database_url=db_url))
    init_schema(engine)
    SessionLocal = sessionmaker_for_engine(engine)
    with SessionLocal() as session:
        jobs = session.scalars(select(FetchJobRecord)).all()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "调度完成" in output
    assert len(jobs) == 1


def test_pipeline_once_command_runs_without_pending_jobs(tmp_path, monkeypatch, capsys):
    db_url = f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    exit_code = run_pipeline_once_command(["--now", datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc).isoformat()])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "流水线完成" in output
