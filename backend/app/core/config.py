from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str                          # required -> startup fails if unset (Req 39.6)
    jwt_secret: str = Field(min_length=32)     # required
    jwt_expire_minutes: int = 60
    openai_api_key: str | None = None          # missing -> AI endpoints return 503
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = "http://localhost:5173"   # comma-separated
    enable_scheduler: bool = False
    reminder_threshold_minutes: int = 15
    ai_rate_limit_per_minute: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
