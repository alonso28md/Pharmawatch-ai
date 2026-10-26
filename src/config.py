"""Centralized application configuration, loaded from environment variables / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings sourced from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic / Claude
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5-5", alias="ANTHROPIC_MODEL")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Storage
    db_path: str = Field(default="data/pharmawatch.db", alias="DB_PATH")
    chroma_persist_dir: str = Field(default="data/chroma_db", alias="CHROMA_PERSIST_DIR")

    # RAG chunking / retrieval
    chunk_size: int = Field(default=800, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")

    # API
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000", alias="CORS_ORIGINS"
    )
    api_key: str = Field(default="", alias="API_KEY")
    rate_limit_per_minute: int = Field(default=30, alias="RATE_LIMIT_PER_MINUTE")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def db_path_absolute(self) -> Path:
        path = Path(self.db_path)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def chroma_persist_dir_absolute(self) -> Path:
        path = Path(self.chroma_persist_dir)
        return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
