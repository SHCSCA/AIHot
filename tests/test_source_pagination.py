from __future__ import annotations

from fastapi.testclient import TestClient

from intel_engine.models import SourceRecord, SourceStateRecord
from tests.admin_helpers import app_with_admin_data, auth_header


def _add_extra_sources(app, count: int = 6) -> None:
    SessionLocal = app.state.production_sessionmaker
    with SessionLocal() as session:
        for index in range(count):
            source_id = f"extra_ai_{index:03d}"
            session.add(
                SourceRecord(
                    id=source_id,
                    channel="ai",
                    source_type="rss",
                    tier="T2",
                    name=f"Extra AI Source {index:03d}",
                    url=f"https://example.com/{source_id}.xml",
                    language="en",
                    region="global",
                    marketplace=None,
                    authority_weight=80,
                    noise_level=0.18,
                    fetch_adapter="rss",
                    parser_type="rss",
                    default_categories=["ai_models"],
                    fetch_interval_minutes=60,
                    enabled=True,
                    visibility="public",
                    source_group="media",
                    contributor_no=f"AIHOT-{index + 10:03d}",
                    social_handle=None,
                    collection_status="collectable",
                    free_access=True,
                    notes=None,
                )
            )
            session.add(SourceStateRecord(source_id=source_id, health_score=90))
        session.commit()


def test_internal_sources_support_cursor_pagination(tmp_path):
    app = app_with_admin_data(tmp_path)
    _add_extra_sources(app)
    client = TestClient(app)

    first = client.get("/api/v1/internal/sources?channel=ai&take=3", headers=auth_header())
    first_payload = first.json()
    second = client.get(
        f"/api/v1/internal/sources?channel=ai&take=3&cursor={first_payload['nextCursor']}",
        headers=auth_header(),
    )
    second_payload = second.json()

    assert first.status_code == 200
    assert len(first_payload["sources"]) == 3
    assert first_payload["hasNext"] is True
    assert first_payload["nextCursor"]
    assert len(second_payload["sources"]) == 3
    assert {source["id"] for source in first_payload["sources"]}.isdisjoint(
        {source["id"] for source in second_payload["sources"]}
    )


def test_internal_source_diagnostics_support_cursor_pagination(tmp_path):
    app = app_with_admin_data(tmp_path)
    _add_extra_sources(app)
    client = TestClient(app)

    first = client.get("/api/v1/internal/source-diagnostics?channel=ai&take=4", headers=auth_header())
    first_payload = first.json()
    second = client.get(
        f"/api/v1/internal/source-diagnostics?channel=ai&take=4&cursor={first_payload['nextCursor']}",
        headers=auth_header(),
    )
    second_payload = second.json()

    assert first.status_code == 200
    assert len(first_payload["sourceDiagnostics"]) == 4
    assert first_payload["hasNext"] is True
    assert len(second_payload["sourceDiagnostics"]) == 3
    assert {source["sourceId"] for source in first_payload["sourceDiagnostics"]}.isdisjoint(
        {source["sourceId"] for source in second_payload["sourceDiagnostics"]}
    )


def test_public_sources_support_cursor_pagination(tmp_path):
    app = app_with_admin_data(tmp_path)
    _add_extra_sources(app)
    client = TestClient(app)

    first = client.get("/api/v1/public/sources?channel=ai&take=5")
    first_payload = first.json()
    second = client.get(f"/api/v1/public/sources?channel=ai&take=5&cursor={first_payload['nextCursor']}")
    second_payload = second.json()

    assert first.status_code == 200
    assert len(first_payload["sources"]) == 5
    assert first_payload["hasNext"] is True
    assert len(second_payload["sources"]) == 2
