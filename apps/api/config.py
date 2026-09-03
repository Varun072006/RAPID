"""
Application settings — loaded from .env via pydantic-settings.
All config validated at startup; missing required vars fail fast.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration.

    Values come from environment variables / .env file.
    Set RAZORPAY_MODE=mock to run without real credentials.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Razorpay ────────────────────────────────────────────────
    razorpay_key_id: str = Field(default="rzp_test_mock")
    razorpay_key_secret: str = Field(default="mock_secret")
    razorpay_webhook_secret: str = Field(default="mock_webhook_secret")
    razorpay_mode: str = Field(default="mock")  # "mock" or "test"

    # ── Database ─────────────────────────────────────────────────
    database_url: str = Field(default="postgresql://rapid:rapid@localhost:5432/rapid_db")

    # ── Redis ────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ── API ──────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    debug: bool = Field(default=True)
    secret_key: str = Field(default="dev-secret-change-in-prod")

    # ── LLM (Ollama) ─────────────────────────────────────────────
    ollama_host: str = Field(default="http://localhost:11434")
    llm_model: str = Field(default="qwen3:8b")
    llm_provider: str = Field(default="mock")  # "ollama" or "mock"

    # ── Dashboard ────────────────────────────────────────────────
    next_public_api_url: str = Field(default="http://localhost:8000")

    @property
    def use_mock_razorpay(self) -> bool:
        return self.razorpay_mode.lower() == "mock"

    @property
    def use_mock_llm(self) -> bool:
        return self.llm_provider.lower() == "mock"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
