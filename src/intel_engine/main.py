from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from intel_engine.auth import seed_rbac_defaults
from intel_engine.db import (
    create_engine_from_settings as create_production_engine,
    init_schema_for_sqlite,
    sessionmaker_for_engine,
)
from intel_engine.routes import router
from intel_engine.settings import Settings
from intel_engine.storage import DEFAULT_DB_PATH, create_engine_for_path, init_db
from intel_engine.system_settings import ensure_system_settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def create_app(
    db_path: str | Path = DEFAULT_DB_PATH,
    production_database_url: str | None = None,
    web_dist_path: str | Path | None = None,
) -> FastAPI:
    app = FastAPI(title="情报引擎", version="0.2.0")
    engine = create_engine_for_path(db_path)
    init_db(engine)
    app.state.db_engine = engine

    if production_database_url is None:
        production_database_url = os.getenv("DATABASE_URL")

    if production_database_url is not None:
        production_engine = create_production_engine(Settings(database_url=production_database_url))
        init_schema_for_sqlite(production_engine)
        app.state.production_engine = production_engine
        app.state.production_sessionmaker = sessionmaker_for_engine(production_engine)
        with app.state.production_sessionmaker() as session:
            settings = Settings(database_url=production_database_url)
            seed_rbac_defaults(
                session,
                admin_username=settings.admin_username,
                admin_password=settings.admin_password,
            )
            ensure_system_settings(session)
            session.commit()

    app.include_router(router)
    _mount_spa(app, web_dist_path)
    return app


def _mount_spa(app: FastAPI, web_dist_path: str | Path | None) -> None:
    dist_path = Path(web_dist_path) if web_dist_path is not None else PROJECT_ROOT / "web" / "dist"
    index_path = dist_path / "index.html"
    if not index_path.exists():
        return

    def spa_response(full_path: str = ""):
        reserved_prefixes = {"api", "feed", "health", "docs", "redoc", "openapi.json"}
        first_segment = full_path.split("/", 1)[0]
        if first_segment in reserved_prefixes:
            raise HTTPException(status_code=404, detail="not found")

        requested = (dist_path / full_path).resolve()
        if full_path and requested.is_file() and dist_path.resolve() in requested.parents:
            return FileResponse(requested)
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="web app is not built")
        return FileResponse(index_path)

    @app.get("/", include_in_schema=False)
    def public_shell():
        return spa_response()

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{full_path:path}", include_in_schema=False)
    def admin_shell(full_path: str = ""):
        return spa_response(full_path)

    @app.get("/{full_path:path}", include_in_schema=False)
    def web_shell(full_path: str):
        return spa_response(full_path)


app = create_app()
