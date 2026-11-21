from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    # postgresql+psycopg://user:password@host:port/db (a plain postgres:// URL is accepted too).
    database_url: PostgresDsn
    # The web app's origin: state-changing requests must come from it (docs/adr/0002).
    web_origin: str = "http://localhost:3010"

    # Categorization with Claude (docs/adr/0006). Without a key the AI is off and everything else works.
    anthropic_api_key: SecretStr | None = None
    ai_model: str = "claude-haiku-5-5"
    # Daily token ceilings: per person, and for the whole installation (the real cost control).
    ai_daily_tokens_per_user: int = 60_000
    ai_daily_tokens_global: int = 1_500_000

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
