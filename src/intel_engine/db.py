from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from intel_engine.settings import Settings


class Base(DeclarativeBase):
    pass


def create_engine_from_settings(settings: Settings | None = None) -> Engine:
    resolved_settings = settings or Settings()
    connect_args = {}
    engine_options = {"future": True, "pool_pre_ping": True}
    if resolved_settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(resolved_settings.database_url, connect_args=connect_args, **engine_options)


def sessionmaker_for_engine(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_schema(engine: Engine) -> None:
    import intel_engine.models  # noqa: F401

    Base.metadata.create_all(engine)


def init_schema_for_sqlite(engine: Engine) -> None:
    if engine.dialect.name == "sqlite":
        init_schema(engine)
