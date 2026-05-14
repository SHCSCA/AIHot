from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from intel_engine.main import create_app


def _auth_header(username: str = "admin", password: str = "secret") -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_internal_api_requires_basic_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    app = create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
    )
    client = TestClient(app)

    response = client.get("/api/v1/internal/sources")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


def test_internal_api_accepts_correct_basic_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    app = create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
    )
    client = TestClient(app)

    response = client.get("/api/v1/internal/sources", headers=_auth_header())

    assert response.status_code == 200
    assert response.json() == {"count": 0, "hasNext": False, "nextCursor": None, "sources": []}


def test_admin_shell_serves_login_app_without_basic_auth_when_web_dist_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    web_dist = tmp_path / "web" / "dist"
    web_dist.mkdir(parents=True)
    (web_dist / "index.html").write_text("<html><body>Admin</body></html>", encoding="utf-8")
    app = create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
        web_dist_path=web_dist,
    )
    client = TestClient(app)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Admin" in response.text


def test_spa_shell_serves_public_root_and_admin_paths_without_intercepting_apis(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    web_dist = tmp_path / "web" / "dist"
    assets = web_dist / "assets"
    assets.mkdir(parents=True)
    (web_dist / "index.html").write_text("<html><body>Public SPA</body></html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('asset')", encoding="utf-8")
    app = create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
        web_dist_path=web_dist,
    )
    client = TestClient(app)

    root = client.get("/")
    admin = client.get("/admin/events")
    asset = client.get("/assets/app.js")
    public_api = client.get("/api/v1/public/events?channel=ai")
    internal_api = client.get("/api/v1/internal/sources")

    assert root.status_code == 200
    assert admin.status_code == 200
    assert asset.status_code == 200
    assert "Public SPA" in root.text
    assert "Public SPA" in admin.text
    assert "asset" in asset.text
    assert public_api.status_code == 200
    assert public_api.headers["content-type"].startswith("application/json")
    assert internal_api.status_code == 401
