from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from intel_engine.main import create_app
from intel_engine.models import NormalizedItemRecord, RawDocumentRecord, SourceRecord
from intel_engine.pipeline import _score_item, _screen_raw_document


def _auth_header() -> dict[str, str]:
    import base64

    token = base64.b64encode(b"admin:admin").decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _source() -> SourceRecord:
    return SourceRecord(
        id="openai_news",
        channel="ai",
        source_type="html",
        tier="T1",
        name="OpenAI News",
        url="https://openai.com/news/",
        language="en",
        region="global",
        authority_weight=95,
        noise_level=0.05,
        fetch_adapter="http_article",
        parser_type="website",
        default_categories=["ai_models"],
        fetch_interval_minutes=1440,
        enabled=True,
        visibility="public",
    )


def test_system_settings_api_persists_ai_analysis_switch(tmp_path):
    app = create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
    )
    client = TestClient(app)

    initial = client.get("/api/v1/internal/system-settings", headers=_auth_header())
    disabled = client.patch(
        "/api/v1/internal/system-settings",
        json={"aiAnalysisEnabled": False},
        headers=_auth_header(),
    )
    reread = client.get("/api/v1/internal/system-settings", headers=_auth_header())

    assert initial.status_code == 200
    assert initial.json()["settings"]["aiAnalysisEnabled"] is True
    assert disabled.status_code == 200
    assert disabled.json()["settings"]["analysisMode"] == "rules"
    assert reread.json()["settings"]["aiAnalysisEnabled"] is False


def test_disabled_analysis_bypasses_injected_ai_providers():
    now = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)
    source = _source()
    raw = RawDocumentRecord(
        fetch_run_id=1,
        source_id=source.id,
        url="https://openai.com/news/gpt-5",
        canonical_url="https://openai.com/news/gpt-5",
        content_type="text/html",
        body_text="OpenAI announced a new GPT-5 model release with updated reasoning capabilities.",
        response_headers_json={
            "x-intel-title": "OpenAI launches GPT-5",
            "x-intel-published-at": now.isoformat(),
        },
        content_hash="raw-rules-test",
        fetched_at=now,
    )
    item = NormalizedItemRecord(
        id=1,
        channel="ai",
        source_id=source.id,
        raw_document_id=1,
        title_original="OpenAI launches GPT-5",
        url="https://openai.com/news/gpt-5",
        canonical_url="https://openai.com/news/gpt-5",
        summary_original="OpenAI announced a new GPT-5 model release with updated reasoning capabilities.",
        published_at=now,
        fetched_at=now,
        language="en",
        content_hash="item-rules-test",
    )

    class ExplodingScreeningProvider:
        def screen_item(self, payload):
            raise AssertionError("AI screening provider must not be called")

    class ExplodingScoringProvider:
        def score_item(self, payload):
            raise AssertionError("AI scoring provider must not be called")

    screening = _screen_raw_document(
        raw,
        source,
        now=now,
        screening_provider=ExplodingScreeningProvider(),
        ai_analysis_enabled=False,
    )
    score = _score_item(
        item,
        source,
        llm_provider=ExplodingScoringProvider(),
        ai_analysis_enabled=False,
    )

    assert screening.raw_json["provider"] == "rules"
    assert screening.raw_json["model"] == "rules-v1"
    assert score.raw_json["provider"] == "rules"
    assert score.raw_json["model"] == "rules-v1"
