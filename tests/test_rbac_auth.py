from __future__ import annotations

from fastapi.testclient import TestClient

from intel_engine.main import create_app
from intel_engine.models import AuditLogRecord


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    return create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
    )


def test_login_sets_session_cookie_and_me_returns_admin_permissions(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = TestClient(app)

    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"})
    me = client.get("/api/v1/me")

    assert login.status_code == 200
    assert "aihot_session" in login.headers["set-cookie"]
    assert login.json()["user"]["username"] == "admin"
    assert "admin" in login.json()["roles"]
    assert "users.manage" in login.json()["permissions"]
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "admin"
    assert "roles.manage" in me.json()["permissions"]


def test_guest_me_returns_public_capabilities_without_internal_access(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = TestClient(app)

    me = client.get("/api/v1/me")
    internal = client.get("/api/v1/internal/dashboard")

    assert me.status_code == 200
    assert me.json()["user"] is None
    assert me.json()["roles"] == ["guest"]
    assert me.json()["permissions"] == ["feedback.create", "public.read"]
    assert internal.status_code == 401


def test_operator_can_read_sources_but_cannot_manage_users(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = TestClient(app)
    SessionLocal = app.state.production_sessionmaker
    from intel_engine.auth import create_user

    with SessionLocal() as session:
        create_user(
            session,
            username="operator",
            password="operator-secret",
            display_name="运营",
            role_ids=["operator"],
        )
        session.commit()

    assert client.post("/api/v1/auth/login", json={"username": "operator", "password": "operator-secret"}).status_code == 200
    sources = client.get("/api/v1/internal/sources")
    users = client.get("/api/v1/internal/users")

    assert sources.status_code == 200
    assert users.status_code == 403


def test_admin_user_management_and_audit_log(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = TestClient(app)
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"}).status_code == 200

    created = client.post(
        "/api/v1/internal/users",
        json={
            "username": "alice",
            "password": "alice-secret",
            "displayName": "Alice",
            "email": "alice@example.com",
            "roleIds": ["operator"],
        },
    )
    listed = client.get("/api/v1/internal/users")
    audits = client.get("/api/v1/internal/audit-logs")

    assert created.status_code == 200
    assert created.json()["user"]["username"] == "alice"
    assert created.json()["user"]["roles"] == ["operator"]
    assert listed.status_code == 200
    assert "password" not in listed.text
    assert audits.status_code == 200
    assert audits.json()["auditLogs"][0]["action"] == "users.create"

    SessionLocal = app.state.production_sessionmaker
    with SessionLocal() as session:
        assert session.query(AuditLogRecord).filter_by(action="users.create").count() == 1
