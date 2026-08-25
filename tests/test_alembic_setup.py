from __future__ import annotations

from pathlib import Path


def test_alembic_files_exist():
    root = Path(__file__).resolve().parents[1]

    assert (root / "alembic.ini").is_file()
    assert (root / "migrations" / "env.py").is_file()
    assert (root / "migrations" / "script.py.mako").is_file()


def test_initial_migration_declares_production_tables():
    root = Path(__file__).resolve().parents[1]
    versions_dir = root / "migrations" / "versions"
    migration_text = "\n".join(path.read_text(encoding="utf-8") for path in versions_dir.glob("*.py"))

    for table_name in (
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
        "system_settings",
    ):
        assert table_name in migration_text
