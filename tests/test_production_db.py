from __future__ import annotations

from sqlalchemy import inspect, select

from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.models import SourceRecord, SourceStateRecord, StrategyVersionRecord
from intel_engine.settings import Settings


def test_settings_can_disable_dotenv_file_loading(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("INTEL_ENV_FILE", "")
    (tmp_path / ".env").write_text("LLM_MODEL=must-not-load\n", encoding="utf-8")

    settings = Settings()

    assert settings.llm_model == "fake-default"


def test_settings_uses_database_url_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/intel")

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/intel"


def test_settings_defaults_to_postgresql():
    settings = Settings()

    assert settings.database_url.startswith("postgresql+psycopg://")


def test_engine_pre_pings_pooled_connections():
    settings = Settings(database_url="postgresql+psycopg://user:pass@localhost:5432/intel")
    engine = create_engine_from_settings(settings)

    assert getattr(engine.pool, "_pre_ping") is True


def test_init_schema_creates_production_tables(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'test.sqlite3'}")
    engine = create_engine_from_settings(settings)

    init_schema(engine)

    table_names = set(inspect(engine).get_table_names())
    assert {
        "sources",
        "source_states",
        "fetch_jobs",
        "fetch_runs",
        "raw_documents",
        "raw_screening_results",
        "normalized_items",
        "prefilter_results",
        "model_scores",
        "ranked_items",
        "event_clusters",
        "cluster_members",
        "strategy_versions",
        "feedback_events",
        "daily_digests",
        "evaluation_runs",
        "pipeline_runs",
    }.issubset(table_names)


def test_source_state_and_strategy_version_are_persisted(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'test.sqlite3'}")
    engine = create_engine_from_settings(settings)
    init_schema(engine)
    SessionLocal = sessionmaker_for_engine(engine)

    with SessionLocal() as session:
        source = SourceRecord(
            id="openai-blog",
            channel="ai",
            source_type="rss",
            tier="T1",
            name="OpenAI Blog",
            url="https://openai.com/news/rss.xml",
            language="en",
            region="global",
            marketplace=None,
            authority_weight=95.0,
            noise_level=0.05,
            fetch_adapter="rss",
            parser_type="rss",
            default_categories=["model"],
            fetch_interval_minutes=60,
            enabled=True,
            visibility="public",
            notes="official feed",
        )
        state = SourceStateRecord(source_id=source.id)
        strategy = StrategyVersionRecord(
            id="ai-default-v1",
            channel="ai",
            name="AI default strategy",
            status="active",
            prefilter_prompt_version="prefilter-v1",
            score_prompt_version="score-v1",
            rank_formula_version="rank-v1",
            thresholds_json={"selected": 70},
            model_config_json={"provider": "fake"},
        )
        session.add_all([source, state, strategy])
        session.commit()

    with SessionLocal() as session:
        saved_source = session.scalar(select(SourceRecord).where(SourceRecord.id == "openai-blog"))
        saved_state = session.scalar(select(SourceStateRecord).where(SourceStateRecord.source_id == "openai-blog"))
        saved_strategy = session.scalar(select(StrategyVersionRecord).where(StrategyVersionRecord.id == "ai-default-v1"))

    assert saved_source is not None
    assert saved_source.default_categories == ["model"]
    assert saved_state is not None
    assert saved_state.error_streak == 0
    assert saved_strategy is not None
    assert saved_strategy.status == "active"
