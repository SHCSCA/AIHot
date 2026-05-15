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


def test_public_sources_support_grouped_source_filter(tmp_path):
    app = app_with_admin_data(tmp_path)
    _add_extra_sources(app)
    client = TestClient(app)

    response = client.get("/api/v1/public/sources?channel=ai&sourceGroup=official,media&page=1&pageSize=20")
    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 7
    assert {source["sourceGroup"] for source in payload["sources"]} == {"official", "media"}


def test_internal_sources_support_filters_and_full_result_metrics(tmp_path):
    app = app_with_admin_data(tmp_path)
    _add_extra_sources(app)
    SessionLocal = app.state.production_sessionmaker
    with SessionLocal() as session:
        source = session.get(SourceRecord, "extra_ai_000")
        assert source is not None
        source.enabled = False
        source.source_group = "social"
        source.collection_status = "pending_api"
        source.authority_weight = 91
        session.commit()
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/sources?channel=ai&q=Extra&sourceGroup=social&collectionStatus=pending_api&enabled=false&page=1&pageSize=50",
        headers=auth_header(),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 1
    assert payload["metrics"]["sourceCount"] == 1
    assert payload["metrics"]["enabledSourceCount"] == 0
    assert payload["metrics"]["highAuthorityCount"] == 1
    assert payload["metrics"]["pendingSocialCount"] == 1
    assert payload["sources"][0]["id"] == "extra_ai_000"


def test_internal_source_diagnostics_support_filters_sort_and_metrics(tmp_path):
    app = app_with_admin_data(tmp_path)
    _add_extra_sources(app)
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/source-diagnostics?channel=ai&q=Extra AI Source&sourceGroup=media&diagnosticStatus=waiting&sort=health_asc&page=1&pageSize=3",
        headers=auth_header(),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 6
    assert payload["metrics"]["sourceCount"] == 6
    assert payload["metrics"]["waitingCount"] == 6
    assert [source["sourceId"] for source in payload["sourceDiagnostics"]] == [
        "extra_ai_000",
        "extra_ai_001",
        "extra_ai_002",
    ]
