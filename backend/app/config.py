from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    serpapi_api_key: str | None = None
    firecrawl_api_key: str | None = None
    firecrawl_wait_for_ms: int | None = Field(default=None, ge=0)
    browserbase_api_key: str | None = None
    browserbase_project_id: str | None = None

    database_url: str = "sqlite:///./jameco.db"
    app_host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("APP_HOST", "HOST"))
    app_port: int = Field(default=8000, validation_alias=AliasChoices("APP_PORT", "PORT"))
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    llm_reasoning_model: str = "claude-sonnet-4-6"
    llm_writing_model: str = "claude-sonnet-4-6"
    llm_extraction_model: str = "gpt-5"

    serpapi_country: str = "us"
    serpapi_language: str = "en"

    bulk_max_urls_per_batch: int = Field(default=100, ge=1, le=5000)

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
