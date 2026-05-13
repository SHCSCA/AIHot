from __future__ import annotations

import os

from pydantic import BaseModel, Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    BaseSettings = BaseModel
    SettingsConfigDict = None


DEFAULT_DATABASE_URL = "postgresql+psycopg://intel:intel@localhost:5432/intel_engine"


class Settings(BaseSettings):
    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(default=DEFAULT_DATABASE_URL)
    admin_username: str = Field(default="admin")
    admin_password: str = Field(default="admin")
    llm_provider: str = Field(default="fake")
    llm_model: str = Field(default="fake-default")
    llm_screening_model: str = Field(default="deepseek-v4-flash")
    llm_scoring_model: str = Field(default="deepseek-v4-pro")
    llm_timeout_seconds: int = Field(default=30)
    deepseek_api_key: str | None = Field(default=None)
    deepseek_base_url: str = Field(default="https://api.deepseek.com")

    def __init__(self, **data: object) -> None:
        if "database_url" not in data:
            env_database_url = os.getenv("DATABASE_URL")
            if env_database_url:
                data["database_url"] = env_database_url
        super().__init__(**data)
