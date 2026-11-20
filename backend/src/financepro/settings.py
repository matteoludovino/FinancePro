from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    # postgresql+psycopg://user:password@host:port/db (a plain postgres:// URL is accepted too).
    database_url: PostgresDsn
    # The web app's origin: state-changing requests must come from it (see ADR on sessions).
    web_origin: str = "http://localhost:3010"

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @property
    def sqlalchemy_url(self) -> str:
        url = str(self.database_url)
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url.removeprefix(prefix)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
